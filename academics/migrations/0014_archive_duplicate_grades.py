import re
import unicodedata

from django.db import migrations


_ARABIC_TRANSLATION = str.maketrans({
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ى": "ي",
    "ؤ": "و",
    "ئ": "ي",
    "ة": "ه",
})


def grade_key(value):
    text = re.sub(r"\s+", " ", str(value or "").strip()).translate(_ARABIC_TRANSLATION)
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    text = text.replace("ـ", "").lower()
    return re.sub(r"[^0-9a-z\u0621-\u064a]+", "", text)


def archive_duplicate_grades(apps, schema_editor):
    Grade = apps.get_model("academics", "Grade")
    Section = apps.get_model("academics", "Section")
    Enrollment = apps.get_model("academics", "Enrollment")
    Subject = apps.get_model("academics", "Subject")
    GradeFee = apps.get_model("admissions", "GradeFee")

    grouped = {}
    for grade in Grade.objects.all().order_by("school_id", "order", "id"):
        key = (grade.school_id, grade_key(grade.name))
        if not key[1]:
            continue
        grouped.setdefault(key, []).append(grade)

    for grades in grouped.values():
        if len(grades) < 2:
            continue

        def usage_score(grade):
            return (
                Section.objects.filter(grade_id=grade.pk).count()
                + Enrollment.objects.filter(grade_id=grade.pk).count()
                + Subject.objects.filter(grade_id=grade.pk).count()
                + GradeFee.objects.filter(grade_id=grade.pk).count()
            )

        canonical = sorted(
            grades,
            key=lambda grade: (-usage_score(grade), grade.order, grade.pk),
        )[0]
        Grade.objects.filter(pk=canonical.pk).update(is_active=True)
        Grade.objects.filter(pk__in=[grade.pk for grade in grades if grade.pk != canonical.pk]).update(
            is_active=False
        )


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0013_unified_academic_relations"),
        ("admissions", "0005_unified_guardian_identity"),
    ]

    operations = [
        migrations.RunPython(archive_duplicate_grades, migrations.RunPython.noop),
    ]
