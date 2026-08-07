from .grade_names import (
    grade_name_key,
    normalize_grade_display_name,
    normalize_section_name,
    section_name_key,
)
from .models import Grade, Section


def resolve_grade(*, school, name, defaults=None):
    """Resolve or create the one canonical grade for a normalized name."""
    display_name = normalize_grade_display_name(name)
    key = grade_name_key(display_name)
    if not key:
        raise ValueError("اسم الصف مطلوب.")
    for grade in Grade.objects.filter(school=school).order_by("pk"):
        if grade_name_key(grade.name) == key:
            return grade, False
    values = {"name": display_name}
    values.update(defaults or {})
    return Grade.objects.create(school=school, **values), True


def resolve_section(*, academic_year, branch, grade, name, defaults=None):
    """Resolve or create one section inside the canonical academic structure."""
    section_name = normalize_section_name(name, grade.name)
    if not section_name:
        raise ValueError("اسم الشعبة مطلوب.")
    wanted_key = section_name_key(section_name, grade.name)
    candidates = Section.objects.filter(
        academic_year=academic_year,
        branch=branch,
        grade=grade,
    ).order_by("pk")
    for existing in candidates.only("pk", "name", "grade"):
        if section_name_key(existing.name, grade.name) == wanted_key:
            return existing, False
    values = {"name": section_name}
    values.update(defaults or {})
    values["name"] = section_name
    return Section.objects.create(
        academic_year=academic_year,
        branch=branch,
        grade=grade,
        **values,
    ), True
