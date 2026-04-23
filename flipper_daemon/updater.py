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

_GITHUB_API = "https://api.github.com/repos/Elad-hor/language-flipper-desktop/releases/latest"

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
        subprocess.Popen([tmp, "/SILENT"])
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
                release = json.loads(r.read())

            latest_tag = release.get("tag_name", "")
            if _parse_version(latest_tag) <= _parse_version(VERSION):
                return

            for asset in release.get("assets", []):
                if asset["name"] == asset_name:
                    version_str = latest_tag.lstrip("v").split("-")[0]
                    on_available(version_str, asset["browser_download_url"])
                    break
        except Exception:
            pass

    threading.Thread(target=_check, daemon=True).start()
