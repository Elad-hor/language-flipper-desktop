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

# macOS input source identifiers — listed in priority order
_MAC_SOURCES = {
    "en_us": [
        "com.apple.keylayout.ABC",
        "com.apple.keylayout.US",
        "com.apple.keylayout.USInternational-PC",
        "com.apple.keylayout.British",
        "com.apple.keylayout.Australian",
        "com.apple.keylayout.Canadian",
        "com.apple.keylayout.ABC-QWERTY",
    ],
    "he_il": [
        "com.apple.keylayout.Hebrew",
        "com.apple.keylayout.Hebrew-PC",
        "com.apple.keylayout.Hebrew-QWERTY",
        "com.apple.keylayout.Hebrew-Left-Hand",
    ],
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
    candidates = _MAC_SOURCES.get(layout_id)
    if not candidates:
        return

    def _do():
        try:
            from Foundation import NSBundle
            import objc
            HIToolbox = NSBundle.bundleWithIdentifier_("com.apple.HIToolbox")
            g = {}
            objc.loadBundleFunctions(HIToolbox, g, [
                ("TISCreateInputSourceList", b"@@B"),
                ("TISGetInputSourceProperty", b"@@@"),
                ("TISSelectInputSource",     b"i@"),
            ])
            objc.loadBundleVariables(HIToolbox, g, [
                ("kTISPropertyInputSourceID", b"@"),
            ])
            sources = g["TISCreateInputSourceList"](None, False)
            # Build a map of available source IDs → source objects
            available = {}
            for src in sources:
                sid = g["TISGetInputSourceProperty"](src, g["kTISPropertyInputSourceID"])
                if sid:
                    available[sid] = src
            # Try candidates in order until one is found
            for candidate in candidates:
                if candidate in available:
                    g["TISSelectInputSource"](available[candidate])
                    break
        except Exception:
            pass

    # TIS APIs require the AppKit run loop — dispatch to main thread
    from Foundation import NSOperationQueue
    NSOperationQueue.mainQueue().addOperationWithBlock_(_do)



# ---------------------------------------------------------------------------
# Caps Lock
# ---------------------------------------------------------------------------

def caps_lock_is_on() -> bool:
    try:
        system = platform.system()
        if system == "Windows":
            import ctypes
            return bool(ctypes.windll.user32.GetKeyState(0x14) & 0x0001)
        elif system == "Darwin":
            import Quartz
            flags = Quartz.CGEventSourceFlagsState(
                Quartz.kCGEventSourceStateCombinedSessionState
            )
            return bool(flags & Quartz.kCGEventFlagMaskAlphaShift)
    except Exception:
        pass
    return False


def turn_off_caps_lock() -> None:
    try:
        system = platform.system()
        if system == "Windows":
            import ctypes
            if ctypes.windll.user32.GetKeyState(0x14) & 0x0001:
                KEYEVENTF_KEYUP = 0x0002
                ctypes.windll.user32.keybd_event(0x14, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x14, 0, KEYEVENTF_KEYUP, 0)
        elif system == "Darwin":
            if not caps_lock_is_on():
                return
            from pynput.keyboard import Controller, Key
            kb = Controller()
            kb.press(Key.caps_lock)
            kb.release(Key.caps_lock)
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
