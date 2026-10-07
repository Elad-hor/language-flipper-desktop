"""
Three-layout flipping (Hebrew + Russian + English) and the press-again cycle.

    python3 tests/test_flip_engine.py

Stdlib only; uses the shipped layouts/lang_models.json.gz.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flipper_daemon import langdetect  # noqa: E402
from flipper_daemon.flip_engine import CYCLE_SECONDS, FlipEngine  # noqa: E402
from flipper_daemon.flipper import flip_text  # noqa: E402
from flipper_daemon.installed_layouts import (  # noqa: E402
    langs_from_mac_source_ids, langs_from_windows_hkls)
from flipper_daemon.keymaps import convert  # noqa: E402

ALL = frozenset({"en", "he", "ru"})
TWO = frozenset({"en", "he"})


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def engine(installed=ALL):
    clock = Clock()
    return FlipEngine(lambda: installed, clock=clock), clock


def press(eng, text, caps=False):
    """One hotkey press that the app manages to write."""
    r = eng.flip(text, caps)
    if r:
        eng.commit()
    return r


class ConvertTest(unittest.TestCase):
    def test_round_trips(self):
        self.assertEqual(convert("ghbdtn", "en", "ru"), "привет")
        self.assertEqual(convert("привет", "ru", "en"), "ghbdtn")
        self.assertEqual(convert("שלום", "he", "ru"), "флгщ")
        self.assertEqual(convert("флгщ", "ru", "he"), "שלום")

    def test_keeps_capitals_where_the_target_has_them(self):
        self.assertEqual(convert("Ghbdtn", "en", "ru"), "Привет")


class ShippedDataTest(unittest.TestCase):
    def test_data_file_loads_with_all_three_languages(self):
        det = langdetect.load()
        self.assertEqual(set(det.models), {"en", "he", "ru"})
        self.assertGreater(len(det.dictionaries["ru"]), 10000)


class TwoLayoutsUnchangedTest(unittest.TestCase):
    """Users without Russian must get exactly what flip_text gave them."""

    def test_same_output_as_before(self):
        eng, _ = engine(TWO)
        for text in ("akuo", "שלום", "t,h ckc'", "Hello world", "/'", "ghbdtn"):
            r = eng.flip(text)
            expected = flip_text(text)
            if expected == text:
                self.assertIsNone(r)
            else:
                self.assertEqual(r.text, expected, text)

    def test_targets(self):
        eng, _ = engine(TWO)
        self.assertEqual(eng.flip("akuo").target, "he")
        self.assertEqual(eng.flip("שלום").target, "en")


class MixedLineTest(unittest.TestCase):
    """A line that is partly right and partly mistyped. flip_text decides one
    direction for the whole line by letter majority, so it either flipped the
    correct part (when it was the longer one) or dragged the correct part's
    punctuation along (`,` → `ת`)."""

    def setUp(self):
        self.eng, _ = engine(TWO)

    def test_short_caps_lock_part_after_hebrew(self):
        # Hebrew layout + Caps Lock types English capitals.
        r = self.eng.flip("אני בדרך הביתה AKUO", caps_lock=True)
        self.assertEqual(r.text, "אני בדרך הביתה שלום")
        self.assertEqual(r.target, "he")

    def test_hebrew_comma_survives(self):
        gib = flip_text("אני בדרך הביתה")
        r = self.eng.flip("שלום, " + gib)
        self.assertEqual(r.text, "שלום, אני בדרך הביתה")

    def test_mistyped_part_first(self):
        r = self.eng.flip(flip_text("שלום") + " מה נשמע")
        self.assertEqual(r.text, "שלום מה נשמע")

    def test_mistyped_hebrew_inside_english(self):
        r = self.eng.flip("hello " + flip_text("hello"))
        self.assertEqual(r.text, "hello hello")
        self.assertEqual(r.target, "en")

    def test_real_english_word_in_hebrew_is_kept(self):
        r = self.eng.flip("פתחתי את Chrome " + flip_text("שלום"))
        self.assertEqual(r.text, "פתחתי את Chrome שלום")


class ThreeLayoutsTest(unittest.TestCase):
    def test_picks_russian(self):
        eng, _ = engine()
        r = press(eng, "ghbdtn rfr ltkf")
        self.assertEqual((r.text, r.source, r.target), ("привет как дела", "en", "ru"))

    def test_picks_hebrew(self):
        eng, _ = engine()
        r = press(eng, convert("שלום מה נשמע", "he", "en"))
        self.assertEqual((r.text, r.target), ("שלום מה נשמע", "he"))

    def test_hebrew_typed_on_russian(self):
        eng, _ = engine()
        r = press(eng, convert("שלום מה נשמע", "he", "ru"))
        self.assertEqual((r.text, r.source, r.target), ("שלום מה נשמע", "ru", "he"))

    def test_english_typed_on_russian(self):
        eng, _ = engine()
        self.assertEqual(press(eng, "руддщ цщкдв").text, "hello world")

    def test_en_he_output_still_comes_from_flip_text(self):
        # keymaps' Hebrew ' key differs from en_he_map.json; flips between
        # English and Hebrew must not change because Russian is installed.
        eng, _ = engine()
        r = press(eng, "akuo")
        self.assertEqual(r.text, flip_text("akuo"))

    def test_caps_lock_capitals_come_out_lower_case(self):
        eng, _ = engine()
        self.assertEqual(press(eng, "GHBDTN", caps=True).text, "привет")

    def test_trailing_space_is_kept(self):
        eng, _ = engine()
        self.assertEqual(press(eng, "ghbdtn ").text, "привет ")


class CycleTest(unittest.TestCase):
    def test_pressing_again_cycles_and_comes_back(self):
        eng, _ = engine()
        first = press(eng, "ghbdtn")
        self.assertEqual(first.text, "привет")
        second = press(eng, first.text)
        self.assertTrue(second.is_cycle)
        self.assertEqual((second.text, second.target), (convert("ghbdtn", "en", "he"), "he"))
        third = press(eng, second.text)
        self.assertEqual((third.text, third.target), ("ghbdtn", "en"))
        fourth = press(eng, third.text)
        self.assertEqual(fourth.text, "привет")

    def test_cycles_the_flipped_word_at_the_end_of_a_line(self):
        # First press flipped a selection; the second reads the whole line.
        eng, _ = engine()
        press(eng, "ghbdtn")
        r = press(eng, "שלום привет")
        self.assertEqual(r.text, "שלום " + convert("ghbdtn", "en", "he"))

    def test_no_cycle_once_the_user_typed_on(self):
        eng, _ = engine()
        press(eng, "ghbdtn")
        r = press(eng, "привет rfr ltkf")
        self.assertFalse(r.is_cycle)

    def test_no_cycle_after_the_window(self):
        eng, clock = engine()
        press(eng, "ghbdtn")
        clock.t += CYCLE_SECONDS + 1
        r = press(eng, "привет")
        self.assertFalse(r.is_cycle)
        self.assertEqual(r.source, "ru")

    def test_a_failed_write_does_not_advance_the_cycle(self):
        # macOS calls flip() twice for one press when Accessibility fails and
        # the clipboard path retries; only the written result may count.
        eng, _ = engine()
        press(eng, "ghbdtn")
        a = eng.flip("привет")
        b = eng.flip("привет")
        self.assertEqual(a, b)
        eng.commit()
        self.assertEqual(press(eng, b.text).text, "ghbdtn")


class InstalledLayoutsTest(unittest.TestCase):
    def test_windows(self):
        # HKLs: US English, Hebrew, Russian; low word is the LANGID.
        self.assertEqual(langs_from_windows_hkls([0x04090409, 0x040D040D, 0x04190419]), ALL)
        self.assertEqual(langs_from_windows_hkls([0x08090809, 0x040D040D]), TWO)  # UK English

    def test_mac(self):
        ids = ["com.apple.keylayout.ABC", "com.apple.keylayout.Hebrew-PC",
               "com.apple.keylayout.RussianWin", "com.apple.inputmethod.Kotoeri"]
        self.assertEqual(langs_from_mac_source_ids(ids), ALL)


if __name__ == "__main__":
    unittest.main()
