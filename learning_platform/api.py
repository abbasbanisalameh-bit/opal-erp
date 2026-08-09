from __future__ import annotations

import json
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .ai_services import run_grounded_assistance
from .models import (
    LearningAIInteraction,
    LearningAssessment,
    LearningCourse,
    LearningCertificate,
    LearningEnrollment,
    LearningLesson,
    LearningNotification,
    LearningSubmission,
    LearningSubscriptionPlan,
    LearningSubscriptionCard,
)
from .security_services import (
    account_is_locked,
    consume_rate_limit,
    email_verification_required,
    find_api_token,
    issue_api_token,
    record_login_failure,
    record_login_success,
    revoke_api_token,
    touch_api_token,
)
from .services import (
    enroll_learner,
    learner_can_access_course,
    mark_lesson_completed,
    submit_assignment,
    submit_quiz,
)
from .models import LearningAccount


def _client_ip(request):
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or "unknown"


def _json_body(request):
    try:
        return json.loads((request.body or b"{}").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("JSON غير صالح.") from exc


def _error(message, *, status=400, code="invalid_request", details=None):
    payload = {"ok": False, "error": {"code": code, "message": str(message)}}
    if details:
        payload["error"]["details"] = details
    response = JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response


def _success(data=None, *, status=200):
    response = JsonResponse(
        {"ok": True, "data": data if data is not None else {}},
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )
    response["Cache-Control"] = "no-store"
    return response


def _validation_message(exc):
    if hasattr(exc, "messages") and exc.messages:
        return " ".join(str(item) for item in exc.messages)
    return str(exc)


def api_auth_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        header = (request.META.get("HTTP_AUTHORIZATION") or "").strip()
        if not header.lower().startswith("bearer "):
            return _error("رمز المصادقة مفقود.", status=401, code="authentication_required")
        token = find_api_token(header.split(" ", 1)[1].strip())
        if token is None:
            return _error("رمز المصادقة منتهي أو ملغي.", status=401, code="invalid_token")
        try:
            consume_rate_limit(
                "api",
                f"token:{token.pk}",
                limit=int(getattr(settings, "OPAL_LEARNING_API_RATE_LIMIT", 120)),
                window_seconds=60,
            )
        except ValidationError as exc:
            return _error(_validation_message(exc), status=429, code="rate_limited")
        touch_api_token(token)
        request.learning_api_token = token
        request.learning_account = token.account
        try:
            response = view_func(request, *args, **kwargs)
        except Http404:
            response = _error("العنصر المطلوب غير موجود.", status=404, code="not_found")
        except PermissionDenied as exc:
            response = _error(str(exc), status=403, code="permission_denied")
        except ValidationError as exc:
            response = _error(_validation_message(exc), status=400, code="validation_error")
        response["Cache-Control"] = "no-store"
        return response

    return wrapped



def _issue_mobile_profile(account, *, device_name, ip_address, profile=None):
    token, raw_token = issue_api_token(
        account,
        device_name=(device_name or "OPAL Mobile")[:120],
        ip_address=ip_address,
    )
    payload = {
        "token": raw_token,
        "token_type": "Bearer",
        "expires_at": token.expires_at.isoformat(),
        "account": _account_payload(account),
    }
    if profile:
        payload["profile"] = profile
    return payload


@csrf_exempt
@require_http_methods(["POST"])
def api_school_login(request):
    """Authenticate an OPAL ERP guardian/teacher and issue learning tokens.

    School-managed LearningAccount rows deliberately have unusable passwords.
    This endpoint keeps one credential source: the existing ERP account.  A
    guardian receives one scoped learning token per eligible child, while a
    teacher receives a token for the teacher learning identity.
    """
    try:
        payload = _json_body(request)
        username = str(payload.get("username") or payload.get("identifier") or "").strip()
        password = str(payload.get("password") or "")
        if not username or not password:
            return _error("اسم المستخدم وكلمة المرور مطلوبان.", code="credentials_required")
        identifier = f"{_client_ip(request)}:{username.lower()}"
        consume_rate_limit(
            "school_api_login",
            identifier,
            limit=int(getattr(settings, "OPAL_LEARNING_LOGIN_RATE_LIMIT", 10)),
            window_seconds=300,
        )
        user = authenticate(request=request, username=username, password=password)
        if user is None or not user.is_active:
            return _error("اسم المستخدم أو كلمة المرور غير صحيحة.", status=401, code="invalid_credentials")

        from parent_portal.models import FamilyStudent
        from .school_bridge import (
            ensure_student_learning_account,
            ensure_teacher_learning_account,
            student_learning_access,
            teacher_learning_access,
        )

        device_name = str(payload.get("device_name") or "OPAL Mobile")[:120]
        ip_address = _client_ip(request)
        family = getattr(user, "family_account", None)
        if family is not None and family.is_active:
            profiles = []
            links = FamilyStudent.objects.filter(
                family=family,
                family__is_active=True,
                is_active=True,
                student__is_active=True,
            ).select_related("student").order_by("student__full_name", "student_id")
            for link in links:
                access = student_learning_access(link.student)
                if not access["enabled"]:
                    continue
                account = ensure_student_learning_account(link.student)
                enrollment = access.get("enrollment")
                class_label = ""
                if enrollment is not None:
                    class_label = f"{enrollment.grade.name} - {enrollment.section.name}"
                profiles.append(
                    _issue_mobile_profile(
                        account,
                        device_name=device_name,
                        ip_address=ip_address,
                        profile={
                            "kind": "student",
                            "student_id": link.student_id,
                            "student_name": link.student.full_name,
                            "class_label": class_label,
                        },
                    )
                )
            if not profiles:
                return _error("لا يوجد ابن متاح له دخول منصة أوبال التعليمية حاليًا.", status=403, code="learning_access_disabled")
            return _success({"mode": "guardian", "guardian_name": family.guardian_name, "profiles": profiles}, status=201)

        teacher = getattr(user, "teacher_profile", None)
        if teacher is not None and teacher.is_active:
            if not teacher_learning_access(teacher):
                return _error("دخول منصة أوبال التعليمية غير متاح للمعلمين حاليًا.", status=403, code="learning_access_disabled")
            account = ensure_teacher_learning_account(teacher)
            profile = _issue_mobile_profile(
                account,
                device_name=device_name,
                ip_address=ip_address,
                profile={
                    "kind": "teacher",
                    "teacher_id": teacher.pk,
                    "teacher_name": teacher.full_name,
                },
            )
            return _success({"mode": "teacher", "profiles": [profile]}, status=201)

        return _error("هذا الحساب ليس حساب ولي أمر أو معلمًا مرتبطًا بالمنصة.", status=403, code="unsupported_school_account")
    except ValidationError as exc:
        return _error(_validation_message(exc), status=429 if "تجاوز" in _validation_message(exc) else 400)


@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
    try:
        payload = _json_body(request)
        identifier = f"{_client_ip(request)}:{str(payload.get('email') or '').strip().lower()}"
        consume_rate_limit(
            "api_login",
            identifier,
            limit=int(getattr(settings, "OPAL_LEARNING_LOGIN_RATE_LIMIT", 10)),
            window_seconds=300,
        )
        email = str(payload.get("email") or "").strip().lower()
        password = str(payload.get("password") or "")
        account = LearningAccount.objects.filter(email__iexact=email, is_active=True).first()
        if account and account_is_locked(account):
            return _error("الحساب مقفل مؤقتًا بسبب محاولات دخول متكررة.", status=423, code="account_locked")
        if not account or not account.check_password(password) or account.role == LearningAccount.Role.MANAGER:
            if account:
                record_login_failure(account)
            return _error("البريد الإلكتروني أو كلمة المرور غير صحيحة.", status=401, code="invalid_credentials")
        if not account.terms_accepted_at or not account.privacy_accepted_at:
            return _error("يجب قبول شروط الاستخدام وسياسة الخصوصية من واجهة الويب أولًا.", status=403, code="legal_acceptance_required")
        if email_verification_required(account):
            return _error("يجب توثيق البريد الإلكتروني أولًا.", status=403, code="email_not_verified")
        record_login_success(account)
        token, raw_token = issue_api_token(
            account,
            device_name=str(payload.get("device_name") or "")[:120],
            ip_address=_client_ip(request),
        )
        return _success(
            {
                "token": raw_token,
                "token_type": "Bearer",
                "expires_at": token.expires_at.isoformat(),
                "account": _account_payload(account),
            },
            status=201,
        )
    except ValidationError as exc:
        return _error(_validation_message(exc), status=429 if "تجاوز" in _validation_message(exc) else 400)


@csrf_exempt
@api_auth_required
@require_http_methods(["POST"])
def api_logout(request):
    revoke_api_token(request.learning_api_token, ip_address=_client_ip(request))
    return _success({"logged_out": True})


def _account_payload(account):
    return {
        "id": account.pk,
        "full_name": account.full_name,
        "email": account.email,
        "phone": account.phone,
        "role": account.role,
        "email_verified": account.email_verified_at is not None,
        "is_school_managed": account.is_school_managed,
    }


@api_auth_required
@require_http_methods(["GET"])
def api_me(request):
    return _success(_account_payload(request.learning_account))


def _course_payload(course, *, account=None, include_lessons=False):
    payload = {
        "id": course.pk,
        "title": course.title,
        "slug": course.slug,
        "summary": course.summary,
        "grade_label": course.grade_label,
        "cover_color": course.cover_color,
        "subject": {"id": course.subject_id, "name": course.subject.name},
        "teacher": {"id": course.teacher_id, "name": course.teacher.full_name},
        "published_at": course.published_at.isoformat() if course.published_at else None,
    }
    if account is not None:
        enrollment = course.enrollments.filter(learner=account).first()
        payload["enrollment"] = (
            {
                "id": enrollment.pk,
                "status": enrollment.status,
                "progress_percent": enrollment.progress_percent,
            }
            if enrollment
            else None
        )
        payload["has_access"] = learner_can_access_course(account, course)
    if include_lessons:
        payload["lessons"] = [
            {
                "id": lesson.pk,
                "title": lesson.title,
                "slug": lesson.slug,
                "order": lesson.order,
                "duration_minutes": lesson.duration_minutes,
            }
            for lesson in course.lessons.filter(is_published=True).order_by("order", "id")
        ]
        payload["assessments"] = [
            {
                "id": assessment.pk,
                "title": assessment.title,
                "slug": assessment.slug,
                "type": assessment.assessment_type,
                "max_score": assessment.max_score,
                "pass_score": assessment.pass_score,
                "max_attempts": assessment.max_attempts,
                "due_at": assessment.due_at.isoformat() if assessment.due_at else None,
            }
            for assessment in course.assessments.filter(is_published=True).order_by("order", "id")
        ]
    return payload


@api_auth_required
@require_http_methods(["GET"])
def api_course_list(request):
    account = request.learning_account
    courses = LearningCourse.objects.filter(
        status=LearningCourse.Status.PUBLISHED,
        subject__is_active=True,
    ).select_related("subject", "teacher").order_by("-published_at", "title")
    if account.is_school_managed and account.role == LearningAccount.Role.LEARNER:
        from .school_bridge import eligible_courses_for_student, managed_student_for_account
        student = managed_student_for_account(account)
        courses = (
            eligible_courses_for_student(student).select_related("subject", "teacher").order_by("-published_at", "title")
            if student is not None else courses.none()
        )
    elif account.role == LearningAccount.Role.TEACHER:
        courses = courses.filter(teacher=account)
    return _success([_course_payload(course, account=account) for course in courses])


@api_auth_required
@require_http_methods(["GET"])
def api_course_detail(request, slug):
    account = request.learning_account
    courses = LearningCourse.objects.select_related("subject", "teacher").filter(
        status=LearningCourse.Status.PUBLISHED,
    )
    if account.is_school_managed and account.role == LearningAccount.Role.LEARNER:
        from .school_bridge import eligible_courses_for_student, managed_student_for_account
        student = managed_student_for_account(account)
        courses = (
            eligible_courses_for_student(student).select_related("subject", "teacher")
            if student is not None else courses.none()
        )
    elif account.role == LearningAccount.Role.TEACHER:
        courses = courses.filter(teacher=account)
    course = get_object_or_404(courses, slug=slug)
    return _success(_course_payload(course, account=account, include_lessons=True))


@csrf_exempt
@api_auth_required
@require_http_methods(["POST"])
def api_course_enroll(request, slug):
    account = request.learning_account
    if account.role != LearningAccount.Role.LEARNER:
        return _error("التسجيل في الدورات متاح للمتعلم فقط.", status=403, code="learner_required")
    course = get_object_or_404(
        LearningCourse.objects.select_related("subject"),
        slug=slug,
        status=LearningCourse.Status.PUBLISHED,
    )
    try:
        enrollment, created = enroll_learner(account, course, ip_address=_client_ip(request))
    except ValidationError as exc:
        return _error(_validation_message(exc), status=403, code="enrollment_denied")
    return _success(
        {
            "id": enrollment.pk,
            "created": created,
            "status": enrollment.status,
            "progress_percent": enrollment.progress_percent,
        },
        status=201 if created else 200,
    )


@api_auth_required
@require_http_methods(["GET"])
def api_lesson_detail(request, course_slug, lesson_slug):
    account = request.learning_account
    course = get_object_or_404(LearningCourse.objects.select_related("subject"), slug=course_slug)
    enrollment = get_object_or_404(
        LearningEnrollment.objects.select_related("course", "learner"),
        learner=account,
        course=course,
    )
    if not learner_can_access_course(account, course):
        return _error("لا يوجد اشتراك فعال لهذه الدورة.", status=403, code="subscription_required")
    lesson = get_object_or_404(
        LearningLesson,
        course=course,
        slug=lesson_slug,
        is_published=True,
    )
    return _success(
        {
            "id": lesson.pk,
            "title": lesson.title,
            "slug": lesson.slug,
            "content": lesson.content,
            "video_url": lesson.video_url,
            "duration_minutes": lesson.duration_minutes,
            "order": lesson.order,
            "enrollment_id": enrollment.pk,
        }
    )


@csrf_exempt
@api_auth_required
@require_http_methods(["POST"])
def api_lesson_complete(request, course_slug, lesson_slug):
    account = request.learning_account
    enrollment = get_object_or_404(
        LearningEnrollment.objects.select_related("course", "learner", "course__subject"),
        learner=account,
        course__slug=course_slug,
    )
    lesson = get_object_or_404(
        LearningLesson,
        course=enrollment.course,
        slug=lesson_slug,
        is_published=True,
    )
    try:
        _progress, enrollment = mark_lesson_completed(
            enrollment,
            lesson,
            ip_address=_client_ip(request),
        )
    except ValidationError as exc:
        return _error(_validation_message(exc), status=403)
    return _success(
        {
            "progress_percent": enrollment.progress_percent,
            "status": enrollment.status,
            "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
        }
    )


@api_auth_required
@require_http_methods(["GET"])
def api_assessment_detail(request, course_slug, assessment_slug):
    account = request.learning_account
    if account.role != LearningAccount.Role.LEARNER:
        return _error("التقييمات متاحة للمتعلم فقط.", status=403, code="learner_required")
    enrollment = get_object_or_404(
        LearningEnrollment.objects.select_related("course", "learner", "course__subject"),
        learner=account,
        course__slug=course_slug,
    )
    if not learner_can_access_course(account, enrollment.course):
        return _error("لا يوجد اشتراك فعال لهذه الدورة.", status=403, code="subscription_required")
    assessment = get_object_or_404(
        LearningAssessment.objects.prefetch_related("questions"),
        course=enrollment.course,
        slug=assessment_slug,
        is_published=True,
    )
    prior_attempts = list(
        assessment.submissions.filter(enrollment=enrollment).order_by("attempt_no").values(
            "id", "attempt_no", "status", "score", "is_passed", "submitted_at", "graded_at", "feedback"
        )
    )
    data = {
        "id": assessment.pk,
        "title": assessment.title,
        "slug": assessment.slug,
        "type": assessment.assessment_type,
        "instructions": assessment.instructions,
        "max_score": assessment.max_score,
        "pass_score": assessment.pass_score,
        "max_attempts": assessment.max_attempts,
        "due_at": assessment.due_at.isoformat() if assessment.due_at else None,
        "attempts": [
            {
                **item,
                "score": str(item["score"]) if item["score"] is not None else None,
                "submitted_at": item["submitted_at"].isoformat(),
                "graded_at": item["graded_at"].isoformat() if item["graded_at"] else None,
            }
            for item in prior_attempts
        ],
    }
    if assessment.assessment_type == LearningAssessment.Type.QUIZ:
        data["questions"] = [
            {
                "id": question.pk,
                "text": question.text,
                "order": question.order,
                "choices": {
                    "a": question.choice_a,
                    "b": question.choice_b,
                    "c": question.choice_c,
                    "d": question.choice_d,
                },
            }
            for question in assessment.questions.order_by("order", "id")
        ]
    return _success(data)


@csrf_exempt
@api_auth_required
@require_http_methods(["POST"])
def api_assessment_submit(request, course_slug, assessment_slug):
    account = request.learning_account
    enrollment = get_object_or_404(
        LearningEnrollment.objects.select_related("course", "learner", "course__subject"),
        learner=account,
        course__slug=course_slug,
    )
    assessment = get_object_or_404(
        LearningAssessment,
        course=enrollment.course,
        slug=assessment_slug,
        is_published=True,
    )
    try:
        payload = _json_body(request)
        if assessment.assessment_type == LearningAssessment.Type.QUIZ:
            submission, enrollment = submit_quiz(
                enrollment,
                assessment,
                payload.get("answers") or {},
                ip_address=_client_ip(request),
            )
        else:
            submission, enrollment = submit_assignment(
                enrollment,
                assessment,
                str(payload.get("answer_text") or ""),
                ip_address=_client_ip(request),
            )
    except ValidationError as exc:
        return _error(_validation_message(exc), status=400, code="submission_rejected")
    return _success(
        {
            "submission_id": submission.pk,
            "status": submission.status,
            "score": str(submission.score) if submission.score is not None else None,
            "is_passed": submission.is_passed,
            "attempt_no": submission.attempt_no,
            "progress_percent": enrollment.progress_percent,
        },
        status=201,
    )


@api_auth_required
@require_http_methods(["GET"])
def api_notifications(request):
    notices = request.learning_account.notifications.order_by("-created_at")[:100]
    return _success(
        [
            {
                "id": notice.pk,
                "type": notice.notification_type,
                "title": notice.title,
                "body": notice.body,
                "action_url": notice.action_url,
                "read_at": notice.read_at.isoformat() if notice.read_at else None,
                "created_at": notice.created_at.isoformat(),
            }
            for notice in notices
        ]
    )


@csrf_exempt
@api_auth_required
@require_http_methods(["POST"])
def api_notification_read(request, pk):
    notice = get_object_or_404(LearningNotification, pk=pk, recipient=request.learning_account)
    notice.mark_read()
    return _success({"id": notice.pk, "read_at": notice.read_at.isoformat()})


@api_auth_required
@require_http_methods(["GET"])
def api_certificates(request):
    account = request.learning_account
    if account.role != LearningAccount.Role.LEARNER:
        return _error("الشهادات متاحة للمتعلم فقط.", status=403, code="learner_required")
    certificates = LearningCertificate.objects.filter(
        enrollment__learner=account,
        revoked_at__isnull=True,
    ).select_related("enrollment__course").order_by("-issued_at")
    return _success(
        [
            {
                "id": certificate.pk,
                "serial": certificate.serial,
                "course": {
                    "title": certificate.enrollment.course.title,
                    "slug": certificate.enrollment.course.slug,
                },
                "issued_at": certificate.issued_at.isoformat(),
                "verification_code": certificate.verification_code,
            }
            for certificate in certificates
        ]
    )


@csrf_exempt
@api_auth_required
@require_http_methods(["POST"])
def api_subscription_card_redeem(request):
    account = request.learning_account
    if account.role != LearningAccount.Role.LEARNER:
        return _error("تفعيل البطاقة متاح لحساب المتعلم فقط.", status=403, code="learner_required")
    payload = _json_body(request)
    code = str(payload.get("code") or "").strip().upper()
    if not code:
        return _error("أدخل رمز البطاقة.", code="card_code_required")
    card = LearningSubscriptionCard.objects.filter(code=code).prefetch_related("subjects").first()
    if card is None:
        return _error("رمز البطاقة غير صحيح.", status=404, code="card_not_found")
    try:
        card.activate(account)
    except ValidationError as exc:
        return _error(_validation_message(exc), status=409, code="card_unavailable")
    return _success({
        "code": card.code,
        "duration": card.duration,
        "expires_at": card.expires_at.isoformat() if card.expires_at else None,
        "grants_all_subjects": card.grants_all_subjects,
        "subjects": [{"id": item.pk, "name": item.name} for item in card.subjects.all()],
    }, status=201)


@api_auth_required
@require_http_methods(["GET"])
def api_subscription_plans(request):
    plans = LearningSubscriptionPlan.objects.filter(is_active=True).prefetch_related("subjects")
    return _success(
        [
            {
                "id": plan.pk,
                "name": plan.name,
                "slug": plan.slug,
                "duration": plan.duration,
                "price": str(plan.price),
                "currency": plan.currency,
                "grants_all_subjects": plan.grants_all_subjects,
                "subjects": [{"id": subject.pk, "name": subject.name} for subject in plan.subjects.all()],
            }
            for plan in plans
        ]
    )


@csrf_exempt
@api_auth_required
@require_http_methods(["POST"])
def api_ai_question(request):
    account = request.learning_account
    if account.role != LearningAccount.Role.LEARNER:
        return _error("مساعد المتعلم متاح لحساب المتعلم فقط.", status=403)
    try:
        payload = _json_body(request)
        course = get_object_or_404(LearningCourse, slug=str(payload.get("course_slug") or ""))
        interaction, _draft = run_grounded_assistance(
            account,
            course,
            LearningAIInteraction.Type.LEARNER_QUESTION,
            str(payload.get("question") or ""),
            ip_address=_client_ip(request),
        )
    except (ValidationError, PermissionDenied) as exc:
        return _error(_validation_message(exc), status=403)
    return _success(
        {
            "answer": interaction.response,
            "sources": interaction.source_labels,
            "provider_mode": interaction.provider_mode,
        },
        status=201,
    )
