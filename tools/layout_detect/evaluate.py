"""
How often does the detector pick the layout the user meant, with Hebrew,
Russian and English all installed?

    python3 -m tools.layout_detect.evaluate

Simulates the mistake directly: take a real word in language L, "type" it on
layout S ≠ L (its key presses, read through S), hand the gibberish to the
detector with all three layouts installed, and check it chooses L.

Word data: hermitdave/FrequencyWords (OpenSubtitles 2018, 50k words per
language), downloaded once into ~/.cache/lf-layout-detect.

Test sets, per language:
  common  — words drawn by real frequency, i.e. what people actually type.
            These are in the training data, as they would be in a shipped
            model.
  unseen  — 10% of the vocabulary held out of training *and* the dictionary
            entirely (rare words, names, typos). The pessimistic case.
  phrases — 2-4 common words in a row.
  hand    — short real sentences, written by hand.
"""

import hashlib
import random
import urllib.request
from collections import defaultdict
from pathlib import Path

from .detect import Detector
from .layouts import ALPHABET, convert, source_layout
from .model import TrigramModel

LANGS = ("en", "he", "ru")
CACHE = Path.home() / ".cache" / "lf-layout-detect"
URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/{0}/{0}_50k.txt"
DICT_SIZE = 20000

HAND = {
    "en": ["hello how are you", "i am on my way", "thanks a lot", "where are you",
           "what are you doing tonight", "call me tomorrow", "okay", "yes", "no", "mom"],
    "he": ["שלום מה נשמע", "אני בדרך", "תודה רבה", "איפה אתה", "מה אתה עושה הערב",
           "תתקשר אליי מחר", "בסדר", "כן", "לא", "אמא"],
    "ru": ["привет как дела", "я сейчас приду", "спасибо большое", "где ты",
           "что делаешь сегодня вечером", "позвони мне завтра", "хорошо", "да", "нет", "мама"],
}


def load_words(lang):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{lang}_50k.txt"
    if not path.exists():
        urllib.request.urlretrieve(URL.format(lang), path)
    letters = ALPHABET[lang]
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        word, count = parts[0].lower(), int(parts[1])
        if word and set(word) <= letters:
            out.append((word, count))
    return out


def held_out(word):
    return hashlib.md5(word.encode()).digest()[0] < 26  # ~10%


def bucket(text):
    if " " in text:
        return "phrase"
    n = len(text)
    return {1: "1", 2: "2", 3: "3", 4: "4"}.get(n, "5-6" if n <= 6 else "7+")


def main():
    rng = random.Random(1452)
    models, dicts, tests = {}, {}, defaultdict(list)

    for lang in LANGS:
        words = load_words(lang)
        train = [(w, c) for w, c in words if not held_out(w)]
        unseen = [w for w, _ in words if held_out(w)]
        models[lang] = TrigramModel(ALPHABET[lang]).train(train)
        dicts[lang] = {w for w, _ in train[:DICT_SIZE]}

        common = rng.choices([w for w, _ in train], weights=[c for _, c in train], k=3000)
        tests["common"] += [(lang, w) for w in common]
        tests["unseen"] += [(lang, w) for w in rng.sample(unseen, 1500)]
        tests["phrases"] += [(lang, " ".join(rng.sample(common, rng.randint(2, 4))))
                             for _ in range(500)]
        tests["hand"] += [(lang, s) for s in HAND[lang]]

    detectors = {
        "letters only": Detector(models),
        "letters + dictionary": Detector(models, dicts),
    }

    installed = LANGS
    for name, det in detectors.items():
        print(f"\n=== {name} ===")
        for set_name, cases in tests.items():
            by_bucket = defaultdict(lambda: [0, 0])
            by_pair = defaultdict(lambda: [0, 0])
            misses = []
            for meant, text in cases:
                for typed_on in LANGS:
                    if typed_on == meant:
                        continue
                    gib = convert(text, meant, typed_on)
                    ranked = det.rank(gib, installed)
                    ok = source_layout(gib) == typed_on and ranked[0][0] == meant
                    for tally in (by_bucket[bucket(text)], by_pair[f"{meant} typed on {typed_on}"]):
                        tally[0] += ok
                        tally[1] += 1
                    if not ok and len(misses) < 8:
                        misses.append(f"{text!r} on {typed_on} = {gib!r} → {ranked[0][1]!r}")
            right = sum(v[0] for v in by_bucket.values())
            total = sum(v[1] for v in by_bucket.values())
            print(f"\n  {set_name}: {100 * right / total:.1f}% right on the first press ({total} cases)")
            order = ["1", "2", "3", "4", "5-6", "7+", "phrase"]
            print("    by length:  " + "  ".join(
                f"{b}: {100 * by_bucket[b][0] / by_bucket[b][1]:.0f}% (n={by_bucket[b][1]})"
                for b in order if by_bucket[b][1]))
            print("    by mistake: " + "  ".join(
                f"{p}: {100 * v[0] / v[1]:.0f}%" for p, v in sorted(by_pair.items())))
            if set_name in ("hand", "common") and misses:
                print("    e.g. misses: " + " | ".join(misses[:5]))


if __name__ == "__main__":
    main()
