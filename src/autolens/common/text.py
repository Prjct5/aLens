"""Text normalisation and string similarity (handbook 6.3 and 6.4)."""

from __future__ import annotations

import re
import unicodedata

# Arabic-Indic (0660-0669) and Extended Arabic-Indic (06F0-06F9) -> ASCII
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Character unification for *matching only*, never for display (6.3)
_UNIFY = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",  # alef variants -> plain alef
        "ى": "ي",  # alef maqsura -> ya
        "ة": "ه",  # ta marbuta -> ha
    }
)

_TASHKEEL = re.compile(r"[\u064b-\u065f\u0670]")
_TATWEEL = "\u0640"
_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)


def to_ascii_digits(text: str) -> str:
    return text.translate(_DIGITS)


def normalize_arabic(text: str | None) -> str:
    """Normalise mixed Arabic/Latin/Franco text for comparison (6.3)."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", str(text))
    t = to_ascii_digits(t)
    t = _TASHKEEL.sub("", t).replace(_TATWEEL, "")
    t = t.translate(_UNIFY).lower()
    t = _PUNCT.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def levenshtein(a: str, b: str) -> int:
    """Classic edit distance - O(len(a)*len(b)) with two rows."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def slev(a: str, b: str) -> float:
    """Normalised Levenshtein similarity (equation 6.1)."""
    m = max(len(a), len(b))
    return 1.0 - levenshtein(a, b) / m if m else 1.0


def char_ngrams(text: str, n: int = 3) -> set[str]:
    """Set of character n-grams G_n(x) (equation 6.2)."""
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def sng(a: str, b: str, n: int = 3) -> float:
    """N-gram Jaccard similarity (equation 6.2)."""
    ga, gb = char_ngrams(a, n), char_ngrams(b, n)
    union = ga | gb
    return len(ga & gb) / len(union) if union else 1.0


def similarity(a: str, b: str) -> float:
    """s = max(slev, sng) on normalised strings (6.4)."""
    na, nb = normalize_arabic(a), normalize_arabic(b)
    return max(slev(na, nb), sng(na, nb))
