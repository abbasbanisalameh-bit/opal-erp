"""Canonical grade and section-name normalization for the academic structure."""

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


def normalize_section_name(value: object, grade_name: object = "") -> str:
    """Store a short section label such as ``شعبة أ`` without repeating grade."""
    text = normalize_grade_display_name(value)
    grade = normalize_grade_display_name(grade_name)
    if not text:
        return ""

    # Remove the grade prefix repeatedly because imported values may contain it
    # twice (for example: "الصف الأول الصف الأول شعبة أ").
    if grade:
        grade_pattern = re.compile(re.escape(grade), flags=re.IGNORECASE)
        previous = None
        while previous != text:
            previous = text
            text = grade_pattern.sub(" ", text).strip()

    text = re.sub(r"^[\s\-–—,:،/|]+|[\s\-–—,:،/|]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^(?:ال)?شعب(?:ة|ه)\s*", "", text, flags=re.IGNORECASE).strip()
    if not text:
        text = "عامة"
    if text in {"الشعبة العامة", "شعبة عامة", "العامة"}:
        text = "عامة"
    return f"شعبة {text}"


def section_name_key(value: object, grade_name: object = "") -> str:
    return grade_name_key(normalize_section_name(value, grade_name))


def class_display_name(grade_name: object, section_name: object) -> str:
    grade = normalize_grade_display_name(grade_name)
    section = normalize_section_name(section_name, grade)
    return " ".join(part for part in (grade, section) if part)
