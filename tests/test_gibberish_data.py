"""
The site's gibberish table must agree with the app's own character map.

site/src/lib/gibberish.ts lists Hebrew words next to what they look like typed
on an English layout, and those strings are the page's whole SEO argument — if
they are wrong, the page claims something the app does not do and targets
search terms nobody types. Four of the twenty-four were wrong when first typed
by hand, which is why this exists.

Runs anywhere: stdlib only, no deps.

    python3 tests/test_gibberish_data.py
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flipper_daemon.flipper import flip_text  # noqa: E402

DATA = ROOT / "site" / "src" / "lib" / "gibberish.ts"
_PAIR_RE = re.compile(r"\{ he: '([^']+)', gib: '([^']*)' \}")


def parse_pairs():
    return _PAIR_RE.findall(DATA.read_text(encoding="utf-8"))


class GibberishData(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(DATA.exists(), f"missing {DATA}")

    def test_has_pairs(self):
        self.assertGreaterEqual(len(parse_pairs()), 20)

    def test_every_pair_matches_the_map(self):
        wrong = [
            (he, gib, flip_text(he))
            for he, gib in parse_pairs()
            if flip_text(he) != gib
        ]
        self.assertEqual(
            wrong, [],
            "gibberish.ts disagrees with en_he_map.json — regenerate it "
            "rather than hand-editing:\n" +
            "\n".join(f"  {he}: file={gib!r} map={real!r}" for he, gib, real in wrong),
        )

    def test_the_two_strings_search_console_actually_records(self):
        """dhcrha and akuo are real recorded queries; the page is built on them."""
        self.assertEqual(flip_text("גיבריש"), "dhcrha")
        self.assertEqual(flip_text("שלום"), "akuo")

    def test_round_trip(self):
        """Flipping back must return the original, or the table is misleading."""
        for he, gib in parse_pairs():
            self.assertEqual(flip_text(gib), he, f"{gib!r} does not flip back to {he!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
