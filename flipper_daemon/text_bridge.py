"""
Text read/replace via AT-SPI with clipboard fallback.

AT-SPI path  — zero clipboard touch, works in any GTK/Qt/Electron app.
Clipboard fallback — Ctrl+C → flip → Ctrl+V, used when AT-SPI is unavailable
                     or the focused element is a canvas (Figma, games, etc.).
"""

import subprocess
import time

try:
    import pyatspi
    _ATSPI_AVAILABLE = True
except ImportError:
    _ATSPI_AVAILABLE = False

try:
    import pyperclip
    _CLIPBOARD_AVAILABLE = True
except ImportError:
    _CLIPBOARD_AVAILABLE = False


# ---------------------------------------------------------------------------
# AT-SPI helpers
# ---------------------------------------------------------------------------

def _get_focused_text_iface():
    """Return the pyatspi Text interface for the currently focused element, or None."""
    if not _ATSPI_AVAILABLE:
        return None
    try:
        desktop = pyatspi.Registry.getDesktop(0)
        for app in desktop:
            if app is None:
                continue
            focused = _find_focused(app)
            if focused:
                try:
                    return focused.queryText()
                except Exception:
                    return None
    except Exception:
        return None
    return None


def _find_focused(node, depth=0):
    if depth > 12:
        return None
    try:
        state = node.getState()
        if state.contains(pyatspi.STATE_FOCUSED):
            return node
        for child in node:
            result = _find_focused(child, depth + 1)
            if result:
                return result
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_and_replace(flipped_fn) -> bool:
    """
    Read the current selection (or word at cursor), flip it via flipped_fn,
    and write it back. Returns True on success.
    """
    if _ATSPI_AVAILABLE:
        success = _atspi_replace(flipped_fn)
        if success:
            return True

    # Fallback: clipboard-based swap
    return _clipboard_replace(flipped_fn)


def _atspi_replace(flipped_fn) -> bool:
    text_iface = _get_focused_text_iface()
    if text_iface is None:
        return False

    try:
        sel_count = text_iface.getNSelections()
        if sel_count > 0:
            start, end = text_iface.getSelection(0)
        else:
            # No selection — grab word at cursor
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


def _clipboard_replace(flipped_fn) -> bool:
    if not _CLIPBOARD_AVAILABLE:
        return False
    try:
        # Save clipboard
        saved = pyperclip.paste()

        # Copy selection
        _send_keys(["ctrl", "c"])
        time.sleep(0.08)
        selected = pyperclip.paste()

        if not selected or selected == saved:
            pyperclip.copy(saved)
            return False

        flipped = flipped_fn(selected)
        if flipped == selected:
            pyperclip.copy(saved)
            return False

        pyperclip.copy(flipped)
        _send_keys(["ctrl", "v"])
        time.sleep(0.08)

        # Restore clipboard
        pyperclip.copy(saved)
        return True

    except Exception:
        return False


def _send_keys(keys: list):
    """Send a key combo via xdotool (X11) — simple and reliable."""
    try:
        subprocess.run(["xdotool", "key", "+".join(keys)], check=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _word_bounds(text: str, pos: int) -> tuple[int, int]:
    """Return (start, end) of the word that contains position pos."""
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
