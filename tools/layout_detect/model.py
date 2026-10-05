"""
Letter-trigram language models: "how much does this look like Russian?"

Trained from a word-frequency list. Each word is padded with boundary marks
(^^word$) so the model learns how words start and end — which matters for
Hebrew final letters and for Russian endings. Counts are weighted by
log(frequency), a middle ground between treating every word equally (rare
words dominate) and by raw frequency (a few function words dominate).

score() returns the mean log2-probability per character, so strings of
different lengths and languages are comparable. Higher = more plausible.
"""

import math
from collections import Counter

BOS, EOS = "^", "$"
_L3, _L2, _L1 = 0.6, 0.3, 0.1  # interpolation weights: trigram, bigram, unigram


class TrigramModel:
    def __init__(self, alphabet):
        self.alphabet = set(alphabet)
        self.c3, self.c2ctx, self.c2, self.c1ctx, self.c1 = (Counter() for _ in range(5))
        self.total = 0.0
        # Characters a model can be asked about: its letters, the end mark,
        # plus anything foreign (punctuation from the wrong layout) which gets
        # only the floor probability.
        self.vocab = len(self.alphabet) + 1

    def train(self, words_with_counts):
        for word, count in words_with_counts:
            w = math.log(count + 1)
            padded = BOS + BOS + word + EOS
            for i in range(2, len(padded)):
                a, b, c = padded[i - 2], padded[i - 1], padded[i]
                self.c3[(a, b, c)] += w
                self.c2ctx[(a, b)] += w
                self.c2[(b, c)] += w
                self.c1ctx[b] += w
                self.c1[c] += w
                self.total += w
        return self

    def _p(self, a, b, c):
        p3 = self.c3[(a, b, c)] / self.c2ctx[(a, b)] if self.c2ctx[(a, b)] else 0.0
        p2 = self.c2[(b, c)] / self.c1ctx[b] if self.c1ctx[b] else 0.0
        p1 = self.c1[c] / self.total if self.total else 0.0
        floor = 1e-4 / self.vocab
        return _L3 * p3 + _L2 * p2 + _L1 * p1 + floor

    def score_word(self, word):
        padded = BOS + BOS + word + EOS
        logp = sum(math.log2(self._p(padded[i - 2], padded[i - 1], padded[i]))
                   for i in range(2, len(padded)))
        return logp, len(padded) - 2

    def score(self, text):
        total, n = 0.0, 0
        for word in text.split():
            lp, k = self.score_word(word)
            total += lp
            n += k
        return total / n if n else float("-inf")
