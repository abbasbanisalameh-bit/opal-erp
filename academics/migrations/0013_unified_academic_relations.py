from datetime import date

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


def normalize_identifier(value):
    table = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
    return "".join(ch for ch in str(value or "").translate(table).upper() if ch.isalnum())


def normalize_phone(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def migrate_relations(apps, schema_editor):
    School = apps.get_model("core", "School")
    AcademicYear = apps.get_model("core", "AcademicYear")
    Grade = apps.get_model("academics", "Grade")
    Section = apps.get_model("academics", "Section")
    Subject = apps.get_model("academics", "Subject")
    Enrollment = apps.get_model("academics", "Enrollment")
    Guardian = apps.get_model("academics", "Guardian")
    StudentGuardian = apps.get_model("academics", "StudentGuardian")
    Family = apps.get_model("parent_portal", "Family")
    FamilyStudent = apps.get_model("parent_portal", "FamilyStudent")

    fallback_school = School.objects.first()
    if fallback_school is None and (Section.objects.filter(academic_year__isnull=True).exists() or Subject.objects.filter(grade__isnull=True).exists() or Enrollment.objects.filter(grade__isnull=True).exists()):
        fallback_school = School.objects.create(name="مدرسة مرحّلة", official_name="مدرسة مرحّلة")

    def year_for_school(school):
        year = AcademicYear.objects.filter(school=school, is_current=True).first() or AcademicYear.objects.filter(school=school).order_by("-start_date").first()
        if year:
            return year
        return AcademicYear.objects.create(
            school=school,
            name="عام دراسي مرحّل",
            start_date=date(2025, 9, 1),
            midyear_break_start=date(2026, 1, 16),
            midyear_break_end=date(2026, 1, 31),
            end_date=date(2026, 6, 30),
            is_current=False,
        )

    fallback_grade = None
    if fallback_school:
        fallback_grade = Grade.objects.filter(school=fallback_school).order_by("order", "id").first()
        if fallback_grade is None:
            fallback_grade = Grade.objects.create(school=fallback_school, name="صف غير مصنف", order=999, is_active=False)

    for section in Section.objects.filter(academic_year__isnull=True).select_related("branch"):
        section.academic_year = year_for_school(section.branch.school)
        if Section.objects.filter(academic_year=section.academic_year, branch=section.branch, grade=section.grade, name=section.name).exclude(pk=section.pk).exists():
            section.name = f"{section.name}-{section.pk}"
        section.save(update_fields=["academic_year", "name"])

    for enrollment in Enrollment.objects.filter(grade__isnull=True).select_related("section"):
        grade = enrollment.section.grade if enrollment.section_id else fallback_grade or Grade.objects.order_by("id").first()
        if grade:
            enrollment.grade = grade
            enrollment.save(update_fields=["grade"])

    for subject in Subject.objects.filter(grade__isnull=True):
        grade = fallback_grade or Grade.objects.order_by("id").first()
        if grade:
            subject.grade = grade
            subject.save(update_fields=["grade"])

    # Make legacy subject duplicates distinct before adding canonical constraints.
    seen_names = set()
    seen_codes = set()
    for subject in Subject.objects.all().order_by("id"):
        name = (subject.name or "مادة").strip()
        code = (subject.code or "").strip().upper()
        name_key = (subject.grade_id, name.lower())
        if name_key in seen_names:
            name = f"{name}-{subject.pk}"
        seen_names.add((subject.grade_id, name.lower()))
        code_key = (subject.grade_id, code)
        if code and code_key in seen_codes:
            code = f"{code}-{subject.pk}"
        if code:
            seen_codes.add((subject.grade_id, code))
        subject.name = name
        subject.code = code
        subject.save(update_fields=["name", "code"])

    # Copy every legacy guardian link into the canonical Family/FamilyStudent path.
    for link in StudentGuardian.objects.select_related("guardian", "student").all().order_by("id"):
        guardian = link.guardian
        identity = normalize_identifier(guardian.national_id)
        phone = normalize_phone(guardian.phone)
        family = None
        if identity:
            family = Family.objects.filter(school_id=guardian.school_id, identity_number=identity).first()
        if family is None and phone:
            family = Family.objects.filter(school_id=guardian.school_id, phone=phone, is_active=True).first()
        if family is None:
            family = Family.objects.create(
                school_id=guardian.school_id,
                guardian_name=guardian.full_name or "ولي أمر",
                relation=dict(Guardian._meta.get_field("relation").choices).get(guardian.relation, guardian.relation or "ولي أمر"),
                identity_type="national",
                identity_number=identity,
                phone=phone,
                secondary_phone=normalize_phone(guardian.secondary_phone),
                email=guardian.email or "",
                job_title=guardian.job_title or "",
                address=guardian.address or "",
                medical_notes=getattr(guardian, "medical_notes", "") or "",
                family_code="",
                source="manual",
                is_active=guardian.is_active,
            )
            family.family_code = f"FAM-{family.pk:06d}"
            family.save(update_fields=["family_code"])
        FamilyStudent.objects.filter(student_id=link.student_id, is_active=True).exclude(family_id=family.pk).update(is_active=False)
        FamilyStudent.objects.update_or_create(
            family_id=family.pk,
            student_id=link.student_id,
            defaults={"relation": family.relation or "ولي أمر", "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0012_academic_structure"),
        ("core", "0005_unified_two_semesters"),
        ("parent_portal", "0008_unified_family_source"),
        ("students", "0008_unified_student_source"),
    ]
    operations = [
        migrations.RunPython(migrate_relations, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(name="studentguardian", unique_together=set()),
        migrations.AlterField(model_name="section", name="academic_year", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sections", to="core.academicyear")),
        migrations.AlterField(model_name="enrollment", name="grade", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="academics.grade")),
        migrations.AlterField(model_name="subject", name="grade", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subjects", to="academics.grade")),
        migrations.AddConstraint(model_name="subject", constraint=models.UniqueConstraint(fields=("grade", "name"), name="uniq_subject_name_per_grade")),
        migrations.AddConstraint(model_name="subject", constraint=models.UniqueConstraint(condition=~Q(code=""), fields=("grade", "code"), name="uniq_subject_code_per_grade")),
        migrations.DeleteModel(name="StudentGuardian"),
        migrations.DeleteModel(name="Guardian"),
    ]
