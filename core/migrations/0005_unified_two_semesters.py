from datetime import timedelta

from django.db import migrations, models
from django.db.models import Q


def normalize_structure(apps, schema_editor):
    Branch = apps.get_model("core", "Branch")
    AcademicYear = apps.get_model("core", "AcademicYear")
    Semester = apps.get_model("core", "Semester")

    for branch in Branch.objects.all().order_by("id"):
        duplicate = Branch.objects.filter(school_id=branch.school_id, name=branch.name).exclude(pk=branch.pk).order_by("id").first()
        if duplicate and duplicate.pk < branch.pk:
            branch.name = f"{branch.name}-{branch.pk}"
            branch.save(update_fields=["name"])

    for year in AcademicYear.objects.all().order_by("id"):
        if AcademicYear.objects.filter(school_id=year.school_id, name=year.name).exclude(pk=year.pk).exists():
            year.name = f"{year.name}-{year.pk}"
        duration = max((year.end_date - year.start_date).days, 4)
        midpoint = year.start_date + timedelta(days=duration // 2)
        break_start = midpoint
        break_end = midpoint
        if break_start <= year.start_date:
            break_start = year.start_date + timedelta(days=1)
        if break_end >= year.end_date:
            break_end = year.end_date - timedelta(days=1)
        year.midyear_break_start = break_start
        year.midyear_break_end = break_end
        year.save(update_fields=["name", "midyear_break_start", "midyear_break_end"])

        semesters = list(Semester.objects.filter(academic_year=year).order_by("start_date", "id"))
        while len(semesters) < 2:
            semesters.append(Semester.objects.create(
                academic_year=year,
                code=None,
                name="فصل مرحّل",
                start_date=year.start_date,
                end_date=year.end_date,
                is_current=False,
            ))
        for extra in semesters[2:]:
            extra.delete()
        first, second = semesters[:2]
        Semester.objects.filter(academic_year=year).update(code=None, is_current=False)
        first.code = "first"
        first.name = "الفصل الدراسي الأول"
        first.start_date = year.start_date
        first.end_date = break_start - timedelta(days=1)
        first.save(update_fields=["code", "name", "start_date", "end_date", "is_current"])
        second.code = "second"
        second.name = "الفصل الدراسي الثاني"
        second.start_date = break_end + timedelta(days=1)
        second.end_date = year.end_date
        second.save(update_fields=["code", "name", "start_date", "end_date", "is_current"])


class Migration(migrations.Migration):
    dependencies = [("core", "0004_dataintegrityrun_dataintegrityissue")]
    operations = [
        migrations.AlterModelOptions(name="semester", options={"ordering": ["academic_year__start_date", "code"]}),
        migrations.AddField(model_name="academicyear", name="midyear_break_start", field=models.DateField(null=True, verbose_name="بداية عطلة منتصف العام")),
        migrations.AddField(model_name="academicyear", name="midyear_break_end", field=models.DateField(null=True, verbose_name="نهاية عطلة منتصف العام")),
        migrations.AddField(model_name="semester", name="code", field=models.CharField(blank=True, choices=[("first", "الفصل الدراسي الأول"), ("second", "الفصل الدراسي الثاني")], max_length=10, null=True)),
        migrations.RunPython(normalize_structure, migrations.RunPython.noop),
        migrations.AlterField(model_name="academicyear", name="midyear_break_start", field=models.DateField(verbose_name="بداية عطلة منتصف العام")),
        migrations.AlterField(model_name="academicyear", name="midyear_break_end", field=models.DateField(verbose_name="نهاية عطلة منتصف العام")),
        migrations.AlterField(model_name="semester", name="code", field=models.CharField(choices=[("first", "الفصل الدراسي الأول"), ("second", "الفصل الدراسي الثاني")], max_length=10)),
        migrations.AddConstraint(model_name="academicyear", constraint=models.UniqueConstraint(fields=("school", "name"), name="uniq_academic_year_per_school")),
        migrations.AddConstraint(model_name="branch", constraint=models.UniqueConstraint(fields=("school", "name"), name="uniq_branch_per_school")),
        migrations.AddConstraint(model_name="semester", constraint=models.UniqueConstraint(fields=("academic_year", "code"), name="uniq_semester_code_per_year")),
    ]
