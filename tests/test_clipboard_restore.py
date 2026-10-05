"""
The clipboard flip must paste the flipped text even when the app reads the
clipboard late.

    python3 tests/test_clipboard_restore.py

Background: the clipboard path puts the flipped text on the clipboard, sends
Ctrl+V, and then puts the user's old clipboard back. It used to do that 0.1s
after Ctrl+V. New Outlook (WebView2) reads the clipboard asynchronously, after
that window, so it pasted the user's *previously copied* text instead of the
flip — seen live in a new-mail window on Windows.
"""

import sys
import threading
import time
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flipper_daemon import text_bridge  # noqa: E402


class FakeClipboard:
    def __init__(self, text):
        self.text = text
        self.lock = threading.Lock()

    def paste(self):
        with self.lock:
            return self.text

    def copy(self, text):
        with self.lock:
            self.text = text


class SlowPasteApp:
    """An editor whose selection is `selected` and which reads the clipboard
    `read_delay` seconds after Ctrl+V, like WebView2."""

    def __init__(self, clipboard, selected, read_delay):
        self.clipboard = clipboard
        self.selected = selected
        self.read_delay = read_delay
        self.pasted = []
        self._threads = []

    def ctrl_c(self):
        self.clipboard.copy(self.selected)

    def ctrl_v(self):
        def read():
            time.sleep(self.read_delay)
            self.pasted.append(self.clipboard.paste())
        t = threading.Thread(target=read)
        t.start()
        self._threads.append(t)

    def join(self):
        for t in self._threads:
            t.join()


class ClipboardRestoreTest(unittest.TestCase):
    def setUp(self):
        self.clipboard = FakeClipboard("last thing the user copied")
        self._saved = {
            name: getattr(text_bridge, name)
            for name in ("_win_ctrl_c", "_win_ctrl_v", "_win_select_line",
                         "_release_modifiers", "_RESTORE_DELAY_SECONDS")
        }
        self._saved_module = sys.modules.get("pyperclip")
        sys.modules["pyperclip"] = types.SimpleNamespace(
            paste=self.clipboard.paste, copy=self.clipboard.copy)
        text_bridge._release_modifiers = lambda: None
        text_bridge._win_select_line = lambda: None
        text_bridge._RESTORE_DELAY_SECONDS = 0.6

    def tearDown(self):
        text_bridge._cancel_pending_restore_for_tests()
        for name, value in self._saved.items():
            setattr(text_bridge, name, value)
        if self._saved_module is None:
            sys.modules.pop("pyperclip", None)
        else:
            sys.modules["pyperclip"] = self._saved_module

    def _app(self, selected, read_delay):
        app = SlowPasteApp(self.clipboard, selected, read_delay)
        text_bridge._win_ctrl_c = app.ctrl_c
        text_bridge._win_ctrl_v = app.ctrl_v
        return app

    def test_slow_app_pastes_the_flip_not_the_old_clipboard(self):
        app = self._app("AKUO", read_delay=0.3)
        self.assertTrue(text_bridge._windows_replace(lambda s: "שלום"))
        app.join()
        self.assertEqual(app.pasted, ["שלום"])

    def test_old_clipboard_comes_back_afterwards(self):
        app = self._app("AKUO", read_delay=0.05)
        text_bridge._windows_replace(lambda s: "שלום")
        app.join()
        time.sleep(0.8)
        self.assertEqual(self.clipboard.paste(), "last thing the user copied")

    def test_a_new_copy_by_the_user_is_not_overwritten(self):
        app = self._app("AKUO", read_delay=0.05)
        text_bridge._windows_replace(lambda s: "שלום")
        app.join()
        self.clipboard.copy("something the user copied just now")
        time.sleep(0.8)
        self.assertEqual(self.clipboard.paste(), "something the user copied just now")

    def test_back_to_back_flips_restore_the_original_clipboard(self):
        app = self._app("AKUO", read_delay=0.05)
        text_bridge._windows_replace(lambda s: "שלום")
        app.join()
        # Second flip before the first restore fired: the clipboard still
        # holds our flipped text, which must not become the "saved" value.
        app.selected = "שלום"
        text_bridge._windows_replace(lambda s: "akuo")
        app.join()
        time.sleep(0.8)
        self.assertEqual(app.pasted, ["שלום", "akuo"])
        self.assertEqual(self.clipboard.paste(), "last thing the user copied")


if __name__ == "__main__":
    unittest.main()
