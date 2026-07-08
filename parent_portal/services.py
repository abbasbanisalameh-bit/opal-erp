from django.contrib.auth.models import User
from django.db import transaction
from core.models import School
from accounts.models import Role, UserProfile
from .models import Family, FamilyStudent, ParentProfile


def _safe_username_from_phone(phone):
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if digits:
        return f"parent_{digits[-10:]}"
    return "parent_user"


@transaction.atomic
def create_or_update_parent_family_for_student(student, guardian_name="", phone="", school=None):
    school = school or School.objects.filter(is_active=True).first()
    guardian_name = guardian_name or student.guardian_name or "ولي أمر"
    phone = phone or student.phone or ""

    family = None
    if phone:
        family = Family.objects.filter(phone=phone).first()
    if family is None and guardian_name:
        family = Family.objects.filter(guardian_name__iexact=guardian_name).first()

    if family is None:
        username_base = _safe_username_from_phone(phone)
        username = username_base
        counter = 1
        while User.objects.filter(username=username).exists():
            counter += 1
            username = f"{username_base}_{counter}"
        user = User.objects.create_user(username=username, password=phone[-6:] if len(phone) >= 6 else "opal12345")
        user.first_name = guardian_name
        user.save(update_fields=["first_name"])
        parent_role, _ = Role.objects.get_or_create(code="parent", defaults={"name": "ولي أمر", "description": "حساب ولي أمر"})
        UserProfile.objects.get_or_create(
            user=user,
            defaults={"school": school, "role": parent_role, "full_name": guardian_name, "phone": phone, "is_school_user": False},
        )
        family = Family.objects.create(school=school, user=user, guardian_name=guardian_name, phone=phone)
    else:
        if not family.user:
            username = _safe_username_from_phone(phone)
            counter = 1
            base = username
            while User.objects.filter(username=username).exists():
                counter += 1
                username = f"{base}_{counter}"
            family.user = User.objects.create_user(username=username, password=phone[-6:] if len(phone) >= 6 else "opal12345")
        if not family.guardian_name and guardian_name:
            family.guardian_name = guardian_name
        if not family.phone and phone:
            family.phone = phone
        family.save()

    FamilyStudent.objects.get_or_create(family=family, student=student, defaults={"relation": "ولي أمر"})
    ParentProfile.objects.get_or_create(user=family.user, defaults={"student": student, "phone": phone})
    return family
