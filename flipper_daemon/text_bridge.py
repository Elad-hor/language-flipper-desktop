"""
Text read/replace — platform-aware.

macOS  → Accessibility API (ApplicationServices via pyobjc)
Linux  → AT-SPI
Both   → clipboard fallback if native path fails
"""

import platform
import time

_PLATFORM = platform.system()  # 'Darwin' | 'Linux' | 'Windows'


# ---------------------------------------------------------------------------
# macOS — Accessibility API
# ---------------------------------------------------------------------------

def _mac_replace(flipped_fn) -> bool:
    try:
        import ApplicationServices as AS

        system = AS.AXUIElementCreateSystemWide()
        err, focused = AS.AXUIElementCopyAttributeValue(
            system, AS.kAXFocusedUIElementAttribute, None
        )
        if err or focused is None:
            return False

        # Try to get selected text
        err, selected = AS.AXUIElementCopyAttributeValue(
            focused, AS.kAXSelectedTextAttribute, None
        )

        if err or not selected:
            # No selection — get word at cursor
            err2, full = AS.AXUIElementCopyAttributeValue(
                focused, AS.kAXValueAttribute, None
            )
            err3, range_val = AS.AXUIElementCopyAttributeValue(
                focused, AS.kAXSelectedTextRangeAttribute, None
            )
            if err2 or err3 or not full:
                return False

            import CoreFoundation as CF
            loc = CF.CFRangeMake(0, 0)
            AS.AXValueGetValue(range_val, AS.kAXValueCFRangeType, loc)
            caret = loc.location

            start, end = _word_bounds(str(full), caret)
            selected = str(full)[start:end]

            if not selected:
                return False

            flipped = flipped_fn(selected)
            if flipped == selected:
                return False

            # Select the word range, then replace
            new_range = CF.CFRangeMake(start, end - start)
            range_ref = AS.AXValueCreate(AS.kAXValueCFRangeType, new_range)
            AS.AXUIElementSetAttributeValue(
                focused, AS.kAXSelectedTextRangeAttribute, range_ref
            )

        else:
            flipped = flipped_fn(str(selected))
            if flipped == str(selected):
                return False

        # Replace selected text by setting kAXSelectedTextAttribute
        err = AS.AXUIElementSetAttributeValue(
            focused, AS.kAXSelectedTextAttribute, flipped
        )
        return err == AS.kAXErrorSuccess

    except Exception:
        return False


# ---------------------------------------------------------------------------
# Linux — AT-SPI
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
        return True

    except Exception:
        return False


# ---------------------------------------------------------------------------
# Clipboard fallback (both platforms)
# ---------------------------------------------------------------------------

def _clipboard_replace(flipped_fn) -> bool:
    try:
        import pyperclip
        import pyautogui

        saved = pyperclip.paste()

        if _PLATFORM == "Darwin":
            pyautogui.hotkey("command", "c")
        else:
            pyautogui.hotkey("ctrl", "c")
        time.sleep(0.08)

        selected = pyperclip.paste()
        if not selected or selected == saved:
            return False

        flipped = flipped_fn(selected)
        if flipped == selected:
            return False

        pyperclip.copy(flipped)

        if _PLATFORM == "Darwin":
            pyautogui.hotkey("command", "v")
        else:
            pyautogui.hotkey("ctrl", "v")
        time.sleep(0.08)

        pyperclip.copy(saved)
        return True

    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def read_and_replace(flipped_fn) -> bool:
    if _PLATFORM == "Darwin":
        if _mac_replace(flipped_fn):
            return True
    elif _PLATFORM == "Linux":
        if _atspi_replace(flipped_fn):
            return True

    return _clipboard_replace(flipped_fn)


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
