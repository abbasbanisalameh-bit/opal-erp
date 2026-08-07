from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_dataintegrityrun_school"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="academicyear",
            name="prepared_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ تهيئة العام"),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="prepared_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="prepared_academic_years", to=settings.AUTH_USER_MODEL, verbose_name="هيأه"),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="preparation_source",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="prepared_successors", to="core.academicyear", verbose_name="عام التهيئة المصدر"),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="transition_completed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ اكتمال الانتقال"),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="transition_completed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="completed_academic_year_transitions", to=settings.AUTH_USER_MODEL, verbose_name="منفذ الانتقال"),
        ),
        migrations.AddField(
            model_name="semester",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ إغلاق الفصل"),
        ),
        migrations.AddField(
            model_name="semester",
            name="closed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="closed_semesters", to=settings.AUTH_USER_MODEL, verbose_name="أغلقه"),
        ),
        migrations.AddField(
            model_name="semester",
            name="closure_notes",
            field=models.TextField(blank=True, verbose_name="ملاحظات إغلاق الفصل"),
        ),
        migrations.AddField(
            model_name="semester",
            name="is_closed",
            field=models.BooleanField(db_index=True, default=False, verbose_name="فصل مغلق أكاديميًا"),
        ),
    ]
