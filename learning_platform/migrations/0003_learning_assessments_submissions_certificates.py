import secrets

import django.db.models.deletion
from django.db import migrations, models


def backfill_completed_certificates(apps, schema_editor):
    Enrollment = apps.get_model("learning_platform", "LearningEnrollment")
    Certificate = apps.get_model("learning_platform", "LearningCertificate")
    for enrollment in Enrollment.objects.filter(status="completed").iterator():
        if Certificate.objects.filter(enrollment_id=enrollment.pk).exists():
            continue
        Certificate.objects.create(
            enrollment_id=enrollment.pk,
            serial=f"OPAL-LRN-BACKFILL-{enrollment.pk:07d}",
            verification_code=secrets.token_urlsafe(18),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("learning_platform", "0002_learninglessonprogress_and_operational_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="LearningAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220, verbose_name="عنوان التقييم")),
                ("slug", models.SlugField(allow_unicode=True, max_length=240, verbose_name="المعرف")),
                (
                    "assessment_type",
                    models.CharField(
                        choices=[("quiz", "اختبار إلكتروني"), ("assignment", "واجب")],
                        max_length=20,
                        verbose_name="النوع",
                    ),
                ),
                ("instructions", models.TextField(blank=True, verbose_name="التعليمات")),
                ("max_score", models.PositiveSmallIntegerField(default=100, verbose_name="العلامة القصوى")),
                ("pass_score", models.PositiveSmallIntegerField(default=60, verbose_name="علامة النجاح")),
                ("max_attempts", models.PositiveSmallIntegerField(default=3, verbose_name="عدد المحاولات")),
                ("order", models.PositiveIntegerField(default=1, verbose_name="الترتيب")),
                ("is_required", models.BooleanField(default=True, verbose_name="مطلوب لإكمال الدورة")),
                ("is_published", models.BooleanField(db_index=True, default=False, verbose_name="منشور")),
                ("due_at", models.DateTimeField(blank=True, null=True, verbose_name="آخر موعد")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assessments",
                        to="learning_platform.learningcourse",
                        verbose_name="الدورة",
                    ),
                ),
            ],
            options={
                "ordering": ["course_id", "order", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("course", "slug"), name="uniq_learning_assessment_slug"),
                    models.UniqueConstraint(fields=("course", "order"), name="uniq_learning_assessment_order"),
                    models.CheckConstraint(
                        condition=models.Q(pass_score__lte=models.F("max_score")),
                        name="learning_assessment_pass_lte_max",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="LearningCertificate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("serial", models.CharField(max_length=64, unique=True, verbose_name="الرقم التسلسلي")),
                ("verification_code", models.CharField(max_length=64, unique=True, verbose_name="رمز التحقق")),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_reason", models.CharField(blank=True, max_length=240, verbose_name="سبب الإلغاء")),
                (
                    "enrollment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certificate",
                        to="learning_platform.learningenrollment",
                        verbose_name="تسجيل الدورة",
                    ),
                ),
            ],
            options={"ordering": ["-issued_at"]},
        ),
        migrations.CreateModel(
            name="LearningQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(verbose_name="نص السؤال")),
                ("choice_a", models.CharField(max_length=500, verbose_name="الخيار أ")),
                ("choice_b", models.CharField(max_length=500, verbose_name="الخيار ب")),
                ("choice_c", models.CharField(max_length=500, verbose_name="الخيار ج")),
                ("choice_d", models.CharField(max_length=500, verbose_name="الخيار د")),
                (
                    "correct_choice",
                    models.CharField(
                        choices=[("a", "أ"), ("b", "ب"), ("c", "ج"), ("d", "د")],
                        max_length=1,
                        verbose_name="الإجابة الصحيحة",
                    ),
                ),
                ("points", models.PositiveSmallIntegerField(default=1, verbose_name="النقاط")),
                ("order", models.PositiveIntegerField(default=1, verbose_name="الترتيب")),
                (
                    "assessment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="questions",
                        to="learning_platform.learningassessment",
                        verbose_name="الاختبار",
                    ),
                ),
            ],
            options={
                "ordering": ["assessment_id", "order", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("assessment", "order"),
                        name="uniq_learning_question_order",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="LearningSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attempt_no", models.PositiveSmallIntegerField(default=1, verbose_name="رقم المحاولة")),
                ("answer_text", models.TextField(blank=True, verbose_name="إجابة الواجب")),
                ("answers", models.JSONField(blank=True, default=dict, verbose_name="إجابات الاختبار")),
                (
                    "status",
                    models.CharField(
                        choices=[("submitted", "بانتظار التصحيح"), ("graded", "مصحح")],
                        db_index=True,
                        default="submitted",
                        max_length=20,
                        verbose_name="الحالة",
                    ),
                ),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name="العلامة")),
                ("is_passed", models.BooleanField(db_index=True, default=False, verbose_name="ناجح")),
                ("feedback", models.TextField(blank=True, verbose_name="ملاحظات المصحح")),
                ("submitted_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("graded_at", models.DateTimeField(blank=True, null=True)),
                ("graded_by_label", models.CharField(blank=True, max_length=200, verbose_name="اسم المصحح")),
                (
                    "assessment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submissions",
                        to="learning_platform.learningassessment",
                        verbose_name="التقييم",
                    ),
                ),
                (
                    "enrollment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submissions",
                        to="learning_platform.learningenrollment",
                        verbose_name="تسجيل الدورة",
                    ),
                ),
                (
                    "graded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="graded_submissions",
                        to="learning_platform.learningaccount",
                    ),
                ),
            ],
            options={
                "ordering": ["-submitted_at", "-id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("assessment", "enrollment", "attempt_no"),
                        name="uniq_learning_submission_attempt",
                    )
                ],
            },
        ),
        migrations.RunPython(
            backfill_completed_certificates,
            migrations.RunPython.noop,
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
                ],
                db_index=True,
                max_length=40,
            ),
        ),
    ]
