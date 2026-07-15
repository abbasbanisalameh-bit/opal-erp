from decimal import Decimal, ROUND_HALF_UP

import django.db.models.deletion
from django.db import migrations, models

ASSESSMENTS = [
    ("first", Decimal("20.00")),
    ("second", Decimal("20.00")),
    ("third", Decimal("20.00")),
    ("final", Decimal("40.00")),
]


def scale(value, old_max, new_max):
    value = Decimal(value or 0)
    old_max = Decimal(old_max or 100)
    if old_max <= 0:
        return Decimal("0.00")
    result = value / old_max * new_max
    return min(max(result, Decimal("0.00")), new_max).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_exams(apps, schema_editor):
    Exam = apps.get_model("exams", "Exam")
    StudentMark = apps.get_model("exams", "StudentMark")
    Semester = apps.get_model("core", "Semester")

    # Remove accidental duplicate marks defensively.
    seen_marks = set()
    for mark in StudentMark.objects.all().order_by("-updated_at", "-id"):
        key = (mark.exam_id, mark.student_id)
        if key in seen_marks:
            mark.delete()
        else:
            seen_marks.add(key)

    groups = {}
    for exam in Exam.objects.select_related("academic_year", "semester", "subject").all().order_by("academic_year_id", "grade_id", "subject_id", "exam_date", "id"):
        if exam.subject_id and exam.subject.grade_id and exam.grade_id != exam.subject.grade_id:
            exam.grade_id = exam.subject.grade_id
            exam.save(update_fields=["grade"])
        valid_semester = exam.semester if exam.semester_id and exam.semester.academic_year_id == exam.academic_year_id else None
        if valid_semester is None:
            semester_code = "first"
            if exam.exam_date and exam.academic_year.midyear_break_start and exam.exam_date >= exam.academic_year.midyear_break_start:
                semester_code = "second"
            valid_semester = Semester.objects.filter(academic_year_id=exam.academic_year_id, code=semester_code).first()
        if valid_semester is None:
            valid_semester = Semester.objects.filter(academic_year_id=exam.academic_year_id).order_by("code", "id").first()
        if valid_semester is None:
            continue
        exam.semester_id = valid_semester.pk
        exam.exam_type = f"legacy{exam.pk}"
        exam.save(update_fields=["semester", "exam_type", "grade"])
        groups.setdefault((exam.academic_year_id, valid_semester.pk, exam.grade_id, exam.subject_id), []).append(exam)

    for _key, exams in groups.items():
        keep = exams[:4]
        for index, exam in enumerate(keep):
            exam_type, maximum = ASSESSMENTS[index]
            old_max = Decimal(exam.max_mark or 100)
            for mark in StudentMark.objects.filter(exam_id=exam.pk):
                mark.mark = scale(mark.mark, old_max, maximum)
                mark.save(update_fields=["mark"])
            exam.exam_type = exam_type
            exam.max_mark = maximum
            exam.weight = maximum
            if not exam.name:
                exam.name = dict(ASSESSMENTS).get(exam_type, exam_type)
            exam.save(update_fields=["exam_type", "max_mark", "weight", "name", "semester", "grade"])

        for extra_index, extra in enumerate(exams[4:]):
            target = keep[extra_index % len(keep)] if keep else None
            if target:
                target_max = dict(ASSESSMENTS)[target.exam_type]
                old_max = Decimal(extra.max_mark or 100)
                for mark in StudentMark.objects.filter(exam_id=extra.pk):
                    converted = scale(mark.mark, old_max, target_max)
                    existing = StudentMark.objects.filter(exam_id=target.pk, student_id=mark.student_id).first()
                    if existing:
                        if converted > existing.mark:
                            existing.mark = converted
                            existing.notes = ((existing.notes or "") + "\nدُمجت علامة من تقييم قديم أثناء توحيد الامتحانات.").strip()
                            existing.save(update_fields=["mark", "notes"])
                    else:
                        mark.exam_id = target.pk
                        mark.mark = converted
                        mark.notes = ((mark.notes or "") + "\nنُقلت من تقييم قديم أثناء توحيد الامتحانات.").strip()
                        mark.save(update_fields=["exam", "mark", "notes"])
            extra.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("exams", "0004_exam_approved_at_exam_approved_by_exam_is_locked_and_more"),
        ("core", "0005_unified_two_semesters"),
        ("academics", "0013_unified_academic_relations"),
        ("students", "0008_unified_student_source"),
    ]
    operations = [
        migrations.AlterModelOptions(name="exam", options={"ordering": ["academic_year", "semester__code", "grade__order", "subject__name", "exam_type"]}),
        migrations.AlterUniqueTogether(name="studentmark", unique_together=set()),
        migrations.RunPython(normalize_exams, migrations.RunPython.noop),
        migrations.AlterField(model_name="exam", name="name", field=models.CharField(blank=True, max_length=200)),
        migrations.AlterField(model_name="exam", name="exam_type", field=models.CharField(choices=[("first", "الامتحان الأول"), ("second", "الامتحان الثاني"), ("third", "الامتحان الثالث"), ("final", "الامتحان النهائي")], max_length=30)),
        migrations.AlterField(model_name="exam", name="academic_year", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exams", to="core.academicyear")),
        migrations.AlterField(model_name="exam", name="semester", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exams", to="core.semester")),
        migrations.AlterField(model_name="exam", name="grade", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exams", to="academics.grade")),
        migrations.AlterField(model_name="exam", name="subject", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exams", to="academics.subject")),
        migrations.AlterField(model_name="exam", name="max_mark", field=models.DecimalField(decimal_places=2, default=20, editable=False, max_digits=6)),
        migrations.AlterField(model_name="exam", name="weight", field=models.DecimalField(decimal_places=2, default=20, editable=False, max_digits=5, verbose_name="وزن الامتحان")),
        migrations.AddConstraint(model_name="exam", constraint=models.UniqueConstraint(fields=("academic_year", "semester", "grade", "subject", "exam_type"), name="uniq_four_assessments_per_subject_term")),
        migrations.AddConstraint(model_name="studentmark", constraint=models.UniqueConstraint(fields=("exam", "student"), name="uniq_student_mark_per_exam")),
    ]
