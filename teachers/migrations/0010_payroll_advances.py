from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("teachers", "0009_alter_teacher_is_demo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherAdvance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="قيمة السلفة")),
                ("status", models.CharField(choices=[("requested", "مطلوبة"), ("disbursed", "مصروفة"), ("acknowledged", "تم الإقرار بالاستلام"), ("deducted", "خُصمت من الراتب"), ("cancelled", "ملغاة قبل الصرف")], db_index=True, default="requested", max_length=20)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("disbursed_at", models.DateTimeField(blank=True, null=True)),
                ("payment_method", models.CharField(blank=True, max_length=30)),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("deducted_at", models.DateTimeField(blank=True, null=True)),
                ("admin_note", models.TextField(blank=True)),
                ("disbursed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="disbursed_teacher_advances", to=settings.AUTH_USER_MODEL)),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="salary_advances", to="teachers.teacher")),
            ],
            options={"ordering": ["-requested_at", "teacher__full_name"]},
        ),
        migrations.CreateModel(
            name="TeacherPayroll",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period", models.DateField(db_index=True, help_text="يُحفظ اليوم الأول من الشهر.", verbose_name="شهر الراتب")),
                ("due_date", models.DateField(verbose_name="تاريخ الاستحقاق")),
                ("base_salary", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="الراتب الأساسي")),
                ("manager_increase", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="زيادة الإدارة")),
                ("advance_deduction", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="خصم السلف")),
                ("absence_deduction", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="خصم الغياب المعتمد")),
                ("other_deduction", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="خصومات أخرى")),
                ("net_salary", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="صافي الراتب")),
                ("status", models.CharField(choices=[("draft", "مسودة"), ("ready", "جاهز"), ("sent", "مرسل"), ("acknowledged", "مقرّ به"), ("objection", "اعتراض"), ("corrected", "مصحح")], db_index=True, default="draft", max_length=20)),
                ("payment_method", models.CharField(blank=True, max_length=30)),
                ("payment_reference", models.CharField(blank=True, max_length=100)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("objection_text", models.TextField(blank=True)),
                ("correction_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("advances", models.ManyToManyField(blank=True, related_name="payroll_records", to="teachers.teacheradvance")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_teacher_payrolls", to=settings.AUTH_USER_MODEL)),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payroll_records", to="teachers.teacher")),
            ],
            options={"ordering": ["-period", "teacher__full_name"]},
        ),
        migrations.AddConstraint(
            model_name="teacherpayroll",
            constraint=models.UniqueConstraint(fields=("teacher", "period"), name="uniq_teacher_payroll_period"),
        ),
    ]
