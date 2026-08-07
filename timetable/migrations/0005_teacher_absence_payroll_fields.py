from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timetable", "0004_timetableentry_generated_automatically_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacherabsence",
            name="absence_type",
            field=models.CharField(
                choices=[("excused", "غياب مبرر"), ("unexcused", "غياب غير مبرر")],
                db_index=True,
                default="excused",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="teacherabsence",
            name="deduction_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="قيمة الخصم"),
        ),
        migrations.AddField(
            model_name="teacherabsence",
            name="payroll_approved",
            field=models.BooleanField(db_index=True, default=False, verbose_name="معتمد للخصم من الراتب"),
        ),
        migrations.AddField(
            model_name="teacherabsence",
            name="payroll_notes",
            field=models.CharField(blank=True, max_length=250, verbose_name="ملاحظات الخصم"),
        ),
    ]
