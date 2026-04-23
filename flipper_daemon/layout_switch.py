"""
Switch the active input layout after a successful flip.
Windows-only for now — no-op on other platforms.
"""

import ctypes
import platform

_LAYOUTS = {
    "en_us": "00000409",
    "he_il": "0000040d",
}

_WM_INPUTLANGCHANGEREQUEST = 0x0050


def switch_to(layout_id: str) -> None:
    if platform.system() != "Windows":
        return
    try:
        lang_str = _LAYOUTS.get(layout_id)
        if not lang_str:
            return
        hkl = ctypes.windll.user32.LoadKeyboardLayoutW(lang_str, 1)
        if not hkl:
            return
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.PostMessageW(hwnd, _WM_INPUTLANGCHANGEREQUEST, 0, hkl)
    except Exception:
        pass
