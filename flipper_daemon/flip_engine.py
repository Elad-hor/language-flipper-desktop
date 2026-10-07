"""
Decide what a flip turns text into, and which layout to switch to.

Two installed layouts (the usual Hebrew + English): exactly the pre-Russian
behaviour — flipper.flip_text, and pressing again flips back.

Three installed layouts: there is a choice of target. The first press takes
langdetect's best guess; pressing again within CYCLE_SECONDS, on the text we
just wrote, moves to the next guess and finally back to what was typed:

    ghbdtn  →  привет (best guess)  →  פריבתמ (next)  →  ghbdtn (as typed)

A wrong guess on a 1-2 letter word therefore costs one more press. Cycle
presses are reported as such so they don't count against the free flips.

EN<->HE output always comes from flip_text, even with Russian installed, so
those flips don't change for anyone (keymaps' Hebrew table differs from
en_he_map.json on the ' key).
"""

import time
from dataclasses import dataclass, field

from . import langdetect
from .flipper import detect_layout, flip_mixed, flip_text, is_mixed
from .keymaps import convert, source_layout

CYCLE_SECONDS = 15

_LEGACY_NAME = {"en_us": "en", "he_il": "he"}


@dataclass
class FlipResult:
    text: str          # full replacement for the text that was read
    source: str        # layout the text was typed on: "en" / "he" / "ru"
    target: str        # layout the result belongs to — switch to this one
    is_cycle: bool = False


@dataclass
class _Last:
    original: str      # the segment as the user typed it
    src: str
    order: list        # targets to cycle through; ends with src
    idx: int
    output: str        # what we wrote last
    at: float = field(default=0.0)


class FlipEngine:
    def __init__(self, installed_fn, detector_fn=langdetect.load, clock=time.monotonic):
        self._installed = installed_fn
        self._detector = detector_fn
        self._clock = clock
        self._last = None
        self._pending = None

    def flip(self, text: str, caps_lock: bool = False):
        """
        FlipResult, or None if there is nothing to change.

        Has no lasting effect until commit(): text_bridge may call this twice
        for one press (macOS tries Accessibility, then the clipboard) and both
        calls must give the same answer.
        """
        self._pending = None
        if not text:
            return None
        installed = self._installed()
        if "ru" not in installed:
            self._pending = ("reset",)
            return self._flip_two_layouts(text)

        cycled = self._try_cycle(text, caps_lock)
        if cycled:
            return cycled

        body = text.rstrip()
        trailing = text[len(body):]
        src = source_layout(body)
        ranked = self._detector().rank(body, sorted(installed))
        if not ranked:
            return None
        order = [lang for lang, _, _ in ranked] + [src]
        out = _render(body, src, order[0], caps_lock)
        if out == body:
            return None
        self._pending = _Last(body, src, order, 0, out)
        return FlipResult(out + trailing, src, order[0])

    def commit(self):
        """The last flip() result was written into the app: remember it, so
        the next press can cycle from it."""
        pending, self._pending = self._pending, None
        if pending is None:
            return
        if pending == ("reset",):
            self._last = None
            return
        pending.at = self._clock()
        self._last = pending

    def _flip_two_layouts(self, text):
        if is_mixed(text):
            mixed = flip_mixed(text, self._detector())
            if mixed:
                return FlipResult(*mixed)
        out = flip_text(text)
        if out == text:
            return None
        src = _LEGACY_NAME[detect_layout(text)]
        return FlipResult(out, src, "he" if src == "en" else "en")

    def _try_cycle(self, text, caps_lock):
        last = self._last
        if not last or self._clock() - last.at > CYCLE_SECONDS:
            return None
        # The flip may have been of a selection, and the second press reads
        # the whole line (nothing is selected after a paste) — so our output
        # only has to end the text, not be all of it. It must *end* it: if the
        # user has typed on since, this press is about the new text.
        # Trailing whitespace is let through: a space after a word isn't
        # "typing on".
        body = text.rstrip()
        trailing = text[len(body):]
        if not last.output or not body.endswith(last.output):
            return None
        head = body[:len(body) - len(last.output)]
        idx = (last.idx + 1) % len(last.order)
        target = last.order[idx]
        seg = _render(last.original, last.src, target, caps_lock)
        self._pending = _Last(last.original, last.src, last.order, idx, seg)
        return FlipResult(head + seg + trailing, last.src, target, is_cycle=True)


def _render(original, src, target, caps_lock):
    if target == src:
        return original
    if {src, target} == {"en", "he"}:
        return flip_text(original)
    out = convert(original, src, target)
    # Caps Lock on means the capitals were an accident, not intent: Russian
    # and English layouts honour Caps Lock, so ghbdtn typed with it on arrives
    # as GHBDTN and should come out as привет, not ПРИВЕТ.
    return out.lower() if caps_lock else out
