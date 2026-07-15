"""Canonical grade-name normalization for the single academic structure."""

import re
import unicodedata

_ARABIC_TRANSLATION = str.maketrans({
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ى": "ي",
    "ؤ": "و",
    "ئ": "ي",
    "ة": "ه",
})


def normalize_grade_display_name(value: object) -> str:
    """Return a clean display name without changing the user's words."""
    return re.sub(r"\s+", " ", str(value or "").strip())


def grade_name_key(value: object) -> str:
    """Return a comparison key resilient to Arabic spelling/spacing variants."""
    text = normalize_grade_display_name(value).translate(_ARABIC_TRANSLATION)
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    text = text.replace("ـ", "").lower()
    return re.sub(r"[^0-9a-z\u0621-\u064a]+", "", text)
