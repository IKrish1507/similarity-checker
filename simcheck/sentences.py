"""Split text into sentences, keeping each sentence's position in the text."""

from __future__ import annotations

import re

# A sentence is a run of text without . ! ? or a line break, plus its closing
# punctuation and any closing quote or bracket. Simple rules like this split
# "e.g." and "Dr." too early; that is acceptable for estimating patterns.
_SENTENCE = re.compile(r"[^.!?\n]*[^.!?\n\s][^.!?\n]*(?:[.!?]+[\"'”’)\]]*)?")
_WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")


def split_sentences(text: str) -> list[tuple[int, int]]:
    """Return (start, end) character ranges of sentences, leading spaces trimmed."""
    spans = []
    for match in _SENTENCE.finditer(text):
        start, end = match.span()
        while start < end and text[start].isspace():
            start += 1
        if start < end:
            spans.append((start, end))
    return spans


def words(text: str) -> list[str]:
    """Words for counting and statistics (keeps "don't" and "well-known" whole)."""
    return _WORD.findall(text)
