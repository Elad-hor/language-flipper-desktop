"""
Which of the layouts the app knows (en / he / ru) the user has installed.

The flip only has to guess a target language when more than two are
installed; with two there is exactly one place to go.

Windows: GetKeyboardLayoutList — cheap, read on every call.
macOS:   TISCreateInputSourceList. HIToolbox wants the main thread (Key Past
         Bug #7), so the list is read there and cached; the flip, which runs
         on a worker thread, reads the cache and asks for a refresh.

If the list cannot be read, the answer is {"en", "he"} — the app's behaviour
before Russian existed.
"""

import platform
import threading

DEFAULT = frozenset({"en", "he"})

# Windows primary language IDs (LANGID & 0x3FF).
_WIN_PRIMARY_LANG = {0x09: "en", 0x0D: "he", 0x19: "ru"}

_mac_cache = None
_mac_lock = threading.Lock()


def langs_from_windows_hkls(hkls) -> frozenset:
    found = set()
    for hkl in hkls:
        lang = _WIN_PRIMARY_LANG.get((hkl or 0) & 0x3FF)
        if lang:
            found.add(lang)
    return frozenset(found)


def langs_from_mac_source_ids(source_ids) -> frozenset:
    found = set()
    for sid in source_ids:
        if not sid or not sid.startswith("com.apple.keylayout."):
            continue
        name = sid[len("com.apple.keylayout."):]
        if name.startswith("Hebrew"):
            found.add("he")
        elif name.startswith("Russian"):
            found.add("ru")
        elif name in ("ABC", "US", "USInternational-PC", "British", "British-PC",
                      "Australian", "Canadian", "ABC-QWERTY", "Irish", "Colemak", "Dvorak"):
            found.add("en")
    return frozenset(found)


def _windows() -> frozenset:
    import ctypes
    user32 = ctypes.windll.user32
    user32.GetKeyboardLayoutList.restype = ctypes.c_int
    n = user32.GetKeyboardLayoutList(0, None)
    if n <= 0:
        return frozenset()
    buf = (ctypes.c_void_p * n)()
    n = user32.GetKeyboardLayoutList(n, buf)
    return langs_from_windows_hkls(buf[:n])


def _read_mac_sources() -> frozenset:
    from Foundation import NSBundle
    import objc
    toolbox = NSBundle.bundleWithIdentifier_("com.apple.HIToolbox")
    g = {}
    objc.loadBundleFunctions(toolbox, g, [
        ("TISCreateInputSourceList", b"@@B"),
        ("TISGetInputSourceProperty", b"@@@"),
    ])
    objc.loadBundleVariables(toolbox, g, [("kTISPropertyInputSourceID", b"@")])
    sources = g["TISCreateInputSourceList"](None, False)  # enabled ones only
    ids = [str(g["TISGetInputSourceProperty"](s, g["kTISPropertyInputSourceID"]) or "")
           for s in sources]
    return langs_from_mac_source_ids(ids)


def _refresh_mac():
    def _do():
        global _mac_cache
        try:
            langs = _read_mac_sources()
            with _mac_lock:
                _mac_cache = langs
        except Exception as e:
            print(f"[installed_layouts] macOS read failed: {e}")
    from Foundation import NSOperationQueue
    NSOperationQueue.mainQueue().addOperationWithBlock_(_do)


def get() -> frozenset:
    try:
        system = platform.system()
        if system == "Windows":
            langs = _windows()
        elif system == "Darwin":
            # The answer used is the one cached by the previous refresh; a
            # layout added a moment ago shows up from the next flip on.
            with _mac_lock:
                langs = _mac_cache
            _refresh_mac()
            if langs is None:
                return DEFAULT
        else:
            return DEFAULT
    except Exception as e:
        print(f"[installed_layouts] read failed: {e}")
        return DEFAULT
    # Fewer than two known layouts means we can't tell where to flip to.
    return langs if len(langs) >= 2 else DEFAULT


def warm_up():
    """Fill the macOS cache at startup so the first flip already knows."""
    if platform.system() == "Darwin":
        try:
            _refresh_mac()
        except Exception as e:
            print(f"[installed_layouts] warm-up failed: {e}")
