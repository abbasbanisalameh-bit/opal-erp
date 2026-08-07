from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("parent_portal", "0011_family_financial_policy"),
        ("teachers", "0010_payroll_advances"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherMonthlyEvaluation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period", models.DateField(db_index=True, help_text="يحفظ اليوم الأول من الشهر.", verbose_name="شهر التقييم")),
                ("teaching_quality_rating", models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="جودة التدريس")),
                ("electronic_services_rating", models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="الخدمات الإلكترونية")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("family", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_evaluations", to="parent_portal.family")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="parent_evaluations", to="teachers.teacher")),
            ],
            options={"verbose_name": "تقييم ولي الأمر للمعلم", "verbose_name_plural": "تقييمات أولياء الأمور للمعلمين", "ordering": ["-period", "teacher__full_name"]},
        ),
        migrations.AddConstraint(
            model_name="teachermonthlyevaluation",
            constraint=models.UniqueConstraint(fields=("family", "teacher", "period"), name="uniq_family_teacher_month_eval"),
        ),
    ]
