import secrets
import string

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import Role, UserProfile
from core.models import School

from .models import Family, FamilyStudent


def normalize_phone(phone):
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def initial_parent_password(phone=""):
    """Return a one-time random password; never derive credentials from identity data."""
    alphabet = string.ascii_letters + string.digits
    value = [secrets.choice(string.ascii_uppercase), secrets.choice(string.ascii_lowercase), secrets.choice(string.digits)]
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


def find_existing_family(*, school=None, guardian_name="", phone="", national_id=""):
    """Find one authoritative family without falling back across schools."""
    digits = normalize_phone(phone)
    qs = Family.objects.all()
    if school:
        qs = qs.filter(school=school)
    if national_id:
        found = qs.filter(guardian_national_id__iexact=national_id.strip()).first()
        if found:
            return found
    if digits:
        found = qs.filter(phone=digits).first() or qs.filter(phone__icontains=digits[-9:]).first()
        if found:
            return found
    # Names are not identifiers. Falling back to a name can expose one family's
    # children to an unrelated guardian who happens to have the same name.
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
):
    """Create or repair the single Family/FamilyStudent parent-account path."""
    school = school or School.objects.filter(is_active=True).first()
    guardian_name = (guardian_name or student.guardian_name or "ولي أمر").strip()
    phone = normalize_phone(phone or student.phone or "")
    national_id = (national_id or "").strip()
    family = find_existing_family(
        school=school,
        guardian_name=guardian_name,
        phone=phone,
        national_id=national_id,
    )

    password = initial_parent_password(phone or national_id or str(student.pk))
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
            guardian_name=guardian_name,
            phone=phone,
            guardian_national_id=national_id,
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
        if guardian_name and not family.guardian_name:
            family.guardian_name = guardian_name
            changed.append("guardian_name")
        if phone and family.phone != phone:
            family.phone = phone
            changed.append("phone")
        if national_id and not family.guardian_national_id:
            family.guardian_national_id = national_id
            changed.append("guardian_national_id")
        if school and not family.school_id:
            family.school = school
            changed.append("school")
        if changed:
            family.save(update_fields=changed)

    if not family.family_code:
        family.family_code = f"FAM-{family.pk:06d}"
        family.save(update_fields=["family_code"])

    _ensure_user_profile(
        family.user,
        school=school,
        guardian_name=guardian_name,
        phone=phone,
    )
    # OPAL currently has one authoritative family account per student.
    FamilyStudent.objects.filter(student=student, is_active=True).exclude(family=family).update(is_active=False)
    link, _ = FamilyStudent.objects.get_or_create(
        family=family,
        student=student,
        defaults={"relation": "ولي أمر"},
    )
    if not link.is_active:
        link.is_active = True
        link.save(update_fields=["is_active"])

    family.initial_username = family.user.username
    family.initial_password = password if created_user else ""
    family.account_created_now = created_user
    return family


@transaction.atomic
def ensure_family_account(family):
    """Create or repair the login account for an existing family."""
    password = initial_parent_password(
        family.phone or family.guardian_national_id or str(family.pk)
    )
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
        family.save(update_fields=["user"])
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
    password = initial_parent_password(
        family.phone or family.guardian_national_id or str(family.pk)
    )
    user.set_password(password)
    user.is_active = True
    user.save(update_fields=["password", "is_active"])
    return user, password


@transaction.atomic
def update_family_identity(family, *, guardian_name, phone, national_id=""):
    """Update the canonical parent identity and synchronize its read-only copies."""
    guardian_name = (guardian_name or "").strip()
    phone = normalize_phone(phone)
    national_id = (national_id or "").strip()
    if not guardian_name or not phone:
        raise ValidationError("اسم ولي الأمر ورقم الهاتف مطلوبان.")

    others = Family.objects.filter(school=family.school).exclude(pk=family.pk)
    if national_id and others.filter(guardian_national_id__iexact=national_id).exists():
        raise ValidationError("الرقم الوطني مرتبط بأسرة أخرى. استخدم أداة الدمج بدل إنشاء تعارض.")
    if phone and others.filter(phone=phone).exists():
        raise ValidationError("رقم الهاتف مرتبط بأسرة أخرى. استخدم أداة الدمج بدل إنشاء تعارض.")

    family.guardian_name = guardian_name
    family.phone = phone
    family.guardian_national_id = national_id
    family.save(update_fields=["guardian_name", "phone", "guardian_national_id"])

    if family.user_id:
        family.user.first_name = guardian_name[:150]
        family.user.save(update_fields=["first_name"])
        _ensure_user_profile(family.user, school=family.school, guardian_name=guardian_name, phone=phone)

    from academics.models import Guardian, StudentGuardian

    for link in FamilyStudent.objects.filter(family=family, is_active=True).select_related("student"):
        student = link.student
        student.guardian_name = guardian_name
        student.phone = phone
        student.save(update_fields=["guardian_name", "phone", "updated_at"])
        guardian_link = StudentGuardian.objects.filter(student=student, is_primary=True).select_related("guardian").first()
        if guardian_link:
            guardian = guardian_link.guardian
            guardian.full_name = guardian_name
            guardian.phone = phone
            guardian.national_id = national_id
            guardian.save(update_fields=["full_name", "phone", "national_id"])
        elif family.school_id:
            guardian = Guardian.objects.create(
                school=family.school,
                full_name=guardian_name,
                relation="guardian",
                phone=phone,
                national_id=national_id,
            )
            StudentGuardian.objects.create(student=student, guardian=guardian, is_primary=True)
    return family
