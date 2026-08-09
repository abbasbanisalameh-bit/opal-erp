"""Secure subscription-card code generation for OPAL Learning.

The public card value must never reveal sequential database identifiers, student
numbers, order identifiers, or other predictable source data. Existing cards
remain valid; this module is used only when issuing new cards.
"""

from __future__ import annotations

import re
import secrets

CARD_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CARD_CODE_GROUPS = 5
CARD_CODE_GROUP_SIZE = 4
DEFAULT_CARD_PREFIX = "OPAL"
MAX_GENERATION_ATTEMPTS = 64

_PREFIX_RE = re.compile(r"[^A-Z0-9-]+")


def normalize_card_prefix(prefix: str | None) -> str:
    """Return a short display prefix without weakening the random token."""
    value = (prefix or DEFAULT_CARD_PREFIX).strip().upper()
    value = _PREFIX_RE.sub("", value).strip("-")
    return (value or DEFAULT_CARD_PREFIX)[:16]


def random_card_token(*, groups: int = CARD_CODE_GROUPS, group_size: int = CARD_CODE_GROUP_SIZE) -> str:
    """Generate 100 bits of human-readable cryptographic randomness by default.

    The alphabet has exactly 32 characters (5 bits per character) and omits
    ambiguous 0/O and 1/I characters. 20 random characters therefore provide
    100 bits of entropy before formatting separators are added.
    """
    if groups < 1 or group_size < 1:
        raise ValueError("groups and group_size must be positive")
    chunks = []
    for _ in range(groups):
        chunks.append("".join(secrets.choice(CARD_CODE_ALPHABET) for _ in range(group_size)))
    return "-".join(chunks)


def new_card_code(*, prefix: str | None = DEFAULT_CARD_PREFIX) -> str:
    """Return a new unpredictable card candidate without consulting the DB."""
    return f"{normalize_card_prefix(prefix)}-{random_card_token()}"


def generate_unique_card_code(*, prefix: str | None = DEFAULT_CARD_PREFIX, reserved=None) -> str:
    """Generate a code not present in the database or the caller's reserved set.

    Database uniqueness remains the final concurrency guard via
    LearningSubscriptionCard.code(unique=True).
    """
    from .models import LearningSubscriptionCard

    reserved = reserved if reserved is not None else set()
    for _ in range(MAX_GENERATION_ATTEMPTS):
        code = new_card_code(prefix=prefix)
        if code in reserved:
            continue
        if not LearningSubscriptionCard.objects.filter(code=code).exists():
            reserved.add(code)
            return code
    raise RuntimeError("تعذر إنشاء رمز بطاقة فريد بعد عدة محاولات آمنة.")


def generate_unique_card_codes(count: int, *, prefix: str | None = DEFAULT_CARD_PREFIX) -> list[str]:
    """Generate a DB-safe, mutually unique batch with bounded DB lookups."""
    from .models import LearningSubscriptionCard

    if count < 0:
        raise ValueError("count must not be negative")
    if count == 0:
        return []

    selected: list[str] = []
    reserved: set[str] = set()
    for _round in range(MAX_GENERATION_ATTEMPTS):
        needed = count - len(selected)
        if needed <= 0:
            return selected
        candidates: list[str] = []
        candidate_set: set[str] = set()
        # Generate extra candidates locally so the overwhelmingly likely path
        # completes with one database lookup even for the 500-card demo seed.
        for _ in range(max(needed * 2, 16)):
            code = new_card_code(prefix=prefix)
            if code not in reserved and code not in candidate_set:
                candidate_set.add(code)
                candidates.append(code)
            if len(candidates) >= needed:
                break
        existing = set(
            LearningSubscriptionCard.objects.filter(code__in=candidates).values_list("code", flat=True)
        )
        for code in candidates:
            if code in existing or code in reserved:
                continue
            reserved.add(code)
            selected.append(code)
            if len(selected) >= count:
                return selected
    raise RuntimeError("تعذر إنشاء دفعة رموز بطاقات فريدة بعد عدة محاولات آمنة.")
