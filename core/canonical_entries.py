"""Canonical OPAL data-entry definitions.

This module is deliberately small and dependency-light.  It documents the
single approved model and operational entry route for each core domain so
views, tests, integrations and future updates can refer to one source of
truth without introducing a parallel workflow.
"""

CANONICAL_MODELS = {
    "student": "students.Student",
    "teacher": "teachers.Teacher",
    "grade": "academics.Grade",
    "section": "academics.Section",
    "mark": "exams.StudentMark",
}

CANONICAL_ENTRY_ROUTES = {
    "student": "admissions:direct_registration",
    "teacher": "teachers:teacher_create",
    "grade": "academics:academic_structure",
    "section": "academics:academic_structure",
    "mark": "exams:exam_marks_bulk",
}

# Routes remain available as compatibility redirects.  They must never create
# a second record or render a second data-entry form.
LEGACY_ENTRY_ROUTES = {
    "students:student_create": "admissions:direct_registration",
    "academics:student_create": "admissions:direct_registration",
    "academics:student_admission": "admissions:direct_registration",
    "academics:grade_create": "academics:academic_structure",
    "academics:grade_update": "academics:academic_structure",
    "academics:section_create": "academics:academic_structure",
    "academics:section_update": "academics:academic_structure",
    "exams:mark_create": "exams:exam_list",
    "teachers:portal_marks": "exams:exam_marks_bulk",
}
