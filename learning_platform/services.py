import secrets
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.mail import send_mail

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import (
    LearningAccount,
    LearningAssessment,
    LearningAuditEvent,
    LearningCertificate,
    LearningCourse,
    LearningEnrollment,
    LearningLesson,
    LearningLessonProgress,
    LearningNotification,
    LearningPasswordResetRequest,
    LearningSubmission,
    LearningSubscriptionCard,
)



def _password_reset_token_hash(raw_token):
    return salted_hmac(
        "opal-learning-password-reset",
        raw_token,
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def create_learning_notification(
    recipient,
    *,
    notification_type=LearningNotification.Type.SYSTEM,
    title,
    body,
    action_url="",
    dedupe_key="",
):
    if recipient is None or not recipient.is_active:
        return None
    values = {
        "notification_type": notification_type,
        "title": title[:180],
        "body": body[:500],
        "action_url": action_url[:500],
    }
    if dedupe_key:
        notification, _created = LearningNotification.objects.get_or_create(
            recipient=recipient,
            dedupe_key=dedupe_key[:180],
            defaults=values,
        )
        return notification
    return LearningNotification.objects.create(recipient=recipient, **values)


def sync_account_notifications(account, *, at=None):
    """Create idempotent expiry notices for the signed-in platform account."""
    if account is None or account.role != LearningAccount.Role.LEARNER:
        return 0
    moment = at or timezone.now()
    created_before = account.notifications.count()
    cards = account.subscription_cards.filter(
        status=LearningSubscriptionCard.Status.REDEEMED,
        expires_at__isnull=False,
    ).order_by("expires_at", "id")
    for card in cards:
        local_expiry = timezone.localtime(card.expires_at)
        date_key = local_expiry.date().isoformat()
        if card.expires_at <= moment:
            create_learning_notification(
                account,
                notification_type=LearningNotification.Type.SUBSCRIPTION,
                title="انتهى اشتراكك التعليمي",
                body=f"انتهت صلاحية البطاقة {card.code}. فعّل بطاقة جديدة لمتابعة الدورات المشمولة.",
                action_url=reverse("learning_platform:subscriptions"),
                dedupe_key=f"subscription-expired:{card.pk}:{date_key}",
            )
        elif card.expires_at <= moment + timedelta(days=7):
            days = max(1, (card.expires_at.date() - moment.date()).days)
            create_learning_notification(
                account,
                notification_type=LearningNotification.Type.SUBSCRIPTION,
                title="اشتراكك يقترب من الانتهاء",
                body=f"تنتهي البطاقة {card.code} خلال {days} يوم/أيام.",
                action_url=reverse("learning_platform:subscriptions"),
                dedupe_key=f"subscription-expiring:{card.pk}:{date_key}",
            )
    return max(0, account.notifications.count() - created_before)


@transaction.atomic
def create_password_reset_request(account, *, ip_address=None, expires_minutes=None):
    if not account.is_active or account.role == LearningAccount.Role.MANAGER:
        raise ValidationError("هذا الحساب غير مؤهل للاستعادة الذاتية.")
    now = timezone.now()
    minutes = expires_minutes or int(getattr(settings, "OPAL_LEARNING_PASSWORD_RESET_MINUTES", 60))
    LearningPasswordResetRequest.objects.filter(
        account=account,
        used_at__isnull=True,
        expires_at__gt=now,
    ).update(used_at=now)
    raw_token = secrets.token_urlsafe(32)
    reset_request = LearningPasswordResetRequest.objects.create(
        account=account,
        token_hash=_password_reset_token_hash(raw_token),
        expires_at=now + timedelta(minutes=minutes),
        request_ip=ip_address,
    )
    LearningAuditEvent.objects.create(
        account=account,
        action=LearningAuditEvent.Action.PASSWORD_RESET_REQUESTED,
        entity_type="learning_password_reset",
        entity_id=str(reset_request.pk),
        ip_address=ip_address,
    )
    return reset_request, raw_token


def deliver_password_reset_email(reset_request, raw_token, reset_url):
    if not getattr(settings, "OPAL_LEARNING_EMAIL_ENABLED", False):
        reset_request.delivery_status = LearningPasswordResetRequest.DeliveryStatus.FAILED
        reset_request.delivery_error = "إرسال البريد غير مهيأ في إعدادات البيئة."
        reset_request.save(update_fields=["delivery_status", "delivery_error"])
        return False
    subject = "استعادة كلمة المرور — منصة أوبال التعليمية"
    body = (
        f"مرحبًا {reset_request.account.full_name}،\n\n"
        "وصلنا طلب لتغيير كلمة مرور حسابك في منصة أوبال التعليمية. "
        "استخدم الرابط التالي قبل انتهاء صلاحيته:\n"
        f"{reset_url}\n\n"
        "إذا لم تطلب ذلك، تجاهل الرسالة ولا تشارك الرابط مع أي شخص."
    )
    try:
        sent = send_mail(
            subject,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@opal-learning.local"),
            [reset_request.account.email],
            fail_silently=False,
        )
        if sent != 1:
            raise RuntimeError("لم يقبل مزود البريد الرسالة.")
    except Exception as exc:
        reset_request.delivery_status = LearningPasswordResetRequest.DeliveryStatus.FAILED
        reset_request.delivery_error = str(exc)[:240]
        reset_request.save(update_fields=["delivery_status", "delivery_error"])
        return False
    reset_request.delivery_status = LearningPasswordResetRequest.DeliveryStatus.SENT
    reset_request.delivery_error = ""
    reset_request.save(update_fields=["delivery_status", "delivery_error"])
    return True


def find_valid_password_reset(raw_token):
    if not raw_token:
        return None
    return (
        LearningPasswordResetRequest.objects.select_related("account")
        .filter(
            token_hash=_password_reset_token_hash(raw_token),
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
            account__is_active=True,
        )
        .first()
    )


@transaction.atomic
def complete_password_reset(reset_request, new_password, *, ip_address=None, manager_label=""):
    locked = (
        LearningPasswordResetRequest.objects.select_for_update()
        .select_related("account")
        .get(pk=reset_request.pk)
    )
    now = timezone.now()
    if locked.used_at is not None or locked.expires_at <= now or not locked.account.is_active:
        raise ValidationError("رابط الاستعادة منتهي أو مستخدم سابقًا.")
    account = LearningAccount.objects.select_for_update().get(pk=locked.account_id)
    account.set_password(new_password)
    account.password_changed_at = now
    account.auth_version = account.auth_version + 1
    account.failed_login_count = 0
    account.locked_until = None
    account.save(update_fields=["password", "password_changed_at", "auth_version", "failed_login_count", "locked_until", "updated_at"])
    account.api_tokens.filter(revoked_at__isnull=True).update(revoked_at=now)
    locked.used_at = now
    locked.save(update_fields=["used_at"])
    LearningPasswordResetRequest.objects.filter(
        account=account, used_at__isnull=True
    ).exclude(pk=locked.pk).update(used_at=now)
    LearningAuditEvent.objects.create(
        account=account,
        action=LearningAuditEvent.Action.PASSWORD_RESET_COMPLETED,
        entity_type="learning_password_reset",
        entity_id=str(locked.pk),
        ip_address=ip_address,
        metadata={"manager_label": manager_label} if manager_label else {},
    )
    create_learning_notification(
        account,
        title="تم تغيير كلمة المرور",
        body="تم تغيير كلمة مرور حسابك التعليمي. إذا لم تكن أنت، تواصل مع إدارة المنصة فورًا.",
        dedupe_key=f"password-reset-completed:{locked.pk}",
    )
    return account


@transaction.atomic
def reset_password_by_manager(account, raw_password, *, manager_label, ip_address=None):
    account = LearningAccount.objects.select_for_update().get(pk=account.pk)
    if account.role == LearningAccount.Role.MANAGER:
        raise ValidationError("مدير المنصة يستخدم حساب OPAL ERP ولا يعاد ضبطه من هنا.")
    now = timezone.now()
    account.set_password(raw_password)
    account.password_changed_at = now
    account.auth_version = account.auth_version + 1
    account.failed_login_count = 0
    account.locked_until = None
    account.save(update_fields=["password", "password_changed_at", "auth_version", "failed_login_count", "locked_until", "updated_at"])
    account.api_tokens.filter(revoked_at__isnull=True).update(revoked_at=now)
    LearningPasswordResetRequest.objects.filter(
        account=account, used_at__isnull=True
    ).update(used_at=now)
    LearningAuditEvent.objects.create(
        account=account,
        action=LearningAuditEvent.Action.PASSWORD_RESET_BY_MANAGER,
        entity_type="learning_account",
        entity_id=str(account.pk),
        ip_address=ip_address,
        metadata={"manager_label": manager_label},
    )
    create_learning_notification(
        account,
        title="أعادت الإدارة ضبط كلمة المرور",
        body="استخدم كلمة المرور المؤقتة التي زودتك بها الإدارة ثم احتفظ بها بسرية.",
        dedupe_key=f"manager-password-reset:{account.pk}:{account.auth_version}",
    )
    return account

def current_entitlement(account, subject, *, at=None):
    """Return the active subscription card that grants access to a subject."""
    if not account or account.role != LearningAccount.Role.LEARNER:
        return None
    moment = at or timezone.now()
    return (
        LearningSubscriptionCard.objects.filter(
            redeemed_by=account,
            status=LearningSubscriptionCard.Status.REDEEMED,
            expires_at__gt=moment,
        )
        .filter(Q(grants_all_subjects=True) | Q(subjects=subject))
        .distinct()
        .order_by("-expires_at", "-id")
        .first()
    )


def learner_can_access_course(account, course, *, at=None):
    if not account or account.role != LearningAccount.Role.LEARNER:
        return False
    if not account.is_active:
        return False
    if course.status != LearningCourse.Status.PUBLISHED or not course.subject.is_active:
        return False
    return current_entitlement(account, course.subject, at=at) is not None


@transaction.atomic
def enroll_learner(account, course, *, ip_address=None):
    if account.role != LearningAccount.Role.LEARNER:
        raise ValidationError("التسجيل في الدورات متاح لحساب المتعلم فقط.")
    if not learner_can_access_course(account, course):
        raise ValidationError("تحتاج إلى اشتراك فعال يشمل مادة هذه الدورة.")

    enrollment, created = LearningEnrollment.objects.select_for_update().get_or_create(
        learner=account,
        course=course,
        defaults={
            "status": LearningEnrollment.Status.ACTIVE,
            "last_activity_at": timezone.now(),
        },
    )
    if not created and enrollment.status == LearningEnrollment.Status.CANCELLED:
        enrollment.status = LearningEnrollment.Status.ACTIVE
        enrollment.completed_at = None
        enrollment.last_activity_at = timezone.now()
        enrollment.save(update_fields=["status", "completed_at", "last_activity_at"])
    elif not created:
        enrollment.last_activity_at = timezone.now()
        enrollment.save(update_fields=["last_activity_at"])

    if created:
        create_learning_notification(
            account,
            notification_type=LearningNotification.Type.COURSE,
            title="تم تسجيلك في دورة جديدة",
            body=f"أصبحت مسجلًا في دورة {course.title} ويمكنك بدء التعلم الآن.",
            action_url=reverse("learning_platform:course_detail", kwargs={"slug": course.slug}),
            dedupe_key=f"course-enrolled:{enrollment.pk}",
        )
        LearningAuditEvent.objects.create(
            account=account,
            action=LearningAuditEvent.Action.COURSE_ENROLLED,
            entity_type="learning_course",
            entity_id=str(course.pk),
            ip_address=ip_address,
            metadata={"course_slug": course.slug},
        )
    return enrollment, created


def first_incomplete_lesson(enrollment):
    if enrollment is None:
        return None
    completed_ids = LearningLessonProgress.objects.filter(
        enrollment=enrollment,
        completed_at__isnull=False,
    ).values_list("lesson_id", flat=True)
    return (
        LearningLesson.objects.filter(
            course=enrollment.course,
            is_published=True,
        )
        .exclude(pk__in=completed_ids)
        .order_by("order", "id")
        .first()
    )


def _certificate_serial(enrollment):
    return f"OPAL-LRN-{timezone.localdate():%Y}-{enrollment.pk:07d}"


@transaction.atomic
def issue_certificate(enrollment):
    """Create or reactivate the canonical certificate for a completed enrollment."""
    if enrollment.status != LearningEnrollment.Status.COMPLETED:
        return None
    certificate, created = LearningCertificate.objects.get_or_create(
        enrollment=enrollment,
        defaults={
            "serial": _certificate_serial(enrollment),
            "verification_code": secrets.token_urlsafe(18),
        },
    )
    if not created and certificate.revoked_at is not None:
        certificate.revoked_at = None
        certificate.revocation_reason = ""
        certificate.save(update_fields=["revoked_at", "revocation_reason"])
    if created or certificate.revoked_at is None:
        LearningAuditEvent.objects.get_or_create(
            account=enrollment.learner,
            action=LearningAuditEvent.Action.CERTIFICATE_ISSUED,
            entity_type="learning_certificate",
            entity_id=str(certificate.pk),
            defaults={
                "metadata": {
                    "course_id": enrollment.course_id,
                    "serial": certificate.serial,
                }
            },
        )
        create_learning_notification(
            enrollment.learner,
            notification_type=LearningNotification.Type.CERTIFICATE,
            title="صدرت شهادتك",
            body=f"أكملت دورة {enrollment.course.title} وأصبحت شهادتك الرقمية جاهزة.",
            action_url=reverse(
                "learning_platform:certificate_detail",
                kwargs={"course_slug": enrollment.course.slug},
            ),
            dedupe_key=f"certificate-issued:{certificate.pk}:{certificate.issued_at.isoformat()}",
        )
    return certificate


@transaction.atomic
def revoke_certificate(enrollment, *, reason="تغيرت متطلبات إكمال الدورة."):
    certificate = LearningCertificate.objects.filter(enrollment=enrollment, revoked_at__isnull=True).first()
    if certificate is None:
        return None
    certificate.revoked_at = timezone.now()
    certificate.revocation_reason = reason
    certificate.save(update_fields=["revoked_at", "revocation_reason"])
    LearningAuditEvent.objects.create(
        account=enrollment.learner,
        action=LearningAuditEvent.Action.CERTIFICATE_REVOKED,
        entity_type="learning_certificate",
        entity_id=str(certificate.pk),
        metadata={"course_id": enrollment.course_id, "reason": reason},
    )
    return certificate


@transaction.atomic
def refresh_enrollment_progress(enrollment, *, touch_activity=True):
    locked = LearningEnrollment.objects.select_for_update().select_related("course", "learner").get(
        pk=enrollment.pk
    )
    published_lessons = LearningLesson.objects.filter(
        course=locked.course,
        is_published=True,
    )
    required_assessments = LearningAssessment.objects.filter(
        course=locked.course,
        is_published=True,
        is_required=True,
    )
    lesson_total = published_lessons.count()
    completed_lessons = LearningLessonProgress.objects.filter(
        enrollment=locked,
        lesson__in=published_lessons,
        completed_at__isnull=False,
    ).count()
    assessment_total = required_assessments.count()
    passed_assessments = (
        LearningSubmission.objects.filter(
            enrollment=locked,
            assessment__in=required_assessments,
            status=LearningSubmission.Status.GRADED,
            is_passed=True,
        )
        .values("assessment_id")
        .distinct()
        .count()
    )

    total = lesson_total + assessment_total
    completed = completed_lessons + passed_assessments
    percent = round((completed * 100) / total) if total else 0
    now = timezone.now()

    locked.progress_percent = percent
    if touch_activity:
        locked.last_activity_at = now
    completed_now = bool(total and completed == total)
    if completed_now:
        locked.status = LearningEnrollment.Status.COMPLETED
        locked.completed_at = locked.completed_at or now
    elif locked.status != LearningEnrollment.Status.CANCELLED:
        locked.status = LearningEnrollment.Status.ACTIVE
        locked.completed_at = None
    update_fields = ["progress_percent", "status", "completed_at"]
    if touch_activity:
        update_fields.append("last_activity_at")
    locked.save(update_fields=update_fields)

    if completed_now:
        issue_certificate(locked)
    else:
        revoke_certificate(locked)

    enrollment.refresh_from_db()
    return enrollment


def refresh_course_enrollments(course):
    """Recalculate stored progress after published lessons or assessments change."""
    refreshed = 0
    for enrollment in course.enrollments.exclude(
        status=LearningEnrollment.Status.CANCELLED
    ).iterator():
        refresh_enrollment_progress(enrollment, touch_activity=False)
        refreshed += 1
    return refreshed


@transaction.atomic
def mark_lesson_completed(enrollment, lesson, *, ip_address=None):
    if lesson.course_id != enrollment.course_id or not lesson.is_published:
        raise ValidationError("هذا الدرس لا ينتمي إلى تسجيلك الحالي أو لم يعد منشورًا.")
    if enrollment.status == LearningEnrollment.Status.CANCELLED:
        raise ValidationError("هذا التسجيل ملغي ولا يمكن تحديث تقدمه.")
    if not learner_can_access_course(enrollment.learner, enrollment.course):
        raise ValidationError("انتهى الاشتراك الذي يمنح الوصول إلى هذه الدورة.")

    progress, created = LearningLessonProgress.objects.select_for_update().get_or_create(
        enrollment=enrollment,
        lesson=lesson,
        defaults={
            "last_viewed_at": timezone.now(),
            "completed_at": timezone.now(),
        },
    )
    transitioned = created or progress.completed_at is None
    if not created and progress.completed_at is None:
        progress.completed_at = timezone.now()
        progress.last_viewed_at = timezone.now()
        progress.save(update_fields=["completed_at", "last_viewed_at"])
    elif not created:
        progress.last_viewed_at = timezone.now()
        progress.save(update_fields=["last_viewed_at"])

    refresh_enrollment_progress(enrollment)
    if transitioned:
        LearningAuditEvent.objects.create(
            account=enrollment.learner,
            action=LearningAuditEvent.Action.LESSON_COMPLETED,
            entity_type="learning_lesson",
            entity_id=str(lesson.pk),
            ip_address=ip_address,
            metadata={
                "course_id": enrollment.course_id,
                "progress_percent": enrollment.progress_percent,
            },
        )
    return progress, enrollment


def _validate_assessment_attempt(enrollment, assessment):
    if assessment.course_id != enrollment.course_id or not assessment.is_published:
        raise ValidationError("هذا التقييم غير متاح ضمن تسجيلك الحالي.")
    if enrollment.status == LearningEnrollment.Status.CANCELLED:
        raise ValidationError("هذا التسجيل ملغي.")
    if assessment.due_at and assessment.due_at < timezone.now():
        raise ValidationError("انتهى الموعد المحدد لهذا التقييم.")
    if not learner_can_access_course(enrollment.learner, enrollment.course):
        raise ValidationError("انتهى الاشتراك الذي يمنح الوصول إلى هذه الدورة.")
    if LearningSubmission.objects.filter(
        enrollment=enrollment,
        assessment=assessment,
        status=LearningSubmission.Status.GRADED,
        is_passed=True,
    ).exists():
        raise ValidationError("لقد اجتزت هذا التقييم بنجاح ولا تحتاج إلى محاولة جديدة.")
    attempts = LearningSubmission.objects.filter(enrollment=enrollment, assessment=assessment).count()
    if attempts >= assessment.max_attempts:
        raise ValidationError("استنفدت عدد المحاولات المتاحة لهذا التقييم.")
    return attempts + 1


@transaction.atomic
def submit_quiz(enrollment, assessment, answers, *, ip_address=None):
    enrollment = (
        LearningEnrollment.objects.select_for_update()
        .select_related("learner", "course", "course__subject")
        .get(pk=enrollment.pk)
    )
    assessment = LearningAssessment.objects.select_for_update().get(pk=assessment.pk)
    if assessment.assessment_type != LearningAssessment.Type.QUIZ:
        raise ValidationError("هذا التقييم ليس اختبارًا إلكترونيًا.")
    attempt_no = _validate_assessment_attempt(enrollment, assessment)
    questions = list(assessment.questions.order_by("order", "id"))
    if not questions:
        raise ValidationError("لا يحتوي الاختبار على أسئلة منشورة للاعتماد.")
    total_points = sum(question.points for question in questions)
    if total_points <= 0:
        raise ValidationError("مجموع نقاط الاختبار غير صالح.")
    earned_points = sum(
        question.points
        for question in questions
        if answers.get(str(question.pk)) == question.correct_choice
    )
    score = (
        (Decimal(earned_points) * Decimal(assessment.max_score)) / Decimal(total_points)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    passed = score >= Decimal(assessment.pass_score)
    now = timezone.now()
    submission = LearningSubmission.objects.create(
        assessment=assessment,
        enrollment=enrollment,
        attempt_no=attempt_no,
        answers=answers,
        status=LearningSubmission.Status.GRADED,
        score=score,
        is_passed=passed,
        feedback="تم التصحيح تلقائيًا.",
        graded_at=now,
        graded_by_label="التصحيح الآلي لمنصة أوبال",
    )
    refresh_enrollment_progress(enrollment)
    create_learning_notification(
        enrollment.learner,
        notification_type=LearningNotification.Type.ASSESSMENT,
        title="ظهرت نتيجة الاختبار",
        body=f"نتيجتك في {assessment.title}: {score} من {assessment.max_score} — {'ناجح' if passed else 'لم يجتز'}.",
        action_url=reverse(
            "learning_platform:assessment_detail",
            kwargs={"course_slug": enrollment.course.slug, "assessment_slug": assessment.slug},
        ),
        dedupe_key=f"quiz-result:{submission.pk}",
    )
    LearningAuditEvent.objects.create(
        account=enrollment.learner,
        action=LearningAuditEvent.Action.ASSESSMENT_SUBMITTED,
        entity_type="learning_submission",
        entity_id=str(submission.pk),
        ip_address=ip_address,
        metadata={
            "assessment_id": assessment.pk,
            "attempt_no": attempt_no,
            "auto_graded": True,
            "score": str(score),
            "passed": passed,
        },
    )
    return submission, enrollment


@transaction.atomic
def submit_assignment(enrollment, assessment, answer_text, *, ip_address=None):
    enrollment = (
        LearningEnrollment.objects.select_for_update()
        .select_related("learner", "course", "course__subject")
        .get(pk=enrollment.pk)
    )
    assessment = LearningAssessment.objects.select_for_update().get(pk=assessment.pk)
    if assessment.assessment_type != LearningAssessment.Type.ASSIGNMENT:
        raise ValidationError("هذا التقييم ليس واجبًا.")
    pending = LearningSubmission.objects.filter(
        enrollment=enrollment,
        assessment=assessment,
        status=LearningSubmission.Status.SUBMITTED,
    ).exists()
    if pending:
        raise ValidationError("لديك واجب مرسل ينتظر التصحيح؛ لا يمكن إرسال محاولة جديدة الآن.")
    attempt_no = _validate_assessment_attempt(enrollment, assessment)
    submission = LearningSubmission.objects.create(
        assessment=assessment,
        enrollment=enrollment,
        attempt_no=attempt_no,
        answer_text=answer_text.strip(),
        status=LearningSubmission.Status.SUBMITTED,
    )
    enrollment.last_activity_at = timezone.now()
    enrollment.save(update_fields=["last_activity_at"])
    create_learning_notification(
        enrollment.course.teacher,
        notification_type=LearningNotification.Type.ASSESSMENT,
        title="واجب جديد ينتظر التصحيح",
        body=f"أرسل {enrollment.learner.full_name} واجب {assessment.title} في دورة {enrollment.course.title}.",
        action_url=reverse(
            "learning_platform:teacher_submission_grade",
            kwargs={"pk": submission.pk},
        ),
        dedupe_key=f"assignment-submitted:{submission.pk}",
    )
    LearningAuditEvent.objects.create(
        account=enrollment.learner,
        action=LearningAuditEvent.Action.ASSESSMENT_SUBMITTED,
        entity_type="learning_submission",
        entity_id=str(submission.pk),
        ip_address=ip_address,
        metadata={
            "assessment_id": assessment.pk,
            "attempt_no": attempt_no,
            "auto_graded": False,
        },
    )
    return submission


@transaction.atomic
def grade_assignment(submission, *, score, feedback="", grader=None, grader_label=""):
    locked = (
        LearningSubmission.objects.select_for_update()
        .select_related("assessment", "enrollment", "enrollment__learner", "enrollment__course")
        .get(pk=submission.pk)
    )
    if locked.assessment.assessment_type != LearningAssessment.Type.ASSIGNMENT:
        raise ValidationError("التصحيح اليدوي مخصص للواجبات فقط.")
    score = Decimal(score)
    if score < 0 or score > Decimal(locked.assessment.max_score):
        raise ValidationError("العلامة خارج النطاق المسموح.")
    locked.score = score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    locked.is_passed = locked.score >= Decimal(locked.assessment.pass_score)
    locked.feedback = (feedback or "").strip()
    locked.status = LearningSubmission.Status.GRADED
    locked.graded_at = timezone.now()
    locked.graded_by = grader if getattr(grader, "role", None) == LearningAccount.Role.TEACHER else None
    locked.graded_by_label = (grader_label or getattr(grader, "full_name", "") or "").strip()
    locked.save(
        update_fields=[
            "score",
            "is_passed",
            "feedback",
            "status",
            "graded_at",
            "graded_by",
            "graded_by_label",
        ]
    )
    refresh_enrollment_progress(locked.enrollment)
    create_learning_notification(
        locked.enrollment.learner,
        notification_type=LearningNotification.Type.ASSESSMENT,
        title="تم تصحيح واجبك",
        body=f"علامتك في {locked.assessment.title}: {locked.score} من {locked.assessment.max_score}.",
        action_url=reverse(
            "learning_platform:assessment_detail",
            kwargs={
                "course_slug": locked.enrollment.course.slug,
                "assessment_slug": locked.assessment.slug,
            },
        ),
        dedupe_key=f"assignment-graded:{locked.pk}:{locked.graded_at.isoformat()}",
    )
    LearningAuditEvent.objects.create(
        account=locked.enrollment.learner,
        action=LearningAuditEvent.Action.ASSESSMENT_GRADED,
        entity_type="learning_submission",
        entity_id=str(locked.pk),
        metadata={
            "assessment_id": locked.assessment_id,
            "score": str(locked.score),
            "passed": locked.is_passed,
            "grader": locked.graded_by_label,
        },
    )
    submission.refresh_from_db()
    return submission
