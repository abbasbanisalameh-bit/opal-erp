import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("learning_platform", "0003_learning_assessments_submissions_certificates"),
    ]

    operations = [
        migrations.AddField(
            model_name="learningaccount",
            name="auth_version",
            field=models.PositiveIntegerField(default=1, editable=False, verbose_name="إصدار الجلسة"),
        ),
        migrations.AddField(
            model_name="learningaccount",
            name="password_changed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="آخر تغيير لكلمة المرور"),
        ),
        migrations.CreateModel(
            name="LearningPasswordResetRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="بصمة الرمز")),
                ("expires_at", models.DateTimeField(db_index=True, verbose_name="ينتهي في")),
                ("used_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="استخدم في")),
                ("request_ip", models.GenericIPAddressField(blank=True, null=True, verbose_name="عنوان الطلب")),
                (
                    "delivery_status",
                    models.CharField(
                        choices=[
                            ("pending", "بانتظار الإرسال"),
                            ("sent", "تم الإرسال"),
                            ("failed", "تعذر الإرسال"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                        verbose_name="حالة الإرسال",
                    ),
                ),
                ("delivery_error", models.CharField(blank=True, max_length=240, verbose_name="خطأ الإرسال")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="password_reset_requests",
                        to="learning_platform.learningaccount",
                        verbose_name="الحساب",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["account", "used_at", "expires_at"],
                        name="learn_reset_account_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="LearningNotification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "notification_type",
                    models.CharField(
                        choices=[
                            ("system", "نظام"),
                            ("subscription", "اشتراك"),
                            ("course", "دورة"),
                            ("assessment", "تقييم"),
                            ("certificate", "شهادة"),
                        ],
                        db_index=True,
                        default="system",
                        max_length=24,
                        verbose_name="النوع",
                    ),
                ),
                ("title", models.CharField(max_length=180, verbose_name="العنوان")),
                ("body", models.CharField(max_length=500, verbose_name="النص")),
                ("action_url", models.CharField(blank=True, max_length=500, verbose_name="رابط الإجراء")),
                ("dedupe_key", models.CharField(blank=True, max_length=180, verbose_name="مفتاح منع التكرار")),
                ("read_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="قُرئ في")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="learning_platform.learningaccount",
                        verbose_name="المستلم",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["recipient", "read_at", "created_at"],
                        name="learn_notice_inbox_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=~models.Q(dedupe_key=""),
                        fields=("recipient", "dedupe_key"),
                        name="uniq_learning_notification_dedupe",
                    )
                ],
            },
        ),
        migrations.AlterField(
            model_name="learningauditevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("registered", "تسجيل حساب"),
                    ("login", "تسجيل دخول"),
                    ("logout", "تسجيل خروج"),
                    ("subscription_activated", "تفعيل اشتراك"),
                    ("subscription_created", "إنشاء بطاقة اشتراك"),
                    ("subscription_cancelled", "إلغاء بطاقة اشتراك"),
                    ("course_enrolled", "تسجيل في دورة"),
                    ("lesson_completed", "إكمال درس"),
                    ("assessment_submitted", "تسليم تقييم"),
                    ("assessment_graded", "تصحيح تقييم"),
                    ("certificate_issued", "إصدار شهادة"),
                    ("certificate_revoked", "إلغاء شهادة"),
                    ("password_reset_requested", "طلب استعادة كلمة المرور"),
                    ("password_reset_completed", "إكمال استعادة كلمة المرور"),
                    ("password_reset_by_manager", "إعادة كلمة المرور من المدير"),
                    ("notification_read", "قراءة إشعار"),
                ],
                db_index=True,
                max_length=40,
            ),
        ),
    ]
