"""
Auto-start on login — macOS LaunchAgent plist approach.
Works both when running from source (python run.py) and as a .app bundle.
"""

import os
import platform
import subprocess
from pathlib import Path

_PLIST_LABEL = "com.languageflipper.desktop"
_PLIST_PATH  = Path.home() / "Library/LaunchAgents" / f"{_PLIST_LABEL}.plist"


def _get_executable() -> str:
    """Return the path to the running executable or 'python3 run.py'."""
    import sys
    # When bundled by PyInstaller, sys.frozen is True
    if getattr(sys, "frozen", False):
        return sys.executable
    # Running from source
    return f"{sys.executable} {Path(__file__).parent.parent / 'run.py'}"


def is_enabled() -> bool:
    return _PLIST_PATH.exists()


def enable():
    exe = _get_executable()
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        {"".join(f"<string>{p}</string>" for p in exe.split())}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
    _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PLIST_PATH.write_text(plist, encoding="utf-8")
    subprocess.run(["launchctl", "load", str(_PLIST_PATH)], check=False)


def disable():
    if _PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(_PLIST_PATH)], check=False)
        _PLIST_PATH.unlink(missing_ok=True)
