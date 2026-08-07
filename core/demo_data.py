"""Compatibility imports for older commands and extensions."""

from .system_data import DEMO_TEACHER_COUNT, reset_all_operational_data, seed_system_data


def seed_demo_school(*, student_count=500, teacher_count=DEMO_TEACHER_COUNT, user=None):
    return seed_system_data(user=user)


def reset_demo_school(*, user=None):
    return reset_all_operational_data(keep_user=user)
