from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0014_archive_duplicate_grades"),
        ("core", "0009_academic_lifecycle_states"),
        ("exams", "0006_alter_exam_options_and_more"),
        ("students", "0010_alter_student_is_demo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamCycle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("exam_type", models.CharField(choices=[("first", "الامتحان الأول"), ("second", "الامتحان الثاني"), ("third", "الامتحان الثالث"), ("final", "الامتحان النهائي")], max_length=30, verbose_name="نوع الدورة")),
                ("name", models.CharField(blank=True, max_length=200, verbose_name="اسم الدورة")),
                ("status", models.CharField(choices=[("open", "مفتوحة للمعلمين"), ("closed", "مغلقة")], db_index=True, default="open", max_length=20, verbose_name="الحالة")),
                ("opened_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                ("academic_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_cycles", to="core.academicyear")),
                ("semester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_cycles", to="core.semester")),
                ("opened_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opened_exam_cycles", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-academic_year__start_date", "semester__code", "exam_type"]},
        ),
        migrations.AddConstraint(
            model_name="examcycle",
            constraint=models.UniqueConstraint(fields=("academic_year", "semester", "exam_type"), name="uniq_exam_cycle_per_term_type"),
        ),
        migrations.AddField(
            model_name="exam",
            name="cycle",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="exams", to="exams.examcycle", verbose_name="الدورة الامتحانية العامة"),
        ),
        migrations.CreateModel(
            name="SemesterSubjectResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("score", models.DecimalField(decimal_places=2, max_digits=6, verbose_name="نتيجة الفصل من 100")),
                ("calculated_at", models.DateTimeField(auto_now=True)),
                ("semester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subject_results", to="core.semester")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="semester_subject_results", to="students.student")),
                ("subject", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="semester_results", to="academics.subject")),
            ],
            options={"ordering": ["student__full_name", "subject__name"]},
        ),
        migrations.AddConstraint(
            model_name="semestersubjectresult",
            constraint=models.UniqueConstraint(fields=("semester", "student", "subject"), name="uniq_term_student_subject_result"),
        ),
        migrations.CreateModel(
            name="AnnualSubjectResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("first_semester_score", models.DecimalField(decimal_places=2, max_digits=6)),
                ("second_semester_score", models.DecimalField(decimal_places=2, max_digits=6)),
                ("annual_score", models.DecimalField(decimal_places=2, max_digits=6, verbose_name="المعدل السنوي للمادة")),
                ("calculated_at", models.DateTimeField(auto_now=True)),
                ("academic_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="annual_subject_results", to="core.academicyear")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="annual_subject_results", to="students.student")),
                ("subject", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="annual_results", to="academics.subject")),
            ],
            options={"ordering": ["student__full_name", "subject__name"]},
        ),
        migrations.AddConstraint(
            model_name="annualsubjectresult",
            constraint=models.UniqueConstraint(fields=("academic_year", "student", "subject"), name="uniq_year_student_subject_result"),
        ),
        migrations.CreateModel(
            name="AnnualStudentResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("general_average", models.DecimalField(decimal_places=2, max_digits=6, verbose_name="المعدل السنوي العام")),
                ("subject_count", models.PositiveSmallIntegerField(default=0)),
                ("calculated_at", models.DateTimeField(auto_now=True)),
                ("academic_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="annual_student_results", to="core.academicyear")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="annual_results", to="students.student")),
            ],
            options={"ordering": ["student__full_name"]},
        ),
        migrations.AddConstraint(
            model_name="annualstudentresult",
            constraint=models.UniqueConstraint(fields=("academic_year", "student"), name="uniq_year_student_summary"),
        ),
    ]
