"""Estimate how strongly a text shows common AI-writing patterns.

This is a transparent heuristic, not a trained classifier. It measures a few
patterns that large language models produce more often than most people do,
and explains each one. It cannot prove who or what wrote a text: careful
human writers, formal academic style and non-native English writers can all
score high, and edited AI text can score low. Never treat the score as
evidence on its own.
"""

from __future__ import annotations

import re
import statistics

from .sentences import split_sentences, words

MIN_WORDS = 150

# Words and phrases that AI assistants use far more often than typical writers.
AI_PHRASES = (
    "delve", "delves", "delving", "tapestry", "testament to", "it is important to note",
    "it's important to note", "it is worth noting", "it's worth noting", "in today's",
    "fast-paced world", "ever-evolving", "ever-changing", "navigate the", "navigating the",
    "multifaceted", "pivotal", "crucial role", "plays a key role", "plays a vital role",
    "a vital role", "landscape", "realm", "foster", "fostering", "leverage", "leveraging",
    "seamless", "seamlessly", "robust", "holistic", "underscore", "underscores",
    "showcase", "showcases", "intricate", "intricacies", "paramount", "meticulous",
    "meticulously", "embark", "harness", "harnessing", "vibrant", "nuanced",
    "commendable", "noteworthy", "in conclusion", "in summary", "overall,",
    "a wide range of", "a myriad of", "myriad", "plethora", "furthermore", "moreover",
    "additionally", "not only", "but also", "stands as", "serves as a", "unlock",
    "unwavering", "elevate", "streamline", "transformative", "game-changer",
)

# Stock openers that AI text uses to start many sentences.
TRANSITIONS = (
    "furthermore", "moreover", "additionally", "in addition", "however", "overall",
    "in conclusion", "in summary", "ultimately", "consequently", "therefore",
    "notably", "importantly", "similarly", "conversely", "thus", "hence",
)

_PHRASE_RE = re.compile(
    r"(?<![\w-])(" + "|".join(re.escape(p) for p in sorted(AI_PHRASES, key=len, reverse=True)) + r")(?![\w-])",
    re.IGNORECASE,
)
_TRANSITION_RE = re.compile(r"^(?:" + "|".join(re.escape(t) for t in TRANSITIONS) + r")\b", re.IGNORECASE)
# "X, Y, and Z" lists of up to three words per item.
_TRIAD_RE = re.compile(r"\b[\w'-]+(?: [\w'-]+){0,2}, [\w'-]+(?: [\w'-]+){0,2},? (?:and|or) [\w'-]+", re.IGNORECASE)

# (id, name, weight). Weights add up to 1.
SIGNALS = (
    ("rhythm", "Even sentence lengths", 0.35),
    ("vocabulary", "AI-typical wording", 0.30),
    ("transitions", "Stock transitions", 0.15),
    ("lists", "Three-part lists", 0.10),
    ("dashes", "Em-dash use", 0.10),
)


def _scale(value: float, low: float, high: float) -> float:
    """Map value linearly so `low` gives 0 and `high` gives 1, clamped to 0..1."""
    if high == low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def ai_check(text: str) -> dict:
    sentence_spans = split_sentences(text)
    sentence_words = [words(text[s:e]) for s, e in sentence_spans]
    total_words = sum(len(w) for w in sentence_words)
    per_1000 = 1000 / total_words if total_words else 0.0

    # Only real sentences (3+ words) count for rhythm; this skips headings.
    lengths = [len(w) for w in sentence_words if len(w) >= 3]
    phrase_hits = [(m.start(), m.end(), m.group(0).lower()) for m in _PHRASE_RE.finditer(text)]

    flagged = []
    transition_count = 0
    triad_count = 0
    for (start, end), sentence_word_list in zip(sentence_spans, sentence_words):
        sentence = text[start:end]
        reasons = []
        found = sorted({p for s, e, p in phrase_hits if start <= s < end})
        if found:
            reasons.append("AI-typical wording: " + ", ".join(f'"{p}"' for p in found))
        opener = _TRANSITION_RE.match(sentence)
        if opener:
            transition_count += 1
            reasons.append(f'Starts with a stock transition ("{opener.group(0)}")')
        if _TRIAD_RE.search(sentence):
            triad_count += 1
            reasons.append("Three-part list")
        if reasons and len(sentence_word_list) >= 3:
            flagged.append({"start": start, "end": end, "reasons": reasons})

    real_sentences = len(lengths)
    variation = statistics.pstdev(lengths) / statistics.mean(lengths) if real_sentences >= 5 else None
    dash_count = text.count("—")

    values = {
        # People mix short and long sentences (variation often 0.6+); AI text is more even.
        "rhythm": (
            _scale(0.65 - variation, 0.0, 0.35) if variation is not None else 0.0,
            f"length variation {variation:.2f}" if variation is not None else "too few sentences",
            "How much sentence lengths vary. People tend to mix short and long sentences; "
            "AI text is often evenly paced.",
        ),
        "vocabulary": (
            _scale(len(phrase_hits) * per_1000, 0, 8),
            f"{len(phrase_hits)} found ({len(phrase_hits) * per_1000:.1f} per 1,000 words)",
            "Words and phrases AI assistants overuse, such as \"delve\", \"pivotal\" and \"it is important to note\".",
        ),
        "transitions": (
            _scale(transition_count / real_sentences if real_sentences else 0, 0.05, 0.25),
            f"{transition_count} of {real_sentences} sentences",
            "Sentences opening with \"Furthermore\", \"Moreover\", \"Additionally\" and similar.",
        ),
        "lists": (
            _scale(triad_count / real_sentences if real_sentences else 0, 0.05, 0.30),
            f"{triad_count} of {real_sentences} sentences",
            "Lists of exactly three items (\"clear, concise, and engaging\"), a common AI habit.",
        ),
        "dashes": (
            _scale(dash_count * per_1000, 0, 6),
            f"{dash_count} em dashes",
            "Frequent em dashes (—) are common in AI text, though many writers use them too.",
        ),
    }

    enough = total_words >= MIN_WORDS and real_sentences >= 5
    score = round(100 * sum(weight * values[key][0] for key, _, weight in SIGNALS)) if enough else None
    if score is None:
        band = "Not enough text"
    elif score >= 60:
        band = "Many AI-style patterns"
    elif score >= 30:
        band = "Some AI-style patterns"
    else:
        band = "Few AI-style patterns"

    return {
        "words": total_words,
        "sentences": real_sentences,
        "min_words": MIN_WORDS,
        "enough_text": enough,
        "score": score,
        "band": band,
        "signals": [
            {"id": key, "name": name, "weight": weight, "score": round(values[key][0], 3),
             "value": values[key][1], "explanation": values[key][2]}
            for key, name, weight in SIGNALS
        ],
        "flagged": flagged,
    }
