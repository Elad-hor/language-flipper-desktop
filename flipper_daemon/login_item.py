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


def _get_program_arguments() -> list:
    """Return the ProgramArguments list for the LaunchAgent plist."""
    import sys
    if getattr(sys, "frozen", False):
        # Use `open -a` so macOS launches the .app with proper app context
        return ["/usr/bin/open", "-a", "Language Flipper"]
    # Running from source
    return [sys.executable, str(Path(__file__).parent.parent / "run.py")]


def is_enabled() -> bool:
    return _PLIST_PATH.exists()


def enable():
    args = _get_program_arguments()
    args_xml = "".join(f"        <string>{p}</string>\n" for p in args)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
{args_xml.rstrip()}
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
