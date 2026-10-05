"""
Pick the layout the user meant, given text typed on the wrong one.

Where the text was typed is read off its script (Hebrew letters → Hebrew
layout, and so on). Where it was meant to go is the open question with three
layouts: every other installed layout is converted to and scored, and the most
language-like result wins. Pressing the hotkey again would take the next one.
"""

from .layouts import convert, source_layout

DICT_BONUS = 2.0  # added (in bits/char) when every word is a known word


class Detector:
    def __init__(self, models, dictionaries=None, dict_bonus=DICT_BONUS):
        self.models = models
        self.dictionaries = dictionaries or {}
        self.dict_bonus = dict_bonus

    def _score(self, text, lang):
        s = self.models[lang].score(text)
        words = text.split()
        known = self.dictionaries.get(lang)
        if known and words:
            s += self.dict_bonus * sum(w in known for w in words) / len(words)
        return s

    def rank(self, text, installed):
        """[(lang, converted_text, score)] best first, over installed layouts
        other than the one the text was typed on."""
        src = source_layout(text)
        out = []
        for lang in installed:
            if lang == src:
                continue
            conv = convert(text, src, lang)
            out.append((lang, conv, self._score(conv, lang)))
        out.sort(key=lambda r: r[2], reverse=True)
        return out
