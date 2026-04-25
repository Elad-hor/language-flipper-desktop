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
        import ctypes
        import ctypes.util

        carbon = ctypes.cdll.LoadLibrary(ctypes.util.find_library("Carbon"))
        cf     = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))

        # Must declare restypes — without this, 64-bit pointers get truncated to int
        carbon.TISCreateInputSourceList.restype   = ctypes.c_void_p
        carbon.TISCreateInputSourceList.argtypes  = [ctypes.c_void_p, ctypes.c_bool]
        carbon.TISGetInputSourceProperty.restype  = ctypes.c_void_p
        carbon.TISGetInputSourceProperty.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        carbon.TISSelectInputSource.restype       = ctypes.c_int
        carbon.TISSelectInputSource.argtypes      = [ctypes.c_void_p]
        cf.CFArrayGetCount.restype                = ctypes.c_long
        cf.CFArrayGetCount.argtypes               = [ctypes.c_void_p]
        cf.CFArrayGetValueAtIndex.restype         = ctypes.c_void_p
        cf.CFArrayGetValueAtIndex.argtypes        = [ctypes.c_void_p, ctypes.c_long]
        cf.CFStringGetCString.restype             = ctypes.c_bool
        cf.CFStringGetCString.argtypes            = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_int]
        cf.CFRelease.argtypes                     = [ctypes.c_void_p]

        # kTISPropertyInputSourceID is a global CFStringRef symbol in Carbon
        prop_key = ctypes.c_void_p.in_dll(carbon, "kTISPropertyInputSourceID")

        sources = carbon.TISCreateInputSourceList(None, False)
        count   = cf.CFArrayGetCount(sources)
        for i in range(count):
            src  = cf.CFArrayGetValueAtIndex(sources, i)
            prop = carbon.TISGetInputSourceProperty(src, prop_key)
            if not prop:
                continue
            buf = ctypes.create_string_buffer(256)
            cf.CFStringGetCString(prop, buf, 256, 0x08000100)
            if buf.value.decode("utf-8", errors="ignore") == source_id:
                carbon.TISSelectInputSource(src)
                break
        cf.CFRelease(sources)
    except Exception:
        pass



def switch_to(layout_id: str) -> None:
    try:
        system = platform.system()
        if system == "Windows":
            _switch_windows(layout_id)
        elif system == "Darwin":
            _switch_mac(layout_id)
    except Exception:
        pass
