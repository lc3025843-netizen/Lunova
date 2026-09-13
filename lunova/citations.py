"""Helpers for protecting academic citations and fragile factual tokens."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ProtectedText:
    text: str
    replacements: dict[str, str]


# Parenthetical references containing a 4-digit year, e.g. (García, 2024; Pérez & Ruiz, 2023)
PAREN_CITATION_RE = re.compile(r"\([^()]{0,220}?\b(?:19|20)\d{2}[a-z]?\b[^()]{0,220}?\)")
# DOI / URL / e-mail-like references are fragile and should not be rewritten.
URL_RE = re.compile(r"https?://\S+|www\.\S+|doi:\s*\S+", re.IGNORECASE)
# Percentages and decimal values with optional symbols.
NUMBER_RE = re.compile(r"(?<!\w)(?:\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+[.,]\d+)\s*%?(?!\w)")


def protect_fragments(text: str, protect_numbers: bool = True) -> ProtectedText:
    """Replace citations/URLs/numbers with stable tokens before LLM rewriting."""
    replacements: dict[str, str] = {}
    counter = 1

    def _replace(pattern: re.Pattern[str], value: str, prefix: str) -> str:
        nonlocal counter

        def repl(match: re.Match[str]) -> str:
            nonlocal counter
            token = f"[[LNV_{prefix}_{counter:04d}]]"
            replacements[token] = match.group(0)
            counter += 1
            return token

        return pattern.sub(repl, value)

    protected = _replace(PAREN_CITATION_RE, text, "CIT")
    protected = _replace(URL_RE, protected, "REF")
    if protect_numbers:
        protected = _replace(NUMBER_RE, protected, "NUM")
    return ProtectedText(text=protected, replacements=replacements)


def restore_fragments(text: str, replacements: dict[str, str]) -> str:
    for token, original in replacements.items():
        text = text.replace(token, original)
    return text


def missing_protected_tokens(text: str, replacements: dict[str, str]) -> list[str]:
    """Return original protected fragments that are missing from output."""
    return [original for original in replacements.values() if original not in text]
