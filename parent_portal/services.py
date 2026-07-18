import secrets
import string

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import Role, UserProfile
from core.identifiers import normalize_identifier, normalize_phone
from core.models import School

from .models import Family, FamilyStudent


def initial_parent_password(_seed=""):
    """Return a one-time random password; never derive credentials from identity data."""
    alphabet = string.ascii_letters + string.digits
    value = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]
    value.extend(secrets.choice(alphabet) for _ in range(9))
    secrets.SystemRandom().shuffle(value)
    return "".join(value)


def _safe_username_from_phone(phone, fallback="parent"):
    digits = normalize_phone(phone)
    if digits:
        return f"parent_{digits[-10:]}"
    clean = "".join(ch for ch in (fallback or "parent") if ch.isalnum())[:20] or "parent"
    return f"parent_{clean}"


def _unique_username(base):
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        counter += 1
        username = f"{base}_{counter}"
    return username


def find_existing_family(
    *,
    school=None,
    guardian_name="",
    phone="",
    national_id="",
    identity_number="",
):
    """Find the authoritative family by identity first, then phone within one school."""
    digits = normalize_phone(phone)
    identity = normalize_identifier(identity_number or national_id)
    qs = Family.objects.filter(is_active=True)
    if school:
        qs = qs.filter(school=school)

    identity_family = qs.filter(identity_number=identity).first() if identity else None
    phone_family = qs.filter(phone=digits).first() if digits else None
    if identity_family and phone_family and identity_family.pk != phone_family.pk:
        raise ValidationError(
            "بيانات ولي الأمر متعارضة: رقم الهوية والهاتف مرتبطان بملفين مختلفين لولي الأمر. "
            "يجب مراجعة السجلين قبل المتابعة."
        )
    if identity_family:
        return identity_family
    if phone_family:
        return phone_family
    # Names are not identifiers and are deliberately never used to merge families.
    return None


def _ensure_user_profile(user, *, school=None, guardian_name="", phone=""):
    parent_role, _ = Role.objects.get_or_create(
        code="parent",
        defaults={"name": "ولي أمر", "description": "حساب ولي أمر"},
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    changed = []
    if school and profile.school_id != school.id:
        profile.school = school
        changed.append("school")
    if profile.role_id != parent_role.id:
        profile.role = parent_role
        changed.append("role")
    if guardian_name and profile.full_name != guardian_name:
        profile.full_name = guardian_name
        changed.append("full_name")
    if phone and profile.phone != phone:
        profile.phone = phone
        changed.append("phone")
    if profile.is_school_user:
        profile.is_school_user = False
        changed.append("is_school_user")
    if changed:
        profile.save(update_fields=changed)
    return profile


@transaction.atomic
def create_or_update_parent_family_for_student(
    student,
    guardian_name="",
    phone="",
    school=None,
    national_id="",
    identity_type="national",
    identity_number="",
    relation="ولي أمر",
    source="manual",
    openemis_data=None,
    **extra_fields,
):
    """Create or repair the single canonical Family/FamilyStudent path."""
    school = school or School.objects.filter(is_active=True).first() or School.objects.first()
    guardian_name = (guardian_name or student.guardian_name or "ولي أمر").strip()
    phone = normalize_phone(phone or student.phone or "")
    identity_number = normalize_identifier(identity_number or national_id)
    identity_type = identity_type if identity_type in dict(Family.IDENTITY_TYPES) else "other"
    relation = (relation or "ولي أمر").strip()

    family = find_existing_family(
        school=school,
        guardian_name=guardian_name,
        phone=phone,
        identity_number=identity_number,
    )

    password = initial_parent_password()
    created_user = False
    if family is None:
        username = _unique_username(_safe_username_from_phone(phone, guardian_name))
        user = User.objects.create_user(username=username, password=password)
        user.first_name = guardian_name
        user.save(update_fields=["first_name"])
        created_user = True
        family = Family.objects.create(
            school=school,
            user=user,
            source=source if source in dict(Family.SOURCE_CHOICES) else "manual",
            guardian_name=guardian_name,
            relation=relation,
            phone=phone,
            identity_type=identity_type,
            identity_number=identity_number,
            openemis_data=openemis_data or {},
            secondary_phone=extra_fields.get("secondary_phone", ""),
            email=extra_fields.get("email", ""),
            job_title=extra_fields.get("job_title", ""),
            address=extra_fields.get("address", ""),
            medical_notes=extra_fields.get("medical_notes", ""),
        )
    else:
        changed = []
        if not family.user_id:
            username = _unique_username(_safe_username_from_phone(phone, guardian_name))
            family.user = User.objects.create_user(username=username, password=password)
            family.user.first_name = guardian_name
            family.user.save(update_fields=["first_name"])
            changed.append("user")
            created_user = True
        values = {
            "guardian_name": guardian_name,
            "relation": relation,
            "phone": phone,
            "identity_type": identity_type,
            "identity_number": identity_number,
        }
        if source == "openemis":
            values["source"] = "openemis"
        if openemis_data:
            values["openemis_data"] = openemis_data
        for field in ("secondary_phone", "email", "job_title", "address", "medical_notes"):
            if field in extra_fields and extra_fields[field] not in (None, ""):
                values[field] = extra_fields[field]
        if school and not family.school_id:
            values["school"] = school
        for field, value in values.items():
            if value not in (None, "") and getattr(family, field) != value:
                setattr(family, field, value)
                changed.append(field)
        if changed:
            family.save(update_fields=list(dict.fromkeys(changed + ["updated_at"])))

    if not family.family_code:
        family.family_code = f"FAM-{family.pk:06d}"
        family.save(update_fields=["family_code", "updated_at"])

    _ensure_user_profile(
        family.user,
        school=school,
        guardian_name=guardian_name,
        phone=phone,
    )

    # Exactly one active family account per student.
    FamilyStudent.objects.filter(student=student, is_active=True).exclude(family=family).update(is_active=False)
    link, _ = FamilyStudent.objects.get_or_create(
        family=family,
        student=student,
        defaults={"relation": relation, "is_active": True},
    )
    link_changed = []
    if link.relation != relation:
        link.relation = relation
        link_changed.append("relation")
    if not link.is_active:
        link.is_active = True
        link_changed.append("is_active")
    if link_changed:
        link.save(update_fields=link_changed)

    # Keep student contact snapshots synchronized for lists and legacy reports.
    student_changed = []
    if guardian_name and student.guardian_name != guardian_name:
        student.guardian_name = guardian_name
        student_changed.append("guardian_name")
    if phone and student.phone != phone:
        student.phone = phone
        student_changed.append("phone")
    if student_changed:
        student.save(update_fields=student_changed + ["updated_at"])

    family.initial_username = family.user.username
    family.initial_password = password if created_user else ""
    family.account_created_now = created_user
    return family


@transaction.atomic
def ensure_family_account(family):
    """Create or repair the login account for an existing family."""
    password = initial_parent_password()
    created = False
    if family.user_id:
        user = family.user
    else:
        username = _unique_username(
            _safe_username_from_phone(
                family.phone,
                family.guardian_name or f"family{family.pk}",
            )
        )
        user = User.objects.create_user(username=username, password=password)
        user.first_name = family.guardian_name or "ولي أمر"
        user.save(update_fields=["first_name"])
        family.user = user
        family.save(update_fields=["user", "updated_at"])
        created = True

    _ensure_user_profile(
        user,
        school=family.school,
        guardian_name=family.guardian_name,
        phone=normalize_phone(family.phone),
    )
    return user, password, created


@transaction.atomic
def reset_family_password(family):
    user, _, _ = ensure_family_account(family)
    password = initial_parent_password()
    user.set_password(password)
    user.is_active = True
    user.save(update_fields=["password", "is_active"])
    return user, password


@transaction.atomic
def update_family_identity(
    family,
    *,
    guardian_name,
    phone,
    national_id="",
    identity_type="national",
    identity_number="",
    relation=None,
):
    """Update the single canonical parent identity and its student snapshots."""
    guardian_name = (guardian_name or "").strip()
    phone = normalize_phone(phone)
    identity_number = normalize_identifier(identity_number or national_id)
    identity_type = identity_type if identity_type in dict(Family.IDENTITY_TYPES) else "other"
    if not guardian_name or not phone:
        raise ValidationError("اسم ولي الأمر ورقم الهاتف مطلوبان.")

    others = Family.objects.filter(school=family.school, is_active=True).exclude(pk=family.pk)
    if identity_number and others.filter(identity_number=identity_number).exists():
        raise ValidationError("رقم الهوية مرتبط بملف ولي أمر آخر. استخدم الملف الموجود بدل إنشاء تعارض.")
    if phone and others.filter(phone=phone).exists():
        raise ValidationError("رقم الهاتف مرتبط بملف ولي أمر آخر. استخدم الملف الموجود أو أداة الدمج.")

    family.guardian_name = guardian_name
    family.phone = phone
    family.identity_type = identity_type
    family.identity_number = identity_number
    update_fields = ["guardian_name", "phone", "identity_type", "identity_number", "updated_at"]
    if relation is not None:
        family.relation = relation or "ولي أمر"
        update_fields.append("relation")
    family.save(update_fields=update_fields)

    if family.user_id:
        family.user.first_name = guardian_name[:150]
        family.user.save(update_fields=["first_name"])
        _ensure_user_profile(family.user, school=family.school, guardian_name=guardian_name, phone=phone)

    for link in FamilyStudent.objects.filter(family=family, is_active=True).select_related("student"):
        student = link.student
        student.guardian_name = guardian_name
        student.phone = phone
        student.save(update_fields=["guardian_name", "phone", "updated_at"])
    return family
