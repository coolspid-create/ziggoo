from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_phrase_or_tokens(haystack: str, needle: str) -> bool:
    needle = normalize_text(needle)
    if not needle:
        return True
    if needle in haystack:
        return True

    tokens = [token for token in re.split(r"[\s,/|]+", needle) if token]
    return bool(tokens) and all(token in haystack for token in tokens)


def check_dual_match(query: str, verify: str | None, product_name: str) -> bool:
    haystack = normalize_text(product_name)
    return _contains_phrase_or_tokens(haystack, query) and _contains_phrase_or_tokens(
        haystack,
        verify or "",
    )

