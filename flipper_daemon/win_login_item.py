"""
Windows auto-start on login via HKCU registry run key.
No admin rights needed — per-user only.
"""

import sys

_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "LanguageFlipper"


def _exe_path() -> str:
    return sys.executable


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
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY,
                            access=winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, _APP_NAME, 0, winreg.REG_SZ, _exe_path())
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
