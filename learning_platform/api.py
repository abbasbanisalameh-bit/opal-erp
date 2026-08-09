from __future__ import annotations

import json
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.db import transaction
from django.db.models import Count, Q
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
    LearningSubject,
    LearningAuditEvent,
    LearningPasswordResetRequest,
    LearningPaymentOrder,
    LearningAccessSettings,
    LearningGradeAccessOverride,
    LearningStudentAccessOverride,
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
    find_manager_api_token,
    issue_manager_api_token,
    revoke_manager_api_token,
    touch_manager_api_token,
)
from .services import (
    enroll_learner,
    learner_can_access_course,
    mark_lesson_completed,
    submit_assignment,
    submit_quiz,
)
from .models import LearningAccount
from .forms import LearningSubscriptionBatchForm
from .production import collect_learning_readiness_checks


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


def _authorization_token(request):
    header = (request.META.get("HTTP_AUTHORIZATION") or "").strip()
    if not header.lower().startswith("bearer "):
        return ""
    return header.split(" ", 1)[1].strip()


def _manager_account_payload(user):
    from accounts.workflow import role_code

    full_name = (user.get_full_name() or "").strip()
    if not full_name:
        try:
            full_name = (user.profile.full_name or "").strip()
        except Exception:
            full_name = ""
    return {
        "id": user.pk,
        "full_name": full_name or user.get_username(),
        "username": user.get_username(),
        "email": user.email or "",
        "phone": "",
        "role": "manager",
        "management_role": role_code(user),
        "is_school_managed": True,
        "email_verified": True,
    }


def api_manager_auth_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        raw_token = _authorization_token(request)
        if not raw_token:
            return _error("رمز مصادقة الإدارة مفقود.", status=401, code="authentication_required")
        token = find_manager_api_token(raw_token)
        if token is None:
            return _error("رمز إدارة المنصة منتهي أو ملغي.", status=401, code="invalid_token")
        try:
            consume_rate_limit(
                "manager_api",
                f"token:{token.pk}",
                limit=int(getattr(settings, "OPAL_LEARNING_MANAGER_API_RATE_LIMIT", 180)),
                window_seconds=60,
            )
        except ValidationError as exc:
            return _error(_validation_message(exc), status=429, code="rate_limited")
        touch_manager_api_token(token)
        request.learning_manager_api_token = token
        request.erp_manager = token.user
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


def _record_manager_api_event(request, *, action, entity_type="", entity_id="", metadata=None):
    user = request.erp_manager
    LearningAuditEvent.objects.create(
        account=None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ""),
        ip_address=_client_ip(request),
        metadata={
            "erp_manager_username": user.get_username(),
            "erp_manager_name": _manager_account_payload(user)["full_name"],
            **(metadata or {}),
        },
    )



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

        from accounts.workflow import is_management_user

        if is_management_user(user):
            token, raw_token = issue_manager_api_token(
                user,
                device_name=str(payload.get("device_name") or "OPAL Mobile")[:120],
                ip_address=_client_ip(request),
            )
            profile = {
                "token": raw_token,
                "token_type": "Bearer",
                "expires_at": token.expires_at.isoformat(),
                "account": _manager_account_payload(user),
                "profile": {"kind": "manager", "manager_username": user.get_username()},
            }
            return _success({"mode": "manager", "profiles": [profile]}, status=201)

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

        return _error("هذا الحساب ليس حساب إدارة أو ولي أمر أو معلمًا مرتبطًا بالمنصة.", status=403, code="unsupported_school_account")
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
@require_http_methods(["POST"])
def api_logout(request):
    raw_token = _authorization_token(request)
    manager_token = find_manager_api_token(raw_token)
    if manager_token is not None:
        revoke_manager_api_token(manager_token, ip_address=_client_ip(request))
        return _success({"logged_out": True, "mode": "manager"})
    token = find_api_token(raw_token)
    if token is None:
        return _error("رمز المصادقة منتهي أو ملغي.", status=401, code="invalid_token")
    revoke_api_token(token, ip_address=_client_ip(request))
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


@require_http_methods(["GET"])
def api_me(request):
    raw_token = _authorization_token(request)
    manager_token = find_manager_api_token(raw_token)
    if manager_token is not None:
        touch_manager_api_token(manager_token)
        return _success(_manager_account_payload(manager_token.user))
    token = find_api_token(raw_token)
    if token is None:
        return _error("رمز المصادقة منتهي أو ملغي.", status=401, code="invalid_token")
    touch_api_token(token)
    return _success(_account_payload(token.account))


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


def _manager_course_payload(course):
    return {
        "id": course.pk,
        "title": course.title,
        "slug": course.slug,
        "summary": course.summary,
        "grade_label": course.grade_label,
        "status": course.status,
        "published_at": course.published_at.isoformat() if course.published_at else None,
        "subject": {"id": course.subject_id, "name": course.subject.name},
        "teacher": {"id": course.teacher_id, "name": course.teacher.full_name},
        "lesson_count": getattr(course, "lesson_count", course.lessons.count()),
        "assessment_count": getattr(course, "assessment_count", course.assessments.count()),
    }


def _manager_card_payload(card):
    return {
        "id": card.pk,
        "code": card.code,
        "duration": card.duration,
        "duration_label": card.get_duration_display(),
        "status": card.status,
        "status_label": card.get_status_display(),
        "grants_all_subjects": card.grants_all_subjects,
        "subjects": [{"id": item.pk, "name": item.name} for item in card.subjects.all()],
        "redeemed_by": (
            {"id": card.redeemed_by_id, "name": card.redeemed_by.full_name}
            if card.redeemed_by_id
            else None
        ),
        "activated_at": card.activated_at.isoformat() if card.activated_at else None,
        "expires_at": card.expires_at.isoformat() if card.expires_at else None,
        "created_at": card.created_at.isoformat(),
    }


@api_manager_auth_required
@require_http_methods(["GET"])
def api_manager_dashboard(request):
    accounts = LearningAccount.objects.all()
    courses = LearningCourse.objects.select_related("subject", "teacher")
    now = timezone.now()
    readiness = collect_learning_readiness_checks(include_migrations=False)
    stats = {
        "accounts": accounts.count(),
        "learners": accounts.filter(role=LearningAccount.Role.LEARNER, is_active=True).count(),
        "teachers": accounts.filter(role=LearningAccount.Role.TEACHER, is_active=True).count(),
        "courses": courses.count(),
        "published_courses": courses.filter(status=LearningCourse.Status.PUBLISHED).count(),
        "published_lessons": LearningLesson.objects.filter(is_published=True).count(),
        "published_assessments": LearningAssessment.objects.filter(is_published=True).count(),
        "pending_submissions": LearningSubmission.objects.filter(status=LearningSubmission.Status.SUBMITTED).count(),
        "certificates": LearningCertificate.objects.filter(revoked_at__isnull=True).count(),
        "enrollments": LearningEnrollment.objects.filter(status=LearningEnrollment.Status.ACTIVE).count(),
        "active_subscriptions": LearningSubscriptionCard.objects.filter(
            status=LearningSubscriptionCard.Status.REDEEMED,
            expires_at__gt=now,
        ).count(),
        "available_subscriptions": LearningSubscriptionCard.objects.filter(status=LearningSubscriptionCard.Status.AVAILABLE).count(),
        "subscription_plans": LearningSubscriptionPlan.objects.filter(is_active=True).count(),
        "pending_payments": LearningPaymentOrder.objects.filter(
            status__in=[LearningPaymentOrder.Status.PENDING, LearningPaymentOrder.Status.PROCESSING]
        ).count(),
        "open_password_resets": LearningPasswordResetRequest.objects.filter(
            used_at__isnull=True,
            expires_at__gt=now,
        ).count(),
    }
    recent_courses = [
        _manager_course_payload(item)
        for item in courses.annotate(
            lesson_count=Count("lessons", distinct=True),
            assessment_count=Count("assessments", distinct=True),
        ).order_by("-updated_at")[:6]
    ]
    recent_accounts = [
        {
            "id": item.pk,
            "full_name": item.full_name,
            "email": item.email,
            "role": item.role,
            "is_active": item.is_active,
            "is_school_managed": item.is_school_managed,
        }
        for item in accounts.order_by("-created_at")[:8]
    ]
    return _success(
        {
            "manager": _manager_account_payload(request.erp_manager),
            "stats": stats,
            "readiness": readiness,
            "recent_courses": recent_courses,
            "recent_accounts": recent_accounts,
        }
    )


@api_manager_auth_required
@require_http_methods(["GET"])
def api_manager_accounts(request):
    query = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()
    rows = LearningAccount.objects.all()
    if query:
        rows = rows.filter(Q(full_name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query))
    if role in {LearningAccount.Role.LEARNER, LearningAccount.Role.TEACHER}:
        rows = rows.filter(role=role)
    rows = rows.order_by("-created_at")[:100]
    return _success(
        [
            {
                "id": item.pk,
                "full_name": item.full_name,
                "email": item.email,
                "phone": item.phone,
                "role": item.role,
                "is_active": item.is_active,
                "is_school_managed": item.is_school_managed,
                "email_verified": item.email_verified_at is not None,
                "created_at": item.created_at.isoformat(),
            }
            for item in rows
        ]
    )


@api_manager_auth_required
@require_http_methods(["GET"])
def api_manager_subjects(request):
    rows = LearningSubject.objects.filter(is_active=True).order_by("name")
    return _success([{"id": item.pk, "name": item.name, "slug": item.slug} for item in rows])


@api_manager_auth_required
@require_http_methods(["GET"])
def api_manager_courses(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    rows = LearningCourse.objects.select_related("subject", "teacher").annotate(
        lesson_count=Count("lessons", distinct=True),
        assessment_count=Count("assessments", distinct=True),
    )
    if query:
        rows = rows.filter(Q(title__icontains=query) | Q(subject__name__icontains=query) | Q(teacher__full_name__icontains=query))
    if status in set(LearningCourse.Status.values):
        rows = rows.filter(status=status)
    return _success([_manager_course_payload(item) for item in rows.order_by("-updated_at")[:100]])


@csrf_exempt
@api_manager_auth_required
@require_http_methods(["POST"])
def api_manager_course_status(request, pk):
    course = get_object_or_404(LearningCourse.objects.select_related("teacher", "subject"), pk=pk)
    action = str(_json_body(request).get("action") or "").strip()
    target_status = {
        "publish": LearningCourse.Status.PUBLISHED,
        "draft": LearningCourse.Status.DRAFT,
        "archive": LearningCourse.Status.ARCHIVED,
    }.get(action)
    if target_status is None:
        return _error("إجراء حالة الدورة غير معروف.", code="invalid_course_action")
    if target_status == LearningCourse.Status.PUBLISHED:
        errors = []
        if not course.teacher.is_active or course.teacher.role != LearningAccount.Role.TEACHER:
            errors.append("حساب المدرّس غير فعال أو ليس حساب مدرّس.")
        if not course.subject.is_active:
            errors.append("المادة المرتبطة بالدورة غير فعالة.")
        if not course.lessons.filter(is_published=True).exists():
            errors.append("يجب نشر درس واحد على الأقل قبل نشر الدورة.")
        if course.assessments.filter(
            is_published=True,
            assessment_type=LearningAssessment.Type.QUIZ,
            questions__isnull=True,
        ).exists():
            errors.append("يوجد اختبار منشور دون أسئلة؛ أضف سؤالًا أو أوقف نشر الاختبار.")
        if errors:
            return _error(" ".join(errors), status=400, code="course_not_publishable", details=errors)
    course.status = target_status
    fields = ["status", "updated_at"]
    if target_status == LearningCourse.Status.PUBLISHED and course.published_at is None:
        course.published_at = timezone.now()
        fields.append("published_at")
    course.save(update_fields=fields)
    _record_manager_api_event(
        request,
        action="manager_course_status",
        entity_type="learning_course",
        entity_id=course.pk,
        metadata={"status": target_status},
    )
    course = LearningCourse.objects.select_related("subject", "teacher").annotate(
        lesson_count=Count("lessons", distinct=True),
        assessment_count=Count("assessments", distinct=True),
    ).get(pk=course.pk)
    return _success(_manager_course_payload(course))


@api_manager_auth_required
@require_http_methods(["GET"])
def api_manager_subscription_cards(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    rows = LearningSubscriptionCard.objects.select_related("redeemed_by").prefetch_related("subjects")
    if query:
        rows = rows.filter(Q(code__icontains=query) | Q(redeemed_by__full_name__icontains=query))
    if status in set(LearningSubscriptionCard.Status.values):
        rows = rows.filter(status=status)
    return _success([_manager_card_payload(item) for item in rows.order_by("-created_at")[:100]])


@csrf_exempt
@api_manager_auth_required
@require_http_methods(["POST"])
def api_manager_subscription_generate(request):
    payload = _json_body(request)
    subject_ids = payload.get("subject_ids") or []
    data = {
        "duration": str(payload.get("duration") or ""),
        "grants_all_subjects": "on" if bool(payload.get("grants_all_subjects")) else "",
        "subjects": [str(value) for value in subject_ids],
        "quantity": str(payload.get("quantity") or "1"),
        "prefix": str(payload.get("prefix") or "OPAL"),
    }
    form = LearningSubscriptionBatchForm(data)
    if not form.is_valid():
        details = {key: [str(item) for item in value] for key, value in form.errors.items()}
        return _error("بيانات إنشاء البطاقات غير صالحة.", status=400, code="invalid_card_batch", details=details)
    with transaction.atomic():
        cards = form.save()
        for card in cards:
            _record_manager_api_event(
                request,
                action=LearningAuditEvent.Action.SUBSCRIPTION_CREATED,
                entity_type="subscription_card",
                entity_id=card.pk,
                metadata={"duration": card.duration, "grants_all_subjects": card.grants_all_subjects},
            )
    hydrated = LearningSubscriptionCard.objects.filter(pk__in=[item.pk for item in cards]).select_related("redeemed_by").prefetch_related("subjects")
    return _success([_manager_card_payload(item) for item in hydrated], status=201)


@csrf_exempt
@api_manager_auth_required
@require_http_methods(["POST"])
def api_manager_subscription_cancel(request, pk):
    with transaction.atomic():
        card = get_object_or_404(LearningSubscriptionCard.objects.select_for_update(), pk=pk)
        if card.status != LearningSubscriptionCard.Status.AVAILABLE:
            return _error("لا يمكن إلغاء بطاقة مفعلة أو ملغاة سابقًا.", status=409, code="card_not_cancellable")
        card.status = LearningSubscriptionCard.Status.CANCELLED
        card.save(update_fields=["status"])
        _record_manager_api_event(
            request,
            action=LearningAuditEvent.Action.SUBSCRIPTION_CANCELLED,
            entity_type="subscription_card",
            entity_id=card.pk,
            metadata={"code": card.code},
        )
    card = LearningSubscriptionCard.objects.select_related("redeemed_by").prefetch_related("subjects").get(pk=pk)
    return _success(_manager_card_payload(card))


@api_manager_auth_required
@require_http_methods(["GET"])
def api_manager_readiness(request):
    return _success(collect_learning_readiness_checks(include_migrations=True))


@csrf_exempt
@api_manager_auth_required
@require_http_methods(["GET", "POST"])
def api_manager_school_access(request):
    from academics.models import Grade
    from core.models import School
    from students.models import Student
    from .school_bridge import access_settings_for_school, student_learning_access

    school = School.objects.filter(is_active=True).first()
    if school is None:
        return _error("أدخل بيانات المدرسة أولًا.", status=409, code="school_required")
    access = access_settings_for_school(school)

    if request.method == "POST":
        payload = _json_body(request)
        action = str(payload.get("action") or "").strip()
        if action == "global":
            access.parent_default_enabled = bool(payload.get("parent_default_enabled"))
            access.teacher_sso_enabled = bool(payload.get("teacher_sso_enabled"))
            access.save(update_fields=["parent_default_enabled", "teacher_sso_enabled", "updated_at"])
        elif action in {"all_on", "all_off"}:
            access.parent_default_enabled = action == "all_on"
            access.save(update_fields=["parent_default_enabled", "updated_at"])
            LearningStudentAccessOverride.objects.filter(settings=access).delete()
            LearningGradeAccessOverride.objects.filter(settings=access).delete()
        elif action == "grade":
            grade = get_object_or_404(Grade, pk=payload.get("grade_id"), school=school)
            mode = str(payload.get("mode") or "").strip()
            if mode == "inherit":
                LearningGradeAccessOverride.objects.filter(settings=access, grade=grade).delete()
            elif mode in {"enabled", "disabled"}:
                LearningGradeAccessOverride.objects.update_or_create(
                    settings=access,
                    grade=grade,
                    defaults={"is_enabled": mode == "enabled"},
                )
            else:
                return _error("وضع إتاحة الصف غير صالح.", code="invalid_grade_mode")
        elif action == "student":
            student = get_object_or_404(Student, pk=payload.get("student_id"), is_active=True)
            student_access = student_learning_access(student)
            enrollment = student_access.get("enrollment")
            if enrollment is None or enrollment.academic_year.school_id != school.pk:
                raise PermissionDenied("الطالب لا يتبع المدرسة الحالية.")
            mode = str(payload.get("mode") or "").strip()
            if mode == "inherit":
                LearningStudentAccessOverride.objects.filter(settings=access, student=student).delete()
            elif mode in {"enabled", "disabled"}:
                LearningStudentAccessOverride.objects.update_or_create(
                    settings=access,
                    student=student,
                    defaults={"is_enabled": mode == "enabled"},
                )
            else:
                return _error("وضع إتاحة الطالب غير صالح.", code="invalid_student_mode")
        else:
            return _error("إجراء الإتاحة غير معروف.", code="invalid_access_action")
        _record_manager_api_event(
            request,
            action="manager_school_access",
            entity_type="learning_access_settings",
            entity_id=access.pk,
            metadata={"action": action},
        )

    grades = list(Grade.objects.filter(school=school, is_active=True).order_by("order", "name"))
    grade_overrides = {
        item.grade_id: item.is_enabled
        for item in LearningGradeAccessOverride.objects.filter(settings=access)
    }
    query = (request.GET.get("q") or "").strip()
    students = Student.objects.filter(
        is_active=True,
        enrollments__academic_year__school=school,
        enrollments__status="active",
    ).distinct()
    if query:
        students = students.filter(Q(full_name__icontains=query) | Q(student_number__icontains=query))
    students = students.order_by("full_name")[:50]
    student_override_map = {
        item.student_id: item.is_enabled
        for item in LearningStudentAccessOverride.objects.filter(settings=access, student_id__in=[item.pk for item in students])
    }
    return _success(
        {
            "school": {"id": school.pk, "name": school.name},
            "parent_default_enabled": access.parent_default_enabled,
            "teacher_sso_enabled": access.teacher_sso_enabled,
            "grades": [
                {
                    "id": grade.pk,
                    "name": grade.name,
                    "mode": (
                        "enabled" if grade_overrides.get(grade.pk) is True
                        else "disabled" if grade_overrides.get(grade.pk) is False
                        else "inherit"
                    ),
                }
                for grade in grades
            ],
            "students": [
                {
                    "id": student.pk,
                    "student_number": student.student_number,
                    "full_name": student.full_name,
                    "mode": (
                        "enabled" if student_override_map.get(student.pk) is True
                        else "disabled" if student_override_map.get(student.pk) is False
                        else "inherit"
                    ),
                }
                for student in students
            ],
        }
    )
