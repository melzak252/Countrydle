"""Utility for sanitizing player-facing explanations to prevent target entity leaks and prompt plumbing leaks."""

from __future__ import annotations

import re
from typing import Collection


_PROMPT_PLUMBING_PATTERN = re.compile(
    r"^(?:the\s+provided\s+text\s+(?:mentions|states|indicates|shows|notes)\s+that|based\s+on\s+the\s+provided\s+text,?\s*|according\s+to\s+the\s+provided\s+text,?\s*|from\s+the\s+provided\s+context,?\s*|in\s+the\s+provided\s+text,?\s*|w\s+dostarczonym\s+tek[sś]cie\s+wspomniano,?\s+[zż]e|na\s+podstawie\s+dostarczonego\s+tekstu,?\s*)",
    re.IGNORECASE,
)


def sanitize_explanation_for_player(
    explanation: str | None,
    entity_names: Collection[str] | None = None,
    entity_label: str = "the country",
) -> str:
    """Strip internal RAG/prompt plumbing and redact target entity names from player explanations."""
    if not explanation or not isinstance(explanation, str):
        return ""
    text = explanation.strip()
    if not text:
        return ""
    # 1. Remove introductory prompt/RAG plumbing
    text = _PROMPT_PLUMBING_PATTERN.sub("", text).strip()

    # 2. Redact target entity names and possessives
    if entity_names:
        for raw_name in sorted(entity_names, key=len, reverse=True):
            if not raw_name or len(raw_name) < 2:
                continue
            # Redact possessive e.g. "Vietnam's" -> "the country's"
            pattern_possessive = re.compile(rf"\b{re.escape(raw_name)}['’]s\b", re.IGNORECASE)
            text = pattern_possessive.sub(f"{entity_label}'s", text)
            pattern_word = re.compile(rf"\b{re.escape(raw_name)}\b", re.IGNORECASE)
            text = pattern_word.sub(entity_label, text)

    # 3. Capitalize first letter
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text
