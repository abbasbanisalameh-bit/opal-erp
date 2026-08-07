"""Canonical subject identity and colour policy for OPAL ERP.

A subject may have one annual row per grade, while ``canonical_key`` keeps the
same visible subject identity and colour stable across grades and years.
"""

from __future__ import annotations

import math
import re
import unicodedata

from django.core.exceptions import ValidationError

_ARABIC_TRANSLATION = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه",
})

# High-contrast palette. Common subjects get a stable semantic colour first;
# the rest are allocated from the same palette by the canonical key.
# The capacity data set uses 18 canonical subject identities.  The previous
# 18-item palette contained several visually-near shades, so the allocator could
# reject every remaining candidate before reaching the tenth identity.  This
# expanded max-distance palette keeps every pair more than 45 RGB units apart
# and leaves headroom for future subjects without weakening the collision rule.
SUBJECT_PALETTE = (
    "#2563EB",
    "#DC2626",
    "#16A34A",
    "#9333EA",
    "#EA580C",
    "#0891B2",
    "#9BD921",
    "#62D9D9",
    "#4B2A8C",
    "#D96289",
    "#8C733F",
    "#62D975",
    "#D9C562",
    "#8C1551",
    "#B21B99",
    "#D962D9",
    "#3FD921",
    "#518C15",
    "#21D99B",
    "#6289D9",
    "#3F738C",
    "#3F21D9",
    "#D99B21",
    "#8C3D15",
    "#7150B2",
    "#D921D9",
    "#81B250",
    "#21D9D9",
    "#1B4DB2",
    "#50B2A2",
    "#B25061",
    "#21D95E",
    "#B250B2",
    "#158C15",
    "#D9215E",
    "#D98962",
    "#801BB2",
    "#B2671B",
    "#158C78",
    "#D95A41",
)

_SEMANTIC_COLOUR_NAMES = {
    "الرياضيات": "#2563EB",
    "اللغة العربية": "#DC2626",
    "العربية": "#DC2626",
    "العلوم": "#16A34A",
    "اللغة الإنجليزية": "#9333EA",
    "الإنجليزية": "#9333EA",
    "التربية الإسلامية": "#EA580C",
    "الحاسوب": "#0891B2",
    "التربية الرياضية": "#518C15",
    "التربية المهنية": "#50B2A2",
    "التربية الفنية": "#D96289",
    "الثقافة المالية": "#D921D9",
    "الاجتماعيات": "#D98962",
    "التاريخ": "#801BB2",
    "الجغرافيا": "#3FD921",
    "التربية الوطنية": "#9BD921",
    "الفيزياء": "#158C15",
    "الكيمياء": "#B21B99",
    "الأحياء": "#B2671B",
    "علوم الأرض": "#D95A41",
}


_CANONICAL_ALIASES = {
    "الرياضيات": "رياضيات", "رياضيات": "رياضيات",
    "اللغهالعربيه": "اللغهالعربيه", "لغهعربيه": "اللغهالعربيه", "العربيه": "اللغهالعربيه",
    "اللغهالانجليزيه": "اللغهالانجليزيه", "لغهانجليزيه": "اللغهالانجليزيه",
    "الانجليزيه": "اللغهالانجليزيه", "انجليزي": "اللغهالانجليزيه",
    "العلوم": "علوم", "علوم": "علوم",
    "التربيهالاسلاميه": "التربيهالاسلاميه", "تربيهاسلاميه": "التربيهالاسلاميه",
    "الحاسوب": "حاسوب", "حاسوب": "حاسوب", "الكمبيوتر": "حاسوب", "كمبيوتر": "حاسوب",
}


def normalize_subject_key(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip()).translate(_ARABIC_TRANSLATION)
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    text = text.replace("ـ", "").lower()
    raw = re.sub(r"[^0-9a-z\u0621-\u064a]+", "", text)
    return _CANONICAL_ALIASES.get(raw, raw)


def normalize_hex_colour(value: object) -> str:
    colour = str(value or "").strip().upper()
    if colour and not colour.startswith("#"):
        colour = f"#{colour}"
    if not re.fullmatch(r"#[0-9A-F]{6}", colour):
        raise ValidationError("لون المادة يجب أن يكون بصيغة سداسية مثل #2563EB.")
    return colour


def _rgb(colour: str) -> tuple[int, int, int]:
    colour = normalize_hex_colour(colour)
    return tuple(int(colour[index:index + 2], 16) for index in (1, 3, 5))


def colour_distance(first: str, second: str) -> float:
    """Simple RGB distance used as a conservative visual collision guard."""
    a = _rgb(first)
    b = _rgb(second)
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b)))


SEMANTIC_COLOURS = {
    normalize_subject_key(name): colour for name, colour in _SEMANTIC_COLOUR_NAMES.items()
}


def _is_visually_available(colour: str, used_colours, *, minimum_distance: float = 45) -> bool:
    for used in used_colours:
        try:
            if colour_distance(colour, used) < minimum_distance:
                return False
        except ValidationError:
            continue
    return True


def default_subject_colour(canonical_key: str, used_colours=()) -> str:
    key = normalize_subject_key(canonical_key)
    used = [str(item or "").upper() for item in used_colours if item]
    semantic = SEMANTIC_COLOURS.get(key)
    if semantic and _is_visually_available(semantic, used):
        return semantic
    seed = sum((index + 1) * ord(char) for index, char in enumerate(key))
    ordered = SUBJECT_PALETTE[seed % len(SUBJECT_PALETTE):] + SUBJECT_PALETTE[:seed % len(SUBJECT_PALETTE)]
    colour = next((item for item in ordered if _is_visually_available(item, used)), None)
    if colour is None:
        raise ValidationError(
            "لا يوجد لون متباين كافٍ لهذه المادة ضمن اللوحة الحالية. وسّع لوحة الألوان قبل إضافة هوية مادة جديدة."
        )
    return colour


def ensure_subject_identity(subject, *, propagate=True):
    """Normalize identity, choose one stable colour, and synchronize annual rows."""
    model = type(subject)
    original = None
    if subject.pk:
        original = model.objects.filter(pk=subject.pk).values("canonical_key", "color").first()

    subject.canonical_key = normalize_subject_key(subject.canonical_key or subject.name)
    if not subject.canonical_key:
        raise ValidationError({"name": "أدخل اسم مادة صالحًا لتكوين هويتها الموحدة."})

    requested_colour = normalize_hex_colour(subject.color) if subject.color else ""
    explicit_colour_change = bool(
        requested_colour
        and (not original or requested_colour != str(original.get("color") or "").upper())
    )
    siblings = model.objects.filter(canonical_key=subject.canonical_key).exclude(pk=subject.pk)
    sibling_colour = siblings.exclude(color="").values_list("color", flat=True).first()

    if explicit_colour_change:
        subject.color = requested_colour
    elif sibling_colour:
        subject.color = normalize_hex_colour(sibling_colour)
    elif requested_colour:
        subject.color = requested_colour
    else:
        used = model.objects.exclude(canonical_key=subject.canonical_key).exclude(color="").values_list("color", flat=True)
        subject.color = default_subject_colour(subject.canonical_key, used)

    collisions = model.objects.exclude(canonical_key=subject.canonical_key).exclude(color="").values(
        "canonical_key", "name", "color"
    )
    for row in collisions:
        if colour_distance(subject.color, row["color"]) < 45:
            raise ValidationError({
                "color": f"اللون قريب بصريًا من لون المادة «{row['name']}». اختر لونًا أوضح اختلافًا.",
            })

    if propagate and subject.pk:
        siblings.exclude(color=subject.color).update(color=subject.color)
    return subject
