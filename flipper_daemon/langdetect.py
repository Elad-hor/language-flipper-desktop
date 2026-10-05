"""
Pick the layout the user meant, given text typed on the wrong one.

Where the text was typed is read off its script (Hebrew letters → Hebrew
layout, and so on). Where it was meant to go is the open question once three
layouts are installed: every other installed layout is converted to and
scored, and the most language-like result wins.

Scoring is a letter-trigram model per language plus a bonus for known words.
Both are built by tools/layout_detect/build_data.py into
layouts/lang_models.json.gz; tools/layout_detect/evaluate.py measures them.
"""

import gzip
import json
import math
import sys
import platform
from collections import Counter
from pathlib import Path

from .keymaps import convert, source_layout

BOS, EOS = "^", "$"
_L3, _L2, _L1 = 0.6, 0.3, 0.1  # interpolation weights: trigram, bigram, unigram
DICT_BONUS = 2.0  # added (in bits/char) when every word is a known word

if getattr(sys, "frozen", False):
    if platform.system() == "Darwin":
        _DATA_PATH = Path(sys.executable).parent.parent / "Resources" / "flipper_daemon" / "layouts" / "lang_models.json.gz"
    else:
        _DATA_PATH = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "layouts" / "lang_models.json.gz"
else:
    _DATA_PATH = Path(__file__).parent / "layouts" / "lang_models.json.gz"


class TrigramModel:
    """
    Each word is padded with boundary marks (^^word$) so the model learns how
    words start and end — which matters for Hebrew final letters and Russian
    endings. score() is the mean log2-probability per character, so strings of
    different lengths and languages compare. Higher = more plausible.
    """

    def __init__(self, alphabet, trigrams=None):
        self.alphabet = set(alphabet)
        # Anything foreign (punctuation from the wrong layout) gets only the
        # floor probability.
        self.vocab = len(self.alphabet) + 1
        self.c3 = Counter()
        if trigrams:
            self.c3.update(trigrams)
        self._derive()

    def train(self, words_with_counts):
        """Counts are weighted by log(frequency): a middle ground between every
        word counting the same (rare words dominate) and raw frequency (a few
        function words dominate)."""
        for word, count in words_with_counts:
            w = math.log(count + 1)
            padded = BOS + BOS + word + EOS
            for i in range(2, len(padded)):
                self.c3[padded[i - 2:i + 1]] += w
        self._derive()
        return self

    def _derive(self):
        self.c2ctx, self.c2, self.c1ctx, self.c1 = Counter(), Counter(), Counter(), Counter()
        for abc, w in self.c3.items():
            self.c2ctx[abc[:2]] += w
            self.c2[abc[1:]] += w
            self.c1ctx[abc[1]] += w
            self.c1[abc[2]] += w
        self.total = sum(self.c1.values())

    def _p(self, a, b, c):
        ctx2, ctx1 = self.c2ctx.get(a + b), self.c1ctx.get(b)
        p3 = self.c3.get(a + b + c, 0) / ctx2 if ctx2 else 0.0
        p2 = self.c2.get(b + c, 0) / ctx1 if ctx1 else 0.0
        p1 = self.c1.get(c, 0) / self.total if self.total else 0.0
        return _L3 * p3 + _L2 * p2 + _L1 * p1 + 1e-4 / self.vocab

    def score(self, text):
        total, n = 0.0, 0
        for word in text.lower().split():
            padded = BOS + BOS + word + EOS
            for i in range(2, len(padded)):
                total += math.log2(self._p(padded[i - 2], padded[i - 1], padded[i]))
                n += 1
        return total / n if n else float("-inf")


class Detector:
    def __init__(self, models, dictionaries=None, dict_bonus=DICT_BONUS):
        self.models = models
        self.dictionaries = dictionaries or {}
        self.dict_bonus = dict_bonus

    def _score(self, text, lang):
        model = self.models.get(lang)
        s = model.score(text) if model else float("-inf")
        words = text.lower().split()
        known = self.dictionaries.get(lang)
        if known and words:
            s += self.dict_bonus * sum(w in known for w in words) / len(words)
        return s

    def rank(self, text, installed):
        """Installed layouts other than the one `text` was typed on, best
        guess first, as [(lang, converted_text, score)]."""
        src = source_layout(text)
        out = []
        for lang in installed:
            if lang == src:
                continue
            conv = convert(text, src, lang)
            out.append((lang, conv, self._score(conv, lang)))
        # Stable sort: with no models every score ties, and `installed`'s order
        # becomes the guess order.
        out.sort(key=lambda r: r[2], reverse=True)
        return out


_detector = None


def load(path=None) -> Detector:
    """The shipped detector, loaded once. If the data file is missing or bad,
    falls back to a model-less detector (guesses in installed order) rather
    than breaking the flip."""
    global _detector
    if _detector is not None and path is None:
        return _detector
    from .keymaps import ALPHABET
    try:
        with gzip.open(path or _DATA_PATH, "rt", encoding="utf-8") as f:
            data = json.load(f)
        models = {lang: TrigramModel(ALPHABET[lang], d["trigrams"]) for lang, d in data["langs"].items()}
        dicts = {lang: set(d["words"].split()) for lang, d in data["langs"].items()}
        det = Detector(models, dicts)
    except Exception as e:
        print(f"[langdetect] could not load {path or _DATA_PATH}: {e}")
        det = Detector({})
    if path is None:
        _detector = det
    return det
