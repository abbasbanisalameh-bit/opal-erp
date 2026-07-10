from django.contrib.auth.models import User
from django.db import transaction
from core.models import School
from accounts.models import Role, UserProfile
from .models import Family, FamilyStudent, ParentProfile


DEFAULT_PARENT_PASSWORD = "opal12345"


def normalize_phone(phone):
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def initial_parent_password(phone):
    digits = normalize_phone(phone)
    return digits[-6:] if len(digits) >= 6 else DEFAULT_PARENT_PASSWORD


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
    digits = normalize_phone(phone)
    qs = Family.objects.all()
    if school:
        qs = qs.filter(school=school)
    if national_id:
        found = qs.filter(national_id__iexact=national_id.strip()).first()
        if found:
            return found
    if digits:
        found = qs.filter(phone__icontains=digits[-9:]).first() or qs.filter(phone=phone).first()
        if found:
            return found
    if guardian_name:
        found = qs.filter(guardian_name__iexact=guardian_name.strip()).first()
        if found:
            return found
    return None


@transaction.atomic
def create_or_update_parent_family_for_student(student, guardian_name="", phone="", school=None, national_id=""):
    school = school or School.objects.filter(is_active=True).first()
    guardian_name = (guardian_name or student.guardian_name or "ولي أمر").strip()
    phone = (phone or student.phone or "").strip()
    national_id = (national_id or "").strip()

    family = find_existing_family(school=school, guardian_name=guardian_name, phone=phone, national_id=national_id)
    created_user = False
    password = initial_parent_password(phone)

    if family is None:
        username = _unique_username(_safe_username_from_phone(phone, guardian_name))
        user = User.objects.create_user(username=username, password=password)
        created_user = True
        user.first_name = guardian_name
        user.save(update_fields=["first_name"])
        family = Family.objects.create(school=school, user=user, guardian_name=guardian_name, phone=phone, national_id=national_id)
    else:
        if not family.user:
            username = _unique_username(_safe_username_from_phone(phone, guardian_name))
            family.user = User.objects.create_user(username=username, password=password)
            created_user = True
        if guardian_name and not family.guardian_name:
            family.guardian_name = guardian_name
        if phone and not family.phone:
            family.phone = phone
        if national_id and not family.national_id:
            family.national_id = national_id
        if school and not family.school:
            family.school = school
        family.save()

    parent_role, _ = Role.objects.get_or_create(code="parent", defaults={"name": "ولي أمر", "description": "حساب ولي أمر"})
    profile, _ = UserProfile.objects.get_or_create(user=family.user)
    changed = []
    if school and profile.school_id != getattr(school, "id", None):
        profile.school = school
        changed.append("school")
    if profile.role_id != getattr(parent_role, "id", None):
        profile.role = parent_role
        changed.append("role")
    if guardian_name and not profile.full_name:
        profile.full_name = guardian_name
        changed.append("full_name")
    if phone and not profile.phone:
        profile.phone = phone
        changed.append("phone")
    if profile.is_school_user:
        profile.is_school_user = False
        changed.append("is_school_user")
    if changed:
        profile.save(update_fields=changed)

    FamilyStudent.objects.get_or_create(family=family, student=student, defaults={"relation": "ولي أمر"})
    ParentProfile.objects.get_or_create(user=family.user, defaults={"student": student, "phone": phone})

    # Attach transient info for the current receipt only; no database migration needed.
    family.initial_username = family.user.username if family.user else ""
    family.initial_password = password
    family.account_created_now = created_user
    return family


# ===== OPAL FAMILY V2 ENGINE =====
def create_or_update_parent_family_for_student(student, guardian_name="", phone="", school=None, national_id=""):
    from django.contrib.auth.models import User
    from accounts.models import UserProfile, Role
    from parent_portal.models import Family, FamilyStudent, ParentProfile

    guardian_name = (guardian_name or student.guardian_name or "").strip()
    phone = normalize_phone(phone or student.phone or "")
    national_id = (national_id or "").strip()

    family = None

    if national_id:
        family = Family.objects.filter(guardian_national_id=national_id).first()

    if family is None and phone:
        family = Family.objects.filter(phone=phone).first()

    if family is None and guardian_name and phone:
        family = Family.objects.filter(guardian_name__iexact=guardian_name, phone=phone).first()

    created_user = False
    password = ""

    if family is None:
        base_username = "parent_" + (national_id or phone or str(student.id)).replace(" ", "").replace("+", "")
        username = base_username
        i = 1
        while User.objects.filter(username=username).exists():
            i += 1
            username = f"{base_username}_{i}"

        password = initial_parent_password(phone or national_id or str(student.id))
        user = User.objects.create_user(username=username, password=password)
        created_user = True

        family = Family.objects.create(
            school=school,
            guardian_name=guardian_name or "ولي أمر",
            phone=phone,
            guardian_national_id=national_id,
            user=user,
        )
    else:
        if national_id and not getattr(family, "guardian_national_id", ""):
            family.guardian_national_id = national_id
        if phone and not family.phone:
            family.phone = phone
        if guardian_name and not family.guardian_name:
            family.guardian_name = guardian_name
        if school and not family.school:
            family.school = school
        family.save()

    if not family.family_code:
        family.family_code = f"FAM-{family.id:06d}"
        family.save(update_fields=["family_code"])

    parent_role, _ = Role.objects.get_or_create(
        code="parent",
        defaults={"name": "ولي أمر", "description": "حساب ولي أمر"}
    )

    profile, _ = UserProfile.objects.get_or_create(user=family.user)
    changed = []

    if school and profile.school_id != getattr(school, "id", None):
        profile.school = school
        changed.append("school")

    if profile.role_id != getattr(parent_role, "id", None):
        profile.role = parent_role
        changed.append("role")

    if guardian_name and not profile.full_name:
        profile.full_name = guardian_name
        changed.append("full_name")

    if phone and not profile.phone:
        profile.phone = phone
        changed.append("phone")

    if profile.is_school_user:
        profile.is_school_user = False
        changed.append("is_school_user")

    if changed:
        profile.save(update_fields=changed)

    FamilyStudent.objects.get_or_create(
        family=family,
        student=student,
        defaults={"relation": "ولي أمر"}
    )

    ParentProfile.objects.get_or_create(
        user=family.user,
        defaults={"student": student, "phone": phone}
    )

    family.initial_username = family.user.username if family.user else ""
    family.initial_password = password
    family.account_created_now = created_user

    return family
