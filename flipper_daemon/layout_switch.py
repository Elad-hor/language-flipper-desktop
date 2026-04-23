"""
Switch the active input layout after a successful flip.
Windows: PostMessageW WM_INPUTLANGCHANGEREQUEST
macOS:   InputMethodKit — switches via TIS/TSM APIs
"""

import platform

_LAYOUTS = {
    "en_us": "00000409",   # Windows LANGID
    "he_il": "0000040d",
}

# macOS input source identifiers
_MAC_SOURCES = {
    "en_us": "com.apple.keylayout.US",
    "he_il": "com.apple.keylayout.Hebrew",
}

_WM_INPUTLANGCHANGEREQUEST = 0x0050


def _switch_windows(layout_id: str) -> None:
    import ctypes
    lang_str = _LAYOUTS.get(layout_id)
    if not lang_str:
        return
    hkl = ctypes.windll.user32.LoadKeyboardLayoutW(lang_str, 1)
    if not hkl:
        return
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.PostMessageW(hwnd, _WM_INPUTLANGCHANGEREQUEST, 0, hkl)


def _switch_mac(layout_id: str) -> None:
    source_id = _MAC_SOURCES.get(layout_id)
    if not source_id:
        return
    try:
        from ctypes import cdll, c_void_p, c_char_p
        import ctypes.util
        carbon = cdll.LoadLibrary(ctypes.util.find_library("Carbon"))

        # Get all input sources
        tid = carbon.TISCreateInputSourceList(None, False)
        count = carbon.CFArrayGetCount(tid)
        for i in range(count):
            src = carbon.CFArrayGetValueAtIndex(tid, i)
            prop = carbon.TISGetInputSourceProperty(
                src,
                carbon.kTISPropertyInputSourceID
            )
            sid = _cf_string_to_str(prop)
            if sid == source_id:
                carbon.TISSelectInputSource(src)
                break
        carbon.CFRelease(tid)
    except Exception:
        # Fallback: AppleScript
        import subprocess
        script = f'''
        tell application "System Events"
            set the input source to input source "{source_id}"
        end tell
        '''
        subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )


def _cf_string_to_str(cf_string) -> str:
    try:
        from ctypes import cdll, c_char_p, c_long
        import ctypes.util
        cf = cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        length = cf.CFStringGetLength(cf_string)
        buf = (c_char_p * (length * 4 + 1))()
        cf.CFStringGetCString(cf_string, buf, len(buf), 0x08000100)
        return buf.value.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def switch_to(layout_id: str) -> None:
    try:
        system = platform.system()
        if system == "Windows":
            _switch_windows(layout_id)
        elif system == "Darwin":
            _switch_mac(layout_id)
    except Exception:
        pass
