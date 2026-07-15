"""Canonical choices shared by OPAL's student-facing modules."""

STUDENT_GENDER_CHOICES = (
    ("male", "ذكر"),
    ("female", "أنثى"),
)


def normalize_student_gender(value: object) -> str:
    """Normalize common Arabic/English OpenEMIS gender values.

    Unknown or empty values are kept empty rather than inventing a gender.
    """
    raw = str(value or "").strip().lower()
    mapping = {
        "male": "male",
        "m": "male",
        "1": "male",
        "ذكر": "male",
        "male student": "male",
        "boy": "male",
        "female": "female",
        "f": "female",
        "2": "female",
        "أنثى": "female",
        "انثى": "female",
        "female student": "female",
        "girl": "female",
    }
    return mapping.get(raw, "")
