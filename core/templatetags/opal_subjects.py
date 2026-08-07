"""Safe subject-colour helpers used across OPAL templates.

The database field ``academics.Subject.color`` is the only source of truth.  A
strict hexadecimal whitelist is used before a value is exposed as a CSS custom
property, so templates never interpolate arbitrary style text.
"""

from __future__ import annotations

import re
from typing import Any

from django import template
from django.utils.html import format_html

register = template.Library()

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_FALLBACK = "#64748B"


def _colour(value: Any) -> str:
    if hasattr(value, "color"):
        value = getattr(value, "color", "")
    value = str(value or "").strip()
    return value.upper() if _HEX.fullmatch(value) else _FALLBACK


@register.simple_tag
def subject_style(subject_or_colour: Any) -> str:
    """Return one validated CSS variable declaration for a subject surface."""

    return format_html("--opal-subject-color:{};", _colour(subject_or_colour))


@register.filter
def subject_colour(subject_or_colour: Any) -> str:
    """Return a validated colour value for attributes that need only the hex."""

    return _colour(subject_or_colour)
