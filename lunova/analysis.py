"""Transparent heuristic writing metrics used by the Lunova UI."""
from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher

CONNECTORS = {
    "además", "asimismo", "por otra parte", "en este sentido", "por lo tanto", "por tanto",
    "sin embargo", "de esta manera", "en consecuencia", "debido a ello", "a su vez",
    "no obstante", "de igual manera", "por consiguiente", "en cambio", "finalmente",
}

WORD_RE = re.compile(r"\b[\wáéíóúüñÁÉÍÓÚÜÑ]+\b", re.UNICODE)
SENT_RE = re.compile(r"(?<=[.!?])\s+")


def _words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def similarity(original: str, revised: str) -> int:
    """Character-sequence similarity, 0-100. It is not a plagiarism score."""
    if not original.strip() or not revised.strip():
        return 0
    return round(100 * SequenceMatcher(None, original.lower(), revised.lower()).ratio())


def repetition_level(text: str) -> tuple[str, int]:
    words = [w for w in _words(text) if len(w) >= 5]
    if not words:
        return "Bajas", 90
    counts = Counter(words)
    repeated = sum(c - 1 for c in counts.values() if c > 1)
    ratio = repeated / max(1, len(words))
    score = max(25, min(100, round(100 - ratio * 220)))
    label = "Bajas" if score >= 78 else "Medias" if score >= 58 else "Altas"
    return label, score


def writing_metrics(text: str) -> dict[str, int | str]:
    text = text.strip()
    if not text:
        return {"naturalidad": 0, "claridad": 0, "variacion": 0, "repeticiones": "—"}

    sentences = [s.strip() for s in SENT_RE.split(text) if s.strip()]
    lengths = [len(_words(s)) for s in sentences] or [0]
    avg = sum(lengths) / len(lengths)
    variance = sum((x - avg) ** 2 for x in lengths) / max(1, len(lengths))
    std = math.sqrt(variance)

    # Clarity peaks around 18-26 words/sentence and declines toward extremes.
    clarity = 95 - abs(avg - 22) * 2.0
    clarity = int(max(45, min(97, clarity)))

    # Variation rewards some sentence-length diversity, but not chaos.
    variation = int(max(50, min(96, 58 + std * 4.2)))

    low = text.lower()
    connector_hits = sum(1 for c in CONNECTORS if c in low)
    connector_bonus = min(8, connector_hits * 2)
    repetition_label, repetition_score = repetition_level(text)
    naturalness = int(max(50, min(97, (clarity + variation + repetition_score) / 3 + connector_bonus / 2)))

    return {
        "naturalidad": naturalness,
        "claridad": clarity,
        "variacion": variation,
        "repeticiones": repetition_label,
    }
