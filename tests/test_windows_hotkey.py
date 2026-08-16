"""
The Windows WM_HOTKEY message pump.

    python3 tests/test_windows_hotkey.py

Two holes, neither of which has a macOS twin:

The pump called the flip callback bare, so any exception escaping _on_flip —
storage._save on a full or locked disk, a ctypes error in layout_switch — took
the loop's thread down with it and the hotkey was gone for the rest of the run,
silently. The macOS path never had this: its on_press wrapper swallows callback
exceptions.

And `while GetMessageW(...) != 0` treats the -1 error return as "carry on", so
a failure would spin the loop over a garbage MSG. MSDN calls this out by name.

The pump takes its messages from an injected callable so it can be exercised
without Windows.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flipper_daemon.hotkey import _WM_HOTKEY, _pump_hotkey_messages  # noqa: E402

_HOTKEY_ID = 9001


def messages(*items):
    """Feed the pump a fixed script of (got, message, wParam) tuples."""
    queue = list(items)

    def next_message():
        return queue.pop(0) if queue else (0, 0, 0)  # then WM_QUIT

    return next_message


class PumpTest(unittest.TestCase):
    def setUp(self):
        self.flips = []

    def test_fires_the_flip_on_our_hotkey(self):
        result = _pump_hotkey_messages(
            next_message=messages((1, _WM_HOTKEY, _HOTKEY_ID)),
            dispatch=lambda: self.flips.append(1),
            hotkey_id=_HOTKEY_ID,
        )

        self.assertEqual(len(self.flips), 1)
        self.assertEqual(result, "quit")

    def test_ignores_other_messages_and_other_hotkey_ids(self):
        _pump_hotkey_messages(
            next_message=messages(
                (1, 0x0100, _HOTKEY_ID),        # WM_KEYDOWN, not ours
                (1, _WM_HOTKEY, _HOTKEY_ID + 1),  # someone else's hotkey id
            ),
            dispatch=lambda: self.flips.append(1),
            hotkey_id=_HOTKEY_ID,
        )

        self.assertEqual(self.flips, [])

    def test_a_raising_flip_does_not_kill_the_pump(self):
        """One bad flip must not cost the user their hotkey until restart."""
        def angry():
            self.flips.append(1)
            raise RuntimeError("storage write failed")

        result = _pump_hotkey_messages(
            next_message=messages(
                (1, _WM_HOTKEY, _HOTKEY_ID),
                (1, _WM_HOTKEY, _HOTKEY_ID),
            ),
            dispatch=angry,
            hotkey_id=_HOTKEY_ID,
        )

        self.assertEqual(len(self.flips), 2, "pump stopped after the first failure")
        self.assertEqual(result, "quit")

    def test_wm_quit_stops_the_pump(self):
        result = _pump_hotkey_messages(
            next_message=messages((0, 0, 0)),
            dispatch=lambda: self.flips.append(1),
            hotkey_id=_HOTKEY_ID,
        )

        self.assertEqual(result, "quit")

    def test_getmessage_error_is_not_treated_as_a_message(self):
        """-1 is GetMessageW's error return. The old `!= 0` test let it through
        and the loop read a MSG that was never filled in."""
        result = _pump_hotkey_messages(
            next_message=messages((-1, _WM_HOTKEY, _HOTKEY_ID)),
            dispatch=lambda: self.flips.append(1),
            hotkey_id=_HOTKEY_ID,
        )

        self.assertEqual(result, "error")
        self.assertEqual(self.flips, [], "acted on an unfilled MSG")


if __name__ == "__main__":
    unittest.main(verbosity=2)
