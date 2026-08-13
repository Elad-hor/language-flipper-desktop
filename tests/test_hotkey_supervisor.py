"""
The macOS hotkey supervisor.

    python3 tests/test_hotkey_supervisor.py

Background: CGEventTapCreate returns NULL when the process lacks Accessibility,
and pynput reacts by returning from its run-loop thread immediately
(pynput/_util/darwin.py::ListenerMixin._run) — Listener.start() still looks
like it succeeded. macOS revokes Accessibility on every binary hash change,
i.e. on every auto-update, so the app came back up permanently deaf: the user
granted permission in onboarding, nothing re-created the tap, and the hotkey
stayed dead until the app was quit and reopened by hand.
"""

import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flipper_daemon.hotkey import _supervise  # noqa: E402


class FakeListener:
    """Reports alive for a fixed number of polls, then dies — like a listener
    whose event tap could not be created. alive_polls=None never dies."""

    def __init__(self, alive_polls=0, on_poll=None):
        self._left = alive_polls
        self._on_poll = on_poll

    def is_alive(self):
        if self._on_poll:
            self._on_poll()
        if self._left is None:
            return True
        if self._left <= 0:
            return False
        self._left -= 1
        return True


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        self.stop = threading.Event()
        self.created = []

    def _factory(self, alive_polls=0, stop_after=2):
        def start():
            listener = FakeListener(alive_polls)
            self.created.append(listener)
            if len(self.created) >= stop_after:
                self.stop.set()
            return listener

        return start

    def test_recreates_the_listener_after_it_dies(self):
        """A dead listener is the observable symptom of a tap that never came
        up. The supervisor must build a new one rather than leave the app deaf."""
        _supervise(
            start_listener=self._factory(alive_polls=1, stop_after=2),
            is_trusted=lambda: True,
            stop=self.stop,
            poll_seconds=0,
        )
        self.assertEqual(len(self.created), 2)

    def test_does_not_churn_while_the_listener_is_alive(self):
        """A healthy listener must be left alone — no tearing down and
        rebuilding a working event tap every poll."""
        polls = {"n": 0}

        def on_poll():
            polls["n"] += 1
            if polls["n"] >= 5:
                self.stop.set()

        def start():
            listener = FakeListener(alive_polls=None, on_poll=on_poll)
            self.created.append(listener)
            return listener

        _supervise(
            start_listener=start,
            is_trusted=lambda: True,
            stop=self.stop,
            poll_seconds=0,
        )
        self.assertEqual(len(self.created), 1)
        self.assertGreaterEqual(polls["n"], 5, "the listener was actually polled")

    def test_waits_for_accessibility_before_building_a_listener(self):
        """Creating a tap without Accessibility is guaranteed to fail, so the
        supervisor holds off until the user has granted it — which is exactly
        what happens while the onboarding dialog is on screen."""
        trust = {"granted": False}
        polls = {"n": 0}

        def trusted():
            polls["n"] += 1
            if polls["n"] == 3:
                trust["granted"] = True
            return trust["granted"]

        _supervise(
            start_listener=self._factory(alive_polls=99, stop_after=1),
            is_trusted=trusted,
            stop=self.stop,
            poll_seconds=0,
        )
        self.assertEqual(len(self.created), 1, "listener built once, after the grant")
        self.assertEqual(polls["n"], 3, "no listener attempted while untrusted")

    def test_stop_event_ends_the_loop_without_starting_anything(self):
        self.stop.set()
        _supervise(
            start_listener=self._factory(),
            is_trusted=lambda: True,
            stop=self.stop,
            poll_seconds=0,
        )
        self.assertEqual(self.created, [])

    def test_survives_a_listener_that_raises_on_start(self):
        """A raising factory must not kill the supervisor thread — that would
        reintroduce exactly the silent-death failure this fixes."""
        calls = {"n": 0}

        def start():
            calls["n"] += 1
            if calls["n"] >= 3:
                self.stop.set()
            raise RuntimeError("tap creation blew up")

        _supervise(
            start_listener=start,
            is_trusted=lambda: True,
            stop=self.stop,
            poll_seconds=0,
        )
        self.assertEqual(calls["n"], 3, "kept retrying after the exception")


if __name__ == "__main__":
    unittest.main(verbosity=2)
