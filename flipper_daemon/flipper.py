import json
import re
from pathlib import Path

_EN2HE = None
_HE2EN = None
_EN_SET = None
_HE_SET = None

import sys as _sys
if getattr(_sys, "frozen", False):
    _MAP_PATH = Path(_sys._MEIPASS) / "flipper_daemon" / "layouts" / "en_he_map.json"
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

    layout = detect_layout(text)
    forward = layout == "en_us"
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
