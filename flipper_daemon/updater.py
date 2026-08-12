"""
Background update checker. On startup, hits the GitHub releases API,
compares against the current version, and calls on_available(version, url)
if a newer release is found. Silent — never raises to the caller.
"""

import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from .certs import SSL_CONTEXT
from .version import VERSION

_GITHUB_API = "https://api.github.com/repos/Elad-hor/language-flipper-desktop/releases"

_PLATFORM_ASSET = {
    "Windows": "Language-Flipper-Setup.exe",
    "Darwin":  "Language.Flipper.dmg",
}


def _parse_version(tag: str) -> tuple:
    # handles "v0.1.57", "v0.1.57-windows", "0.1.57"
    clean = tag.lstrip("v").split("-")[0]
    try:
        return tuple(int(x) for x in clean.split("."))
    except Exception:
        return (0,)


_MAC_APP_NAME = "Language Flipper"


def _installed_app_bundle() -> str:
    """
    Absolute path of the running .app bundle, or "" when not applicable.

    In a frozen Mac build sys.executable is
        <...>/Language Flipper.app/Contents/MacOS/Language Flipper
    so the bundle is three levels up. Running from source (python run.py)
    there is no bundle, and the caller falls back to opening the DMG.
    """
    if not getattr(sys, "frozen", False):
        return ""
    exe = Path(sys.executable).resolve()
    if len(exe.parents) >= 3 and exe.parents[2].suffix == ".app":
        return str(exe.parents[2])
    return ""


def _install_macos(dmg_path: str) -> None:
    """
    Replace the installed .app with the one inside the downloaded DMG, then
    relaunch — the macOS equivalent of what Windows does with the silent
    installer. Before this, the Mac "updater" only ran `open <dmg>` and left
    the user to drag the app across by hand.

    The work happens in a detached shell script because the app has to exit
    before it can be replaced, so nothing in this process can still be running
    to do it. main._do_update() stops the tray immediately after this returns.

    Every failure path falls back to opening the DMG, which is exactly the old
    behaviour — a broken update must never leave the user with no app.
    """
    app_path = _installed_app_bundle()
    if not app_path:
        subprocess.Popen(["open", dmg_path])
        return

    log_path = os.path.join(tempfile.gettempdir(), "lf-update.log")
    script_path = tempfile.mktemp(suffix=".sh", prefix="lf-update-")

    script = f"""#!/bin/bash
exec >> {shlex.quote(log_path)} 2>&1
echo "=== update run $(date) ==="

APP={shlex.quote(app_path)}
DMG={shlex.quote(dmg_path)}
APPNAME={shlex.quote(_MAC_APP_NAME)}

fallback() {{
  echo "FALLBACK: opening DMG for manual install"
  open "$DMG"
  exit 1
}}

# Wait for the app to quit — it cannot be replaced while running.
for i in $(seq 1 60); do
  pgrep -x "$APPNAME" >/dev/null 2>&1 || break
  sleep 0.5
done
pkill -x "$APPNAME" 2>/dev/null
sleep 1

# -nobrowse keeps Finder from popping the volume open, and an explicit
# mountpoint avoids colliding with a "Language Flipper" volume left mounted
# by a previous run.
MP=$(mktemp -d /tmp/lf-mnt-XXXXXX) || fallback
hdiutil attach "$DMG" -nobrowse -quiet -mountpoint "$MP" || fallback

SRC="$MP/$APPNAME.app"
if [ ! -d "$SRC" ]; then
  echo "no app bundle inside the DMG at $SRC"
  hdiutil detach "$MP" -force -quiet
  fallback
fi

# Move the old bundle aside rather than deleting it, so a failed copy can be
# rolled back instead of leaving the user with no application at all.
BACKUP="$APP.old-$$"
if ! mv "$APP" "$BACKUP"; then
  echo "could not move $APP aside (permissions?)"
  hdiutil detach "$MP" -force -quiet
  fallback
fi

if ditto "$SRC" "$APP"; then
  echo "installed new bundle at $APP"
  rm -rf "$BACKUP"
else
  echo "ditto failed — restoring previous version"
  rm -rf "$APP"
  mv "$BACKUP" "$APP"
  hdiutil detach "$MP" -force -quiet
  fallback
fi

hdiutil detach "$MP" -force -quiet
rmdir "$MP" 2>/dev/null

# The DMG arrived from the internet so its contents carry
# com.apple.quarantine. The app is unsigned, so Gatekeeper would refuse to
# launch the freshly copied bundle without this.
xattr -cr "$APP" 2>/dev/null

sleep 1
open "$APP"
echo "relaunched"
"""

    with open(script_path, "w") as f:
        f.write(script)
    os.chmod(script_path, 0o755)

    # start_new_session detaches it from this process group, so it survives
    # the app quitting a moment from now.
    subprocess.Popen(
        ["/bin/bash", script_path],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _download(url: str, dest: str) -> None:
    """
    urllib.request.urlretrieve() cannot be given an SSL context, so it hits the
    same CERTIFICATE_VERIFY_FAILED as the check did inside a frozen build.
    Stream it through urlopen with the bundled CA list instead.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "language-flipper-updater"})
    with urllib.request.urlopen(req, timeout=120, context=SSL_CONTEXT) as r:
        with open(dest, "wb") as f:
            shutil.copyfileobj(r, f)


def download_and_run(url: str) -> None:
    system = platform.system()
    suffix = ".exe" if system == "Windows" else ".dmg"
    tmp = tempfile.mktemp(suffix=suffix, prefix="lf-setup-")
    _log(f"downloading {url}")
    try:
        _download(url, tmp)
    except Exception as exc:
        _log(f"download FAILED: {type(exc).__name__}: {exc}")
        raise
    _log(f"downloaded to {tmp} ({os.path.getsize(tmp)} bytes)")
    if system == "Windows":
        install_exe = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs", "Language Flipper", "Language Flipper.exe",
        )
        # Write a VBScript launcher — Shell.Run is identical to double-clicking,
        # fully independent of the cmd chain's environment.
        vbs_path = tempfile.mktemp(suffix=".vbs", prefix="lf-launch-")
        with open(vbs_path, "w") as f:
            f.write(f'Set sh = CreateObject("WScript.Shell")\n')
            f.write(f'sh.Run """{install_exe}"""\n')
        cmd = (
            f'ping -n 2 127.0.0.1 >nul'
            f' && "{tmp}" /VERYSILENT'
            f' && ping -n 15 127.0.0.1 >nul'
            f' && wscript /B "{vbs_path}"'
        )
        subprocess.Popen(cmd, shell=True)
    elif system == "Darwin":
        _install_macos(tmp)


# The app auto-starts at login and then runs for weeks, so a single check at
# startup meant a user who never reboots could sit on an old version
# indefinitely. Re-check periodically instead.
_CHECK_INTERVAL_SECONDS = 6 * 60 * 60

# Set on shutdown so the sleeping checker thread wakes and exits promptly
# instead of being killed mid-request.
_stop_checking = threading.Event()


def _log(msg: str) -> None:
    """
    Append a line to $TMPDIR/lf-update.log — the same file the macOS installer
    script writes to, so the whole update story lands in one place.

    Every failure in here used to be swallowed by `except Exception: pass`,
    which made a silently broken updater indistinguishable from "no update
    available". Never raises; logging must not break the app.
    """
    try:
        path = os.path.join(tempfile.gettempdir(), "lf-update.log")
        with open(path, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _find_update(asset_name: str):
    """
    Newest release carrying asset_name and newer than the running VERSION,
    as (version_str, download_url) — or None. Never raises.
    """
    try:
        req = urllib.request.Request(
            _GITHUB_API,
            headers={"User-Agent": "language-flipper-updater"}
        )
        # context= is load-bearing in a frozen build: without it there are no
        # CA certs in the bundle and this raises CERTIFICATE_VERIFY_FAILED.
        with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as r:
            releases = json.loads(r.read())

        best_ver = _parse_version(VERSION)
        best_url = None
        best_tag = None

        for release in releases:
            if release.get("draft") or release.get("prerelease"):
                continue
            tag = release.get("tag_name", "")
            ver = _parse_version(tag)
            if ver <= best_ver:
                continue
            for asset in release.get("assets", []):
                if asset["name"] == asset_name:
                    best_ver = ver
                    best_url = asset["browser_download_url"]
                    best_tag = tag
                    break

        if best_url:
            found = best_tag.lstrip("v").split("-")[0]
            _log(f"check: running {VERSION}, found {found} ({asset_name})")
            return found, best_url
        _log(f"check: running {VERSION}, no newer release with {asset_name}")
    except Exception as exc:
        _log(f"check FAILED: {type(exc).__name__}: {exc}")
    return None


def stop() -> None:
    """Wake the checker thread so it exits instead of sleeping on."""
    _stop_checking.set()


def start(on_available) -> None:
    asset_name = _PLATFORM_ASSET.get(platform.system())
    if not asset_name:
        return

    def _loop():
        # Only notify when the answer changes. Without this the tray menu would
        # be rebuilt every interval for an update the user has already been
        # told about and chosen to ignore.
        last_reported = None
        while True:
            found = _find_update(asset_name)
            if found and found[0] != last_reported:
                last_reported = found[0]
                try:
                    on_available(*found)
                    _log(f"notified UI of {found[0]}")
                except Exception as exc:
                    _log(f"on_available FAILED: {type(exc).__name__}: {exc}")
            # Event.wait doubles as the sleep and the shutdown signal; it
            # returns True when stop() was called.
            if _stop_checking.wait(_CHECK_INTERVAL_SECONDS):
                return

    threading.Thread(target=_loop, daemon=True).start()
