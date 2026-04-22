"""
Text read/replace — platform-aware.

macOS  → Accessibility API (ApplicationServices via pyobjc)
Linux  → AT-SPI
Both   → clipboard fallback if native path fails or AX succeeds but app ignores it
         (React/web inputs don't respond to AX writes — clipboard is the only option)
"""

import platform
import time

_PLATFORM = platform.system()  # 'Darwin' | 'Linux' | 'Windows'

# Set to True to print which path fired — useful for diagnosing new failure sites
DEBUG = True

def _dbg(msg):
    if DEBUG:
        print(f"[text_bridge] {msg}")


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
            _dbg("AX: no focused element")
            return False

        # Identify the app so we can skip known-broken cases (Chrome web content)
        try:
            err_app, app_elem = AS.AXUIElementCopyAttributeValue(
                focused, AS.kAXApplicationAttribute, None
            )
            err_title, app_title = AS.AXUIElementCopyAttributeValue(
                app_elem, AS.kAXTitleAttribute, None
            ) if not err_app and app_elem else (1, None)
            _dbg(f"AX: focused app = {app_title}")
        except Exception:
            app_title = None

        # Chrome/Firefox/Brave/Edge render web content in a process that exposes AX
        # but silently ignores writes to kAXSelectedTextAttribute for web inputs.
        # Skip straight to clipboard for those apps.
        _WEB_BROWSERS = {"Google Chrome", "Chromium", "Firefox", "Brave Browser",
                         "Microsoft Edge", "Arc", "Opera"}
        if app_title in _WEB_BROWSERS:
            _dbg("AX: browser web content — skipping to clipboard fallback")
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
                _dbg("AX: no selection and no value/range")
                return False

            import CoreFoundation as CF
            loc = CF.CFRangeMake(0, 0)
            AS.AXValueGetValue(range_val, AS.kAXValueCFRangeType, loc)
            caret = loc.location

            start, end = _word_bounds(str(full), caret)
            selected = str(full)[start:end]

            if not selected:
                _dbg("AX: empty word at cursor")
                return False

            flipped = flipped_fn(selected)
            if flipped == selected:
                _dbg("AX: nothing to flip")
                return False

            new_range = CF.CFRangeMake(start, end - start)
            range_ref = AS.AXValueCreate(AS.kAXValueCFRangeType, new_range)
            AS.AXUIElementSetAttributeValue(
                focused, AS.kAXSelectedTextRangeAttribute, range_ref
            )

        else:
            flipped = flipped_fn(str(selected))
            if flipped == str(selected):
                _dbg("AX: nothing to flip")
                return False

        err = AS.AXUIElementSetAttributeValue(
            focused, AS.kAXSelectedTextAttribute, flipped
        )
        success = (err == AS.kAXErrorSuccess)
        _dbg(f"AX: write {'ok' if success else 'failed'} (err={err})")
        return success

    except Exception as e:
        _dbg(f"AX: exception — {e}")
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
            _dbg("AT-SPI: empty selection/word")
            return False

        original = text_iface.getText(start, end)
        flipped = flipped_fn(original)
        if flipped == original:
            _dbg("AT-SPI: nothing to flip")
            return False

        text_iface.deleteText(start, end)
        text_iface.insertText(start, flipped, len(flipped))
        _dbg("AT-SPI: write ok")
        return True

    except Exception as e:
        _dbg(f"AT-SPI: exception — {e}")
        return False


# ---------------------------------------------------------------------------
# Clipboard fallback (both platforms)
# Works for: browser web inputs, React/Angular apps, any app that ignores AX writes
# ---------------------------------------------------------------------------

def _clipboard_replace(flipped_fn) -> bool:
    try:
        import pyperclip
        import pyautogui

        saved = pyperclip.paste()
        _dbg(f"clipboard: saved = {repr(saved[:40])}")

        if _PLATFORM == "Darwin":
            pyautogui.hotkey("command", "c")
        else:
            pyautogui.hotkey("ctrl", "c")

        # Wait for the browser/app to update the clipboard.
        # 150ms is enough for Chrome; bump to 200ms if still flaky.
        time.sleep(0.15)

        selected = pyperclip.paste()
        _dbg(f"clipboard: copied = {repr(selected[:40])}")

        if not selected or selected == saved:
            _dbg("clipboard: nothing new in clipboard — no selection?")
            return False

        flipped = flipped_fn(selected)
        if flipped == selected:
            _dbg("clipboard: nothing to flip")
            pyperclip.copy(saved)
            return False

        pyperclip.copy(flipped)

        if _PLATFORM == "Darwin":
            pyautogui.hotkey("command", "v")
        else:
            pyautogui.hotkey("ctrl", "v")

        time.sleep(0.1)
        pyperclip.copy(saved)  # restore clipboard
        _dbg("clipboard: done")
        return True

    except Exception as e:
        _dbg(f"clipboard: exception — {e}")
        return False


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def read_and_replace(flipped_fn) -> bool:
    if _PLATFORM == "Darwin":
        if _mac_replace(flipped_fn):
            return True
        _dbg("AX failed — trying clipboard fallback")
    elif _PLATFORM == "Linux":
        if _atspi_replace(flipped_fn):
            return True
        _dbg("AT-SPI failed — trying clipboard fallback")

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
