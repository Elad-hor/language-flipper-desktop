"""
The macOS event-tap intercept and the off-thread flip dispatch.

    python3 tests/test_darwin_intercept.py

Passing a darwin_intercept makes pynput build an *active* tap
(kCGEventTapOptionDefault, pynput/_util/darwin.py::_create_event_tap), which
means macOS holds every keystroke in the system until our callback returns. A
flip takes ~0.7s of sleeps plus pbcopy/pbpaste spawns, and can make a blocking
HTTPS call when the licence cache expires — well past the timeout at which
macOS switches an unresponsive tap off. pynput never turns it back on: there is
exactly one CGEventTapEnable in the library and it runs at setup. So one slow
flip froze the keyboard and then killed the hotkey for the rest of the run.

Quartz is faked here so the logic is testable off macOS.
"""

import sys
import threading
import time
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_VK_Y = 0x10
_CMD = 1 << 20
_SHIFT = 1 << 17


class FakeEvent:
    def __init__(self, keycode=0, flags=0):
        self.keycode = keycode
        self.flags = flags


def install_fake_quartz():
    """Put a stand-in Quartz in sys.modules and return it."""
    q = types.ModuleType("Quartz")
    q.kCGEventKeyDown = 10
    q.kCGEventKeyUp = 11
    q.kCGEventTapDisabledByTimeout = 0xFFFFFFFE
    q.kCGEventTapDisabledByUserInput = 0xFFFFFFFF
    q.kCGKeyboardEventKeycode = 9
    q.kCGEventFlagMaskCommand = _CMD
    q.kCGEventFlagMaskShift = _SHIFT
    q.CGEventGetIntegerValueField = lambda event, field: event.keycode
    q.CGEventGetFlags = lambda event: event.flags
    q.enabled = []
    q.CGEventTapEnable = lambda tap, on: q.enabled.append((tap, on))
    sys.modules["Quartz"] = q
    return q


class InterceptTest(unittest.TestCase):
    def setUp(self):
        self.quartz = install_fake_quartz()
        from flipper_daemon.hotkey import _make_darwin_intercept

        self.tap_ref = {"tap": "TAP"}
        self.intercept = _make_darwin_intercept(self.tap_ref)

    def tearDown(self):
        sys.modules.pop("Quartz", None)

    def test_reenables_a_tap_macos_disabled_on_timeout(self):
        """The whole point: a tap switched off by macOS must come back, or the
        hotkey is dead for the rest of the run."""
        self.intercept(self.quartz.kCGEventTapDisabledByTimeout, FakeEvent())

        self.assertEqual(self.quartz.enabled, [("TAP", True)])

    def test_reenables_a_tap_disabled_by_user_input(self):
        self.intercept(self.quartz.kCGEventTapDisabledByUserInput, FakeEvent())

        self.assertEqual(self.quartz.enabled, [("TAP", True)])

    def test_survives_a_disable_arriving_before_the_tap_was_recorded(self):
        from flipper_daemon.hotkey import _make_darwin_intercept

        intercept = _make_darwin_intercept({"tap": None})
        intercept(self.quartz.kCGEventTapDisabledByTimeout, FakeEvent())  # no raise

        self.assertEqual(self.quartz.enabled, [])

    def test_still_swallows_the_hotkey(self):
        """Suppression is why the intercept exists — Key Past Bug #15."""
        event = FakeEvent(keycode=_VK_Y, flags=_CMD | _SHIFT)

        self.assertIsNone(self.intercept(self.quartz.kCGEventKeyDown, event))
        self.assertIsNone(self.intercept(self.quartz.kCGEventKeyUp, event))

    def test_passes_other_keys_through(self):
        for event in (
            FakeEvent(keycode=_VK_Y, flags=0),            # plain y
            FakeEvent(keycode=_VK_Y, flags=_CMD),         # Cmd+Y, no shift
            FakeEvent(keycode=0x00, flags=_CMD | _SHIFT),  # Cmd+Shift+A
        ):
            self.assertIs(
                self.intercept(self.quartz.kCGEventKeyDown, event), event
            )

    def test_fails_open_when_quartz_misbehaves(self):
        """Over-suppressing silently eats real keystrokes, so any error must
        pass the event through untouched."""
        def boom(event, field):
            raise RuntimeError("Quartz exploded")

        self.quartz.CGEventGetIntegerValueField = boom
        event = FakeEvent(keycode=_VK_Y, flags=_CMD | _SHIFT)

        self.assertIs(self.intercept(self.quartz.kCGEventKeyDown, event), event)


class DispatchTest(unittest.TestCase):
    def test_flip_does_not_block_the_caller(self):
        """The tap callback has to return in microseconds; the flip itself
        takes the best part of a second."""
        from flipper_daemon.hotkey import _dispatch_off_thread

        started = threading.Event()
        release = threading.Event()

        def slow_flip():
            started.set()
            release.wait(2)

        dispatch = _dispatch_off_thread(slow_flip)

        begin = time.monotonic()
        dispatch()
        elapsed = time.monotonic() - begin

        self.assertTrue(started.wait(1), "the flip never ran")
        self.assertLess(elapsed, 0.2, "the flip blocked the tap callback")
        release.set()

    def test_dispatch_survives_a_raising_callback(self):
        from flipper_daemon.hotkey import _dispatch_off_thread

        done = threading.Event()

        def angry():
            done.set()
            raise RuntimeError("flip failed")

        _dispatch_off_thread(angry)()  # must not raise into the tap

        self.assertTrue(done.wait(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
