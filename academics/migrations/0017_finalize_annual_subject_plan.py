"""Finalize annual Subject constraints and normalize stored section labels."""

import re

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalise_section(value, grade_name=""):
    text = _clean(value)
    grade = _clean(grade_name)
    if grade:
        pattern = re.compile(re.escape(grade), re.IGNORECASE)
        previous = None
        while previous != text:
            previous = text
            text = pattern.sub(" ", text).strip()
    text = re.sub(r"^[\s\-–—,:،/|]+|[\s\-–—,:،/|]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^(?:ال)?شعب(?:ة|ه)\s*", "", text, flags=re.IGNORECASE).strip()
    if not text or text in {"الشعبة العامة", "شعبة عامة", "العامة"}:
        text = "عامة"
    return f"شعبة {text}"


def normalize_sections_and_validate(apps, schema_editor):
    Section = apps.get_model("academics", "Section")
    Student = apps.get_model("students", "Student")
    Lifecycle = apps.get_model("academics", "StudentLifecycleEvent")
    Subject = apps.get_model("academics", "Subject")
    TeacherAssignment = apps.get_model("teachers", "TeacherAssignment")
    TimetableEntry = apps.get_model("timetable", "TimetableEntry")
    Exam = apps.get_model("exams", "Exam")
    SemesterSubjectResult = apps.get_model("exams", "SemesterSubjectResult")
    AnnualSubjectResult = apps.get_model("exams", "AnnualSubjectResult")

    proposed = {}
    collisions = {}
    for section in Section.objects.select_related("grade").all().order_by("pk"):
        normalized = _normalise_section(section.name, section.grade.name)
        key = (section.academic_year_id, section.branch_id, section.grade_id, normalized.casefold())
        if key in collisions:
            collisions[key].append(section.pk)
        else:
            collisions[key] = [section.pk]
        proposed[section.pk] = normalized
    conflict_rows = [ids for ids in collisions.values() if len(ids) > 1]
    if conflict_rows:
        raise RuntimeError(
            "Section name normalization would create duplicate rows; resolve these section IDs first: "
            + "; ".join(",".join(str(pk) for pk in ids) for ids in conflict_rows)
        )
    for pk, normalized in proposed.items():
        Section.objects.filter(pk=pk).update(name=normalized)

    for student in Student.objects.all().only("pk", "grade", "section"):
        normalized = _normalise_section(student.section, student.grade) if student.section else ""
        if normalized != student.section:
            Student.objects.filter(pk=student.pk).update(section=normalized)

    for event in Lifecycle.objects.all().only(
        "pk", "from_grade_snapshot", "from_section_snapshot", "to_grade_snapshot", "to_section_snapshot"
    ):
        updates = {}
        if event.from_section_snapshot:
            updates["from_section_snapshot"] = _normalise_section(
                event.from_section_snapshot, event.from_grade_snapshot
            )
        if event.to_section_snapshot:
            updates["to_section_snapshot"] = _normalise_section(
                event.to_section_snapshot, event.to_grade_snapshot
            )
        if updates:
            Lifecycle.objects.filter(pk=event.pk).update(**updates)

    for subject in Subject.objects.select_related("academic_year", "grade").all():
        if not subject.academic_year_id or not subject.weekly_periods or not subject.canonical_key or not subject.color:
            raise RuntimeError(f"Subject {subject.pk} does not satisfy the final annual plan contract.")
        if subject.academic_year.school_id != subject.grade.school_id:
            raise RuntimeError(f"Subject {subject.pk} links an academic year and grade from different schools.")

    checks = [
        (TeacherAssignment, lambda row: (row.academic_year_id, row.section.grade_id)),
        (TimetableEntry, lambda row: (row.academic_year_id, row.section.grade_id)),
        (Exam, lambda row: (row.academic_year_id, row.grade_id)),
        (SemesterSubjectResult, lambda row: (row.semester.academic_year_id, row.subject.grade_id)),
        (AnnualSubjectResult, lambda row: (row.academic_year_id, row.subject.grade_id)),
    ]
    for Model, owner_scope in checks:
        related = ["subject"]
        if Model in {TeacherAssignment, TimetableEntry}:
            related.append("section")
        elif Model is SemesterSubjectResult:
            related.append("semester")
        for row in Model.objects.select_related(*related).all().order_by("pk"):
            year_id, grade_id = owner_scope(row)
            if row.subject.academic_year_id != year_id or row.subject.grade_id != grade_id:
                raise RuntimeError(
                    f"{Model._meta.label} {row.pk} still references Subject {row.subject_id} from a different year/grade."
                )


def reverse_sections(apps, schema_editor):
    # Short section labels are the canonical representation and are not expanded
    # back to duplicated grade + section strings.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0016_annual_subject_plan_stage"),
        ("curriculum", "0003_remove_parallel_curriculum"),
        ("teachers", "0014_subject_plan_single_source"),
        ("timetable", "0008_subject_plan_protection"),
    ]

    operations = [
        migrations.RunPython(normalize_sections_and_validate, reverse_sections),
        migrations.AlterModelOptions(
            name="subject",
            options={
                "ordering": ["academic_year", "grade__order", "name"],
                "verbose_name": "مادة دراسية",
                "verbose_name_plural": "المواد الدراسية",
            },
        ),
        migrations.AlterField(
            model_name="subject",
            name="academic_year",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subjects",
                to="core.academicyear",
            ),
        ),
        migrations.AlterField(
            model_name="subject",
            name="weekly_periods",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="عدد الحصص أسبوعيًا"),
        ),
        migrations.AddConstraint(
            model_name="subject",
            constraint=models.UniqueConstraint(
                fields=("academic_year", "grade", "name"),
                name="uniq_subject_name_per_year_grade",
            ),
        ),
        migrations.AddConstraint(
            model_name="subject",
            constraint=models.UniqueConstraint(
                condition=~Q(code=""),
                fields=("academic_year", "grade", "code"),
                name="uniq_subject_code_per_year_grade",
            ),
        ),
    ]
