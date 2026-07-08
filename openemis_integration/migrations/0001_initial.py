# Generated for OPAL ERP OpenEMIS foundation

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0001_initial"),
        ("students", "0004_student_national_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OpenEMISSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=False, verbose_name="تفعيل التكامل")),
                ("base_url", models.URLField(blank=True, verbose_name="رابط OpenEMIS / API")),
                ("username", models.CharField(blank=True, max_length=200, verbose_name="اسم المستخدم")),
                ("password", models.CharField(blank=True, max_length=300, verbose_name="كلمة المرور / Token")),
                ("client_id", models.CharField(blank=True, max_length=200, verbose_name="Client ID")),
                ("client_secret", models.CharField(blank=True, max_length=300, verbose_name="Client Secret")),
                ("auto_push_registration", models.BooleanField(default=False, verbose_name="إرسال الطالب بعد التسجيل تلقائيًا")),
                ("auto_pull_student", models.BooleanField(default=False, verbose_name="سحب بيانات الطالب من OpenEMIS عند توفر الرقم الوزاري")),
                ("sync_guardians", models.BooleanField(default=True, verbose_name="مزامنة بيانات ولي الأمر")),
                ("last_tested_at", models.DateTimeField(blank=True, null=True, verbose_name="آخر اختبار اتصال")),
                ("last_sync_at", models.DateTimeField(blank=True, null=True, verbose_name="آخر مزامنة")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="openemis_settings", to="core.school")),
            ],
            options={"verbose_name": "إعدادات OpenEMIS", "verbose_name_plural": "إعدادات OpenEMIS"},
        ),
        migrations.CreateModel(
            name="OpenEMISSyncLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation", models.CharField(choices=[("push_student", "إرسال طالب"), ("pull_student", "سحب طالب"), ("update_student", "تحديث طالب"), ("sync_guardian", "مزامنة ولي الأمر"), ("test_connection", "اختبار اتصال")], max_length=50, verbose_name="العملية")),
                ("status", models.CharField(choices=[("pending", "معلق"), ("success", "ناجح"), ("failed", "فشل"), ("skipped", "تم التجاوز")], default="pending", max_length=30, verbose_name="الحالة")),
                ("message", models.TextField(blank=True, verbose_name="الرسالة")),
                ("request_payload", models.JSONField(blank=True, default=dict, verbose_name="بيانات الإرسال")),
                ("response_payload", models.JSONField(blank=True, default=dict, verbose_name="بيانات الاستجابة")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="openemis_logs", to="core.school")),
                ("student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="openemis_logs", to="students.student")),
            ],
            options={"verbose_name": "سجل مزامنة OpenEMIS", "verbose_name_plural": "سجلات مزامنة OpenEMIS", "ordering": ["-created_at"]},
        ),
    ]
