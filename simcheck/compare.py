"""Compare fingerprinted documents and find the passages they share."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable

from .fingerprint import tokenize_with_spans

FingerprintFn = Callable[[list[str], int, int], list[tuple[int, int]]]


@dataclass(frozen=True)
class Document:
    name: str
    text: str
    tokens: list[str]
    spans: list[tuple[int, int]]  # character range of each token in `text`
    hashes: frozenset[int]
    # hash -> word positions where that fingerprint starts in this document
    positions: dict[int, list[int]]

    @classmethod
    def from_text(cls, name: str, text: str, fingerprint: FingerprintFn, k: int, w: int):
        """Tokenize and fingerprint `text` with the chosen engine's function."""
        tokens, spans = tokenize_with_spans(text)
        positions: dict[int, list[int]] = {}
        for h, pos in fingerprint(tokens, k, w):
            positions.setdefault(h, []).append(pos)
        return cls(name, text, tokens, spans, frozenset(positions), positions)

    def char_range(self, start: int, end: int) -> tuple[int, int]:
        """Character range in `text` covering words [start, end)."""
        return self.spans[start][0], self.spans[end - 1][1]


@dataclass(frozen=True)
class Match:
    a: Document
    b: Document
    shared: frozenset[int]
    jaccard: float  # shared / all distinct fingerprints in either document
    a_in_b: float  # share of A's fingerprints that also appear in B
    b_in_a: float  # share of B's fingerprints that also appear in A

    @property
    def score(self) -> float:
        """Headline score: how much of the more-copied document is shared."""
        return max(self.a_in_b, self.b_in_a)


def _ratio(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def compare(a: Document, b: Document) -> Match:
    shared = a.hashes & b.hashes
    return Match(
        a,
        b,
        shared,
        jaccard=_ratio(len(shared), len(a.hashes | b.hashes)),
        a_in_b=_ratio(len(shared), len(a.hashes)),
        b_in_a=_ratio(len(shared), len(b.hashes)),
    )


def compare_all(docs: list[Document]) -> list[Match]:
    """Compare every pair of documents, most similar first."""
    matches = [compare(a, b) for a, b in combinations(docs, 2)]
    return sorted(matches, key=lambda m: m.score, reverse=True)


def shared_passages(doc: Document, shared: frozenset[int], k: int) -> list[tuple[int, int]]:
    """Turn shared fingerprints into word ranges [start, end) in `doc`.

    Each fingerprint covers k words from its position. Overlapping or
    touching ranges are merged into one passage.
    """
    ranges = sorted((pos, pos + k) for h in shared for pos in doc.positions[h])
    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
