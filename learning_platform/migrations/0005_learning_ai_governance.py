import django.db.models.deletion
from django.db import migrations, models


DEFAULT_POLICY = (
    "استخدم محتوى الدورة المنشور فقط. صرّح بوضوح عندما لا يكفي المحتوى للإجابة. "
    "لا تصدر قرارًا نهائيًا بشأن العلامات أو النجاح أو الاشتراك، ولا تنشر محتوى تلقائيًا."
)


def create_default_ai_settings(apps, schema_editor):
    LearningAISettings = apps.get_model("learning_platform", "LearningAISettings")
    LearningAISettings.objects.get_or_create(singleton_key=1)


class Migration(migrations.Migration):
    dependencies = [
        ("learning_platform", "0004_account_recovery_notifications"),
    ]

    operations = [
        migrations.CreateModel(
            name="LearningAISettings",
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
                ("singleton_key", models.PositiveSmallIntegerField(default=1, editable=False, unique=True)),
                ("assistant_enabled", models.BooleanField(default=True, verbose_name="مساعد المتعلم فعال")),
                ("teacher_tools_enabled", models.BooleanField(default=True, verbose_name="أدوات المدرّس فعالة")),
                ("external_provider_enabled", models.BooleanField(default=False, verbose_name="السماح بالمزود الخارجي")),
                ("local_reference_enabled", models.BooleanField(default=True, verbose_name="المرجع المحلي عند تعذر المزود")),
                ("learner_daily_limit", models.PositiveSmallIntegerField(default=20, verbose_name="حد المتعلم اليومي")),
                ("teacher_daily_limit", models.PositiveSmallIntegerField(default=30, verbose_name="حد المدرّس اليومي")),
                ("max_context_chars", models.PositiveIntegerField(default=12000, verbose_name="أقصى حجم للسياق")),
                ("max_output_chars", models.PositiveIntegerField(default=4000, verbose_name="أقصى حجم للإجابة")),
                ("policy_text", models.TextField(default=DEFAULT_POLICY, verbose_name="سياسة المساعد")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "إعدادات مساعد المنصة",
                "verbose_name_plural": "إعدادات مساعد المنصة",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("learner_daily_limit__gte", 1), ("teacher_daily_limit__gte", 1)),
                        name="learning_ai_daily_limits_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("max_context_chars__gte", 1000), ("max_output_chars__gte", 500)),
                        name="learning_ai_size_limits_positive",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="LearningAIInteraction",
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
                    "interaction_type",
                    models.CharField(
                        choices=[
                            ("learner_question", "سؤال متعلم"),
                            ("teacher_summary", "ملخص للمدرّس"),
                            ("teacher_outline", "خطة درس"),
                            ("teacher_review_questions", "أسئلة مراجعة"),
                            ("teacher_assignment", "مسودة واجب"),
                        ],
                        db_index=True,
                        max_length=32,
                        verbose_name="نوع الطلب",
                    ),
                ),
                ("prompt", models.TextField(verbose_name="الطلب")),
                ("response", models.TextField(blank=True, verbose_name="الإجابة")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("success", "ناجح"),
                            ("local_reference", "مرجع محلي"),
                            ("provider_error", "تعذر المزود"),
                            ("rejected", "مرفوض"),
                        ],
                        db_index=True,
                        max_length=24,
                        verbose_name="الحالة",
                    ),
                ),
                ("provider_mode", models.CharField(blank=True, max_length=32, verbose_name="وضع المزود")),
                ("provider_name", models.CharField(blank=True, max_length=80, verbose_name="اسم المزود")),
                ("model_name", models.CharField(blank=True, max_length=120, verbose_name="اسم النموذج")),
                ("source_lesson_ids", models.JSONField(blank=True, default=list, verbose_name="معرفات الدروس المرجعية")),
                ("source_labels", models.JSONField(blank=True, default=list, verbose_name="المراجع الظاهرة")),
                ("input_chars", models.PositiveIntegerField(default=0)),
                ("output_chars", models.PositiveIntegerField(default=0)),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                ("error_message", models.CharField(blank=True, max_length=500, verbose_name="الخطأ")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_interactions",
                        to="learning_platform.learningaccount",
                        verbose_name="الحساب",
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_interactions",
                        to="learning_platform.learningcourse",
                        verbose_name="الدورة",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["account", "created_at"], name="learn_ai_account_day_idx"),
                    models.Index(fields=["course", "created_at"], name="learn_ai_course_day_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="LearningAIDraft",
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
                    "draft_type",
                    models.CharField(
                        choices=[
                            ("learner_question", "سؤال متعلم"),
                            ("teacher_summary", "ملخص للمدرّس"),
                            ("teacher_outline", "خطة درس"),
                            ("teacher_review_questions", "أسئلة مراجعة"),
                            ("teacher_assignment", "مسودة واجب"),
                        ],
                        max_length=32,
                        verbose_name="نوع المسودة",
                    ),
                ),
                ("title", models.CharField(max_length=220, verbose_name="العنوان")),
                ("content", models.TextField(verbose_name="المحتوى")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "مسودة"),
                            ("accepted", "معتمدة للمراجعة اليدوية"),
                            ("discarded", "مستبعدة"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                        verbose_name="الحالة",
                    ),
                ),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_drafts",
                        to="learning_platform.learningcourse",
                        verbose_name="الدورة",
                    ),
                ),
                (
                    "interaction",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="saved_draft",
                        to="learning_platform.learningaiinteraction",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_drafts",
                        to="learning_platform.learningaccount",
                        verbose_name="المدرّس",
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at", "-id"],
                "indexes": [
                    models.Index(fields=["teacher", "status", "updated_at"], name="learn_ai_draft_teacher_idx"),
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
                    ("ai_requested", "طلب مساعدة تعليمية"),
                    ("ai_draft_saved", "حفظ مسودة مساعدة"),
                    ("ai_draft_reviewed", "مراجعة مسودة مساعدة"),
                    ("ai_settings_updated", "تحديث إعدادات المساعد"),
                ],
                db_index=True,
                max_length=40,
            ),
        ),
        migrations.RunPython(create_default_ai_settings, migrations.RunPython.noop),
    ]
