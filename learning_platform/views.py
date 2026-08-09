import csv
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Avg, Count, Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.workflow import is_management_user

from .forms import (
    LearningAIQuestionForm,
    LearningAISettingsForm,
    LearningAssessmentForm,
    LearningAssignmentSubmissionForm,
    LearningCourseForm,
    LearningLessonForm,
    LearningQuestionForm,
    LearningQuizAttemptForm,
    LearningLoginForm,
    LearningLegalAcceptanceForm,
    LearningManagerPasswordResetForm,
    LearningPasswordResetConfirmForm,
    LearningPasswordResetRequestForm,
    LearningRegistrationForm,
    LearningReportFilterForm,
    LearningSubjectForm,
    LearningSubmissionGradeForm,
    LearningSubscriptionBatchForm,
    LearningSubscriptionPlanForm,
    LearningPaymentCheckoutForm,
    LearningTeacherAIForm,
    LearningTeacherCreateForm,
    LearningTeacherSchoolCourseForm,
    SubscriptionActivationForm,
)
from .models import (
    LearningAccount,
    LearningAIDraft,
    LearningAIInteraction,
    LearningAISettings,
    LearningAssessment,
    LearningAuditEvent,
    LearningCertificate,
    LearningCourse,
    LearningEnrollment,
    LearningLesson,
    LearningLessonProgress,
    LearningNotification,
    LearningPasswordResetRequest,
    LearningQuestion,
    LearningSubject,
    LearningSubmission,
    LearningSubscriptionCard,
    LearningSubscriptionPlan,
    LearningPaymentOrder,
    LearningEmailVerificationRequest,
    LearningAccessSettings,
    LearningGradeAccessOverride,
    LearningStudentAccessOverride,
)
from .ai_services import (
    account_ai_usage,
    provider_status,
    run_grounded_assistance,
)
from .services import (
    complete_password_reset,
    create_learning_notification,
    create_password_reset_request,
    current_entitlement,
    deliver_password_reset_email,
    enroll_learner,
    find_valid_password_reset,
    first_incomplete_lesson,
    grade_assignment,
    learner_can_access_course,
    mark_lesson_completed,
    refresh_course_enrollments,
    refresh_enrollment_progress,
    reset_password_by_manager,
    submit_assignment,
    submit_quiz,
    sync_account_notifications,
)
from .session_auth import (
    end_learning_session,
    get_learning_account,
    learning_login_required,
    start_learning_session,
)
from .security_services import (
    complete_email_verification,
    consume_rate_limit,
    create_email_verification_request,
    deliver_email_verification,
    email_verification_required,
    find_valid_email_verification,
)
from .payment_services import (
    cancel_payment_order,
    create_payment_order,
    initiate_external_checkout,
    mark_order_paid,
    payment_configuration_status,
    process_payment_webhook,
)
from .production import collect_learning_readiness_checks
from .school_bridge import (
    access_settings_for_school,
    assert_parent_can_open_student,
    eligible_courses_for_student,
    ensure_learning_subject_for_academic_subject,
    ensure_student_learning_account,
    ensure_teacher_learning_account,
    managed_student_for_account,
    managed_teacher_for_account,
    school_managed_account_can_see_course,
    student_learning_access,
    teacher_learning_access,
)


def _lesson_video_player(video_url):
    """Return a safe, template-friendly player description for a lesson video URL.

    The lesson stays inside OPAL. Known video providers are converted to their
    official embed endpoints, direct video files use the native HTML5 player,
    and other URLs are shown in a sandboxed in-page frame when the remote site
    permits framing.
    """
    raw_url = (video_url or "").strip()
    if not raw_url:
        return None

    try:
        parsed = urlparse(raw_url)
    except (TypeError, ValueError):
        return None

    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    if scheme not in {"http", "https"} or not host:
        return None

    # YouTube share/watch/short/embed links -> privacy-enhanced embedded player.
    youtube_id = ""
    if host in {"youtu.be", "www.youtu.be"}:
        youtube_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.path == "/watch":
            youtube_id = (parse_qs(parsed.query).get("v") or [""])[0]
        elif len(parts) >= 2 and parts[0] in {"embed", "shorts", "live"}:
            youtube_id = parts[1]
    if youtube_id and all(ch.isalnum() or ch in "-_" for ch in youtube_id):
        return {
            "kind": "iframe",
            "url": f"https://www.youtube-nocookie.com/embed/{youtube_id}",
            "provider": "YouTube",
        }

    # Vimeo public links -> official embedded player.
    if host in {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}:
        parts = [part for part in parsed.path.split("/") if part]
        video_id = ""
        if parts:
            if parts[0] == "video" and len(parts) >= 2:
                video_id = parts[1]
            elif parts[0].isdigit():
                video_id = parts[0]
        if video_id.isdigit():
            return {
                "kind": "iframe",
                "url": f"https://player.vimeo.com/video/{video_id}",
                "provider": "Vimeo",
            }

    path_lower = parsed.path.lower()
    if path_lower.endswith((".mp4", ".webm", ".ogg", ".ogv", ".m4v")):
        return {"kind": "video", "url": raw_url, "provider": "video"}

    return {"kind": "iframe", "url": raw_url, "provider": host}


def _client_ip(request):
    return request.META.get("REMOTE_ADDR") or None


def _safe_learning_next(request, default_name="learning_platform:dashboard"):
    target = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if not target:
        return reverse(default_name)
    allowed = url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )
    learning_prefix = reverse("learning_platform:landing")
    return target if allowed and target.startswith(learning_prefix) else reverse(default_name)


def _manager_display_name(user):
    if not getattr(user, "is_authenticated", False):
        return ""
    full_name = (user.get_full_name() or "").strip()
    if full_name:
        return full_name
    try:
        profile_name = (user.profile.full_name or "").strip()
    except Exception:
        profile_name = ""
    return profile_name or user.get_username()


def _base_context(request, **extra):
    erp_manager = request.user if is_management_user(request.user) else None
    learning_account = get_learning_account(request)
    unread_notifications_count = 0
    if learning_account is not None:
        unread_notifications_count = learning_account.notifications.filter(read_at__isnull=True).count()
    return {
        "learning_account": learning_account,
        "unread_notifications_count": unread_notifications_count,
        "erp_manager": erp_manager,
        "erp_manager_name": _manager_display_name(erp_manager),
        "platform_manager_mode": False,
        **extra,
    }


def _manager_context(request, *, manager_section="dashboard", **extra):
    return _base_context(
        request,
        platform_manager_mode=True,
        manager_section=manager_section,
        **extra,
    )


def platform_manager_required(view_func):
    @login_required(login_url="login")
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_management_user(request.user):
            raise PermissionDenied("هذه الصفحة متاحة لمدير OPAL ERP فقط.")
        return view_func(request, *args, **kwargs)

    return wrapped


def _record_manager_event(request, *, action, entity_type, entity_id, metadata=None, account=None):
    details = {
        "erp_manager_username": request.user.get_username(),
        "erp_manager_name": _manager_display_name(request.user),
        **(metadata or {}),
    }
    LearningAuditEvent.objects.create(
        account=account,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        ip_address=_client_ip(request),
        metadata=details,
    )



def _require_learner(account):
    if account.role != LearningAccount.Role.LEARNER:
        raise PermissionDenied("هذه العملية متاحة للمتعلم فقط.")
    return account


@login_required(login_url="login")
@never_cache
def erp_parent_student_entry(request, student_pk):
    from students.models import Student

    student = get_object_or_404(Student, pk=student_pk, is_active=True)
    assert_parent_can_open_student(request.user, student)
    account = ensure_student_learning_account(student)
    start_learning_session(request, account, ip_address=_client_ip(request), action=LearningAuditEvent.Action.LOGIN)
    messages.success(request, f"تم فتح منصة أوبال التعليمية للطالب {student.full_name}.")
    return redirect("learning_platform:dashboard")


@login_required(login_url="login")
@never_cache
def erp_teacher_entry(request):
    teacher = getattr(request.user, "teacher_profile", None)
    if teacher is None or not teacher_learning_access(teacher):
        raise PermissionDenied("منصة أوبال التعليمية غير متاحة لحساب المعلم الحالي.")
    account = ensure_teacher_learning_account(teacher)
    start_learning_session(request, account, ip_address=_client_ip(request), action=LearningAuditEvent.Action.LOGIN)
    return redirect("learning_platform:dashboard")


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_school_access(request):
    from academics.models import Grade
    from core.models import School
    from students.models import Student

    school = School.objects.filter(is_active=True).first()
    if school is None:
        messages.error(request, "أدخل بيانات المدرسة أولًا.")
        return redirect("core:system_settings")
    access = access_settings_for_school(school)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "global":
            access.parent_default_enabled = request.POST.get("parent_default_enabled") == "1"
            access.teacher_sso_enabled = request.POST.get("teacher_sso_enabled") == "1"
            access.save(update_fields=["parent_default_enabled", "teacher_sso_enabled", "updated_at"])
            messages.success(request, "تم حفظ الإتاحة العامة للمنصة.")
        elif action in {"all_on", "all_off"}:
            # An explicit whole-school switch must be literal: clear all
            # narrower exceptions so an old grade/student override cannot
            # silently defeat the manager's "everyone" decision.
            access.parent_default_enabled = action == "all_on"
            access.save(update_fields=["parent_default_enabled", "updated_at"])
            LearningStudentAccessOverride.objects.filter(settings=access).delete()
            LearningGradeAccessOverride.objects.filter(settings=access).delete()
            messages.success(
                request,
                "تمت إتاحة المنصة لجميع الطلاب وإلغاء الاستثناءات السابقة."
                if access.parent_default_enabled
                else "تم إيقاف المنصة عن جميع الطلاب وإلغاء الاستثناءات السابقة.",
            )
        elif action == "grade":
            grade = get_object_or_404(Grade, pk=request.POST.get("grade_id"), school=school)
            mode = request.POST.get("mode")
            if mode == "inherit":
                LearningGradeAccessOverride.objects.filter(settings=access, grade=grade).delete()
            elif mode in {"enabled", "disabled"}:
                LearningGradeAccessOverride.objects.update_or_create(
                    settings=access,
                    grade=grade,
                    defaults={"is_enabled": mode == "enabled"},
                )
            messages.success(request, f"تم تحديث إتاحة المنصة للصف {grade.name}.")
        elif action == "student":
            student = get_object_or_404(Student, pk=request.POST.get("student_id"), is_active=True)
            enrollment_access = student_learning_access(student)
            if enrollment_access["enrollment"] is None or enrollment_access["enrollment"].academic_year.school_id != school.pk:
                raise PermissionDenied("الطالب لا يتبع المدرسة الحالية.")
            mode = request.POST.get("mode")
            if mode == "inherit":
                LearningStudentAccessOverride.objects.filter(settings=access, student=student).delete()
            elif mode in {"enabled", "disabled"}:
                LearningStudentAccessOverride.objects.update_or_create(
                    settings=access,
                    student=student,
                    defaults={"is_enabled": mode == "enabled"},
                )
            messages.success(request, f"تم تحديث إتاحة المنصة للطالب {student.full_name}.")
        return redirect("learning_platform:manager_school_access")

    grades = list(Grade.objects.filter(school=school, is_active=True).order_by("order", "name"))
    grade_override_map = {
        item.grade_id: item.is_enabled
        for item in LearningGradeAccessOverride.objects.filter(settings=access)
    }
    for grade in grades:
        grade.learning_mode = (
            "enabled" if grade_override_map.get(grade.pk) is True
            else "disabled" if grade_override_map.get(grade.pk) is False
            else "inherit"
        )

    query = (request.GET.get("q") or "").strip()
    students = Student.objects.filter(is_active=True)
    if query:
        students = students.filter(
            models.Q(full_name__icontains=query)
            | models.Q(student_number__icontains=query)
            | models.Q(guardian_name__icontains=query)
        )
    else:
        students = students.none()
    students = list(students.order_by("full_name")[:50])
    student_override_map = {
        item.student_id: item.is_enabled
        for item in LearningStudentAccessOverride.objects.filter(settings=access, student__in=students)
    }
    for student in students:
        student.learning_mode = (
            "enabled" if student_override_map.get(student.pk) is True
            else "disabled" if student_override_map.get(student.pk) is False
            else "inherit"
        )
        student.learning_resolved = student_learning_access(student)

    return render(
        request,
        "learning_platform/manager_school_access.html",
        _manager_context(
            request,
            manager_section="school_access",
            access_settings=access,
            grades=grades,
            students=students,
            query=query,
            school=school,
        ),
    )


def landing(request):
    courses = (
        LearningCourse.objects.filter(status=LearningCourse.Status.PUBLISHED, subject__is_active=True)
        .select_related("subject", "teacher")
        .annotate(lesson_count=Count("lessons", filter=models.Q(lessons__is_published=True)))
        [:6]
    )
    return render(request, "learning_platform/landing.html", _base_context(request, courses=courses))


@never_cache
@require_http_methods(["GET", "POST"])
def register(request):
    if get_learning_account(request) is not None:
        return redirect("learning_platform:dashboard")
    form = LearningRegistrationForm(request.POST or None)
    if request.method == "POST":
        try:
            consume_rate_limit(
                "web_register",
                _client_ip(request) or "unknown",
                limit=5,
                window_seconds=3600,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if form.is_valid():
                account = form.save()
                verification_request, raw_token = create_email_verification_request(
                    account, ip_address=_client_ip(request)
                )
                verify_url = request.build_absolute_uri(
                    reverse(
                        "learning_platform:email_verify",
                        kwargs={"token": raw_token},
                    )
                )
                sent = deliver_email_verification(verification_request, raw_token, verify_url)
                start_learning_session(
                    request,
                    account,
                    ip_address=_client_ip(request),
                    action="registered",
                )
                messages.success(request, "تم إنشاء حسابك التعليمي المستقل بنجاح.")
                if sent:
                    messages.info(request, "أرسلنا رابط توثيق البريد. افتحه لتمكين الاشتراك وتطبيق الموبايل.")
                else:
                    messages.warning(request, "لم يُرسل رابط التوثيق لأن البريد غير مهيأ. راجع إدارة المنصة.")
                return redirect(_safe_learning_next(request))
    return render(
        request,
        "learning_platform/register.html",
        _base_context(request, form=form, next=request.GET.get("next", "")),
    )


@never_cache
@require_http_methods(["GET", "POST"])
def login(request):
    if get_learning_account(request) is not None:
        return redirect("learning_platform:dashboard")
    form = LearningLoginForm(request.POST or None)
    if request.method == "POST":
        try:
            consume_rate_limit(
                "web_login",
                f"{_client_ip(request) or 'unknown'}:{(request.POST.get('email') or '').strip().lower()}",
                limit=int(getattr(settings, "OPAL_LEARNING_LOGIN_RATE_LIMIT", 10)),
                window_seconds=300,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if form.is_valid():
                start_learning_session(request, form.account, ip_address=_client_ip(request))
                messages.success(request, "مرحبًا بعودتك إلى منصة أوبال التعليمية.")
                if email_verification_required(form.account):
                    messages.warning(request, "وثّق بريدك الإلكتروني قبل شراء خطة أو تسجيل تطبيق الموبايل.")
                return redirect(_safe_learning_next(request))
    return render(
        request,
        "learning_platform/login.html",
        _base_context(request, form=form, next=request.GET.get("next", "")),
    )


@never_cache
@require_http_methods(["GET", "POST"])
def legal_acceptance(request):
    account = get_learning_account(request)
    if account is None:
        return redirect("learning_platform:login")
    if account.terms_accepted_at and account.privacy_accepted_at:
        return redirect("learning_platform:dashboard")
    form = LearningLegalAcceptanceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        now = timezone.now()
        account.terms_accepted_at = now
        account.privacy_accepted_at = now
        account.save(update_fields=["terms_accepted_at", "privacy_accepted_at", "updated_at"])
        LearningAuditEvent.objects.create(
            account=account,
            action="legal_terms_accepted",
            entity_type="learning_account",
            entity_id=str(account.pk),
            ip_address=_client_ip(request),
            metadata={"terms_version": "R20", "privacy_version": "R20"},
        )
        messages.success(request, "تم تسجيل موافقتك ويمكنك متابعة استخدام المنصة.")
        return redirect("learning_platform:dashboard")
    return render(
        request,
        "learning_platform/legal_acceptance.html",
        _base_context(request, form=form),
    )


@require_POST
def logout(request):
    end_learning_session(request, ip_address=_client_ip(request))
    messages.success(request, "تم تسجيل الخروج من المنصة التعليمية فقط.")
    return redirect("learning_platform:landing")


@never_cache
@platform_manager_required
def manager_dashboard(request):
    accounts = LearningAccount.objects.all()
    courses = LearningCourse.objects.select_related("subject", "teacher")
    now = timezone.now()
    stats = {
        "accounts": accounts.count(),
        "learners": accounts.filter(role=LearningAccount.Role.LEARNER, is_active=True).count(),
        "teachers": accounts.filter(role=LearningAccount.Role.TEACHER, is_active=True).count(),
        "courses": courses.count(),
        "published_courses": courses.filter(status=LearningCourse.Status.PUBLISHED).count(),
        "published_lessons": LearningLesson.objects.filter(is_published=True).count(),
        "published_assessments": LearningAssessment.objects.filter(is_published=True).count(),
        "pending_submissions": LearningSubmission.objects.filter(
            status=LearningSubmission.Status.SUBMITTED,
        ).count(),
        "certificates": LearningCertificate.objects.filter(revoked_at__isnull=True).count(),
        "enrollments": LearningEnrollment.objects.filter(status=LearningEnrollment.Status.ACTIVE).count(),
        "active_subscriptions": LearningSubscriptionCard.objects.filter(
            status=LearningSubscriptionCard.Status.REDEEMED,
            expires_at__gt=now,
        ).count(),
        "available_subscriptions": LearningSubscriptionCard.objects.filter(
            status=LearningSubscriptionCard.Status.AVAILABLE,
        ).count(),
        "open_password_resets": LearningPasswordResetRequest.objects.filter(
            used_at__isnull=True,
            expires_at__gt=now,
        ).count(),
        "unread_notifications": LearningNotification.objects.filter(read_at__isnull=True).count(),
        "unverified_accounts": accounts.filter(email_verified_at__isnull=True).exclude(role=LearningAccount.Role.MANAGER).count(),
        "subscription_plans": LearningSubscriptionPlan.objects.filter(is_active=True).count(),
        "pending_payments": LearningPaymentOrder.objects.filter(status__in=[LearningPaymentOrder.Status.PENDING, LearningPaymentOrder.Status.PROCESSING]).count(),
        "paid_orders": LearningPaymentOrder.objects.filter(status=LearningPaymentOrder.Status.PAID).count(),
    }
    recent_accounts = accounts.order_by("-created_at")[:8]
    recent_courses = courses.order_by("-updated_at")[:6]
    return render(
        request,
        "learning_platform/manager_dashboard.html",
        _manager_context(
            request,
            stats=stats,
            recent_accounts=recent_accounts,
            recent_courses=recent_courses,
            readiness=collect_learning_readiness_checks(include_migrations=False),
        ),
    )


@never_cache
@platform_manager_required
def manager_account_list(request):
    accounts = LearningAccount.objects.all()
    query = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()
    if query:
        accounts = accounts.filter(
            models.Q(full_name__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(phone__icontains=query)
        )
    if role in {LearningAccount.Role.LEARNER, LearningAccount.Role.TEACHER}:
        accounts = accounts.filter(role=role)
    accounts = accounts.annotate(
        course_count=Count("authored_courses", distinct=True),
        enrollment_count=Count("enrollments", distinct=True),
    ).order_by("-created_at")
    return render(
        request,
        "learning_platform/manager_account_list.html",
        _manager_context(request, manager_section="accounts", accounts=accounts, query=query, role=role),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_teacher_create(request):
    form = LearningTeacherCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        teacher = form.save()
        _record_manager_event(
            request,
            action="manager_teacher_created",
            entity_type="learning_account",
            entity_id=teacher.pk,
            metadata={"role": teacher.role},
            account=teacher,
        )
        messages.success(request, f"تم إنشاء حساب المدرّس {teacher.full_name}.")
        return redirect("learning_platform:manager_account_list")
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="accounts",
            form=form,
            page_title="إنشاء حساب مدرّس",
            page_intro="ينشئ المدير حسابًا مستقلًا للمدرّس. يدخل المدرّس من صفحة دخول المنصة وليس من OPAL ERP.",
            submit_label="إنشاء حساب المدرّس",
            cancel_url=reverse("learning_platform:manager_account_list"),
        ),
    )


@platform_manager_required
@require_POST
def manager_account_toggle(request, pk):
    account = get_object_or_404(
        LearningAccount.objects.filter(role__in=[LearningAccount.Role.LEARNER, LearningAccount.Role.TEACHER]),
        pk=pk,
    )
    account.is_active = not account.is_active
    if not account.is_active:
        account.auth_version += 1
        account.save(update_fields=["is_active", "auth_version", "updated_at"])
    else:
        account.save(update_fields=["is_active", "updated_at"])
    _record_manager_event(
        request,
        action="manager_account_toggled",
        entity_type="learning_account",
        entity_id=account.pk,
        metadata={"is_active": account.is_active},
        account=account,
    )
    messages.success(request, "تم تفعيل الحساب." if account.is_active else "تم إيقاف الحساب ومنع دخوله.")
    return redirect("learning_platform:manager_account_list")


@never_cache
@platform_manager_required
def manager_subject_list(request):
    subjects = LearningSubject.objects.annotate(
        course_count=Count("courses", distinct=True),
        published_course_count=Count(
            "courses",
            filter=models.Q(courses__status=LearningCourse.Status.PUBLISHED),
            distinct=True,
        ),
    ).order_by("name")
    return render(
        request,
        "learning_platform/manager_subject_list.html",
        _manager_context(request, manager_section="subjects", subjects=subjects),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_subject_create(request):
    form = LearningSubjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        subject = form.save()
        _record_manager_event(
            request,
            action="manager_subject_saved",
            entity_type="learning_subject",
            entity_id=subject.pk,
            metadata={"created": True},
        )
        messages.success(request, "تم إنشاء المادة التعليمية.")
        return redirect("learning_platform:manager_subject_list")
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="subjects",
            form=form,
            page_title="إضافة مادة تعليمية",
            page_intro="المادة هي التصنيف الرسمي الذي ترتبط به الدورات داخل المنصة.",
            submit_label="حفظ المادة",
            cancel_url=reverse("learning_platform:manager_subject_list"),
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_subject_update(request, pk):
    subject = get_object_or_404(LearningSubject, pk=pk)
    form = LearningSubjectForm(request.POST or None, instance=subject)
    if request.method == "POST" and form.is_valid():
        subject = form.save()
        _record_manager_event(
            request,
            action="manager_subject_saved",
            entity_type="learning_subject",
            entity_id=subject.pk,
            metadata={"created": False, "is_active": subject.is_active},
        )
        messages.success(request, "تم تحديث المادة التعليمية.")
        return redirect("learning_platform:manager_subject_list")
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="subjects",
            form=form,
            page_title=f"تعديل مادة: {subject.name}",
            page_intro="تعطيل المادة يخفي دوراتها من الدليل العام دون حذفها.",
            submit_label="حفظ التعديلات",
            cancel_url=reverse("learning_platform:manager_subject_list"),
        ),
    )


@never_cache
@platform_manager_required
def manager_course_list(request):
    courses = LearningCourse.objects.select_related("subject", "teacher").annotate(
        lesson_count=Count("lessons", distinct=True),
        published_lesson_count=Count("lessons", filter=models.Q(lessons__is_published=True), distinct=True),
        assessment_count=Count("assessments", distinct=True),
        published_assessment_count=Count(
            "assessments",
            filter=models.Q(assessments__is_published=True),
            distinct=True,
        ),
        learner_count=Count(
            "enrollments",
            filter=models.Q(enrollments__status=LearningEnrollment.Status.ACTIVE),
            distinct=True,
        ),
    )
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if query:
        courses = courses.filter(
            models.Q(title__icontains=query)
            | models.Q(subject__name__icontains=query)
            | models.Q(teacher__full_name__icontains=query)
        )
    if status in set(LearningCourse.Status.values):
        courses = courses.filter(status=status)
    return render(
        request,
        "learning_platform/manager_course_list.html",
        _manager_context(
            request,
            manager_section="courses",
            courses=courses,
            query=query,
            status=status,
            course_statuses=LearningCourse.Status.choices,
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_course_create(request):
    form = LearningCourseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            course = form.save(commit=False)
            course.status = LearningCourse.Status.DRAFT
            course.save()
            _record_manager_event(
                request,
                action="manager_course_saved",
                entity_type="learning_course",
                entity_id=course.pk,
                metadata={"created": True, "teacher_id": course.teacher_id},
            )
        messages.success(request, "تم إنشاء الدورة كمسودة. أضف درسًا منشورًا واحدًا على الأقل قبل نشرها.")
        return redirect("learning_platform:manager_lesson_list", course_pk=course.pk)
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="courses",
            form=form,
            page_title="إنشاء دورة جديدة",
            page_intro="تُنشأ الدورة كمسودة، ثم تُضاف دروسها وتُنشر بعد اكتمال المحتوى الأساسي.",
            submit_label="إنشاء الدورة والمتابعة للدروس",
            cancel_url=reverse("learning_platform:manager_course_list"),
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_course_update(request, pk):
    course = get_object_or_404(LearningCourse, pk=pk)
    form = LearningCourseForm(request.POST or None, instance=course)
    if request.method == "POST" and form.is_valid():
        course = form.save()
        _record_manager_event(
            request,
            action="manager_course_saved",
            entity_type="learning_course",
            entity_id=course.pk,
            metadata={"created": False, "teacher_id": course.teacher_id},
        )
        messages.success(request, "تم تحديث بيانات الدورة.")
        return redirect("learning_platform:manager_course_list")
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="courses",
            form=form,
            page_title=f"تعديل دورة: {course.title}",
            page_intro=f"الحالة الحالية: {course.get_status_display()}. تغيير حالة النشر يتم من قائمة الدورات.",
            submit_label="حفظ التعديلات",
            cancel_url=reverse("learning_platform:manager_course_list"),
        ),
    )


@platform_manager_required
@require_POST
def manager_course_status(request, pk):
    course = get_object_or_404(LearningCourse.objects.select_related("teacher", "subject"), pk=pk)
    action = (request.POST.get("action") or "").strip()
    target_status = {
        "publish": LearningCourse.Status.PUBLISHED,
        "draft": LearningCourse.Status.DRAFT,
        "archive": LearningCourse.Status.ARCHIVED,
    }.get(action)
    if target_status is None:
        messages.error(request, "إجراء حالة الدورة غير معروف.")
        return redirect("learning_platform:manager_course_list")

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
            for error in errors:
                messages.error(request, error)
            return redirect("learning_platform:manager_course_list")

    course.status = target_status
    if target_status == LearningCourse.Status.PUBLISHED and course.published_at is None:
        course.published_at = timezone.now()
        update_fields = ["status", "published_at", "updated_at"]
    else:
        update_fields = ["status", "updated_at"]
    course.save(update_fields=update_fields)
    _record_manager_event(
        request,
        action="manager_course_status",
        entity_type="learning_course",
        entity_id=course.pk,
        metadata={"status": target_status},
    )
    messages.success(request, f"تم تحويل الدورة إلى حالة: {course.get_status_display()}.")
    return redirect("learning_platform:manager_course_list")


@never_cache
@platform_manager_required
def manager_lesson_list(request, course_pk):
    course = get_object_or_404(LearningCourse.objects.select_related("subject", "teacher"), pk=course_pk)
    lessons = course.lessons.all().order_by("order", "id")
    return render(
        request,
        "learning_platform/manager_lesson_list.html",
        _manager_context(
            request,
            manager_section="courses",
            course=course,
            lessons=lessons,
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_lesson_create(request, course_pk):
    course = get_object_or_404(LearningCourse, pk=course_pk)
    instance = LearningLesson(course=course)
    form = LearningLessonForm(request.POST or None, request.FILES or None, instance=instance, course=course)
    if request.method == "POST" and form.is_valid():
        lesson = form.save()
        if lesson.is_published:
            refresh_course_enrollments(course)
        _record_manager_event(
            request,
            action="manager_lesson_saved",
            entity_type="learning_lesson",
            entity_id=lesson.pk,
            metadata={"created": True, "course_id": course.pk, "is_published": lesson.is_published},
        )
        messages.success(request, "تمت إضافة الدرس إلى الدورة.")
        return redirect("learning_platform:manager_lesson_list", course_pk=course.pk)
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="courses",
            form=form,
            page_title=f"إضافة درس إلى: {course.title}",
            page_intro="الدرس غير المنشور لا يظهر للمتعلمين حتى لو كانت الدورة منشورة.",
            submit_label="حفظ الدرس",
            cancel_url=reverse("learning_platform:manager_lesson_list", kwargs={"course_pk": course.pk}),
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_lesson_update(request, pk):
    lesson = get_object_or_404(LearningLesson.objects.select_related("course"), pk=pk)
    course = lesson.course
    was_published = lesson.is_published
    form = LearningLessonForm(request.POST or None, request.FILES or None, instance=lesson, course=course)
    if request.method == "POST" and form.is_valid():
        lesson = form.save()
        if was_published != lesson.is_published:
            refresh_course_enrollments(course)
        _record_manager_event(
            request,
            action="manager_lesson_saved",
            entity_type="learning_lesson",
            entity_id=lesson.pk,
            metadata={"created": False, "course_id": course.pk, "is_published": lesson.is_published},
        )
        messages.success(request, "تم تحديث الدرس.")
        return redirect("learning_platform:manager_lesson_list", course_pk=course.pk)
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="courses",
            form=form,
            page_title=f"تعديل درس: {lesson.title}",
            page_intro=f"الدورة: {course.title}",
            submit_label="حفظ التعديلات",
            cancel_url=reverse("learning_platform:manager_lesson_list", kwargs={"course_pk": course.pk}),
        ),
    )


@never_cache
@platform_manager_required
def manager_subscription_list(request):
    cards = LearningSubscriptionCard.objects.select_related("redeemed_by").prefetch_related("subjects")
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    duration = (request.GET.get("duration") or "").strip()
    if query:
        cards = cards.filter(
            models.Q(code__icontains=query)
            | models.Q(redeemed_by__full_name__icontains=query)
            | models.Q(redeemed_by__email__icontains=query)
        )
    if status in set(LearningSubscriptionCard.Status.values):
        cards = cards.filter(status=status)
    if duration in set(LearningSubscriptionCard.Duration.values):
        cards = cards.filter(duration=duration)
    return render(
        request,
        "learning_platform/manager_subscription_list.html",
        _manager_context(
            request,
            manager_section="subscriptions",
            cards=cards,
            query=query,
            status=status,
            duration=duration,
            subscription_statuses=LearningSubscriptionCard.Status.choices,
            subscription_durations=LearningSubscriptionCard.Duration.choices,
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_subscription_generate(request):
    form = LearningSubscriptionBatchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            cards = form.save()
            for card in cards:
                _record_manager_event(
                    request,
                    action=LearningAuditEvent.Action.SUBSCRIPTION_CREATED,
                    entity_type="subscription_card",
                    entity_id=card.pk,
                    metadata={
                        "duration": card.duration,
                        "grants_all_subjects": card.grants_all_subjects,
                    },
                )
        messages.success(request, f"تم إنشاء {len(cards)} بطاقة اشتراك جديدة.")
        return redirect("learning_platform:manager_subscription_list")
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="subscriptions",
            form=form,
            page_title="إنشاء بطاقات اشتراك",
            page_intro="أنشئ دفعة من الرموز الآمنة، وحدد مدتها والمواد التي تمنح الوصول إليها.",
            submit_label="إنشاء البطاقات",
            cancel_url=reverse("learning_platform:manager_subscription_list"),
        ),
    )


@platform_manager_required
@require_POST
def manager_subscription_cancel(request, pk):
    with transaction.atomic():
        card = get_object_or_404(LearningSubscriptionCard.objects.select_for_update(), pk=pk)
        if card.status != LearningSubscriptionCard.Status.AVAILABLE:
            messages.error(request, "لا يمكن إلغاء بطاقة مفعلة أو ملغاة سابقًا.")
            return redirect("learning_platform:manager_subscription_list")
        card.status = LearningSubscriptionCard.Status.CANCELLED
        card.save(update_fields=["status"])
        _record_manager_event(
            request,
            action=LearningAuditEvent.Action.SUBSCRIPTION_CANCELLED,
            entity_type="subscription_card",
            entity_id=card.pk,
            metadata={"code": card.code},
        )
    messages.success(request, "تم إلغاء البطاقة ومنع تفعيلها.")
    return redirect("learning_platform:manager_subscription_list")


@never_cache
@platform_manager_required
def manager_enrollment_list(request):
    enrollments = LearningEnrollment.objects.select_related(
        "learner",
        "course",
        "course__subject",
        "course__teacher",
    )
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if query:
        enrollments = enrollments.filter(
            models.Q(learner__full_name__icontains=query)
            | models.Q(learner__email__icontains=query)
            | models.Q(course__title__icontains=query)
        )
    if status in set(LearningEnrollment.Status.values):
        enrollments = enrollments.filter(status=status)
    return render(
        request,
        "learning_platform/manager_enrollment_list.html",
        _manager_context(
            request,
            manager_section="enrollments",
            enrollments=enrollments,
            query=query,
            status=status,
            enrollment_statuses=LearningEnrollment.Status.choices,
        ),
    )


@never_cache
@learning_login_required
@require_http_methods(["GET", "POST"])
def teacher_course_create(request):
    account = request.learning_account
    teacher = managed_teacher_for_account(account)
    if teacher is None or not teacher_learning_access(teacher):
        raise PermissionDenied("إنشاء المحتوى متاح للمعلم المرتبط رسميًا بـ OPAL فقط.")
    form = LearningTeacherSchoolCourseForm(request.POST or None, teacher=teacher)
    if request.method == "POST" and form.is_valid():
        assignment = form.cleaned_data["assignment"]
        course = form.save(commit=False)
        course.teacher = account
        course.subject = ensure_learning_subject_for_academic_subject(assignment.subject)
        course.academic_subject = assignment.subject
        course.academic_section = assignment.section
        course.grade_label = assignment.section.grade.name
        course.status = LearningCourse.Status.DRAFT
        course.save()
        messages.success(request, "تم إنشاء الدورة ضمن تكليفك الرسمي. أضف الدروس ثم انشرها.")
        return redirect("learning_platform:teacher_lesson_list", course_pk=course.pk)
    return render(request, "learning_platform/teacher_form.html", _base_context(
        request, form=form, page_title="إنشاء محتوى تعليمي", page_intro="اختر تكليفًا رسميًا ثم أنشئ محتوى المادة والشعبة.",
        submit_label="إنشاء الدورة", cancel_url=reverse("learning_platform:dashboard")
    ))


@never_cache
@learning_login_required
@require_http_methods(["GET", "POST"])
def teacher_course_update(request, pk):
    account = request.learning_account
    teacher = managed_teacher_for_account(account)
    if teacher is None:
        raise PermissionDenied("هذه الصفحة متاحة للمعلم المدرسي فقط.")
    course = get_object_or_404(LearningCourse, pk=pk, teacher=account)
    form = LearningTeacherSchoolCourseForm(request.POST or None, instance=course, teacher=teacher)
    if request.method == "POST" and form.is_valid():
        assignment = form.cleaned_data["assignment"]
        course = form.save(commit=False)
        course.subject = ensure_learning_subject_for_academic_subject(assignment.subject)
        course.academic_subject = assignment.subject
        course.academic_section = assignment.section
        course.grade_label = assignment.section.grade.name
        course.teacher = account
        course.save()
        messages.success(request, "تم تحديث الدورة.")
        return redirect("learning_platform:teacher_lesson_list", course_pk=course.pk)
    return render(request, "learning_platform/teacher_form.html", _base_context(
        request, form=form, page_title=f"تعديل: {course.title}", page_intro="لا يمكن ربط الدورة إلا بأحد تكليفاتك الرسمية.",
        submit_label="حفظ التعديلات", cancel_url=reverse("learning_platform:dashboard")
    ))


@learning_login_required
@require_POST
def teacher_course_publish(request, pk):
    account = request.learning_account
    if managed_teacher_for_account(account) is None:
        raise PermissionDenied("هذه العملية متاحة للمعلم المدرسي فقط.")
    course = get_object_or_404(LearningCourse, pk=pk, teacher=account)
    if not course.lessons.filter(is_published=True).exists():
        messages.error(request, "أضف درسًا منشورًا واحدًا على الأقل قبل نشر الدورة.")
        return redirect("learning_platform:teacher_lesson_list", course_pk=course.pk)
    course.status = LearningCourse.Status.PUBLISHED
    if course.published_at is None:
        course.published_at = timezone.now()
    course.save(update_fields=["status", "published_at", "updated_at"])
    messages.success(request, "تم نشر الدورة لطلاب الصف والشعبة المرتبطين بها.")
    return redirect("learning_platform:teacher_lesson_list", course_pk=course.pk)


@never_cache
@learning_login_required
def teacher_lesson_list(request, course_pk):
    account = request.learning_account
    if managed_teacher_for_account(account) is None:
        raise PermissionDenied("هذه الصفحة متاحة للمعلم المدرسي فقط.")
    course = get_object_or_404(LearningCourse.objects.select_related("subject", "academic_subject", "academic_section"), pk=course_pk, teacher=account)
    return render(request, "learning_platform/teacher_course_content.html", _base_context(
        request, course=course, lessons=course.lessons.all().order_by("order", "id")
    ))


@never_cache
@learning_login_required
@require_http_methods(["GET", "POST"])
def teacher_lesson_create(request, course_pk):
    account = request.learning_account
    if managed_teacher_for_account(account) is None:
        raise PermissionDenied("هذه الصفحة متاحة للمعلم المدرسي فقط.")
    course = get_object_or_404(LearningCourse, pk=course_pk, teacher=account)
    instance = LearningLesson(course=course)
    form = LearningLessonForm(request.POST or None, request.FILES or None, instance=instance, course=course)
    if request.method == "POST" and form.is_valid():
        lesson = form.save()
        if lesson.is_published:
            refresh_course_enrollments(course)
        messages.success(request, "تم حفظ الدرس.")
        return redirect("learning_platform:teacher_lesson_list", course_pk=course.pk)
    return render(request, "learning_platform/teacher_form.html", _base_context(
        request, form=form, page_title=f"إضافة درس — {course.title}", page_intro="يمكنك كتابة المحتوى أو إضافة فيديو أو رفع مرفق للدرس.",
        submit_label="حفظ الدرس", cancel_url=reverse("learning_platform:teacher_lesson_list", kwargs={"course_pk": course.pk})
    ))


@never_cache
@learning_login_required
@require_http_methods(["GET", "POST"])
def teacher_lesson_update(request, pk):
    account = request.learning_account
    if managed_teacher_for_account(account) is None:
        raise PermissionDenied("هذه الصفحة متاحة للمعلم المدرسي فقط.")
    lesson = get_object_or_404(LearningLesson.objects.select_related("course"), pk=pk, course__teacher=account)
    course = lesson.course
    was_published = lesson.is_published
    form = LearningLessonForm(request.POST or None, request.FILES or None, instance=lesson, course=course)
    if request.method == "POST" and form.is_valid():
        lesson = form.save()
        if was_published != lesson.is_published:
            refresh_course_enrollments(course)
        messages.success(request, "تم تحديث الدرس.")
        return redirect("learning_platform:teacher_lesson_list", course_pk=course.pk)
    return render(request, "learning_platform/teacher_form.html", _base_context(
        request, form=form, page_title=f"تعديل الدرس — {lesson.title}", page_intro=course.title,
        submit_label="حفظ التعديلات", cancel_url=reverse("learning_platform:teacher_lesson_list", kwargs={"course_pk": course.pk})
    ))


@never_cache
@learning_login_required
def teacher_course_learners(request, course_pk):
    account = request.learning_account
    if account.role != LearningAccount.Role.TEACHER:
        raise PermissionDenied("هذه الصفحة متاحة للمدرّس فقط.")
    course = get_object_or_404(
        LearningCourse.objects.select_related("subject"),
        pk=course_pk,
        teacher=account,
    )
    enrollments = course.enrollments.select_related("learner").annotate(
        completed_lessons=Count(
            "lesson_progress",
            filter=models.Q(lesson_progress__completed_at__isnull=False),
            distinct=True,
        )
    ).order_by("-last_activity_at", "-enrolled_at")
    return render(
        request,
        "learning_platform/teacher_course_learners.html",
        _base_context(request, course=course, enrollments=enrollments),
    )


@learning_login_required
def dashboard(request):
    account = request.learning_account
    sync_account_notifications(account)
    if account.role == account.Role.MANAGER:
        end_learning_session(request, ip_address=_client_ip(request))
        messages.info(request, "مدير المنصة يدخل من حساب OPAL ERP عبر بوابة الإدارة.")
        return redirect("learning_platform:manager_dashboard")
    if account.role == account.Role.TEACHER:
        courses = account.authored_courses.select_related("subject").annotate(
            learner_count=Count("enrollments", distinct=True),
            lesson_count=Count("lessons", distinct=True),
            assessment_count=Count("assessments", distinct=True),
            pending_submission_count=Count(
                "assessments__submissions",
                filter=models.Q(assessments__submissions__status=LearningSubmission.Status.SUBMITTED),
                distinct=True,
            ),
        )
        return render(
            request,
            "learning_platform/teacher_dashboard.html",
            _base_context(
                request,
                courses=courses,
                school_managed_teacher=managed_teacher_for_account(account),
            ),
        )
    enrollments = list(
        LearningEnrollment.objects.filter(learner=account)
        .select_related("course", "course__subject", "course__teacher")
    )
    managed_student = managed_student_for_account(account)
    available_courses = (
        eligible_courses_for_student(managed_student)
        .select_related("subject", "teacher", "academic_subject", "academic_section")
        .annotate(lesson_count=Count("lessons", filter=models.Q(lessons__is_published=True)))[:24]
        if managed_student is not None else LearningCourse.objects.none()
    )
    for enrollment in enrollments:
        enrollment.continue_lesson = first_incomplete_lesson(enrollment)
        enrollment.has_access = learner_can_access_course(account, enrollment.course)
        enrollment.active_certificate = LearningCertificate.objects.filter(
            enrollment=enrollment,
            revoked_at__isnull=True,
        ).first()
    active_cards = account.subscription_cards.filter(
        status=LearningSubscriptionCard.Status.REDEEMED,
        expires_at__gt=timezone.now(),
    ).prefetch_related("subjects")
    completed_count = sum(1 for enrollment in enrollments if enrollment.status == LearningEnrollment.Status.COMPLETED)
    return render(
        request,
        "learning_platform/dashboard.html",
        _base_context(
            request,
            enrollments=enrollments,
            active_cards=active_cards,
            completed_count=completed_count,
            managed_student=managed_student,
            available_courses=available_courses,
        ),
    )


def course_list(request):
    courses = (
        LearningCourse.objects.filter(status=LearningCourse.Status.PUBLISHED, subject__is_active=True)
        .select_related("subject", "teacher")
        .annotate(lesson_count=Count("lessons", filter=models.Q(lessons__is_published=True)))
    )
    account = get_learning_account(request)
    managed_student = managed_student_for_account(account)
    if managed_student is not None:
        courses = courses.filter(pk__in=eligible_courses_for_student(managed_student).values("pk"))
    query = (request.GET.get("q") or "").strip()
    if query:
        courses = courses.filter(
            models.Q(title__icontains=query)
            | models.Q(subject__name__icontains=query)
            | models.Q(teacher__full_name__icontains=query)
        )
    return render(
        request,
        "learning_platform/course_list.html",
        _base_context(request, courses=courses, query=query),
    )


def course_detail(request, slug):
    published_lessons = Prefetch(
        "lessons",
        queryset=LearningLesson.objects.filter(is_published=True).order_by("order", "id"),
    )
    course = get_object_or_404(
        LearningCourse.objects.filter(status=LearningCourse.Status.PUBLISHED, subject__is_active=True)
        .select_related("subject", "teacher")
        .prefetch_related(published_lessons),
        slug=slug,
    )
    lessons = list(course.lessons.all())
    account = get_learning_account(request)
    if account and account.role == LearningAccount.Role.LEARNER and not school_managed_account_can_see_course(account, course):
        raise PermissionDenied("هذه الدورة ليست ضمن صف الطالب أو مواده الحالية.")
    enrollment = None
    entitlement = None
    completed_lesson_ids = set()
    if account and account.role == LearningAccount.Role.LEARNER:
        enrollment = LearningEnrollment.objects.filter(learner=account, course=course).first()
        entitlement = current_entitlement(account, course.subject)
        if enrollment:
            completed_lesson_ids = set(
                enrollment.lesson_progress.filter(completed_at__isnull=False).values_list("lesson_id", flat=True)
            )
    for lesson in lessons:
        lesson.learning_completed = lesson.pk in completed_lesson_ids
    assessments = list(
        course.assessments.filter(is_published=True).order_by("order", "id")
    )
    active_certificate = None
    if enrollment:
        submissions = list(
            LearningSubmission.objects.filter(enrollment=enrollment, assessment__in=assessments)
            .select_related("assessment")
            .order_by("assessment_id", "-attempt_no")
        )
        submissions_by_assessment = {}
        for submission in submissions:
            submissions_by_assessment.setdefault(submission.assessment_id, submission)
        for assessment in assessments:
            assessment.latest_submission = submissions_by_assessment.get(assessment.pk)
            assessment.is_passed = bool(
                assessment.latest_submission and assessment.latest_submission.is_passed
            )
            assessment.attempts_used = sum(
                1 for submission in submissions if submission.assessment_id == assessment.pk
            )
        active_certificate = LearningCertificate.objects.filter(
            enrollment=enrollment, revoked_at__isnull=True
        ).first()
    continue_lesson = first_incomplete_lesson(enrollment) if enrollment else None
    return render(
        request,
        "learning_platform/course_detail.html",
        _base_context(
            request,
            course=course,
            lessons=lessons,
            enrollment=enrollment,
            entitlement=entitlement,
            continue_lesson=continue_lesson,
            assessments=assessments,
            active_certificate=active_certificate,
            can_enroll=bool(
                account
                and account.role == LearningAccount.Role.LEARNER
                and entitlement
                and (not enrollment or enrollment.status == LearningEnrollment.Status.CANCELLED)
            ),
        ),
    )


@learning_login_required
@require_POST
def course_enroll(request, slug):
    account = _require_learner(request.learning_account)
    course = get_object_or_404(
        LearningCourse.objects.select_related("subject"),
        slug=slug,
        status=LearningCourse.Status.PUBLISHED,
        subject__is_active=True,
    )
    try:
        enrollment, created = enroll_learner(account, course, ip_address=_client_ip(request))
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("learning_platform:subscriptions")
    messages.success(request, "تم تسجيلك في الدورة." if created else "تم تأكيد وصولك إلى الدورة.")
    first_lesson = first_incomplete_lesson(enrollment) or course.lessons.filter(is_published=True).order_by("order", "id").first()
    if first_lesson:
        return redirect(
            "learning_platform:lesson_detail",
            course_slug=course.slug,
            lesson_slug=first_lesson.slug,
        )
    return redirect("learning_platform:course_detail", slug=course.slug)


@never_cache
@learning_login_required
def lesson_detail(request, course_slug, lesson_slug):
    account = _require_learner(request.learning_account)
    course = get_object_or_404(
        LearningCourse.objects.select_related("subject", "teacher"),
        slug=course_slug,
        status=LearningCourse.Status.PUBLISHED,
        subject__is_active=True,
    )
    enrollment = LearningEnrollment.objects.filter(
        learner=account,
        course=course,
        status__in=[LearningEnrollment.Status.ACTIVE, LearningEnrollment.Status.COMPLETED],
    ).first()
    if enrollment is None:
        messages.info(request, "سجّل في الدورة أولًا لفتح دروسها.")
        return redirect("learning_platform:course_detail", slug=course.slug)
    if not learner_can_access_course(account, course):
        messages.error(request, "انتهى اشتراكك أو لا يشمل مادة هذه الدورة.")
        return redirect("learning_platform:subscriptions")

    lesson = get_object_or_404(
        LearningLesson,
        course=course,
        slug=lesson_slug,
        is_published=True,
    )
    now = timezone.now()
    progress, _created = LearningLessonProgress.objects.get_or_create(
        enrollment=enrollment,
        lesson=lesson,
        defaults={"last_viewed_at": now},
    )
    if not _created:
        progress.last_viewed_at = now
        progress.save(update_fields=["last_viewed_at"])
    enrollment.last_activity_at = now
    enrollment.save(update_fields=["last_activity_at"])

    lessons = list(course.lessons.filter(is_published=True).order_by("order", "id"))
    completed_ids = set(
        enrollment.lesson_progress.filter(completed_at__isnull=False).values_list("lesson_id", flat=True)
    )
    current_index = next(index for index, item in enumerate(lessons) if item.pk == lesson.pk)
    previous_lesson = lessons[current_index - 1] if current_index > 0 else None
    next_lesson = lessons[current_index + 1] if current_index + 1 < len(lessons) else None
    for item in lessons:
        item.learning_completed = item.pk in completed_ids
    return render(
        request,
        "learning_platform/lesson_detail.html",
        _base_context(
            request,
            course=course,
            lesson=lesson,
            lessons=lessons,
            enrollment=enrollment,
            progress=progress,
            previous_lesson=previous_lesson,
            next_lesson=next_lesson,
            lesson_video_player=_lesson_video_player(lesson.video_url),
        ),
    )


@learning_login_required
@require_POST
def lesson_complete(request, course_slug, lesson_slug):
    account = _require_learner(request.learning_account)
    course = get_object_or_404(
        LearningCourse.objects.select_related("subject"),
        slug=course_slug,
        status=LearningCourse.Status.PUBLISHED,
        subject__is_active=True,
    )
    lesson = get_object_or_404(
        LearningLesson,
        course=course,
        slug=lesson_slug,
        is_published=True,
    )
    enrollment = get_object_or_404(
        LearningEnrollment,
        learner=account,
        course=course,
        status__in=[LearningEnrollment.Status.ACTIVE, LearningEnrollment.Status.COMPLETED],
    )
    try:
        _progress, enrollment = mark_lesson_completed(
            enrollment,
            lesson,
            ip_address=_client_ip(request),
        )
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("learning_platform:subscriptions")

    next_lesson = (
        course.lessons.filter(is_published=True)
        .filter(models.Q(order__gt=lesson.order) | models.Q(order=lesson.order, id__gt=lesson.id))
        .order_by("order", "id")
        .first()
    )
    if next_lesson:
        messages.success(request, f"تم إكمال الدرس. تقدمك الآن {enrollment.progress_percent}%.")
        return redirect(
            "learning_platform:lesson_detail",
            course_slug=course.slug,
            lesson_slug=next_lesson.slug,
        )
    if enrollment.status == LearningEnrollment.Status.COMPLETED:
        messages.success(request, "أكملت جميع متطلبات الدورة وصدرت شهادتك.")
    else:
        messages.success(request, "أكملت جميع الدروس. أكمل التقييمات المطلوبة لإنهاء الدورة.")
    return redirect("learning_platform:course_detail", slug=course.slug)


@learning_login_required
@require_http_methods(["GET", "POST"])
def subscriptions(request):
    account = _require_learner(request.learning_account)
    form = SubscriptionActivationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            form.card.activate(account)
            create_learning_notification(
                account,
                notification_type=LearningNotification.Type.SUBSCRIPTION,
                title="تم تفعيل اشتراكك",
                body=f"تم تفعيل البطاقة {form.card.code} حتى {timezone.localtime(form.card.expires_at):%Y-%m-%d}.",
                action_url=reverse("learning_platform:subscriptions"),
                dedupe_key=f"subscription-activated:{form.card.pk}",
            )
        except ValidationError as exc:
            form.add_error("code", exc)
        else:
            messages.success(request, "تم تفعيل بطاقة الاشتراك وربطها بحسابك التعليمي.")
            return redirect("learning_platform:subscriptions")
    cards = account.subscription_cards.prefetch_related("subjects")
    plans = LearningSubscriptionPlan.objects.filter(is_active=True).prefetch_related("subjects")
    payment_orders = account.payment_orders.select_related("plan", "subscription_card")[:20]
    return render(
        request,
        "learning_platform/subscriptions.html",
        _base_context(
            request,
            form=form,
            cards=cards,
            plans=plans,
            payment_orders=payment_orders,
            payment_status=payment_configuration_status(),
        ),
    )


@never_cache
@platform_manager_required
def manager_assessment_list(request, course_pk):
    course = get_object_or_404(
        LearningCourse.objects.select_related("subject", "teacher"),
        pk=course_pk,
    )
    assessments = course.assessments.annotate(
        question_count=Count("questions", distinct=True),
        submission_count=Count("submissions", distinct=True),
        pending_count=Count(
            "submissions",
            filter=models.Q(submissions__status=LearningSubmission.Status.SUBMITTED),
            distinct=True,
        ),
    ).order_by("order", "id")
    return render(
        request,
        "learning_platform/manager_assessment_list.html",
        _manager_context(
            request,
            manager_section="courses",
            course=course,
            assessments=assessments,
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_assessment_create(request, course_pk):
    course = get_object_or_404(LearningCourse, pk=course_pk)
    instance = LearningAssessment(course=course)
    form = LearningAssessmentForm(request.POST or None, instance=instance, course=course)
    if request.method == "POST" and form.is_valid():
        if (
            form.cleaned_data["assessment_type"] == LearningAssessment.Type.QUIZ
            and form.cleaned_data.get("is_published")
        ):
            form.add_error("is_published", "أنشئ الاختبار أولًا ثم أضف أسئلته قبل نشره.")
        else:
            assessment = form.save()
            if assessment.is_published and assessment.is_required:
                refresh_course_enrollments(course)
            _record_manager_event(
                request,
                action="manager_assessment_saved",
                entity_type="learning_assessment",
                entity_id=assessment.pk,
                metadata={
                    "created": True,
                    "course_id": course.pk,
                    "type": assessment.assessment_type,
                    "is_published": assessment.is_published,
                },
            )
            messages.success(request, "تم إنشاء التقييم.")
            if assessment.assessment_type == LearningAssessment.Type.QUIZ:
                return redirect("learning_platform:manager_question_list", assessment_pk=assessment.pk)
            return redirect("learning_platform:manager_assessment_list", course_pk=course.pk)
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="courses",
            form=form,
            page_title=f"إضافة تقييم إلى: {course.title}",
            page_intro="الاختبار يُصحح تلقائيًا، أما الواجب فيرسله المتعلم ويصححه المدرّس.",
            submit_label="حفظ التقييم",
            cancel_url=reverse("learning_platform:manager_assessment_list", kwargs={"course_pk": course.pk}),
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_assessment_update(request, pk):
    assessment = get_object_or_404(LearningAssessment.objects.select_related("course"), pk=pk)
    course = assessment.course
    old_published = assessment.is_published
    old_required = assessment.is_required
    protected_values = {
        "assessment_type": assessment.assessment_type,
        "max_score": assessment.max_score,
        "pass_score": assessment.pass_score,
        "max_attempts": assessment.max_attempts,
    }
    form = LearningAssessmentForm(request.POST or None, instance=assessment, course=course)
    if request.method == "POST" and form.is_valid():
        if assessment.submissions.exists():
            for field, old_value in protected_values.items():
                if form.cleaned_data.get(field) != old_value:
                    form.add_error(field, "لا يمكن تغيير هذا الحقل بعد وجود تسليمات.")
        if (
            form.cleaned_data.get("assessment_type") == LearningAssessment.Type.QUIZ
            and form.cleaned_data.get("is_published")
            and not assessment.questions.exists()
        ):
            form.add_error("is_published", "يجب إضافة سؤال واحد على الأقل قبل نشر الاختبار.")
        if form.is_valid():
            assessment = form.save()
            if old_published != assessment.is_published or old_required != assessment.is_required:
                refresh_course_enrollments(course)
            _record_manager_event(
                request,
                action="manager_assessment_saved",
                entity_type="learning_assessment",
                entity_id=assessment.pk,
                metadata={
                    "created": False,
                    "course_id": course.pk,
                    "is_published": assessment.is_published,
                    "is_required": assessment.is_required,
                },
            )
            messages.success(request, "تم تحديث التقييم.")
            return redirect("learning_platform:manager_assessment_list", course_pk=course.pk)
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="courses",
            form=form,
            page_title=f"تعديل تقييم: {assessment.title}",
            page_intro=f"الدورة: {course.title}",
            submit_label="حفظ التعديلات",
            cancel_url=reverse("learning_platform:manager_assessment_list", kwargs={"course_pk": course.pk}),
        ),
    )


@never_cache
@platform_manager_required
def manager_question_list(request, assessment_pk):
    assessment = get_object_or_404(
        LearningAssessment.objects.select_related("course"),
        pk=assessment_pk,
        assessment_type=LearningAssessment.Type.QUIZ,
    )
    questions = assessment.questions.order_by("order", "id")
    return render(
        request,
        "learning_platform/manager_question_list.html",
        _manager_context(
            request,
            manager_section="courses",
            assessment=assessment,
            course=assessment.course,
            questions=questions,
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_question_create(request, assessment_pk):
    assessment = get_object_or_404(
        LearningAssessment.objects.select_related("course"),
        pk=assessment_pk,
        assessment_type=LearningAssessment.Type.QUIZ,
    )
    if assessment.submissions.exists():
        messages.error(request, "لا يمكن إضافة أسئلة بعد بدء المتعلمين بمحاولات الاختبار.")
        return redirect("learning_platform:manager_question_list", assessment_pk=assessment.pk)
    instance = LearningQuestion(assessment=assessment)
    form = LearningQuestionForm(request.POST or None, instance=instance, assessment=assessment)
    if request.method == "POST" and form.is_valid():
        question = form.save()
        _record_manager_event(
            request,
            action="manager_question_saved",
            entity_type="learning_question",
            entity_id=question.pk,
            metadata={"created": True, "assessment_id": assessment.pk},
        )
        messages.success(request, "تمت إضافة السؤال.")
        return redirect("learning_platform:manager_question_list", assessment_pk=assessment.pk)
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="courses",
            form=form,
            page_title=f"إضافة سؤال إلى: {assessment.title}",
            page_intro="اختر الإجابة الصحيحة وحدد نقاط السؤال.",
            submit_label="حفظ السؤال",
            cancel_url=reverse("learning_platform:manager_question_list", kwargs={"assessment_pk": assessment.pk}),
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_question_update(request, pk):
    question = get_object_or_404(
        LearningQuestion.objects.select_related("assessment", "assessment__course"),
        pk=pk,
    )
    assessment = question.assessment
    if assessment.submissions.exists():
        messages.error(request, "لا يمكن تعديل الأسئلة بعد بدء محاولات الاختبار.")
        return redirect("learning_platform:manager_question_list", assessment_pk=assessment.pk)
    form = LearningQuestionForm(request.POST or None, instance=question, assessment=assessment)
    if request.method == "POST" and form.is_valid():
        question = form.save()
        _record_manager_event(
            request,
            action="manager_question_saved",
            entity_type="learning_question",
            entity_id=question.pk,
            metadata={"created": False, "assessment_id": assessment.pk},
        )
        messages.success(request, "تم تحديث السؤال.")
        return redirect("learning_platform:manager_question_list", assessment_pk=assessment.pk)
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="courses",
            form=form,
            page_title=f"تعديل السؤال رقم {question.order}",
            page_intro=f"الاختبار: {assessment.title}",
            submit_label="حفظ التعديلات",
            cancel_url=reverse("learning_platform:manager_question_list", kwargs={"assessment_pk": assessment.pk}),
        ),
    )


@never_cache
@platform_manager_required
def manager_submission_list(request):
    submissions = LearningSubmission.objects.select_related(
        "assessment",
        "assessment__course",
        "enrollment",
        "enrollment__learner",
    )
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    assessment_type = (request.GET.get("type") or "").strip()
    if query:
        submissions = submissions.filter(
            models.Q(enrollment__learner__full_name__icontains=query)
            | models.Q(enrollment__learner__email__icontains=query)
            | models.Q(assessment__title__icontains=query)
            | models.Q(assessment__course__title__icontains=query)
        )
    if status in set(LearningSubmission.Status.values):
        submissions = submissions.filter(status=status)
    if assessment_type in set(LearningAssessment.Type.values):
        submissions = submissions.filter(assessment__assessment_type=assessment_type)
    return render(
        request,
        "learning_platform/manager_submission_list.html",
        _manager_context(
            request,
            manager_section="submissions",
            submissions=submissions,
            query=query,
            status=status,
            assessment_type=assessment_type,
            submission_statuses=LearningSubmission.Status.choices,
            assessment_types=LearningAssessment.Type.choices,
            grading_mode="manager",
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_submission_grade(request, pk):
    submission = get_object_or_404(
        LearningSubmission.objects.select_related(
            "assessment",
            "assessment__course",
            "enrollment__learner",
        ),
        pk=pk,
        assessment__assessment_type=LearningAssessment.Type.ASSIGNMENT,
    )
    form = LearningSubmissionGradeForm(
        request.POST or None,
        max_score=submission.assessment.max_score,
        initial={"score": submission.score, "feedback": submission.feedback},
    )
    if request.method == "POST" and form.is_valid():
        try:
            grade_assignment(
                submission,
                score=form.cleaned_data["score"],
                feedback=form.cleaned_data["feedback"],
                grader_label=_manager_display_name(request.user),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "تم حفظ التصحيح وتحديث تقدم المتعلم.")
            return redirect("learning_platform:manager_submission_list")
    return render(
        request,
        "learning_platform/submission_grade.html",
        _manager_context(
            request,
            manager_section="submissions",
            submission=submission,
            form=form,
            cancel_url=reverse("learning_platform:manager_submission_list"),
        ),
    )


@never_cache
@learning_login_required
def teacher_submission_list(request, course_pk):
    account = request.learning_account
    if account.role != LearningAccount.Role.TEACHER:
        raise PermissionDenied("هذه الصفحة متاحة للمدرّس فقط.")
    course = get_object_or_404(
        LearningCourse.objects.select_related("subject"),
        pk=course_pk,
        teacher=account,
    )
    submissions = LearningSubmission.objects.filter(assessment__course=course).select_related(
        "assessment",
        "enrollment__learner",
    )
    status = (request.GET.get("status") or "").strip()
    if status in set(LearningSubmission.Status.values):
        submissions = submissions.filter(status=status)
    return render(
        request,
        "learning_platform/teacher_submission_list.html",
        _base_context(
            request,
            course=course,
            submissions=submissions,
            status=status,
            submission_statuses=LearningSubmission.Status.choices,
        ),
    )


@never_cache
@learning_login_required
@require_http_methods(["GET", "POST"])
def teacher_submission_grade(request, pk):
    account = request.learning_account
    if account.role != LearningAccount.Role.TEACHER:
        raise PermissionDenied("هذه الصفحة متاحة للمدرّس فقط.")
    submission = get_object_or_404(
        LearningSubmission.objects.select_related(
            "assessment",
            "assessment__course",
            "enrollment__learner",
        ),
        pk=pk,
        assessment__course__teacher=account,
        assessment__assessment_type=LearningAssessment.Type.ASSIGNMENT,
    )
    form = LearningSubmissionGradeForm(
        request.POST or None,
        max_score=submission.assessment.max_score,
        initial={"score": submission.score, "feedback": submission.feedback},
    )
    if request.method == "POST" and form.is_valid():
        try:
            grade_assignment(
                submission,
                score=form.cleaned_data["score"],
                feedback=form.cleaned_data["feedback"],
                grader=account,
                grader_label=account.full_name,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "تم تصحيح الواجب وتحديث تقدم المتعلم.")
            return redirect("learning_platform:teacher_submission_list", course_pk=submission.assessment.course_id)
    return render(
        request,
        "learning_platform/submission_grade.html",
        _base_context(
            request,
            submission=submission,
            form=form,
            cancel_url=reverse(
                "learning_platform:teacher_submission_list",
                kwargs={"course_pk": submission.assessment.course_id},
            ),
        ),
    )


@never_cache
@learning_login_required
@require_http_methods(["GET", "POST"])
def assessment_detail(request, course_slug, assessment_slug):
    account = _require_learner(request.learning_account)
    assessment = get_object_or_404(
        LearningAssessment.objects.select_related("course", "course__subject", "course__teacher"),
        course__slug=course_slug,
        slug=assessment_slug,
        is_published=True,
        course__status=LearningCourse.Status.PUBLISHED,
        course__subject__is_active=True,
    )
    enrollment = get_object_or_404(
        LearningEnrollment.objects.select_related("course", "learner"),
        learner=account,
        course=assessment.course,
        status__in=[LearningEnrollment.Status.ACTIVE, LearningEnrollment.Status.COMPLETED],
    )
    if not learner_can_access_course(account, assessment.course):
        messages.error(request, "انتهى اشتراكك أو لا يشمل مادة هذه الدورة.")
        return redirect("learning_platform:subscriptions")

    submissions = list(
        LearningSubmission.objects.filter(enrollment=enrollment, assessment=assessment).order_by("-attempt_no")
    )
    passed = any(item.is_passed for item in submissions)
    attempts_remaining = max(assessment.max_attempts - len(submissions), 0)
    form = None
    if not passed and attempts_remaining > 0:
        if assessment.assessment_type == LearningAssessment.Type.QUIZ:
            form = LearningQuizAttemptForm(request.POST or None, assessment=assessment)
        else:
            form = LearningAssignmentSubmissionForm(request.POST or None)

    if request.method == "POST":
        if form is None:
            messages.error(request, "لا توجد محاولة جديدة متاحة لهذا التقييم.")
            return redirect(
                "learning_platform:assessment_detail",
                course_slug=assessment.course.slug,
                assessment_slug=assessment.slug,
            )
        if form.is_valid():
            try:
                if assessment.assessment_type == LearningAssessment.Type.QUIZ:
                    submission, enrollment = submit_quiz(
                        enrollment,
                        assessment,
                        form.answers_payload(),
                        ip_address=_client_ip(request),
                    )
                    if submission.is_passed:
                        messages.success(request, f"نجحت في الاختبار بعلامة {submission.score}.")
                    else:
                        messages.warning(request, f"تم التصحيح. علامتك {submission.score} ويمكنك إعادة المحاولة.")
                else:
                    submit_assignment(
                        enrollment,
                        assessment,
                        form.cleaned_data["answer_text"],
                        ip_address=_client_ip(request),
                    )
                    messages.success(request, "تم تسليم الواجب وهو الآن بانتظار تصحيح المدرّس.")
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return redirect(
                    "learning_platform:assessment_detail",
                    course_slug=assessment.course.slug,
                    assessment_slug=assessment.slug,
                )

    return render(
        request,
        "learning_platform/assessment_detail.html",
        _base_context(
            request,
            assessment=assessment,
            course=assessment.course,
            enrollment=enrollment,
            submissions=submissions,
            passed=passed,
            attempts_remaining=attempts_remaining,
            form=form,
        ),
    )


@never_cache
@learning_login_required
def certificate_detail(request, course_slug):
    account = _require_learner(request.learning_account)
    certificate = get_object_or_404(
        LearningCertificate.objects.select_related(
            "enrollment",
            "enrollment__learner",
            "enrollment__course",
            "enrollment__course__teacher",
        ),
        enrollment__learner=account,
        enrollment__course__slug=course_slug,
        revoked_at__isnull=True,
    )
    return render(
        request,
        "learning_platform/certificate.html",
        _base_context(request, certificate=certificate),
    )


def certificate_verify(request, code):
    certificate = LearningCertificate.objects.select_related(
        "enrollment",
        "enrollment__learner",
        "enrollment__course",
        "enrollment__course__teacher",
    ).filter(verification_code=code).first()
    return render(
        request,
        "learning_platform/certificate_verify.html",
        _base_context(request, certificate=certificate, verification_code=code),
    )


@never_cache
@require_http_methods(["GET", "POST"])
def password_reset_request(request):
    if get_learning_account(request) is not None:
        return redirect("learning_platform:dashboard")
    form = LearningPasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        account = LearningAccount.objects.filter(
            email__iexact=email,
            is_active=True,
            role__in=[LearningAccount.Role.LEARNER, LearningAccount.Role.TEACHER],
        ).first()
        if account is not None:
            now = timezone.now()
            ip_address = _client_ip(request)
            account_limited = LearningPasswordResetRequest.objects.filter(
                account=account,
                created_at__gte=now - timedelta(minutes=15),
            ).count() >= 3
            ip_limited = bool(ip_address) and LearningPasswordResetRequest.objects.filter(
                request_ip=ip_address,
                created_at__gte=now - timedelta(minutes=15),
            ).count() >= 5
            if not account_limited and not ip_limited:
                reset_request, raw_token = create_password_reset_request(
                    account,
                    ip_address=ip_address,
                )
                reset_url = request.build_absolute_uri(
                    reverse(
                        "learning_platform:password_reset_confirm",
                        kwargs={"token": raw_token},
                    )
                )
                deliver_password_reset_email(reset_request, raw_token, reset_url)
        return redirect("learning_platform:password_reset_done")
    return render(
        request,
        "learning_platform/password_reset_request.html",
        _base_context(request, form=form),
    )


def password_reset_done(request):
    return render(
        request,
        "learning_platform/password_reset_done.html",
        _base_context(request),
    )


@never_cache
@require_http_methods(["GET", "POST"])
def password_reset_confirm(request, token):
    reset_request = find_valid_password_reset(token)
    if reset_request is None:
        return render(
            request,
            "learning_platform/password_reset_confirm.html",
            _base_context(request, invalid_reset_link=True, form=None),
            status=400,
        )
    form = LearningPasswordResetConfirmForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_password_reset(
                reset_request,
                form.cleaned_data["password1"],
                ip_address=_client_ip(request),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "تم تغيير كلمة المرور. سجّل الدخول بكلمة المرور الجديدة.")
            return redirect("learning_platform:login")
    return render(
        request,
        "learning_platform/password_reset_confirm.html",
        _base_context(request, form=form, reset_account=reset_request.account),
    )


@never_cache
@learning_login_required
def notification_list(request):
    account = request.learning_account
    sync_account_notifications(account)
    notifications = account.notifications.all()
    notice_type = (request.GET.get("type") or "").strip()
    if notice_type in set(LearningNotification.Type.values):
        notifications = notifications.filter(notification_type=notice_type)
    unread_only = (request.GET.get("unread") or "").strip() == "1"
    if unread_only:
        notifications = notifications.filter(read_at__isnull=True)
    return render(
        request,
        "learning_platform/notifications.html",
        _base_context(
            request,
            notifications=notifications[:200],
            notice_type=notice_type,
            unread_only=unread_only,
            notification_types=LearningNotification.Type.choices,
        ),
    )


@learning_login_required
@require_POST
def notification_open(request, pk):
    notification = get_object_or_404(
        LearningNotification,
        pk=pk,
        recipient=request.learning_account,
    )
    notification.mark_read()
    LearningAuditEvent.objects.create(
        account=request.learning_account,
        action=LearningAuditEvent.Action.NOTIFICATION_READ,
        entity_type="learning_notification",
        entity_id=str(notification.pk),
        ip_address=_client_ip(request),
    )
    target = notification.action_url or reverse("learning_platform:notification_list")
    learning_prefix = reverse("learning_platform:landing")
    if not target.startswith(learning_prefix):
        target = reverse("learning_platform:notification_list")
    return redirect(target)


@learning_login_required
@require_POST
def notification_read_all(request):
    now = timezone.now()
    updated = request.learning_account.notifications.filter(read_at__isnull=True).update(read_at=now)
    if updated:
        messages.success(request, f"تم تعليم {updated} إشعار/إشعارات كمقروءة.")
    return redirect("learning_platform:notification_list")


@never_cache
@platform_manager_required
def manager_password_reset_requests(request):
    requests = LearningPasswordResetRequest.objects.select_related("account")
    status = (request.GET.get("status") or "").strip()
    if status == "open":
        requests = requests.filter(used_at__isnull=True, expires_at__gt=timezone.now())
    elif status in set(LearningPasswordResetRequest.DeliveryStatus.values):
        requests = requests.filter(delivery_status=status)
    return render(
        request,
        "learning_platform/manager_password_reset_requests.html",
        _manager_context(
            request,
            manager_section="accounts",
            reset_requests=requests[:250],
            status=status,
            delivery_statuses=LearningPasswordResetRequest.DeliveryStatus.choices,
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_account_password_reset(request, pk):
    account = get_object_or_404(
        LearningAccount,
        pk=pk,
        role__in=[LearningAccount.Role.LEARNER, LearningAccount.Role.TEACHER],
    )
    form = LearningManagerPasswordResetForm(request.POST or None)
    temporary_password = None
    if request.method == "POST" and form.is_valid():
        temporary_password = f"Opal-{secrets.token_urlsafe(10)}!9"
        reset_password_by_manager(
            account,
            temporary_password,
            manager_label=_manager_display_name(request.user),
            ip_address=_client_ip(request),
        )
        account.refresh_from_db()
    response = render(
        request,
        "learning_platform/manager_account_password_reset.html",
        _manager_context(
            request,
            manager_section="accounts",
            account=account,
            form=form,
            temporary_password=temporary_password,
        ),
    )
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


def _report_filter_values(request):
    today = timezone.localdate()
    data = request.GET or {
        "date_from": (today - timedelta(days=30)).isoformat(),
        "date_to": today.isoformat(),
    }
    form = LearningReportFilterForm(data)
    if form.is_valid():
        return form, form.cleaned_data
    return form, {
        "date_from": today - timedelta(days=30),
        "date_to": today,
        "subject": None,
        "course": None,
    }


def _filter_datetime_range(queryset, field_name, values):
    date_from = values.get("date_from")
    date_to = values.get("date_to")
    if date_from:
        queryset = queryset.filter(**{f"{field_name}__date__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{field_name}__date__lte": date_to})
    return queryset


def _report_querysets(values):
    subject = values.get("subject")
    course = values.get("course")
    accounts = LearningAccount.objects.exclude(role=LearningAccount.Role.MANAGER)
    enrollments = LearningEnrollment.objects.select_related(
        "learner", "course", "course__subject", "course__teacher"
    )
    submissions = LearningSubmission.objects.select_related(
        "assessment", "assessment__course", "enrollment", "enrollment__learner"
    )
    courses = LearningCourse.objects.select_related("subject", "teacher")
    if subject:
        enrollments = enrollments.filter(course__subject=subject)
        submissions = submissions.filter(assessment__course__subject=subject)
        courses = courses.filter(subject=subject)
    if course:
        enrollments = enrollments.filter(course=course)
        submissions = submissions.filter(assessment__course=course)
        courses = courses.filter(pk=course.pk)
    return (
        _filter_datetime_range(accounts, "created_at", values),
        _filter_datetime_range(enrollments, "enrolled_at", values),
        _filter_datetime_range(submissions, "submitted_at", values),
        courses.order_by("title"),
    )


@never_cache
@platform_manager_required
def manager_report_center(request):
    form, values = _report_filter_values(request)
    accounts, enrollments, submissions, courses = _report_querysets(values)
    enrollment_count = enrollments.count()
    completed_count = enrollments.filter(status=LearningEnrollment.Status.COMPLETED).count()
    graded_submissions = submissions.filter(status=LearningSubmission.Status.GRADED)
    graded_count = graded_submissions.count()
    passed_count = graded_submissions.filter(is_passed=True).count()
    now = timezone.now()
    active_cards = LearningSubscriptionCard.objects.filter(
        status=LearningSubscriptionCard.Status.REDEEMED,
        expires_at__gt=now,
    )
    selected_subject = values.get("subject")
    selected_course = values.get("course")
    access_subject = selected_course.subject if selected_course else selected_subject
    if access_subject:
        active_cards = active_cards.filter(
            models.Q(grants_all_subjects=True) | models.Q(subjects=access_subject)
        ).distinct()

    enrollment_stats = {
        row["course_id"]: row
        for row in enrollments.values("course_id").annotate(
            enrollments=Count("id"),
            completed=Count(
                "id",
                filter=models.Q(status=LearningEnrollment.Status.COMPLETED),
            ),
            average_progress=Avg("progress_percent"),
        )
    }
    submission_stats = {
        row["assessment__course_id"]: row
        for row in submissions.values("assessment__course_id").annotate(
            pending=Count(
                "id",
                filter=models.Q(status=LearningSubmission.Status.SUBMITTED),
            ),
            graded=Count(
                "id",
                filter=models.Q(status=LearningSubmission.Status.GRADED),
            ),
            passed=Count(
                "id",
                filter=models.Q(
                    status=LearningSubmission.Status.GRADED,
                    is_passed=True,
                ),
            ),
        )
    }
    course_rows = []
    for course in courses[:100]:
        enrollment_row = enrollment_stats.get(course.pk, {})
        submission_row = submission_stats.get(course.pk, {})
        course_total = enrollment_row.get("enrollments", 0)
        course_completed = enrollment_row.get("completed", 0)
        course_graded = submission_row.get("graded", 0)
        course_passed = submission_row.get("passed", 0)
        course_rows.append(
            {
                "course": course,
                "enrollments": course_total,
                "completed": course_completed,
                "completion_rate": round((course_completed * 100) / course_total) if course_total else 0,
                "average_progress": round(enrollment_row.get("average_progress") or 0),
                "pending_submissions": submission_row.get("pending", 0),
                "pass_rate": round((course_passed * 100) / course_graded) if course_graded else 0,
            }
        )

    expiring_cards = active_cards.filter(
        expires_at__lte=now + timedelta(days=7)
    ).select_related("redeemed_by").prefetch_related("subjects")[:100]
    recent_events = _filter_datetime_range(
        LearningAuditEvent.objects.select_related("account"),
        "created_at",
        values,
    )[:60]
    return render(
        request,
        "learning_platform/manager_reports.html",
        _manager_context(
            request,
            manager_section="reports",
            form=form,
            values=values,
            account_count=accounts.count(),
            enrollment_count=enrollment_count,
            completed_count=completed_count,
            completion_rate=round((completed_count * 100) / enrollment_count) if enrollment_count else 0,
            average_progress=round(enrollments.aggregate(value=Avg("progress_percent"))["value"] or 0),
            active_subscription_count=active_cards.count(),
            pending_submission_count=submissions.filter(
                status=LearningSubmission.Status.SUBMITTED
            ).count(),
            assessment_pass_rate=round((passed_count * 100) / graded_count) if graded_count else 0,
            course_rows=course_rows,
            expiring_cards=expiring_cards,
            recent_events=recent_events,
        ),
    )


def _csv_safe(value):
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@platform_manager_required
def manager_report_export_csv(request):
    _form, values = _report_filter_values(request)
    _accounts, enrollments, _submissions, _courses = _report_querysets(values)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="opal_learning_enrollments.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        [
            "اسم المتعلم",
            "البريد الإلكتروني",
            "الدورة",
            "المادة",
            "المدرّس",
            "الحالة",
            "نسبة الإنجاز",
            "تاريخ التسجيل",
            "آخر نشاط",
            "تاريخ الإكمال",
        ]
    )
    for enrollment in enrollments.order_by("-enrolled_at", "-id").iterator():
        writer.writerow(
            [
                _csv_safe(enrollment.learner.full_name),
                _csv_safe(enrollment.learner.email),
                _csv_safe(enrollment.course.title),
                _csv_safe(enrollment.course.subject.name),
                _csv_safe(enrollment.course.teacher.full_name),
                enrollment.get_status_display(),
                enrollment.progress_percent,
                timezone.localtime(enrollment.enrolled_at).strftime("%Y-%m-%d %H:%M"),
                timezone.localtime(enrollment.last_activity_at).strftime("%Y-%m-%d %H:%M")
                if enrollment.last_activity_at
                else "",
                timezone.localtime(enrollment.completed_at).strftime("%Y-%m-%d %H:%M")
                if enrollment.completed_at
                else "",
            ]
        )
    return response


@never_cache
@learning_login_required
def learner_ai_assistant(request):
    account = _require_learner(request.learning_account)
    governance = LearningAISettings.load()
    form = LearningAIQuestionForm(request.POST or None, account=account)
    if request.method == "POST" and form.is_valid():
        try:
            interaction, _draft = run_grounded_assistance(
                account,
                form.cleaned_data["course"],
                LearningAIInteraction.Type.LEARNER_QUESTION,
                form.cleaned_data["question"],
                ip_address=_client_ip(request),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "تم إعداد إجابة مرتبطة بمحتوى الدورة المنشور.")
            return redirect(f"{reverse('learning_platform:learner_ai_assistant')}?interaction={interaction.pk}")

    recent_interactions = account.ai_interactions.select_related("course").filter(
        interaction_type=LearningAIInteraction.Type.LEARNER_QUESTION,
    )[:20]
    selected = None
    selected_id = request.GET.get("interaction")
    if selected_id:
        selected = get_object_or_404(
            account.ai_interactions.select_related("course"),
            pk=selected_id,
            interaction_type=LearningAIInteraction.Type.LEARNER_QUESTION,
        )
    return render(
        request,
        "learning_platform/ai_assistant.html",
        _base_context(
            request,
            form=form,
            governance=governance,
            usage=account_ai_usage(account, ai_settings=governance),
            provider=provider_status(),
            recent_interactions=recent_interactions,
            selected_interaction=selected,
        ),
    )


@never_cache
@learning_login_required
def teacher_ai_workspace(request):
    account = request.learning_account
    if account.role != LearningAccount.Role.TEACHER:
        raise PermissionDenied("هذه الصفحة متاحة للمدرّس فقط.")
    governance = LearningAISettings.load()
    form = LearningTeacherAIForm(request.POST or None, account=account)
    if request.method == "POST" and form.is_valid():
        try:
            interaction, draft = run_grounded_assistance(
                account,
                form.cleaned_data["course"],
                form.cleaned_data["tool"],
                form.cleaned_data["prompt"],
                ip_address=_client_ip(request),
                draft_title=form.cleaned_data.get("title", ""),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "تم إنشاء المسودة وحفظها للمراجعة اليدوية دون نشرها.")
            return redirect(f"{reverse('learning_platform:teacher_ai_workspace')}?draft={draft.pk}")

    drafts = account.ai_drafts.select_related("course", "interaction")[:30]
    selected = None
    selected_id = request.GET.get("draft")
    if selected_id:
        selected = get_object_or_404(
            account.ai_drafts.select_related("course", "interaction"),
            pk=selected_id,
        )
    return render(
        request,
        "learning_platform/teacher_ai_workspace.html",
        _base_context(
            request,
            form=form,
            governance=governance,
            usage=account_ai_usage(account, ai_settings=governance),
            provider=provider_status(),
            drafts=drafts,
            selected_draft=selected,
        ),
    )


@learning_login_required
@require_POST
def teacher_ai_draft_status(request, pk):
    account = request.learning_account
    if account.role != LearningAccount.Role.TEACHER:
        raise PermissionDenied("هذه العملية متاحة للمدرّس فقط.")
    draft = get_object_or_404(
        LearningAIDraft.objects.select_related("course"),
        pk=pk,
        teacher=account,
        course__teacher=account,
    )
    action = request.POST.get("action")
    if action == "accept":
        draft.status = LearningAIDraft.Status.ACCEPTED
        draft.accepted_at = timezone.now()
        message = "تم اعتماد المسودة للمراجعة اليدوية. لم تُنشر في الدورة."
    elif action == "discard":
        draft.status = LearningAIDraft.Status.DISCARDED
        draft.accepted_at = None
        message = "تم استبعاد المسودة."
    elif action == "restore":
        draft.status = LearningAIDraft.Status.DRAFT
        draft.accepted_at = None
        message = "أعيدت المسودة إلى حالة المراجعة."
    else:
        raise ValidationError("إجراء المسودة غير معتمد.")
    draft.save(update_fields=["status", "accepted_at", "updated_at"])
    LearningAuditEvent.objects.create(
        account=account,
        action=LearningAuditEvent.Action.AI_DRAFT_REVIEWED,
        entity_type="learning_ai_draft",
        entity_id=str(draft.pk),
        ip_address=_client_ip(request),
        metadata={"course_id": draft.course_id, "status": draft.status},
    )
    messages.success(request, message)
    return redirect(f"{reverse('learning_platform:teacher_ai_workspace')}?draft={draft.pk}")


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_ai_center(request):
    governance = LearningAISettings.load()
    form = LearningAISettingsForm(request.POST or None, instance=governance)
    if request.method == "POST" and form.is_valid():
        governance = form.save()
        _record_manager_event(
            request,
            action=LearningAuditEvent.Action.AI_SETTINGS_UPDATED,
            entity_type="learning_ai_settings",
            entity_id=governance.pk,
            metadata={
                "assistant_enabled": governance.assistant_enabled,
                "teacher_tools_enabled": governance.teacher_tools_enabled,
                "external_provider_enabled": governance.external_provider_enabled,
                "local_reference_enabled": governance.local_reference_enabled,
            },
        )
        messages.success(request, "تم حفظ إعدادات المساعد التعليمي.")
        return redirect("learning_platform:manager_ai_center")

    interactions = LearningAIInteraction.objects.select_related("account", "course")[:60]
    drafts = LearningAIDraft.objects.select_related("teacher", "course")[:30]
    today = timezone.localdate()
    today_interactions = LearningAIInteraction.objects.filter(created_at__date=today)
    stats = {
        "today": today_interactions.count(),
        "external": today_interactions.filter(provider_mode="external").count(),
        "local": today_interactions.filter(provider_mode="local_reference").count(),
        "errors": today_interactions.filter(status=LearningAIInteraction.Status.PROVIDER_ERROR).count(),
        "drafts": LearningAIDraft.objects.filter(status=LearningAIDraft.Status.DRAFT).count(),
    }
    return render(
        request,
        "learning_platform/manager_ai_center.html",
        _manager_context(
            request,
            manager_section="ai",
            form=form,
            governance=governance,
            provider=provider_status(),
            interactions=interactions,
            drafts=drafts,
            stats=stats,
        ),
    )


@never_cache
@require_http_methods(["GET"])
def email_verify(request, token):
    verification = find_valid_email_verification(token)
    if verification is None:
        return render(
            request,
            "learning_platform/email_verification.html",
            _base_context(request, invalid_verification_link=True),
            status=400,
        )
    try:
        account = complete_email_verification(verification, ip_address=_client_ip(request))
    except ValidationError:
        return render(
            request,
            "learning_platform/email_verification.html",
            _base_context(request, invalid_verification_link=True),
            status=400,
        )
    messages.success(request, "تم توثيق البريد الإلكتروني بنجاح.")
    return render(
        request,
        "learning_platform/email_verification.html",
        _base_context(request, verified_account=account),
    )


@learning_login_required
@require_POST
def email_verification_resend(request):
    account = request.learning_account
    if account.email_verified_at is not None:
        messages.info(request, "البريد الإلكتروني موثق بالفعل.")
        return redirect("learning_platform:dashboard")
    try:
        consume_rate_limit(
            "email_verification_resend",
            f"account:{account.pk}",
            limit=3,
            window_seconds=3600,
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("learning_platform:dashboard")
    verification, raw_token = create_email_verification_request(
        account,
        ip_address=_client_ip(request),
    )
    verify_url = request.build_absolute_uri(
        reverse("learning_platform:email_verify", kwargs={"token": raw_token})
    )
    if deliver_email_verification(verification, raw_token, verify_url):
        messages.success(request, "أُرسل رابط توثيق جديد إلى بريدك.")
    else:
        messages.error(request, "تعذر إرسال الرابط. راجع إدارة المنصة.")
    return redirect("learning_platform:dashboard")


@platform_manager_required
@require_POST
def manager_account_verify_email(request, pk):
    account = get_object_or_404(
        LearningAccount,
        pk=pk,
        role__in=[LearningAccount.Role.LEARNER, LearningAccount.Role.TEACHER],
    )
    if account.email_verified_at is None:
        account.email_verified_at = timezone.now()
        account.save(update_fields=["email_verified_at", "updated_at"])
        _record_manager_event(
            request,
            action="manager_email_verified",
            entity_type="learning_account",
            entity_id=account.pk,
            account=account,
        )
        messages.success(request, "تم توثيق البريد إداريًا.")
    return redirect("learning_platform:manager_account_list")


@never_cache
@platform_manager_required
def manager_plan_list(request):
    plans = LearningSubscriptionPlan.objects.prefetch_related("subjects").all()
    return render(
        request,
        "learning_platform/manager_plan_list.html",
        _manager_context(
            request,
            manager_section="payments",
            plans=plans,
            payment_status=payment_configuration_status(),
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_plan_create(request):
    form = LearningSubscriptionPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        plan = form.save()
        _record_manager_event(
            request,
            action="manager_subscription_plan_saved",
            entity_type="learning_subscription_plan",
            entity_id=plan.pk,
            metadata={"created": True, "price": str(plan.price), "currency": plan.currency},
        )
        messages.success(request, "تم إنشاء خطة الاشتراك.")
        return redirect("learning_platform:manager_plan_list")
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="payments",
            form=form,
            page_title="إنشاء خطة اشتراك",
            page_intro="حدد السعر والمدة والمواد التي تمنحها الخطة.",
            submit_label="حفظ الخطة",
            cancel_url=reverse("learning_platform:manager_plan_list"),
        ),
    )


@never_cache
@platform_manager_required
@require_http_methods(["GET", "POST"])
def manager_plan_update(request, pk):
    plan = get_object_or_404(LearningSubscriptionPlan, pk=pk)
    form = LearningSubscriptionPlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        plan = form.save()
        _record_manager_event(
            request,
            action="manager_subscription_plan_saved",
            entity_type="learning_subscription_plan",
            entity_id=plan.pk,
            metadata={"created": False, "price": str(plan.price), "currency": plan.currency},
        )
        messages.success(request, "تم تحديث خطة الاشتراك.")
        return redirect("learning_platform:manager_plan_list")
    return render(
        request,
        "learning_platform/manager_form.html",
        _manager_context(
            request,
            manager_section="payments",
            form=form,
            page_title=f"تعديل خطة: {plan.name}",
            page_intro="لا يتغير مبلغ الطلبات القديمة عند تعديل سعر الخطة.",
            submit_label="حفظ التعديلات",
            cancel_url=reverse("learning_platform:manager_plan_list"),
        ),
    )


@never_cache
@platform_manager_required
def manager_payment_list(request):
    orders = LearningPaymentOrder.objects.select_related(
        "learner", "plan", "subscription_card"
    )
    status = (request.GET.get("status") or "").strip()
    query = (request.GET.get("q") or "").strip()
    if status in set(LearningPaymentOrder.Status.values):
        orders = orders.filter(status=status)
    if query:
        orders = orders.filter(
            models.Q(public_id__icontains=query)
            | models.Q(learner__full_name__icontains=query)
            | models.Q(learner__email__icontains=query)
            | models.Q(provider_reference__icontains=query)
        )
    return render(
        request,
        "learning_platform/manager_payment_list.html",
        _manager_context(
            request,
            manager_section="payments",
            orders=orders[:500],
            statuses=LearningPaymentOrder.Status.choices,
            status=status,
            query=query,
            payment_status=payment_configuration_status(),
        ),
    )


@platform_manager_required
@require_POST
def manager_payment_mark_paid(request, pk):
    order = get_object_or_404(LearningPaymentOrder, pk=pk)
    payment_status = payment_configuration_status()
    if not payment_status["manual_allowed"]:
        messages.error(request, "اعتماد الدفع اليدوي معطل في إعدادات البيئة.")
        return redirect("learning_platform:manager_payment_list")
    if bool(getattr(settings, "OPAL_LEARNING_PUBLIC_LAUNCH", False)) and order.provider != "manual":
        messages.error(request, "طلبات المزود الخارجي تُعتمد من webhook الموقع فقط ولا يجوز تجاوزها يدويًا.")
        return redirect("learning_platform:manager_payment_list")
    try:
        mark_order_paid(
            order,
            provider_reference=(request.POST.get("reference") or "manual").strip(),
            manager_label=_manager_display_name(request.user),
        )
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    else:
        messages.success(request, "تم اعتماد الدفع وتفعيل الاشتراك.")
    return redirect("learning_platform:manager_payment_list")


@platform_manager_required
@require_POST
def manager_payment_cancel(request, pk):
    order = get_object_or_404(LearningPaymentOrder, pk=pk)
    try:
        cancel_payment_order(order, reason="أُلغي من إدارة المنصة.")
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    else:
        messages.success(request, "تم إلغاء طلب الدفع.")
    return redirect("learning_platform:manager_payment_list")


@never_cache
@learning_login_required
@require_http_methods(["GET", "POST"])
def payment_checkout(request, plan_pk=None):
    account = _require_learner(request.learning_account)
    if email_verification_required(account):
        messages.error(request, "وثّق بريدك الإلكتروني قبل إنشاء طلب دفع.")
        return redirect("learning_platform:dashboard")
    initial = {"plan": plan_pk} if plan_pk else None
    form = LearningPaymentCheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            consume_rate_limit(
                "payment_checkout",
                f"account:{account.pk}",
                limit=10,
                window_seconds=3600,
            )
            order, _created = create_payment_order(
                account,
                form.cleaned_data["plan"],
                idempotency_key=(request.POST.get("idempotency_key") or secrets.token_urlsafe(24)),
                metadata={"ip_address": _client_ip(request)},
            )
            status = payment_configuration_status()
            if status["external"] and status["configured"]:
                order = initiate_external_checkout(
                    order,
                    return_url=request.build_absolute_uri(
                        reverse("learning_platform:payment_return", kwargs={"public_id": order.public_id})
                    ),
                    webhook_url=request.build_absolute_uri(reverse("learning_platform:payment_webhook")),
                )
                return redirect(order.checkout_url)
            if not status["configured"]:
                raise ValidationError("الدفع غير مهيأ حاليًا. لم يتم خصم أي مبلغ.")
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "تم إنشاء طلب الدفع. ستراجعه الإدارة لتفعيل الاشتراك.")
            return redirect("learning_platform:payment_return", public_id=order.public_id)
    return render(
        request,
        "learning_platform/payment_checkout.html",
        _base_context(
            request,
            form=form,
            payment_status=payment_configuration_status(),
            idempotency_key=secrets.token_urlsafe(24),
        ),
    )


@never_cache
@learning_login_required
def payment_return(request, public_id):
    order = get_object_or_404(
        LearningPaymentOrder.objects.select_related("plan", "subscription_card"),
        public_id=public_id,
        learner=request.learning_account,
    )
    return render(
        request,
        "learning_platform/payment_status.html",
        _base_context(request, order=order),
    )


@csrf_exempt
@require_POST
def payment_webhook(request):
    signature = request.META.get("HTTP_X_OPAL_SIGNATURE") or request.META.get("HTTP_X_SIGNATURE") or ""
    try:
        order, event, created = process_payment_webhook(request.body, signature)
    except ValidationError as exc:
        return JsonResponse(
            {"ok": False, "error": " ".join(exc.messages)},
            status=400,
            json_dumps_params={"ensure_ascii": False},
        )
    return JsonResponse(
        {
            "ok": True,
            "created": created,
            "order": order.public_id,
            "status": order.status,
            "event": event.provider_event_id,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@never_cache
@platform_manager_required
def manager_readiness_center(request):
    readiness = collect_learning_readiness_checks(include_migrations=True)
    return render(
        request,
        "learning_platform/manager_readiness.html",
        _manager_context(
            request,
            manager_section="readiness",
            readiness=readiness,
        ),
    )


def health(request):
    readiness = collect_learning_readiness_checks(include_migrations=False)
    status_code = 200 if readiness["overall"] != "not_ready" else 503
    return JsonResponse(
        {
            "service": "opal-learning-platform",
            "status": readiness["overall"],
            "blocking_failures": readiness["blocking_failures"],
            "warnings": readiness["warnings"],
            "time": timezone.now().isoformat(),
        },
        status=status_code,
        json_dumps_params={"ensure_ascii": False},
    )


def terms(request):
    return render(request, "learning_platform/terms.html", _base_context(request))


def privacy(request):
    return render(request, "learning_platform/privacy.html", _base_context(request))


def mobile_manifest(request):
    response = render(
        request,
        "learning_platform/manifest.webmanifest",
        content_type="application/manifest+json",
    )
    response["Cache-Control"] = "public, max-age=3600"
    return response


def mobile_service_worker(request):
    response = render(
        request,
        "learning_platform/service-worker.js",
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/learning/"
    response["Cache-Control"] = "no-cache"
    return response
