import json
import re
from pathlib import Path

_EN2HE = None
_HE2EN = None
_EN_SET = None
_HE_SET = None

import sys as _sys
import platform as _platform
if getattr(_sys, "frozen", False):
    if _platform.system() == "Darwin":
        # Mac app bundle: exe is Contents/MacOS/, datas land in Contents/Resources/
        _MAP_PATH = Path(_sys.executable).parent.parent / "Resources" / "flipper_daemon" / "layouts" / "en_he_map.json"
    else:
        # Windows single-file exe: PyInstaller extracts datas to sys._MEIPASS
        _MAP_PATH = Path(getattr(_sys, "_MEIPASS", Path(_sys.executable).parent)) / "layouts" / "en_he_map.json"
else:
    _MAP_PATH = Path(__file__).parent / "layouts" / "en_he_map.json"

_NORMALIZE = {
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u05f3": "\u05f3", "\u05f4": "\u05f4",
}

def _is_hebrew(ch):
    return "\u0590" <= ch <= "\u05FF"

def _load():
    global _EN2HE, _HE2EN, _EN_SET, _HE_SET
    if _EN2HE is not None:
        return

    pairs = json.loads(_MAP_PATH.read_text(encoding="utf-8"))

    _EN2HE = {}
    _HE2EN = {}
    _EN_SET = set()
    _HE_SET = set()

    for row in pairs:
        en = str(row.get("en", "")).lower()
        he = str(row.get("he", ""))
        if not en:
            continue
        _EN2HE[en] = he
        if "a" <= en <= "z":
            _EN_SET.add(en)
        he_low = he.lower()
        if _is_hebrew(he_low):
            _HE_SET.add(he_low)
        _HE2EN[he_low] = en

    _HE2EN["'"] = "w"
    _HE2EN["\u05f3"] = "w"
    _HE2EN["\u05f4"] = '"'
    _HE2EN["\u2018"] = "w"
    _HE2EN["\u201c"] = '"'
    _HE2EN["\u201d"] = '"'


def detect_layout(text: str) -> str:
    _load()
    he_score = en_score = 0
    for raw in text:
        ch = _NORMALIZE.get(raw, raw).lower()
        if _is_hebrew(ch):
            he_score += 1
        elif "a" <= ch <= "z":
            en_score += 1
        elif ch in _HE_SET:
            he_score += 1
        elif ch in _EN_SET:
            en_score += 1
    return "he_il" if he_score > en_score else "en_us"


def flip_text(text: str) -> str:
    _load()
    if not text:
        return text
    return _map_chars(text, forward=detect_layout(text) == "en_us")


def _map_chars(text: str, forward: bool) -> str:
    _load()
    mapping = _EN2HE if forward else _HE2EN
    out = []
    for raw in text:
        norm = _NORMALIZE.get(raw, raw)
        low = norm.lower()
        mapped = mapping.get(low)
        if mapped is None:
            out.append(raw)
            continue
        if not forward and raw.isupper() and len(mapped) == 1:
            out.append(mapped.upper())
        else:
            out.append(mapped)
    return "".join(out)


# ---------------------------------------------------------------------------
# Mixed lines: part Hebrew, part English
# ---------------------------------------------------------------------------
#
# flip_text decides one direction for the whole text by letter majority. On a
# line that is partly right and partly mistyped that goes wrong two ways:
#   - the mistyped part is the shorter one → the *correct* part gets flipped
#     (e.g. a few words typed with Caps Lock on after a Hebrew sentence);
#   - the mistyped part is the longer one → the correct part's letters survive
#     (they aren't in the map) but its punctuation doesn't: a Hebrew comma
#     becomes ת.
# So a mixed line is split into Hebrew and English runs, each punctuation mark
# going with the word it is attached to, and only runs that read better
# flipped are flipped.

def _letter_script(ch):
    if _is_hebrew(ch):
        return "he"
    if "a" <= ch.lower() <= "z":
        return "en"
    return None


def is_mixed(text: str) -> bool:
    scripts = {_letter_script(ch) for ch in text}
    return "he" in scripts and "en" in scripts


def _runs(text):
    """[(script, segment)] covering `text`. Punctuation takes the script of the
    nearest letter in its own word (before it, else after it); a word with no
    letters takes the previous word's; whitespace goes with what precedes it."""
    n = len(text)
    script = [_letter_script(ch) for ch in text]

    def in_word(i, step):
        j = i + step
        while 0 <= j < n and not text[j].isspace():
            if script[j]:
                return script[j]
            j += step
        return None

    resolved = list(script)
    for i, ch in enumerate(text):
        if resolved[i] or ch.isspace():
            continue
        resolved[i] = in_word(i, -1) or in_word(i, 1)
    # Letterless words and whitespace: carry the last script forward, and
    # anything before the first letter takes the first script found.
    last = next((s for s in resolved if s), "en")
    for i in range(n):
        if resolved[i]:
            last = resolved[i]
        else:
            resolved[i] = last
    runs = []
    for ch, s in zip(text, resolved):
        if runs and runs[-1][0] == s:
            runs[-1][1].append(ch)
        else:
            runs.append((s, [ch]))
    return [(s, "".join(chars)) for s, chars in runs]


def _bare(word):
    """The word without punctuation at its edges, lower-cased — what a
    dictionary lookup needs (a Hebrew word is often followed by a comma)."""
    i, j = 0, len(word)
    while i < j and not _letter_script(word[i]):
        i += 1
    while j > i and not _letter_script(word[j - 1]):
        j -= 1
    return word[i:j].lower()


def flip_mixed(text: str, detector):
    """
    Flip only the mistyped words of a part-Hebrew, part-English line.

    Each word is judged by the dictionary first: a real word that is
    gibberish flipped stays, gibberish that flips into a real word is flipped.
    Words that are both (נשמע typed on English is "bang") or neither follow
    the clear words in their own run; a run with none falls back to the
    letter models (langdetect). Judging those words alone flipped correct
    Hebrew whenever its mistyped twin happened to be English.

    Returns (new_text, source, target), or None if the models aren't loaded,
    in which case the caller falls back to flip_text. `target` is the layout
    the end of the line is in after the flip — the user goes on typing there.
    """
    if not detector.models:
        return None
    dicts = detector.dictionaries
    runs = _runs(text)
    words, flipped, flip = [], [], []
    for r, (s, seg) in enumerate(runs):
        dst = "he" if s == "en" else "en"
        start = len(words)
        undecided = []
        for w in re.findall(r"\S+\s*|\s+", seg):
            f = _map_chars(w, forward=(s == "en"))
            words.append((r, s, w))
            flipped.append(f)
            own = _bare(w) in dicts.get(s, ())
            other = _bare(f) in dicts.get(dst, ())
            if not w.strip():
                flip.append(False)
            elif own != other:
                flip.append(other)
            else:
                flip.append(None)
                undecided.append(len(words) - 1)
        decided = [flip[i] for i in range(start, len(words)) if flip[i] is not None and words[i][2].strip()]
        for i in undecided:
            if decided:
                flip[i] = sum(decided) * 2 > len(decided)
            else:
                w, f = words[i][2].strip(), flipped[i].strip()
                flip[i] = detector.score(f, dst) > detector.score(w, s)
    if not any(flip):
        # The user pressed the hotkey, so something is wrong somewhere: flip
        # the word that comes closest to reading better flipped.
        def gain(i):
            r, s, w = words[i]
            if not w.strip():
                return float("-inf")
            dst = "he" if s == "en" else "en"
            return detector.score(flipped[i].strip(), dst) - detector.score(w.strip(), s)
        flip[max(range(len(words)), key=gain)] = True
    out = "".join(flipped[i] if flip[i] else w for i, (_, _, w) in enumerate(words))
    if out == text:
        return None
    src = next(words[i][1] for i in reversed(range(len(words))) if flip[i])
    last = max(i for i in range(len(words)) if words[i][2].strip())
    last_script = words[last][1]
    target = ("he" if last_script == "en" else "en") if flip[last] else last_script
    return out, src, target
