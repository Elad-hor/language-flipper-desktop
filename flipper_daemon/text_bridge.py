"""
Text read/replace — platform-aware.

macOS  → Accessibility API via AXUIElementCreateApplication(pid) using
         NSWorkspace.frontmostApplication() to get the correct target.
         Falls back to clipboard (Cmd+C / Cmd+V via CGEventPostToPid).
Linux  → AT-SPI, falls back to clipboard via pyautogui.
"""

import platform
import time

_PLATFORM = platform.system()

DEBUG = True
_LOG = open("/tmp/lf_debug.txt", "a", buffering=1)

def _dbg(msg):
    if DEBUG:
        import datetime
        _LOG.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")


# ---------------------------------------------------------------------------
# macOS helpers
# ---------------------------------------------------------------------------

def _get_frontmost_app():
    """Return (pid, app_name) of the current frontmost application."""
    try:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app:
            return app.processIdentifier(), str(app.localizedName() or "")
    except Exception as e:
        _dbg(f"NSWorkspace error: {e}")
    return None, None


def _clipboard_copy_from_pid(pid: int):
    """Send Cmd+C directly to a specific process via Quartz CGEventPostToPid."""
    try:
        import Quartz
        src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)
        # key code 8 = 'c'
        down = Quartz.CGEventCreateKeyboardEvent(src, 8, True)
        up   = Quartz.CGEventCreateKeyboardEvent(src, 8, False)
        Quartz.CGEventSetFlags(down, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventSetFlags(up,   Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPostToPid(pid, down)
        Quartz.CGEventPostToPid(pid, up)
        return True
    except Exception as e:
        _dbg(f"CGEventPostToPid copy failed: {e}")
        return False


def _send_key_to_pid(pid: int, keycode: int, flags: int = 0):
    """Send a single key down+up to a specific process."""
    try:
        import Quartz
        src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)
        down = Quartz.CGEventCreateKeyboardEvent(src, keycode, True)
        up   = Quartz.CGEventCreateKeyboardEvent(src, keycode, False)
        if flags:
            Quartz.CGEventSetFlags(down, flags)
            Quartz.CGEventSetFlags(up,   flags)
        Quartz.CGEventPostToPid(pid, down)
        Quartz.CGEventPostToPid(pid, up)
    except Exception as e:
        _dbg(f"_send_key_to_pid failed: {e}")


def _select_current_line(pid: int):
    """
    Select the current line (matches Chrome extension no-selection behaviour):
      Cmd+Left        → jump to start of line
      Cmd+Shift+Right → extend selection to end of line
    """
    import Quartz
    CMD       = Quartz.kCGEventFlagMaskCommand
    CMD_SHIFT = Quartz.kCGEventFlagMaskCommand | Quartz.kCGEventFlagMaskShift
    _send_key_to_pid(pid, 123, CMD)        # Cmd+Left  (keycode 123)
    time.sleep(0.05)
    _send_key_to_pid(pid, 124, CMD_SHIFT)  # Cmd+Shift+Right (keycode 124)
    time.sleep(0.06)


def _clipboard_paste_to_pid(pid: int):
    """Send Cmd+V directly to a specific process via Quartz CGEventPostToPid."""
    try:
        import Quartz
        src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)
        # key code 9 = 'v'
        down = Quartz.CGEventCreateKeyboardEvent(src, 9, True)
        up   = Quartz.CGEventCreateKeyboardEvent(src, 9, False)
        Quartz.CGEventSetFlags(down, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventSetFlags(up,   Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPostToPid(pid, down)
        Quartz.CGEventPostToPid(pid, up)
        return True
    except Exception as e:
        _dbg(f"CGEventPostToPid paste failed: {e}")
        return False


# ---------------------------------------------------------------------------
# macOS — Accessibility API path
# ---------------------------------------------------------------------------

# Apps that expose AX but silently ignore writes (Electron / web-rendered).
# Strip directional unicode marks before comparing.
_CLIPBOARD_ONLY_APPS = {
    "Google Chrome", "Chromium", "Firefox", "Brave Browser",
    "Microsoft Edge", "Arc", "Opera", "Safari",
    "WhatsApp", "Slack", "Discord", "Notion", "Figma",
    "Microsoft Teams", "Zoom",
}

def _normalize_app_name(name: str) -> str:
    """Strip leading/trailing Unicode directional marks that some apps inject."""
    return name.strip("\u200f\u200e\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")

def _mac_replace(flipped_fn, pid: int, app_name: str) -> bool:
    clean_name = _normalize_app_name(app_name)
    if clean_name in _CLIPBOARD_ONLY_APPS:
        _dbg(f"AX: {clean_name!r} is Electron/browser — skip to clipboard")
        return False

    try:
        import ApplicationServices as AS

        if not AS.AXIsProcessTrusted():
            _dbg("AX: process not trusted")
            return False

        # Query the specific app by PID — avoids the CGEventTap focus problem
        app_elem = AS.AXUIElementCreateApplication(pid)
        err, focused = AS.AXUIElementCopyAttributeValue(
            app_elem, AS.kAXFocusedUIElementAttribute, None
        )
        if err or focused is None:
            _dbg(f"AX: no focused element in {app_name} (err={err})")
            return False

        _dbg(f"AX: got focused element in {app_name}")

        # Read selection
        err, selected = AS.AXUIElementCopyAttributeValue(
            focused, AS.kAXSelectedTextAttribute, None
        )

        if err or not selected:
            # No selection — grab word at cursor
            err2, full = AS.AXUIElementCopyAttributeValue(
                focused, AS.kAXValueAttribute, None
            )
            err3, range_val = AS.AXUIElementCopyAttributeValue(
                focused, AS.kAXSelectedTextRangeAttribute, None
            )
            if err2 or err3 or not full:
                _dbg("AX: no selection and no value/range")
                return False

            import CoreFoundation as CF
            loc = CF.CFRangeMake(0, 0)
            AS.AXValueGetValue(range_val, AS.kAXValueCFRangeType, loc)
            caret = loc.location
            start, end = _line_bounds(str(full), caret)
            selected = str(full)[start:end]
            if not selected:
                _dbg("AX: empty word at cursor")
                return False

            flipped = flipped_fn(selected)
            if flipped == selected:
                return False

            import CoreFoundation as CF
            new_range = CF.CFRangeMake(start, end - start)
            range_ref = AS.AXValueCreate(AS.kAXValueCFRangeType, new_range)
            AS.AXUIElementSetAttributeValue(
                focused, AS.kAXSelectedTextRangeAttribute, range_ref
            )
        else:
            flipped = flipped_fn(str(selected))
            if flipped == str(selected):
                return False

        err = AS.AXUIElementSetAttributeValue(
            focused, AS.kAXSelectedTextAttribute, flipped
        )
        ok = (err == AS.kAXErrorSuccess)
        _dbg(f"AX: write {'ok' if ok else f'failed err={err}'}")
        return ok

    except Exception as e:
        _dbg(f"AX: exception — {e}")
        return False


# ---------------------------------------------------------------------------
# macOS — clipboard path
# ---------------------------------------------------------------------------

def _mac_clipboard_replace(flipped_fn, pid: int) -> bool:
    try:
        import pyperclip

        saved = str(pyperclip.paste() or "")
        _dbg(f"clipboard: saved = {repr(saved[:40])}")

        _clipboard_copy_from_pid(pid)
        time.sleep(0.18)

        selected = str(pyperclip.paste() or "")
        _dbg(f"clipboard: after copy = {repr(selected[:40])}")

        if not selected or selected == saved:
            # Nothing selected — select current line and try again
            _dbg("clipboard: nothing selected — selecting current line")
            _select_current_line(pid)
            _clipboard_copy_from_pid(pid)
            time.sleep(0.18)
            selected = str(pyperclip.paste() or "")
            _dbg(f"clipboard: after word select+copy = {repr(selected[:40])}")

        if not selected or selected == saved:
            _dbg("clipboard: still nothing — cursor not in a word?")
            return False

        flipped = flipped_fn(selected)
        if flipped == selected:
            _dbg("clipboard: nothing to flip")
            pyperclip.copy(saved)
            return False

        pyperclip.copy(flipped)
        _clipboard_paste_to_pid(pid)
        time.sleep(0.1)
        pyperclip.copy(saved)
        _dbg("clipboard: done")
        return True

    except Exception as e:
        _dbg(f"clipboard: exception — {e}")
        return False


# ---------------------------------------------------------------------------
# Linux — AT-SPI path
# ---------------------------------------------------------------------------

def _atspi_replace(flipped_fn) -> bool:
    try:
        import pyatspi

        def find_focused(node, depth=0):
            if depth > 12:
                return None
            try:
                if node.getState().contains(pyatspi.STATE_FOCUSED):
                    return node
                for child in node:
                    r = find_focused(child, depth + 1)
                    if r:
                        return r
            except Exception:
                pass
            return None

        desktop = pyatspi.Registry.getDesktop(0)
        focused = None
        for app in desktop:
            if app is None:
                continue
            focused = find_focused(app)
            if focused:
                break

        if focused is None:
            _dbg("AT-SPI: no focused element")
            return False

        text_iface = focused.queryText()
        if text_iface.getNSelections() > 0:
            start, end = text_iface.getSelection(0)
        else:
            caret = text_iface.caretOffset
            full = text_iface.getText(0, -1)
            start, end = _word_bounds(full, caret)

        if start == end:
            return False

        original = text_iface.getText(start, end)
        flipped = flipped_fn(original)
        if flipped == original:
            return False

        text_iface.deleteText(start, end)
        text_iface.insertText(start, flipped, len(flipped))
        _dbg("AT-SPI: write ok")
        return True

    except Exception as e:
        _dbg(f"AT-SPI: exception — {e}")
        return False


def _linux_clipboard_replace(flipped_fn) -> bool:
    try:
        import pyperclip, pyautogui
        saved = str(pyperclip.paste() or "")
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        selected = str(pyperclip.paste() or "")
        if not selected or selected == saved:
            _dbg("linux clipboard: nothing selected — selecting current line")
            pyautogui.hotkey("home")
            time.sleep(0.05)
            pyautogui.hotkey("shift", "end")
            time.sleep(0.06)
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.15)
            selected = str(pyperclip.paste() or "")
        if not selected or selected == saved:
            return False
        flipped = flipped_fn(selected)
        if flipped == selected:
            pyperclip.copy(saved)
            return False
        pyperclip.copy(flipped)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)
        pyperclip.copy(saved)
        return True
    except Exception as e:
        _dbg(f"linux clipboard: exception — {e}")
        return False


# ---------------------------------------------------------------------------
# Windows — clipboard path
# ---------------------------------------------------------------------------

def _release_modifiers():
    """Release modifier keys still held from the hotkey."""
    try:
        from pynput.keyboard import Controller, Key
        kb = Controller()
        for k in (Key.ctrl, Key.ctrl_l, Key.ctrl_r,
                  Key.shift, Key.shift_l, Key.shift_r,
                  Key.cmd, Key.cmd_l, Key.cmd_r):
            try:
                kb.release(k)
            except Exception:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Windows — low-level keyboard injection (works from any thread)
# ---------------------------------------------------------------------------

# VK codes for navigation keys that require EXTENDEDKEY flag
_WIN_EXTENDED_VK = {
    0x21, 0x22, 0x23, 0x24,  # PgUp, PgDn, End, Home
    0x25, 0x26, 0x27, 0x28,  # Left, Up, Right, Down
    0x2D, 0x2E,              # Insert, Delete
}

def _win_key(vk: int, down: bool):
    """Inject one key event via keybd_event — works from any background thread."""
    import ctypes
    KEYEVENTF_KEYUP       = 0x0002
    KEYEVENTF_EXTENDEDKEY = 0x0001
    flags = 0
    if not down:
        flags |= KEYEVENTF_KEYUP
    if vk in _WIN_EXTENDED_VK:
        flags |= KEYEVENTF_EXTENDEDKEY
    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)


def _win_tap(vk: int):
    _win_key(vk, True)
    _win_key(vk, False)


def _win_ctrl_c():
    _win_key(0x11, True);  _win_tap(0x43);  _win_key(0x11, False)   # Ctrl+C


def _win_ctrl_v():
    _win_key(0x11, True);  _win_tap(0x56);  _win_key(0x11, False)   # Ctrl+V


def _win_select_line():
    """Home → Shift+End to select the current line."""
    _win_tap(0x24)                                   # VK_HOME
    time.sleep(0.05)
    _win_key(0x10, True);  _win_tap(0x23);  _win_key(0x10, False)   # Shift+End
    time.sleep(0.06)


def _windows_replace(flipped_fn) -> bool:
    try:
        import pyperclip

        # Release hotkey modifiers before injecting any keys.
        _release_modifiers()
        time.sleep(0.05)

        saved = str(pyperclip.paste() or "")
        _dbg(f"windows clipboard: saved = {repr(saved[:40])}")

        _win_ctrl_c()
        time.sleep(0.18)
        selected = str(pyperclip.paste() or "")
        _dbg(f"windows clipboard: after copy = {repr(selected[:40])}")

        if not selected or selected == saved:
            _dbg("windows clipboard: nothing selected — selecting current line")
            _release_modifiers()
            _win_select_line()
            _win_ctrl_c()
            time.sleep(0.18)
            selected = str(pyperclip.paste() or "")
            _dbg(f"windows clipboard: after line select = {repr(selected[:40])}")

        if not selected or selected == saved:
            _dbg("windows clipboard: still nothing")
            return False

        flipped = flipped_fn(selected)
        if flipped == selected:
            pyperclip.copy(saved)
            _dbg("windows clipboard: nothing to flip")
            return False

        pyperclip.copy(flipped)
        _release_modifiers()
        _win_ctrl_v()
        time.sleep(0.1)
        pyperclip.copy(saved)
        _dbg("windows clipboard: done")
        return True

    except Exception as e:
        _dbg(f"windows clipboard: exception — {e}")
        return False


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def read_and_replace(flipped_fn) -> bool:
    # Let hotkey keys fully release and OS settle focus back to target app.
    time.sleep(0.08)

    if _PLATFORM == "Darwin":
        pid, app_name = _get_frontmost_app()
        _dbg(f"frontmost: {app_name!r} pid={pid}")
        if pid and _mac_replace(flipped_fn, pid, app_name):
            return True
        _dbg("AX failed — trying clipboard")
        if pid:
            return _mac_clipboard_replace(flipped_fn, pid)
        return False

    elif _PLATFORM == "Windows":
        _release_modifiers()
        return _windows_replace(flipped_fn)

    elif _PLATFORM == "Linux":
        if _atspi_replace(flipped_fn):
            return True
        _dbg("AT-SPI failed — trying clipboard")
        return _linux_clipboard_replace(flipped_fn)

    return False


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _word_bounds(text: str, pos: int) -> tuple[int, int]:
    if not text:
        return (0, 0)
    pos = max(0, min(pos, len(text) - 1))
    start = pos
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    end = pos
    while end < len(text) and not text[end].isspace():
        end += 1
    return (start, end)


def _line_bounds(text: str, pos: int) -> tuple[int, int]:
    """Return (start, end) of the line containing pos (split on newlines)."""
    if not text:
        return (0, 0)
    pos = max(0, min(pos, len(text)))
    start = text.rfind("\n", 0, pos)
    start = 0 if start == -1 else start + 1
    end = text.find("\n", pos)
    end = len(text) if end == -1 else end
    return (start, end)
