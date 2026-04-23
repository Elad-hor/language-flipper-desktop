"""
Windows auto-start on login via HKCU registry run key.
No admin rights needed — per-user only.
"""

import os
import sys
import shutil
from pathlib import Path

_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "LanguageFlipper"
_INSTALL_DIR = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    if os.environ.get("LOCALAPPDATA")
    else Path.home() / "AppData" / "Local"
) / "Programs" / "Language Flipper"
_INSTALL_EXE = _INSTALL_DIR / "Language Flipper.exe"


def _exe_path() -> str:
    return sys.executable


def _self_install() -> str:
    """Copy exe to permanent location if not already there. Returns final exe path."""
    current = Path(_exe_path()).resolve()
    target = _INSTALL_EXE.resolve()
    if current == target:
        return str(_INSTALL_EXE)
    _INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, _INSTALL_EXE)
    return str(_INSTALL_EXE)


def is_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as k:
            val, _ = winreg.QueryValueEx(k, _APP_NAME)
            return bool(val)
    except Exception:
        return False


def enable():
    try:
        import winreg
        exe = _self_install()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY,
                            access=winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, _APP_NAME, 0, winreg.REG_SZ, f'"{exe}"')
    except Exception as e:
        print(f"[win_login_item] enable failed: {e}")


def disable():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY,
                            access=winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, _APP_NAME)
    except Exception:
        pass
