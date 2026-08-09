from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone


class LearningAccount(models.Model):
    """An academy-only identity that is not an OPAL ERP user or school student."""

    class Role(models.TextChoices):
        LEARNER = "learner", "متعلم"
        TEACHER = "teacher", "مدرّس"
        MANAGER = "manager", "مدير المنصة"

    email = models.EmailField("البريد الإلكتروني", max_length=254, db_index=True)
    full_name = models.CharField("الاسم الكامل", max_length=200)
    phone = models.CharField("رقم الهاتف", max_length=30, blank=True)
    role = models.CharField("نوع الحساب", max_length=20, choices=Role.choices, default=Role.LEARNER)
    password = models.CharField("كلمة المرور المشفرة", max_length=128, editable=False)
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    is_school_managed = models.BooleanField("حساب مدرسي مرتبط بـ OPAL ERP", default=False, db_index=True)
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)
    last_login_at = models.DateTimeField("آخر دخول", null=True, blank=True)
    password_changed_at = models.DateTimeField("آخر تغيير لكلمة المرور", null=True, blank=True)
    auth_version = models.PositiveIntegerField("إصدار الجلسة", default=1, editable=False)
    terms_accepted_at = models.DateTimeField("قبول شروط الاستخدام", null=True, blank=True)
    privacy_accepted_at = models.DateTimeField("قبول سياسة الخصوصية", null=True, blank=True)
    email_verified_at = models.DateTimeField("توثيق البريد", null=True, blank=True, db_index=True)
    failed_login_count = models.PositiveSmallIntegerField("محاولات الدخول الفاشلة", default=0, editable=False)
    locked_until = models.DateTimeField("الحساب مقفل حتى", null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["full_name", "id"]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="uniq_learning_account_email_ci"),
        ]

    def __str__(self):
        return self.full_name or self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        self.full_name = " ".join((self.full_name or "").split())
        self.phone = (self.phone or "").strip()
        return super().save(*args, **kwargs)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)


class LearningSubject(models.Model):
    name = models.CharField("اسم المادة", max_length=120, unique=True)
    slug = models.SlugField("المعرف", max_length=140, unique=True, allow_unicode=True)
    is_active = models.BooleanField("فعالة", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LearningCourse(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        PUBLISHED = "published", "منشورة"
        ARCHIVED = "archived", "مؤرشفة"

    subject = models.ForeignKey(
        LearningSubject,
        on_delete=models.PROTECT,
        related_name="courses",
        verbose_name="المادة",
    )
    teacher = models.ForeignKey(
        LearningAccount,
        on_delete=models.PROTECT,
        related_name="authored_courses",
        verbose_name="المدرّس",
    )
    title = models.CharField("عنوان الدورة", max_length=220)
    slug = models.SlugField("المعرف", max_length=240, unique=True, allow_unicode=True)
    summary = models.TextField("الملخص", blank=True)
    grade_label = models.CharField("المستوى أو الصف", max_length=120, blank=True)
    academic_subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_courses",
        verbose_name="المادة المدرسية المرتبطة",
    )
    academic_section = models.ForeignKey(
        "academics.Section",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_courses",
        verbose_name="الشعبة المدرسية المرتبطة",
    )
    cover_color = models.CharField("لون الغلاف", max_length=20, default="#7254d8")
    status = models.CharField("الحالة", max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.teacher_id and self.teacher.role not in {
            LearningAccount.Role.TEACHER,
            LearningAccount.Role.MANAGER,
        }:
            raise ValidationError({"teacher": "يجب أن يكون ناشر الدورة مدرّسًا أو مديرًا للمنصة."})

    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        return super().save(*args, **kwargs)


class LearningLesson(models.Model):
    course = models.ForeignKey(LearningCourse, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField("عنوان الدرس", max_length=220)
    slug = models.SlugField("المعرف", max_length=240, allow_unicode=True)
    content = models.TextField("المحتوى", blank=True)
    video_url = models.URLField("رابط الفيديو", blank=True)
    attachment = models.FileField("مرفق الدرس", upload_to="learning_lessons/", blank=True)
    duration_minutes = models.PositiveSmallIntegerField("المدة بالدقائق", default=0)
    order = models.PositiveIntegerField("الترتيب", default=1)
    is_published = models.BooleanField("منشور", default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course_id", "order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["course", "slug"], name="uniq_learning_lesson_slug"),
            models.UniqueConstraint(fields=["course", "order"], name="uniq_learning_lesson_order"),
        ]

    def __str__(self):
        return f"{self.course}: {self.title}"


class LearningEnrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "فعال"
        COMPLETED = "completed", "مكتمل"
        CANCELLED = "cancelled", "ملغي"

    learner = models.ForeignKey(LearningAccount, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(LearningCourse, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    progress_percent = models.PositiveSmallIntegerField("نسبة الإنجاز", default=0)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_activity_at", "-enrolled_at"]
        constraints = [
            models.UniqueConstraint(fields=["learner", "course"], name="uniq_learning_enrollment"),
            models.CheckConstraint(
                condition=Q(progress_percent__gte=0, progress_percent__lte=100),
                name="learning_progress_between_0_100",
            ),
        ]

    def clean(self):
        super().clean()
        if self.learner_id and self.learner.role != LearningAccount.Role.LEARNER:
            raise ValidationError({"learner": "التسجيل في الدورة متاح لحساب المتعلم فقط."})

    def __str__(self):
        return f"{self.learner} — {self.course}"


class LearningLessonProgress(models.Model):
    enrollment = models.ForeignKey(
        LearningEnrollment,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
        verbose_name="التسجيل",
    )
    lesson = models.ForeignKey(
        LearningLesson,
        on_delete=models.CASCADE,
        related_name="learner_progress",
        verbose_name="الدرس",
    )
    last_viewed_at = models.DateTimeField("آخر مشاهدة", null=True, blank=True)
    completed_at = models.DateTimeField("تاريخ الإكمال", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["lesson_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "lesson"],
                name="uniq_learning_lesson_progress",
            ),
        ]

    def clean(self):
        super().clean()
        if self.enrollment_id and self.lesson_id:
            if self.enrollment.course_id != self.lesson.course_id:
                raise ValidationError("يجب أن ينتمي الدرس إلى دورة التسجيل نفسها.")

    @property
    def is_completed(self):
        return self.completed_at is not None

    def __str__(self):
        return f"{self.enrollment} — {self.lesson}"


class LearningSubscriptionCard(models.Model):
    class Duration(models.TextChoices):
        MONTHLY = "monthly", "شهري"
        TERMLY = "termly", "فصلي"
        YEARLY = "yearly", "سنوي"

    class Status(models.TextChoices):
        AVAILABLE = "available", "متاحة"
        REDEEMED = "redeemed", "مفعلة"
        CANCELLED = "cancelled", "ملغاة"

    DURATION_DAYS = {
        Duration.MONTHLY: 30,
        Duration.TERMLY: 120,
        Duration.YEARLY: 365,
    }

    code = models.CharField("رمز البطاقة", max_length=64, unique=True)
    duration = models.CharField("المدة", max_length=20, choices=Duration.choices)
    grants_all_subjects = models.BooleanField("جميع المواد", default=False)
    subjects = models.ManyToManyField(LearningSubject, blank=True, related_name="subscription_cards")
    status = models.CharField("الحالة", max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    redeemed_by = models.ForeignKey(
        LearningAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subscription_cards",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        return super().save(*args, **kwargs)

    @property
    def is_current(self):
        return (
            self.status == self.Status.REDEEMED
            and self.expires_at is not None
            and self.expires_at > timezone.now()
        )

    def activate(self, account, *, activated_at=None):
        if account.role != LearningAccount.Role.LEARNER:
            raise ValidationError("يمكن تفعيل البطاقة لحساب متعلم فقط.")
        now = activated_at or timezone.now()
        with transaction.atomic():
            locked = type(self).objects.select_for_update().get(pk=self.pk)
            if locked.status != self.Status.AVAILABLE or locked.redeemed_by_id is not None:
                raise ValidationError("هذه البطاقة مستخدمة أو غير متاحة للتفعيل.")
            locked.status = self.Status.REDEEMED
            locked.redeemed_by = account
            locked.activated_at = now
            locked.expires_at = now + timedelta(days=self.DURATION_DAYS[locked.duration])
            locked.save(update_fields=["status", "redeemed_by", "activated_at", "expires_at"])
            LearningAuditEvent.objects.create(
                account=account,
                action=LearningAuditEvent.Action.SUBSCRIPTION_ACTIVATED,
                entity_type="subscription_card",
                entity_id=str(locked.pk),
                metadata={"duration": locked.duration},
            )
        self.refresh_from_db()
        return self


class LearningAssessment(models.Model):
    class Type(models.TextChoices):
        QUIZ = "quiz", "اختبار إلكتروني"
        ASSIGNMENT = "assignment", "واجب"

    course = models.ForeignKey(
        LearningCourse,
        on_delete=models.CASCADE,
        related_name="assessments",
        verbose_name="الدورة",
    )
    title = models.CharField("عنوان التقييم", max_length=220)
    slug = models.SlugField("المعرف", max_length=240, allow_unicode=True)
    assessment_type = models.CharField("النوع", max_length=20, choices=Type.choices)
    instructions = models.TextField("التعليمات", blank=True)
    max_score = models.PositiveSmallIntegerField("العلامة القصوى", default=100)
    pass_score = models.PositiveSmallIntegerField("علامة النجاح", default=60)
    max_attempts = models.PositiveSmallIntegerField("عدد المحاولات", default=3)
    order = models.PositiveIntegerField("الترتيب", default=1)
    is_required = models.BooleanField("مطلوب لإكمال الدورة", default=True)
    is_published = models.BooleanField("منشور", default=False, db_index=True)
    due_at = models.DateTimeField("آخر موعد", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course_id", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "slug"],
                name="uniq_learning_assessment_slug",
            ),
            models.UniqueConstraint(
                fields=["course", "order"],
                name="uniq_learning_assessment_order",
            ),
            models.CheckConstraint(
                condition=Q(pass_score__lte=F("max_score")),
                name="learning_assessment_pass_lte_max",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.pass_score is not None
            and self.max_score is not None
            and self.pass_score > self.max_score
        ):
            raise ValidationError({"pass_score": "علامة النجاح لا يمكن أن تتجاوز العلامة القصوى."})
        if self.max_attempts is not None and self.max_attempts < 1:
            raise ValidationError({"max_attempts": "يجب السماح بمحاولة واحدة على الأقل."})

    def __str__(self):
        return f"{self.course}: {self.title}"


class LearningQuestion(models.Model):
    class Choice(models.TextChoices):
        A = "a", "أ"
        B = "b", "ب"
        C = "c", "ج"
        D = "d", "د"

    assessment = models.ForeignKey(
        LearningAssessment,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="الاختبار",
    )
    text = models.TextField("نص السؤال")
    choice_a = models.CharField("الخيار أ", max_length=500)
    choice_b = models.CharField("الخيار ب", max_length=500)
    choice_c = models.CharField("الخيار ج", max_length=500)
    choice_d = models.CharField("الخيار د", max_length=500)
    correct_choice = models.CharField("الإجابة الصحيحة", max_length=1, choices=Choice.choices)
    points = models.PositiveSmallIntegerField("النقاط", default=1)
    order = models.PositiveIntegerField("الترتيب", default=1)

    class Meta:
        ordering = ["assessment_id", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "order"],
                name="uniq_learning_question_order",
            ),
        ]

    def clean(self):
        super().clean()
        if self.assessment_id and self.assessment.assessment_type != LearningAssessment.Type.QUIZ:
            raise ValidationError("الأسئلة الموضوعية مرتبطة بالاختبارات الإلكترونية فقط.")

    def __str__(self):
        return f"{self.assessment}: {self.order}"


class LearningSubmission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "بانتظار التصحيح"
        GRADED = "graded", "مصحح"

    assessment = models.ForeignKey(
        LearningAssessment,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="التقييم",
    )
    enrollment = models.ForeignKey(
        LearningEnrollment,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="تسجيل الدورة",
    )
    attempt_no = models.PositiveSmallIntegerField("رقم المحاولة", default=1)
    answer_text = models.TextField("إجابة الواجب", blank=True)
    answers = models.JSONField("إجابات الاختبار", default=dict, blank=True)
    status = models.CharField(
        "الحالة",
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        db_index=True,
    )
    score = models.DecimalField("العلامة", max_digits=7, decimal_places=2, null=True, blank=True)
    is_passed = models.BooleanField("ناجح", default=False, db_index=True)
    feedback = models.TextField("ملاحظات المصحح", blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        LearningAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions",
    )
    graded_by_label = models.CharField("اسم المصحح", max_length=200, blank=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "enrollment", "attempt_no"],
                name="uniq_learning_submission_attempt",
            ),
        ]

    def clean(self):
        super().clean()
        if self.assessment_id and self.enrollment_id:
            if self.assessment.course_id != self.enrollment.course_id:
                raise ValidationError("يجب أن ينتمي التقييم إلى دورة التسجيل نفسها.")
        if self.score is not None and self.assessment_id:
            if self.score < 0 or self.score > self.assessment.max_score:
                raise ValidationError({"score": "العلامة خارج النطاق المسموح."})

    def __str__(self):
        return f"{self.enrollment.learner} — {self.assessment} — {self.attempt_no}"


class LearningCertificate(models.Model):
    enrollment = models.OneToOneField(
        LearningEnrollment,
        on_delete=models.CASCADE,
        related_name="certificate",
        verbose_name="تسجيل الدورة",
    )
    serial = models.CharField("الرقم التسلسلي", max_length=64, unique=True)
    verification_code = models.CharField("رمز التحقق", max_length=64, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.CharField("سبب الإلغاء", max_length=240, blank=True)

    class Meta:
        ordering = ["-issued_at"]

    @property
    def is_active(self):
        return self.revoked_at is None

    def __str__(self):
        return self.serial


class LearningAuditEvent(models.Model):
    class Action(models.TextChoices):
        REGISTERED = "registered", "تسجيل حساب"
        LOGIN = "login", "تسجيل دخول"
        LOGOUT = "logout", "تسجيل خروج"
        SUBSCRIPTION_ACTIVATED = "subscription_activated", "تفعيل اشتراك"
        SUBSCRIPTION_CREATED = "subscription_created", "إنشاء بطاقة اشتراك"
        SUBSCRIPTION_CANCELLED = "subscription_cancelled", "إلغاء بطاقة اشتراك"
        COURSE_ENROLLED = "course_enrolled", "تسجيل في دورة"
        LESSON_COMPLETED = "lesson_completed", "إكمال درس"
        ASSESSMENT_SUBMITTED = "assessment_submitted", "تسليم تقييم"
        ASSESSMENT_GRADED = "assessment_graded", "تصحيح تقييم"
        CERTIFICATE_ISSUED = "certificate_issued", "إصدار شهادة"
        CERTIFICATE_REVOKED = "certificate_revoked", "إلغاء شهادة"
        PASSWORD_RESET_REQUESTED = "password_reset_requested", "طلب استعادة كلمة المرور"
        PASSWORD_RESET_COMPLETED = "password_reset_completed", "إكمال استعادة كلمة المرور"
        PASSWORD_RESET_BY_MANAGER = "password_reset_by_manager", "إعادة كلمة المرور من المدير"
        NOTIFICATION_READ = "notification_read", "قراءة إشعار"
        AI_REQUESTED = "ai_requested", "طلب مساعدة تعليمية"
        AI_DRAFT_SAVED = "ai_draft_saved", "حفظ مسودة مساعدة"
        AI_DRAFT_REVIEWED = "ai_draft_reviewed", "مراجعة مسودة مساعدة"
        AI_SETTINGS_UPDATED = "ai_settings_updated", "تحديث إعدادات المساعد"

    account = models.ForeignKey(
        LearningAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=40, choices=Action.choices, db_index=True)
    entity_type = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} — {self.created_at:%Y-%m-%d %H:%M}"


class LearningPasswordResetRequest(models.Model):
    class DeliveryStatus(models.TextChoices):
        PENDING = "pending", "بانتظار الإرسال"
        SENT = "sent", "تم الإرسال"
        FAILED = "failed", "تعذر الإرسال"

    account = models.ForeignKey(
        LearningAccount,
        on_delete=models.CASCADE,
        related_name="password_reset_requests",
        verbose_name="الحساب",
    )
    token_hash = models.CharField("بصمة الرمز", max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField("ينتهي في", db_index=True)
    used_at = models.DateTimeField("استخدم في", null=True, blank=True, db_index=True)
    request_ip = models.GenericIPAddressField("عنوان الطلب", null=True, blank=True)
    delivery_status = models.CharField(
        "حالة الإرسال",
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True,
    )
    delivery_error = models.CharField("خطأ الإرسال", max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["account", "used_at", "expires_at"], name="learn_reset_account_idx"),
        ]

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now() and self.account.is_active

    def __str__(self):
        return f"{self.account} — {self.created_at:%Y-%m-%d %H:%M}"


class LearningNotification(models.Model):
    class Type(models.TextChoices):
        SYSTEM = "system", "نظام"
        SUBSCRIPTION = "subscription", "اشتراك"
        COURSE = "course", "دورة"
        ASSESSMENT = "assessment", "تقييم"
        CERTIFICATE = "certificate", "شهادة"

    recipient = models.ForeignKey(
        LearningAccount,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="المستلم",
    )
    notification_type = models.CharField(
        "النوع", max_length=24, choices=Type.choices, default=Type.SYSTEM, db_index=True
    )
    title = models.CharField("العنوان", max_length=180)
    body = models.CharField("النص", max_length=500)
    action_url = models.CharField("رابط الإجراء", max_length=500, blank=True)
    dedupe_key = models.CharField("مفتاح منع التكرار", max_length=180, blank=True)
    read_at = models.DateTimeField("قُرئ في", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "dedupe_key"],
                condition=~Q(dedupe_key=""),
                name="uniq_learning_notification_dedupe",
            ),
        ]
        indexes = [
            models.Index(fields=["recipient", "read_at", "created_at"], name="learn_notice_inbox_idx"),
        ]

    @property
    def is_read(self):
        return self.read_at is not None

    def mark_read(self, *, at=None):
        if self.read_at is None:
            self.read_at = at or timezone.now()
            self.save(update_fields=["read_at"])
        return self

    def __str__(self):
        return f"{self.recipient}: {self.title}"


class LearningAISettings(models.Model):
    """Singleton governance settings for the independent learning assistant."""

    DEFAULT_POLICY = (
        "استخدم محتوى الدورة المنشور فقط. صرّح بوضوح عندما لا يكفي المحتوى للإجابة. "
        "لا تصدر قرارًا نهائيًا بشأن العلامات أو النجاح أو الاشتراك، ولا تنشر محتوى تلقائيًا."
    )

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    assistant_enabled = models.BooleanField("مساعد المتعلم فعال", default=True)
    teacher_tools_enabled = models.BooleanField("أدوات المدرّس فعالة", default=True)
    external_provider_enabled = models.BooleanField("السماح بالمزود الخارجي", default=False)
    local_reference_enabled = models.BooleanField("المرجع المحلي عند تعذر المزود", default=True)
    learner_daily_limit = models.PositiveSmallIntegerField("حد المتعلم اليومي", default=20)
    teacher_daily_limit = models.PositiveSmallIntegerField("حد المدرّس اليومي", default=30)
    max_context_chars = models.PositiveIntegerField("أقصى حجم للسياق", default=12000)
    max_output_chars = models.PositiveIntegerField("أقصى حجم للإجابة", default=4000)
    policy_text = models.TextField("سياسة المساعد", default=DEFAULT_POLICY)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "إعدادات مساعد المنصة"
        verbose_name_plural = "إعدادات مساعد المنصة"
        constraints = [
            models.CheckConstraint(
                condition=Q(learner_daily_limit__gte=1, teacher_daily_limit__gte=1),
                name="learning_ai_daily_limits_positive",
            ),
            models.CheckConstraint(
                condition=Q(max_context_chars__gte=1000, max_output_chars__gte=500),
                name="learning_ai_size_limits_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        return super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        settings_row, _created = cls.objects.get_or_create(singleton_key=1)
        return settings_row

    def __str__(self):
        return "إعدادات مساعد منصة أوبال التعليمية"


class LearningAIInteraction(models.Model):
    class Type(models.TextChoices):
        LEARNER_QUESTION = "learner_question", "سؤال متعلم"
        TEACHER_SUMMARY = "teacher_summary", "ملخص للمدرّس"
        TEACHER_OUTLINE = "teacher_outline", "خطة درس"
        TEACHER_REVIEW_QUESTIONS = "teacher_review_questions", "أسئلة مراجعة"
        TEACHER_ASSIGNMENT = "teacher_assignment", "مسودة واجب"

    class Status(models.TextChoices):
        SUCCESS = "success", "ناجح"
        LOCAL_REFERENCE = "local_reference", "مرجع محلي"
        PROVIDER_ERROR = "provider_error", "تعذر المزود"
        REJECTED = "rejected", "مرفوض"

    account = models.ForeignKey(
        LearningAccount,
        on_delete=models.CASCADE,
        related_name="ai_interactions",
        verbose_name="الحساب",
    )
    course = models.ForeignKey(
        LearningCourse,
        on_delete=models.CASCADE,
        related_name="ai_interactions",
        verbose_name="الدورة",
    )
    interaction_type = models.CharField("نوع الطلب", max_length=32, choices=Type.choices, db_index=True)
    prompt = models.TextField("الطلب")
    response = models.TextField("الإجابة", blank=True)
    status = models.CharField("الحالة", max_length=24, choices=Status.choices, db_index=True)
    provider_mode = models.CharField("وضع المزود", max_length=32, blank=True)
    provider_name = models.CharField("اسم المزود", max_length=80, blank=True)
    model_name = models.CharField("اسم النموذج", max_length=120, blank=True)
    source_lesson_ids = models.JSONField("معرفات الدروس المرجعية", default=list, blank=True)
    source_labels = models.JSONField("المراجع الظاهرة", default=list, blank=True)
    input_chars = models.PositiveIntegerField(default=0)
    output_chars = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    error_message = models.CharField("الخطأ", max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["account", "created_at"], name="learn_ai_account_day_idx"),
            models.Index(fields=["course", "created_at"], name="learn_ai_course_day_idx"),
        ]

    def clean(self):
        super().clean()
        if self.account_id and self.course_id:
            if self.account.role == LearningAccount.Role.TEACHER and self.course.teacher_id != self.account_id:
                raise ValidationError("لا يمكن للمدرّس استخدام مساعد دورة لا يديرها.")

    def __str__(self):
        return f"{self.account} — {self.get_interaction_type_display()}"


class LearningAIDraft(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        ACCEPTED = "accepted", "معتمدة للمراجعة اليدوية"
        DISCARDED = "discarded", "مستبعدة"

    teacher = models.ForeignKey(
        LearningAccount,
        on_delete=models.CASCADE,
        related_name="ai_drafts",
        verbose_name="المدرّس",
    )
    course = models.ForeignKey(
        LearningCourse,
        on_delete=models.CASCADE,
        related_name="ai_drafts",
        verbose_name="الدورة",
    )
    interaction = models.OneToOneField(
        LearningAIInteraction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saved_draft",
    )
    draft_type = models.CharField("نوع المسودة", max_length=32, choices=LearningAIInteraction.Type.choices)
    title = models.CharField("العنوان", max_length=220)
    content = models.TextField("المحتوى")
    status = models.CharField("الحالة", max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["teacher", "status", "updated_at"], name="learn_ai_draft_teacher_idx"),
        ]

    def clean(self):
        super().clean()
        if self.teacher_id and self.teacher.role != LearningAccount.Role.TEACHER:
            raise ValidationError({"teacher": "المسودة التعليمية ترتبط بحساب مدرّس فقط."})
        if self.teacher_id and self.course_id and self.course.teacher_id != self.teacher_id:
            raise ValidationError("لا يمكن حفظ مسودة للمدرّس خارج دورته.")

    def __str__(self):
        return self.title

class LearningEmailVerificationRequest(models.Model):
    account = models.ForeignKey(
        LearningAccount,
        on_delete=models.CASCADE,
        related_name="email_verification_requests",
        verbose_name="الحساب",
    )
    token_hash = models.CharField("بصمة الرمز", max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField("ينتهي في", db_index=True)
    used_at = models.DateTimeField("استخدم في", null=True, blank=True, db_index=True)
    request_ip = models.GenericIPAddressField("عنوان الطلب", null=True, blank=True)
    delivery_status = models.CharField(
        "حالة الإرسال",
        max_length=20,
        choices=LearningPasswordResetRequest.DeliveryStatus.choices,
        default=LearningPasswordResetRequest.DeliveryStatus.PENDING,
        db_index=True,
    )
    delivery_error = models.CharField("خطأ الإرسال", max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["account", "used_at", "expires_at"], name="learn_verify_account_idx"),
        ]

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now() and self.account.is_active

    def __str__(self):
        return f"{self.account} — توثيق البريد"


class LearningAccessSettings(models.Model):
    """School-owned switches controlling ERP-to-learning access."""

    school = models.OneToOneField(
        "core.School", on_delete=models.CASCADE, related_name="learning_access_settings"
    )
    parent_default_enabled = models.BooleanField("إتاحة المنصة لأولياء الأمور افتراضيًا", default=False)
    teacher_sso_enabled = models.BooleanField("إتاحة المنصة للمعلمين", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "إعداد وصول منصة أوبال التعليمية"
        verbose_name_plural = "إعدادات وصول منصة أوبال التعليمية"

    def __str__(self):
        return f"{self.school} — وصول المنصة"


class LearningGradeAccessOverride(models.Model):
    settings = models.ForeignKey(
        LearningAccessSettings, on_delete=models.CASCADE, related_name="grade_overrides"
    )
    grade = models.OneToOneField(
        "academics.Grade", on_delete=models.CASCADE, related_name="learning_access_override"
    )
    is_enabled = models.BooleanField("متاح للصف")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["grade__order", "grade__name"]

    def __str__(self):
        return f"{self.grade}: {'متاح' if self.is_enabled else 'موقوف'}"


class LearningStudentAccessOverride(models.Model):
    settings = models.ForeignKey(
        LearningAccessSettings, on_delete=models.CASCADE, related_name="student_overrides"
    )
    student = models.OneToOneField(
        "students.Student", on_delete=models.CASCADE, related_name="learning_access_override"
    )
    is_enabled = models.BooleanField("متاح للطالب")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student__full_name", "student_id"]

    def __str__(self):
        return f"{self.student}: {'متاح' if self.is_enabled else 'موقوف'}"


class LearningStudentProfile(models.Model):
    student = models.OneToOneField(
        "students.Student", on_delete=models.CASCADE, related_name="learning_profile"
    )
    account = models.OneToOneField(
        LearningAccount, on_delete=models.CASCADE, related_name="school_student_profile"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} — {self.account}"


class LearningTeacherProfile(models.Model):
    teacher = models.OneToOneField(
        "teachers.Teacher", on_delete=models.CASCADE, related_name="learning_profile"
    )
    account = models.OneToOneField(
        LearningAccount, on_delete=models.CASCADE, related_name="school_teacher_profile"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.teacher} — {self.account}"


class LearningSubscriptionPlan(models.Model):
    name = models.CharField("اسم الخطة", max_length=160)
    slug = models.SlugField("المعرف", max_length=180, unique=True, allow_unicode=True)
    duration = models.CharField(
        "المدة",
        max_length=20,
        choices=LearningSubscriptionCard.Duration.choices,
    )
    price = models.DecimalField("السعر", max_digits=10, decimal_places=3)
    currency = models.CharField("العملة", max_length=3, default="JOD")
    grants_all_subjects = models.BooleanField("جميع المواد", default=False)
    subjects = models.ManyToManyField(LearningSubject, blank=True, related_name="subscription_plans")
    is_active = models.BooleanField("فعالة", default=True, db_index=True)
    display_order = models.PositiveSmallIntegerField("الترتيب", default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "price", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(price__gte=0), name="learning_plan_price_nonnegative"),
        ]

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "JOD").strip().upper()[:3]
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class LearningPaymentOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "بانتظار الدفع"
        PROCESSING = "processing", "قيد المعالجة"
        PAID = "paid", "مدفوع"
        FAILED = "failed", "فشل"
        CANCELLED = "cancelled", "ملغي"
        REFUNDED = "refunded", "مسترد"

    public_id = models.CharField("المعرف العام", max_length=40, unique=True, db_index=True)
    learner = models.ForeignKey(
        LearningAccount,
        on_delete=models.PROTECT,
        related_name="payment_orders",
        verbose_name="المتعلم",
    )
    plan = models.ForeignKey(
        LearningSubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="payment_orders",
        verbose_name="الخطة",
    )
    amount = models.DecimalField("المبلغ", max_digits=10, decimal_places=3)
    currency = models.CharField("العملة", max_length=3, default="JOD")
    status = models.CharField("الحالة", max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    provider = models.CharField("مزود الدفع", max_length=80, default="manual")
    provider_reference = models.CharField("مرجع المزود", max_length=160, blank=True, db_index=True)
    checkout_url = models.URLField("رابط الدفع", max_length=1000, blank=True)
    idempotency_key = models.CharField("مفتاح منع التكرار", max_length=80, unique=True)
    subscription_card = models.OneToOneField(
        LearningSubscriptionCard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_order",
    )
    paid_at = models.DateTimeField(null=True, blank=True, db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField("سبب الفشل", max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="learning_payment_amount_nonnegative"),
        ]
        indexes = [
            models.Index(fields=["learner", "status", "created_at"], name="learn_pay_learner_idx"),
            models.Index(fields=["provider", "provider_reference"], name="learn_pay_provider_idx"),
        ]

    def clean(self):
        super().clean()
        if self.learner_id and self.learner.role != LearningAccount.Role.LEARNER:
            raise ValidationError({"learner": "أوامر الدفع متاحة لحساب المتعلم فقط."})
        if self.plan_id and self.amount != self.plan.price:
            raise ValidationError({"amount": "يجب أن يطابق مبلغ الطلب سعر الخطة."})

    def __str__(self):
        return f"{self.public_id} — {self.learner}"


class LearningPaymentEvent(models.Model):
    order = models.ForeignKey(
        LearningPaymentOrder,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="طلب الدفع",
    )
    provider_event_id = models.CharField("معرف حدث المزود", max_length=180, unique=True)
    event_type = models.CharField("نوع الحدث", max_length=80)
    signature_valid = models.BooleanField("التوقيع صحيح", default=False)
    payload_hash = models.CharField("بصمة الحمولة", max_length=64)
    payload = models.JSONField("الحمولة", default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.provider_event_id} — {self.event_type}"


class LearningAPIToken(models.Model):
    account = models.ForeignKey(
        LearningAccount,
        on_delete=models.CASCADE,
        related_name="api_tokens",
        verbose_name="الحساب",
    )
    token_hash = models.CharField("بصمة الرمز", max_length=64, unique=True, db_index=True)
    token_prefix = models.CharField("بداية الرمز", max_length=12, db_index=True)
    device_name = models.CharField("اسم الجهاز", max_length=120, blank=True)
    expires_at = models.DateTimeField("ينتهي في", db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["account", "revoked_at", "expires_at"], name="learn_api_account_idx"),
        ]

    @property
    def is_valid(self):
        return self.revoked_at is None and self.expires_at > timezone.now() and self.account.is_active

    def __str__(self):
        return f"{self.account} — {self.device_name or self.token_prefix}"


class LearningManagerAPIToken(models.Model):
    """Short-lived mobile token bound directly to an OPAL ERP management user.

    Management authentication deliberately remains rooted in Django/OPAL ERP rather
    than creating a second platform password. The token stores only an opaque hash.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_manager_api_tokens",
        verbose_name="مستخدم OPAL ERP",
    )
    token_hash = models.CharField("بصمة الرمز", max_length=64, unique=True, db_index=True)
    token_prefix = models.CharField("بداية الرمز", max_length=12, db_index=True)
    device_name = models.CharField("اسم الجهاز", max_length=120, blank=True)
    expires_at = models.DateTimeField("ينتهي في", db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "revoked_at", "expires_at"], name="learn_mgr_api_user_idx"),
        ]

    @property
    def is_valid(self):
        if self.revoked_at is not None or self.expires_at <= timezone.now() or not self.user.is_active:
            return False
        from accounts.workflow import is_management_user

        return is_management_user(self.user)

    def __str__(self):
        return f"{self.user.get_username()} — {self.device_name or self.token_prefix}"


class LearningRateLimitBucket(models.Model):
    key_hash = models.CharField("مفتاح الحد", max_length=64, unique=True, db_index=True)
    action = models.CharField("العملية", max_length=40, db_index=True)
    window_started_at = models.DateTimeField("بداية النافذة", db_index=True)
    count = models.PositiveIntegerField("العدد", default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["action", "window_started_at"], name="learn_rate_window_idx"),
        ]

    def __str__(self):
        return f"{self.action}: {self.count}"

