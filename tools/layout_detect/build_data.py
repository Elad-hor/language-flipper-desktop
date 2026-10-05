"""
Build flipper_daemon/layouts/lang_models.json.gz — the letter-trigram models
and word lists the app uses to pick a layout when three are installed.

    python3 -m tools.layout_detect.build_data

Trained on the full word lists (evaluate.py holds 10% out to measure; the
shipped file uses everything). Re-run after changing the model or the data.

Source: hermitdave/FrequencyWords, OpenSubtitles 2018 — CC BY-SA 4.0.
"""

import gzip
import json
from pathlib import Path

from flipper_daemon.keymaps import ALPHABET
from flipper_daemon.langdetect import TrigramModel

from .evaluate import DICT_SIZE, LANGS, load_words

OUT = Path(__file__).resolve().parents[2] / "flipper_daemon" / "layouts" / "lang_models.json.gz"


def main():
    data = {
        "source": "hermitdave/FrequencyWords, OpenSubtitles 2018 (CC BY-SA 4.0)",
        "langs": {},
    }
    for lang in LANGS:
        words = load_words(lang)
        model = TrigramModel(ALPHABET[lang]).train(words)
        data["langs"][lang] = {
            "trigrams": {k: round(v, 1) for k, v in sorted(model.c3.items())},
            "words": " ".join(w for w, _ in words[:DICT_SIZE]),
        }
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # mtime=0 keeps the file byte-identical across rebuilds of the same data.
    OUT.write_bytes(gzip.compress(raw, mtime=0))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
