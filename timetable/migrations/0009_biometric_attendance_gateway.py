from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0014_productiondataresetrun"),
        ("teachers", "0014_subject_plan_single_source"),
        ("timetable", "0008_subject_plan_protection"),
    ]

    operations = [
        migrations.CreateModel(
            name="BiometricDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, verbose_name="اسم الجهاز")),
                ("device_code", models.CharField(max_length=80, unique=True, verbose_name="رمز الجهاز")),
                ("vendor", models.CharField(choices=[("generic", "جهاز عام / بوابة محلية"), ("zkteco", "ZKTeco"), ("other", "شركة أخرى")], default="generic", max_length=20, verbose_name="الشركة")),
                ("serial_number", models.CharField(blank=True, max_length=120, verbose_name="الرقم التسلسلي")),
                ("timezone_name", models.CharField(default="Asia/Amman", max_length=64, verbose_name="المنطقة الزمنية")),
                ("token_hash", models.CharField(blank=True, editable=False, max_length=64, null=True, unique=True, verbose_name="بصمة رمز الربط")),
                ("token_hint", models.CharField(blank=True, editable=False, max_length=8, verbose_name="آخر أحرف الرمز")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="فعال")),
                ("last_seen_at", models.DateTimeField(blank=True, null=True, verbose_name="آخر اتصال")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="biometric_devices", to="core.branch")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="biometric_devices", to="core.school")),
            ],
            options={"verbose_name": "جهاز بصمة", "verbose_name_plural": "أجهزة البصمة", "ordering": ["school__name", "name"]},
        ),
        migrations.CreateModel(
            name="TeacherBiometricIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_user_id", models.CharField(max_length=80, verbose_name="معرف المعلم داخل الجهاز")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_identities", to="timetable.biometricdevice")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="biometric_identities", to="teachers.teacher")),
            ],
            options={"ordering": ["teacher__full_name", "device_user_id"]},
        ),
        migrations.AddConstraint(
            model_name="teacherbiometricidentity",
            constraint=models.UniqueConstraint(fields=("device", "device_user_id"), name="uniq_biometric_device_user"),
        ),
        migrations.AddConstraint(
            model_name="teacherbiometricidentity",
            constraint=models.UniqueConstraint(fields=("device", "teacher"), name="uniq_biometric_device_teacher"),
        ),
        migrations.CreateModel(
            name="TeacherBiometricPunch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_user_id", models.CharField(db_index=True, max_length=80, verbose_name="معرف المستخدم في الجهاز")),
                ("event_uid", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="معرف الحدث")),
                ("punched_at", models.DateTimeField(db_index=True, verbose_name="وقت البصمة")),
                ("direction", models.CharField(choices=[("in", "دخول"), ("out", "خروج"), ("unknown", "غير محدد")], db_index=True, default="unknown", max_length=10, verbose_name="نوع الحركة")),
                ("raw_payload", models.JSONField(blank=True, default=dict, verbose_name="بيانات الجهاز الخام")),
                ("received_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="punches", to="timetable.biometricdevice")),
                ("teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="biometric_punches", to="teachers.teacher")),
            ],
            options={"ordering": ["-punched_at", "-id"]},
        ),
        migrations.AddIndex(model_name="teacherbiometricpunch", index=models.Index(fields=["teacher", "punched_at"], name="bio_teacher_punch_idx")),
        migrations.AddIndex(model_name="teacherbiometricpunch", index=models.Index(fields=["device", "punched_at"], name="bio_device_punch_idx")),
        migrations.CreateModel(
            name="BiometricDailySummary",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True, verbose_name="التاريخ")),
                ("first_punch_at", models.DateTimeField(blank=True, null=True, verbose_name="أول بصمة")),
                ("last_punch_at", models.DateTimeField(blank=True, null=True, verbose_name="آخر بصمة")),
                ("expected_start", models.TimeField(blank=True, null=True, verbose_name="بداية الدوام المتوقعة")),
                ("expected_end", models.TimeField(blank=True, null=True, verbose_name="نهاية الدوام المتوقعة")),
                ("punch_count", models.PositiveSmallIntegerField(default=0, verbose_name="عدد البصمات")),
                ("source_devices_count", models.PositiveSmallIntegerField(default=0, verbose_name="عدد الأجهزة")),
                ("derived_status", models.CharField(choices=[("normal", "منتظم"), ("late", "متأخر"), ("early_departure", "مغادرة مبكرة"), ("late_and_early", "تأخر ومغادرة مبكرة"), ("incomplete", "بصمة واحدة / غير مكتمل"), ("no_punch", "لا توجد بصمة"), ("no_schedule", "لا يوجد جدول في هذا اليوم")], db_index=True, max_length=24, verbose_name="النتيجة المقترحة")),
                ("review_status", models.CharField(choices=[("pending", "بانتظار المراجعة"), ("applied", "اعتمد في الدوام"), ("ignored", "تم التجاهل")], db_index=True, default="pending", max_length=12, verbose_name="حالة المراجعة")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=250, verbose_name="ملاحظة")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("applied_exception", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="biometric_summaries", to="timetable.teacherabsence")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_biometric_summaries", to=settings.AUTH_USER_MODEL)),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="biometric_daily_summaries", to="teachers.teacher")),
            ],
            options={"ordering": ["-date", "teacher__full_name"]},
        ),
        migrations.AddConstraint(
            model_name="biometricdailysummary",
            constraint=models.UniqueConstraint(fields=("teacher", "date"), name="uniq_biometric_teacher_day_summary"),
        ),
        migrations.AddIndex(model_name="biometricdailysummary", index=models.Index(fields=["date", "derived_status", "review_status"], name="bio_daily_review_idx")),
    ]
