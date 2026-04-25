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
            print(f"[layout_switch] switching to {source_id}, found {len(sources)} sources")
            for src in sources:
                sid = g["TISGetInputSourceProperty"](src, g["kTISPropertyInputSourceID"])
                if sid == source_id:
                    result = g["TISSelectInputSource"](src)
                    print(f"[layout_switch] TISSelectInputSource({source_id}) = {result}")
                    break
            else:
                print(f"[layout_switch] source {source_id} not found in list")
        except Exception as e:
            print(f"[layout_switch] error: {e}")

    # TIS APIs require the AppKit run loop — dispatch to main thread
    from Foundation import NSOperationQueue
    NSOperationQueue.mainQueue().addOperationWithBlock_(_do)



def switch_to(layout_id: str) -> None:
    try:
        system = platform.system()
        if system == "Windows":
            _switch_windows(layout_id)
        elif system == "Darwin":
            _switch_mac(layout_id)
    except Exception:
        pass
