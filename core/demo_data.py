"""Compatibility imports for older commands and extensions."""

from .system_data import reset_all_operational_data, seed_system_data


def seed_demo_school(*, student_count=500, teacher_count=50, user=None):
    return seed_system_data(student_count=500, teacher_count=50, guardian_count=300, user=user)


def reset_demo_school(*, user=None):
    return reset_all_operational_data(keep_user=user)
