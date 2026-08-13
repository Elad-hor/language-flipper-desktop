"""
macOS onboarding: the permission re-check path.

    python3 tests/test_onboarding_recheck.py

Two failures lived here. The wizard waited 60s for the user to grant
Accessibility and then carried on regardless, so _finish() announced
"Permissions granted!" whether or not anything had been granted. And the
re-check path never cleared the dead TCC row left behind by an in-place
update — for an unsigned app the old row keeps the app's name and its tick but
no longer matches the new binary, so ticking it in System Settings changes
nothing and the grant silently fails to take.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flipper_daemon import onboarding  # noqa: E402


class OnboardingTestBase(unittest.TestCase):
    def setUp(self):
        self.dialogs = []
        self.panes = []
        self.commands = []
        self.data = {}
        self.trusted = False

        self._orig = {
            name: getattr(onboarding, name)
            for name in ("_osascript", "_open_privacy_pane", "_ax_trusted",
                         "_run_command", "storage", "time")
        }

        onboarding._osascript = lambda script: self.dialogs.append(script) or ""
        onboarding._open_privacy_pane = lambda pane: self.panes.append(pane)
        onboarding._ax_trusted = lambda prompt=False: self.trusted
        onboarding._run_command = lambda argv: self.commands.append(argv)

        class FakeStorage:
            _load = staticmethod(lambda: dict(self.data))
            _save = staticmethod(lambda d: self.data.update(d))

        class FakeTime:
            sleep = staticmethod(lambda _s: None)

        onboarding.storage = FakeStorage
        onboarding.time = FakeTime

    def tearDown(self):
        for name, value in self._orig.items():
            setattr(onboarding, name, value)

    def said(self, needle):
        return any(needle.lower() in d.lower() for d in self.dialogs)


class FinishTest(OnboardingTestBase):
    def test_does_not_claim_success_when_the_grant_never_happened(self):
        self.trusted = False
        self.data["onboarding_done"] = True

        onboarding._finish()

        self.assertFalse(
            self.said("ready to use") or self.said("all set"),
            "claimed the app was ready while it still had no Accessibility",
        )

    def test_does_not_mark_onboarding_done_without_the_grant(self):
        self.trusted = False

        onboarding._finish()

        self.assertNotIn(
            "onboarding_done", self.data,
            "a setup that did not grant anything is not a completed setup",
        )

    def test_confirms_success_once_trusted(self):
        self.trusted = True

        onboarding._finish()

        self.assertTrue(self.data.get("onboarding_done"))
        self.assertTrue(self.said("ready") or self.said("all set"))

    def test_first_run_no_longer_forces_a_quit(self):
        """The supervisor picks the grant up live (see hotkey._supervise), so
        the app must stop killing itself and telling the user to reopen it."""
        self.trusted = True

        onboarding._finish()  # would take the process down if it still exited

        self.assertFalse(self.said("quit now"))


class RecheckTest(OnboardingTestBase):
    def test_clears_the_stale_tcc_row_before_asking_again(self):
        self.trusted = False

        onboarding._check_accessibility()

        reset = [c for c in self.commands if c[:2] == ["tccutil", "reset"]]
        self.assertTrue(reset, "stale TCC row never cleared — re-granting cannot work")
        self.assertIn(
            ["tccutil", "reset", "Accessibility", onboarding._BUNDLE_ID], reset
        )

    def test_leaves_a_working_grant_alone(self):
        self.trusted = True

        onboarding._check_accessibility()

        self.assertEqual(
            [c for c in self.commands if c[:2] == ["tccutil", "reset"]], [],
            "reset a grant that was working",
        )

    def test_opens_the_accessibility_pane_when_untrusted(self):
        self.trusted = False

        onboarding._check_accessibility()

        self.assertIn("Accessibility", self.panes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
