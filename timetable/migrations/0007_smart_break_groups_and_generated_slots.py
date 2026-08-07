from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0015_lifecycle_section_snapshots"),
        ("timetable", "0006_teacherabsence_approved_by_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="timeslot",
            name="generated_for_smart_schedule",
            field=models.BooleanField(
                db_index=True,
                default=False,
                editable=False,
                verbose_name="وقت مشتق آليًا",
            ),
        ),
        migrations.AlterField(
            model_name="schoolschedulesettings",
            name="weekend_days",
            field=models.CharField(default="friday,saturday", max_length=100, verbose_name="أيام العطلة"),
        ),
        migrations.AlterField(
            model_name="schooldayevent",
            name="days",
            field=models.CharField(
                default="sunday,monday,tuesday,wednesday,thursday",
                max_length=120,
                verbose_name="أيام التطبيق",
            ),
        ),
        migrations.AlterField(
            model_name="schooldayevent",
            name="start_time",
            field=models.TimeField(blank=True, null=True, verbose_name="وقت البداية"),
        ),
        migrations.AlterField(
            model_name="schooldayevent",
            name="end_time",
            field=models.TimeField(blank=True, null=True, verbose_name="وقت النهاية"),
        ),
        migrations.AddField(
            model_name="schooldayevent",
            name="duration_minutes",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="مطلوبة للاستراحة الذكية، ويحسب النظام وقتها بين الحصص.",
                null=True,
                verbose_name="المدة بالدقائق",
            ),
        ),
        migrations.AddField(
            model_name="schooldayevent",
            name="placement_mode",
            field=models.CharField(
                choices=[("fixed", "وقت ثابت"), ("smart", "يوزعه النظام بذكاء")],
                default="fixed",
                max_length=20,
                verbose_name="طريقة تحديد الوقت",
            ),
        ),
        migrations.AddField(
            model_name="schooldayevent",
            name="sections",
            field=models.ManyToManyField(
                blank=True,
                help_text="اتركها فارغة فقط للأحداث العامة التي تشمل المدرسة كلها.",
                related_name="school_day_events",
                to="academics.section",
                verbose_name="الشعب التابعة للاستراحة",
            ),
        ),
        migrations.AlterModelOptions(
            name="schooldayevent",
            options={"ordering": ["order", "start_time", "name"]},
        ),
    ]
