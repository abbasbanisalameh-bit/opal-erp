"""Canonical normalization helpers for OPAL identity data."""
from __future__ import annotations

import unicodedata

_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize_identifier(value: object) -> str:
    """Normalize national/personal/ministry IDs to one stable comparison value."""
    text = unicodedata.normalize("NFKC", str(value or "")).translate(_DIGIT_TRANSLATION).strip().upper()
    return "".join(character for character in text if character.isalnum())


def normalize_phone(value: object) -> str:
    """Normalize phone numbers to digits only without guessing a country code."""
    text = unicodedata.normalize("NFKC", str(value or "")).translate(_DIGIT_TRANSLATION)
    return "".join(character for character in text if character.isdigit())
