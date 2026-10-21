"""Turn text into fingerprints: tokenize, hash k-grams, winnow.

This is the pure-Python reference implementation. The Rust core in
simcheck-core/ implements `fingerprint` with exactly the same algorithm
and is used instead when it is installed (see engine.py).
"""

from __future__ import annotations

import re

# FNV-1a 64-bit constants (public, fixed values from the FNV specification).
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
MASK64 = 0xFFFFFFFFFFFFFFFF

# A "word" is a run of letters or digits. [^\W_] means "a word character
# that is not an underscore".
_WORD = re.compile(r"[^\W_]+")


def tokenize_with_spans(text: str) -> tuple[list[str], list[tuple[int, int]]]:
    """Split text into lowercase words, dropping punctuation.

    Also returns each word's (start, end) character position in the original
    text, so matches can be shown as the author wrote them. Words are matched
    on the original text and lowercased one at a time, because lowercasing
    the whole text first can change its length and shift every position.
    """
    tokens: list[str] = []
    spans: list[tuple[int, int]] = []
    for match in _WORD.finditer(text):
        tokens.append(match.group().lower())
        spans.append(match.span())
    return tokens, spans


def tokenize(text: str) -> list[str]:
    """Just the words from tokenize_with_spans."""
    return tokenize_with_spans(text)[0]


def fnv1a_64(data: bytes) -> int:
    """Hash bytes to a 64-bit number that is the same on every run and machine.

    Python's built-in hash() is randomised per process, so it cannot be
    compared with the Rust core or saved between runs.
    """
    h = FNV_OFFSET
    for byte in data:
        h ^= byte
        h = (h * FNV_PRIME) & MASK64
    return h


def hash_kgrams(tokens: list[str], k: int) -> list[int]:
    """Hash every run of k consecutive words ("k-gram").

    Words are joined with single spaces, so "the cat sat" always hashes
    the same however it was punctuated in the original text.
    """
    return [
        fnv1a_64(" ".join(tokens[i : i + k]).encode("utf-8"))
        for i in range(len(tokens) - k + 1)
    ]


def winnow(hashes: list[int], w: int) -> list[tuple[int, int]]:
    """Keep a small, representative subset of hashes (Schleimer et al., 2003).

    Slide a window of w hashes along the list and keep the smallest hash in
    each window (the rightmost one on ties). Returns (hash, position) pairs,
    where position is the index of the k-gram's first word.

    Guarantee: any shared passage of at least w + k - 1 words produces at
    least one shared fingerprint.
    """
    if not hashes:
        return []
    w = min(w, len(hashes))
    picked: list[tuple[int, int]] = []
    last = -1
    for start in range(len(hashes) - w + 1):
        pos = start
        for j in range(start, start + w):
            if hashes[j] <= hashes[pos]:  # <= keeps the rightmost minimum
                pos = j
        if pos != last:
            picked.append((hashes[pos], pos))
            last = pos
    return picked


def fingerprint(tokens: list[str], k: int, w: int) -> list[tuple[int, int]]:
    """Fingerprint a tokenized document. Same signature as the Rust core."""
    if k < 1 or w < 1:
        raise ValueError("k and w must be at least 1")
    return winnow(hash_kgrams(tokens, k), w)
