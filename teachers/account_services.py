import re
import secrets
import string

from django.contrib.auth.models import Group, User
from django.db import transaction

from accounts.models import Role, UserProfile


def _username_seed(teacher):
    seed = (teacher.employee_number or "").strip().lower()
    seed = re.sub(r"[^a-z0-9_.-]+", "", seed)
    return seed or f"teacher{teacher.pk}"


def unique_username(teacher, requested=""):
    base = re.sub(r"[^a-zA-Z0-9_.-]+", "", (requested or "").strip().lower()) or _username_seed(teacher)
    candidate = base
    index = 1
    while User.objects.filter(username=candidate).exists():
        index += 1
        candidate = f"{base}{index}"
    return candidate


def temporary_password(length=12):
    alphabet = string.ascii_letters + string.digits
    # Guarantee a mixed password while keeping it easy to type on a phone.
    value = [secrets.choice(string.ascii_uppercase), secrets.choice(string.ascii_lowercase), secrets.choice(string.digits)]
    value.extend(secrets.choice(alphabet) for _ in range(max(0, length - len(value))))
    secrets.SystemRandom().shuffle(value)
    return "".join(value)


def _sync_profile(user, teacher):
    role, _ = Role.objects.get_or_create(code="teacher", defaults={"name": "معلم", "description": "حساب بوابة المعلم"})
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.school = teacher.school
    profile.branch = teacher.branch
    profile.role = role
    profile.full_name = teacher.full_name
    profile.phone = teacher.phone
    profile.is_school_user = True
    profile.save()


@transaction.atomic
def create_teacher_account(teacher, username=""):
    if teacher.user_id:
        raise ValueError("المعلم مرتبط بحساب مستخدم بالفعل.")
    username = unique_username(teacher, username)
    password = temporary_password()
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=teacher.full_name[:150],
        email=teacher.email or "",
        is_active=teacher.is_active,
        is_staff=False,
    )
    group, _ = Group.objects.get_or_create(name="Teachers")
    user.groups.add(group)
    teacher.user = user
    teacher.save(update_fields=["user"])
    _sync_profile(user, teacher)
    return user, password


@transaction.atomic
def reset_teacher_password(teacher):
    if not teacher.user_id:
        raise ValueError("لا يوجد حساب مستخدم مرتبط بهذا المعلم.")
    password = temporary_password()
    teacher.user.set_password(password)
    teacher.user.is_active = teacher.is_active
    teacher.user.save(update_fields=["password", "is_active"])
    _sync_profile(teacher.user, teacher)
    return password
