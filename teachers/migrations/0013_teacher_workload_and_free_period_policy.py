from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teachers", "0012_teacherperformancesnapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacher",
            name="weekly_teaching_load",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="الحد الأعلى للحصص التدريسية من الأحد إلى الخميس.",
                null=True,
                verbose_name="النصاب الأسبوعي المعتمد",
            ),
        ),
        migrations.AddField(
            model_name="teacher",
            name="free_period_policy",
            field=models.CharField(
                choices=[
                    ("auto", "تلقائي حسب المتاح"),
                    ("daily", "حد أدنى يومي"),
                    ("weekly", "عدد أسبوعي"),
                ],
                default="auto",
                max_length=20,
                verbose_name="سياسة فراغ المعلم",
            ),
        ),
        migrations.AddField(
            model_name="teacher",
            name="daily_free_periods",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="الفراغ اليومي المطلوب"),
        ),
        migrations.AddField(
            model_name="teacher",
            name="weekly_free_periods",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="الفراغ الأسبوعي المطلوب"),
        ),
    ]
