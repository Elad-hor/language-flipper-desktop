"""
Keyboard layouts as physical-key tables, so any layout converts to any other.

Each layout lists what the same 34 physical keys produce (unshifted), in the
order of the US layout's ` q w e … , . /. Converting "typed in A, meant B" is
then: look each character up in A to get the key, read that key in B.

HE is the standard Israeli layout (SI-1452) as Windows and macOS "Hebrew-PC"
ship it, RU is standard ЙЦУКЕН. Note the app's en_he_map.json differs on the
' key (it keeps the apostrophe); this prototype uses the real layout.
"""

EN = list("`qwertyuiop[]asdfghjkl;'zxcvbnm,./")
HE = list(";/'קראטוןםפ][שדגכעיחלךף,זסבהנמצתץ.")
RU = list("ёйцукенгшщзхъфывапролджэячсмитьбю.")

LAYOUTS = {"en": EN, "he": HE, "ru": RU}

assert all(len(keys) == len(EN) for keys in LAYOUTS.values())

# Letters that belong to each language — used to tell which layout text was
# typed in, and to filter training words.
ALPHABET = {
    "en": set("abcdefghijklmnopqrstuvwxyz"),
    "he": set("אבגדהוזחטיכךלמםנןסעפףצץקרשת"),
    "ru": set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя"),
}

_KEY_OF = {name: {ch: i for i, ch in enumerate(keys)} for name, keys in LAYOUTS.items()}


def source_layout(text: str) -> str:
    """Which layout the text was typed in, by majority script. Latin wins ties
    with nothing, i.e. text with no letters at all reads as English."""
    counts = {name: 0 for name in ALPHABET}
    for ch in text.lower():
        for name, letters in ALPHABET.items():
            if ch in letters:
                counts[name] += 1
    best = max(counts, key=counts.get)
    return best if counts[best] else "en"


def convert(text: str, src: str, dst: str) -> str:
    """Re-read `text`, typed on layout `src`, as if typed on layout `dst`."""
    keys_src, keys_dst = _KEY_OF[src], LAYOUTS[dst]
    out = []
    for ch in text.lower():
        i = keys_src.get(ch)
        out.append(keys_dst[i] if i is not None else ch)
    return "".join(out)
