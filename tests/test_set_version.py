"""
The release version setter.

    python3 tests/test_set_version.py

Three files carry the version and all three must move together: version.py is
the source of truth the app reports and the updater compares, the Mac spec's
CFBundleShortVersionString is what macOS shows, and the Inno Setup AppVersion
is what Windows records. Key Past Bug #6 was release_mac.sh bumping only one of
them.

The local release scripts each do this with sed — GNU sed on one platform, BSD
sed on the other, PowerShell regex on a third (Key Past Bug #4). CI needs one
implementation that works everywhere and fails loudly when a pattern stops
matching, rather than quietly leaving a file behind.
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.set_version import set_version  # noqa: E402


class SetVersionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "flipper_daemon").mkdir()
        (self.root / "flipper_daemon" / "version.py").write_text(
            'VERSION = "0.1.111"\n', encoding="utf-8"
        )
        (self.root / "language_flipper.spec").write_text(
            'app = BUNDLE(\n    info_plist={\n'
            '        "CFBundleShortVersionString": "0.1.111",\n'
            '        "LSUIElement": True,\n    },\n)\n',
            encoding="utf-8",
        )
        (self.root / "language_flipper_setup.iss").write_text(
            "[Setup]\nAppName=Language Flipper\nAppVersion=0.1.105\n"
            "OutputDir=dist\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def read(self, name):
        return (self.root / name).read_text(encoding="utf-8")

    def test_moves_all_three_files_together(self):
        set_version("0.1.112", root=self.root)

        self.assertIn('VERSION = "0.1.112"', self.read("flipper_daemon/version.py"))
        self.assertIn(
            '"CFBundleShortVersionString": "0.1.112"',
            self.read("language_flipper.spec"),
        )
        self.assertIn("AppVersion=0.1.112", self.read("language_flipper_setup.iss"))

    def test_touches_nothing_else_in_the_files(self):
        set_version("0.1.112", root=self.root)

        self.assertIn('"LSUIElement": True', self.read("language_flipper.spec"))
        iss = self.read("language_flipper_setup.iss")
        self.assertIn("AppName=Language Flipper", iss)
        self.assertIn("OutputDir=dist", iss)

    def test_reports_which_files_changed(self):
        changed = set_version("0.1.112", root=self.root)

        self.assertEqual(len(changed), 3)

    def test_is_idempotent(self):
        set_version("0.1.112", root=self.root)
        changed = set_version("0.1.112", root=self.root)

        self.assertEqual(changed, [], "rewrote files that were already correct")

    def test_rejects_a_version_that_is_not_x_y_z(self):
        for bad in ("v0.1.112", "0.1", "0.1.112-mac", "", "latest"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    set_version(bad, root=self.root)

    def test_raises_when_a_file_stops_matching(self):
        """A renamed field must fail the release, not silently ship a build
        carrying the previous version."""
        (self.root / "language_flipper_setup.iss").write_text(
            "[Setup]\nAppName=Language Flipper\n", encoding="utf-8"
        )

        with self.assertRaises(LookupError):
            set_version("0.1.112", root=self.root)

    def test_raises_when_a_file_is_missing(self):
        (self.root / "flipper_daemon" / "version.py").unlink()

        with self.assertRaises(FileNotFoundError):
            set_version("0.1.112", root=self.root)

    def test_preserves_crlf_line_endings(self):
        """The .iss is edited on Windows by release_windows.bat; rewriting it
        with LF would show up as a whole-file diff."""
        path = self.root / "language_flipper_setup.iss"
        path.write_bytes(b"[Setup]\r\nAppVersion=0.1.105\r\nOutputDir=dist\r\n")

        set_version("0.1.112", root=self.root)

        self.assertEqual(
            path.read_bytes(),
            b"[Setup]\r\nAppVersion=0.1.112\r\nOutputDir=dist\r\n",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
