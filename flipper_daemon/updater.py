"""
Background update checker. On startup, hits the GitHub releases API,
compares against the current version, and calls on_available(version, url)
if a newer release is found. Silent — never raises to the caller.
"""

import json
import platform
import subprocess
import tempfile
import threading
import urllib.request

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


def download_and_run(url: str) -> None:
    system = platform.system()
    suffix = ".exe" if system == "Windows" else ".dmg"
    tmp = tempfile.mktemp(suffix=suffix, prefix="lf-setup-")
    urllib.request.urlretrieve(url, tmp)
    if system == "Windows":
        import os
        install_exe = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs", "Language Flipper", "Language Flipper.exe",
        )
        # Write a VBScript launcher — Shell.Run is identical to double-clicking,
        # fully independent of the cmd chain's environment.
        vbs_path = tempfile.mktemp(suffix=".vbs", prefix="lf-launch-")
        with open(vbs_path, "w") as f:
            f.write('Set sh = CreateObject("Shell.Application")\n')
            f.write(f'sh.ShellExecute "{install_exe}"\n')
        cmd = (
            f'ping -n 2 127.0.0.1 >nul'
            f' && "{tmp}" /VERYSILENT'
            f' && ping -n 15 127.0.0.1 >nul'
            f' && wscript /B "{vbs_path}"'
        )
        subprocess.Popen(cmd, shell=True)
    elif system == "Darwin":
        subprocess.Popen(["open", tmp])


def start(on_available) -> None:
    asset_name = _PLATFORM_ASSET.get(platform.system())
    if not asset_name:
        return

    def _check():
        try:
            req = urllib.request.Request(
                _GITHUB_API,
                headers={"User-Agent": "language-flipper-updater"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
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
                version_str = best_tag.lstrip("v").split("-")[0]
                on_available(version_str, best_url)
        except Exception:
            pass

    threading.Thread(target=_check, daemon=True).start()
