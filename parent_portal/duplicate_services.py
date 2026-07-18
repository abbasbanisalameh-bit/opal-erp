from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction

from core.identifiers import normalize_identifier, normalize_phone

from .models import Family, FamilyStudent


def guardian_duplicate_groups():
    families = list(
        Family.objects.filter(is_active=True, merged_into__isnull=True)
        .select_related("user", "school")
        .prefetch_related("children")
    )
    parent = {item.pk: item.pk for item in families}

    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    buckets = defaultdict(list)
    for item in families:
        identity = normalize_identifier(item.identity_number)
        phone = normalize_phone(item.phone)
        if identity:
            buckets[(item.school_id, "identity", identity)].append(item.pk)
        if phone:
            buckets[(item.school_id, "phone", phone)].append(item.pk)
    for ids in buckets.values():
        for pk in ids[1:]:
            union(ids[0], pk)

    grouped = defaultdict(list)
    by_id = {item.pk: item for item in families}
    for pk in parent:
        grouped[find(pk)].append(by_id[pk])

    result = []
    for items in grouped.values():
        if len(items) < 2:
            continue
        identities = {normalize_identifier(item.identity_number) for item in items if item.identity_number}
        phones = {normalize_phone(item.phone) for item in items if item.phone}
        canonical = max(
            items,
            key=lambda item: (
                bool(item.user_id and item.user.is_active),
                bool(item.identity_number),
                item.children.count(),
                -item.pk,
            ),
        )
        result.append({
            "families": sorted(items, key=lambda item: item.pk),
            "ids": ",".join(str(item.pk) for item in items),
            "canonical": canonical,
            "match_type": "رقم الهوية" if len(identities) == 1 and identities else "رقم الهاتف",
            "identity": next(iter(identities), ""),
            "phone": next(iter(phones), ""),
            "safe_to_merge": len(identities) <= 1,
        })
    return sorted(result, key=lambda row: row["canonical"].guardian_name)


@transaction.atomic
def merge_guardian_group(*, family_ids, canonical_id, user):
    wanted = sorted({int(pk) for pk in family_ids})
    groups = guardian_duplicate_groups()
    safe_group = next((group for group in groups if sorted(item.pk for item in group["families"]) == wanted), None)
    if not safe_group:
        raise ValidationError("المجموعة لم تعد متطابقة بالهوية أو الهاتف؛ أعد الفحص.")
    if not safe_group["safe_to_merge"]:
        raise ValidationError("لا يمكن الدمج لأن الملفات تحمل أرقام هوية مختلفة رغم اشتراكها في الهاتف.")
    if canonical_id not in wanted:
        raise ValidationError("الملف الأساسي ليس ضمن المجموعة.")
    families = list(Family.objects.select_for_update().filter(pk__in=wanted).select_related("user"))
    canonical = next(item for item in families if item.pk == canonical_id)
    sources = [item for item in families if item.pk != canonical_id]

    changed = []
    for field in ("identity_number", "phone", "secondary_phone", "email", "job_title", "address", "medical_notes"):
        if not getattr(canonical, field):
            value = next((getattr(source, field) for source in sources if getattr(source, field)), "")
            if value:
                setattr(canonical, field, value)
                changed.append(field)
    if changed:
        canonical.save(update_fields=changed + ["updated_at"])

    for source in sources:
        # Newly issued documents follow the canonical guardian record; their
        # immutable applicant/totals snapshots remain unchanged.
        source.issued_documents.update(guardian=canonical)
        links = list(source.children.select_related("student"))
        for link in links:
            if link.is_active:
                link.is_active = False
                link.save(update_fields=["is_active"])
            target, _ = FamilyStudent.objects.get_or_create(
                family=canonical,
                student=link.student,
                defaults={"relation": link.relation, "is_active": True},
            )
            if not target.is_active:
                FamilyStudent.objects.filter(student=link.student, is_active=True).exclude(pk=target.pk).update(is_active=False)
                target.is_active = True
                target.save(update_fields=["is_active"])
        source.is_active = False
        source.merged_into = canonical
        source.save(update_fields=["is_active", "merged_into", "updated_at"])
        if source.user_id and source.user_id != canonical.user_id and source.user.is_active:
            source.user.is_active = False
            source.user.save(update_fields=["is_active"])
    return canonical, len(sources)
