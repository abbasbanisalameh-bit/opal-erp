from __future__ import annotations

import json
import secrets
from datetime import date, timedelta
from functools import wraps

from django.apps import apps
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.workflow import get_user_profile, role_code
from learning_platform.security_services import consume_rate_limit

from .models import AuditLog, SystemMobileAPIToken


ALL_MODULES = (
    "dashboard",
    "students",
    "guardians",
    "teachers",
    "timetable",
    "attendance",
    "finance",
    "exams",
    "documents",
    "announcements",
)
ROLE_MODULES = {
    "super_admin": ALL_MODULES,
    "school_owner": ALL_MODULES,
    "principal": ALL_MODULES,
    "accountant": ("dashboard", "students", "guardians", "finance", "announcements"),
    "secretary": ("dashboard", "students", "guardians", "teachers", "timetable", "documents", "announcements"),
    "teacher": ("dashboard", "timetable", "attendance", "exams", "announcements"),
}


def _client_ip(request):
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or "unknown"


def _json_body(request):
    try:
        return json.loads((request.body or b"{}").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("JSON غير صالح.") from exc


def _success(data=None, *, status=200):
    response = JsonResponse(
        {"ok": True, "data": data if data is not None else {}},
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )
    response["Cache-Control"] = "no-store"
    return response


def _error(message, *, status=400, code="invalid_request"):
    response = JsonResponse(
        {"ok": False, "error": {"code": code, "message": str(message)}},
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )
    response["Cache-Control"] = "no-store"
    return response


def _token_hash(raw_token):
    return salted_hmac(
        "opal-system-mobile-api-token",
        raw_token,
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def _user_full_name(user):
    name = (user.get_full_name() or "").strip()
    profile = get_user_profile(user)
    if not name and profile is not None:
        name = (profile.full_name or "").strip()
    teacher = getattr(user, "teacher_profile", None)
    if not name and teacher is not None:
        name = (teacher.full_name or "").strip()
    return name or user.get_username()


def _allowed_modules(user):
    if user.is_superuser:
        return list(ALL_MODULES)
    code = role_code(user)
    if code in ROLE_MODULES:
        return list(ROLE_MODULES[code])
    if user.is_staff:
        return list(ALL_MODULES)
    teacher = getattr(user, "teacher_profile", None)
    if teacher is not None and teacher.is_active:
        return list(ROLE_MODULES["teacher"])
    return []


def _scope(user):
    profile = get_user_profile(user)
    teacher = getattr(user, "teacher_profile", None)
    school_id = getattr(profile, "school_id", None) if profile is not None else None
    branch_id = getattr(profile, "branch_id", None) if profile is not None else None
    if teacher is not None and teacher.is_active:
        school_id = school_id or teacher.school_id
        branch_id = branch_id or teacher.branch_id
    return school_id, branch_id


def _current_year(user):
    AcademicYear = apps.get_model("core", "AcademicYear")
    school_id, _ = _scope(user)
    qs = AcademicYear.objects.filter(is_current=True)
    if school_id:
        qs = qs.filter(school_id=school_id)
    return qs.select_related("school").order_by("-start_date").first()


def _current_semester(year):
    if year is None:
        return None
    return year.semesters.filter(is_current=True).first()


def _module_required(module):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if module not in request.opal_mobile_modules:
                return _error("لا يملك حسابك صلاحية هذه الوحدة في تطبيق النظام.", status=403, code="permission_denied")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


@transaction.atomic
def _issue_token(user, *, device_name=""):
    raw = "oer_" + secrets.token_urlsafe(36)
    days = int(getattr(settings, "OPAL_SYSTEM_MOBILE_TOKEN_DAYS", 30))
    row = SystemMobileAPIToken.objects.create(
        user=user,
        token_hash=_token_hash(raw),
        token_prefix=raw[:12],
        device_name=(device_name or "OPAL ERP Android")[:120],
        expires_at=timezone.now() + timedelta(days=days),
    )
    return row, raw


def _find_token(raw):
    if not raw or not raw.startswith("oer_"):
        return None
    wanted = _token_hash(raw)
    token = (
        SystemMobileAPIToken.objects.select_related("user", "user__profile", "user__profile__role")
        .filter(
            token_hash=wanted,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
            user__is_active=True,
        )
        .first()
    )
    if token is None or not constant_time_compare(token.token_hash, wanted):
        return None
    return token


def _authorization_token(request):
    header = (request.META.get("HTTP_AUTHORIZATION") or "").strip()
    if not header.lower().startswith("bearer "):
        return ""
    return header.split(" ", 1)[1].strip()


def mobile_auth_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        token = _find_token(_authorization_token(request))
        if token is None:
            return _error("جلسة تطبيق النظام منتهية أو غير صالحة.", status=401, code="invalid_token")
        modules = _allowed_modules(token.user)
        if not modules:
            return _error("هذا الحساب غير مخول لاستخدام تطبيق النظام.", status=403, code="system_mobile_access_denied")
        try:
            consume_rate_limit(
                "system_mobile_api",
                f"token:{token.pk}",
                limit=int(getattr(settings, "OPAL_SYSTEM_MOBILE_API_RATE_LIMIT", 240)),
                window_seconds=60,
            )
        except ValidationError:
            return _error("عدد الطلبات كبير. حاول بعد قليل.", status=429, code="rate_limited")
        SystemMobileAPIToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
        request.opal_mobile_token = token
        request.opal_mobile_user = token.user
        request.opal_mobile_modules = modules
        try:
            response = view_func(request, *args, **kwargs)
        except ValidationError as exc:
            message = " ".join(exc.messages) if getattr(exc, "messages", None) else str(exc)
            response = _error(message, status=400, code="validation_error")
        response["Cache-Control"] = "no-store"
        return response

    return wrapped


def _account_payload(user):
    profile = get_user_profile(user)
    teacher = getattr(user, "teacher_profile", None)
    code = role_code(user) or ("teacher" if teacher is not None and teacher.is_active else "")
    school = getattr(profile, "school", None) if profile is not None else None
    branch = getattr(profile, "branch", None) if profile is not None else None
    if teacher is not None and teacher.is_active:
        school = school or teacher.school
        branch = branch or teacher.branch
    return {
        "id": user.pk,
        "username": user.get_username(),
        "full_name": _user_full_name(user),
        "role": code,
        "role_label": getattr(getattr(profile, "role", None), "name", "") or ("معلم" if code == "teacher" else "إدارة"),
        "school": {"id": school.pk, "name": school.name} if school else None,
        "branch": {"id": branch.pk, "name": branch.name} if branch else None,
        "modules": _allowed_modules(user),
    }


@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
    try:
        payload = _json_body(request)
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        if not username or not password:
            return _error("اسم المستخدم وكلمة المرور مطلوبان.", code="credentials_required")
        try:
            consume_rate_limit(
                "system_mobile_login",
                f"{_client_ip(request)}:{username.lower()}",
                limit=int(getattr(settings, "OPAL_SYSTEM_MOBILE_LOGIN_RATE_LIMIT", 10)),
                window_seconds=300,
            )
        except ValidationError:
            return _error("تم تجاوز عدد محاولات الدخول. حاول بعد قليل.", status=429, code="rate_limited")
        user = authenticate(request=request, username=username, password=password)
        if user is None or not user.is_active:
            return _error("اسم المستخدم أو كلمة المرور غير صحيحة.", status=401, code="invalid_credentials")
        modules = _allowed_modules(user)
        if not modules:
            return _error("هذا الحساب غير مخول لاستخدام تطبيق نظام أوبال.", status=403, code="system_mobile_access_denied")
        token, raw = _issue_token(user, device_name=str(payload.get("device_name") or ""))
        AuditLog.objects.create(
            user=user,
            school=getattr(get_user_profile(user), "school", None),
            branch=getattr(get_user_profile(user), "branch", None),
            action="login",
            model_name="system_mobile",
            object_id=str(token.pk),
            description="تسجيل دخول إلى تطبيق OPAL ERP Android",
            ip_address=_client_ip(request) if _client_ip(request) != "unknown" else None,
        )
        return _success(
            {
                "token": raw,
                "token_type": "Bearer",
                "expires_at": token.expires_at.isoformat(),
                "account": _account_payload(user),
            },
            status=201,
        )
    except ValidationError as exc:
        message = " ".join(exc.messages) if getattr(exc, "messages", None) else str(exc)
        return _error(message)


@csrf_exempt
@require_http_methods(["POST"])
@mobile_auth_required
def api_logout(request):
    token = request.opal_mobile_token
    SystemMobileAPIToken.objects.filter(pk=token.pk, revoked_at__isnull=True).update(revoked_at=timezone.now())
    AuditLog.objects.create(
        user=request.opal_mobile_user,
        school=getattr(get_user_profile(request.opal_mobile_user), "school", None),
        branch=getattr(get_user_profile(request.opal_mobile_user), "branch", None),
        action="logout",
        model_name="system_mobile",
        object_id=str(token.pk),
        description="تسجيل خروج من تطبيق OPAL ERP Android",
        ip_address=_client_ip(request) if _client_ip(request) != "unknown" else None,
    )
    return _success({"logged_out": True})


@require_http_methods(["GET"])
@mobile_auth_required
def api_me(request):
    return _success(_account_payload(request.opal_mobile_user))


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("dashboard")
def api_dashboard(request):
    user = request.opal_mobile_user
    year = _current_year(user)
    semester = _current_semester(year)
    school_id, branch_id = _scope(user)

    Student = apps.get_model("students", "Student")
    Family = apps.get_model("parent_portal", "Family")
    Teacher = apps.get_model("teachers", "Teacher")
    Attendance = apps.get_model("attendance_v2", "Attendance")
    StudentInvoice = apps.get_model("accounting", "StudentInvoice")
    Announcement = apps.get_model("announcements", "Announcement")

    students = Student.objects.filter(is_active=True)
    if year is not None:
        students = students.filter(enrollments__academic_year=year, enrollments__status="active")
    if branch_id:
        students = students.filter(enrollments__section__branch_id=branch_id)
    students = students.distinct()

    families = Family.objects.filter(is_active=True, merged_into__isnull=True)
    teachers = Teacher.objects.filter(is_active=True)
    if school_id:
        families = families.filter(school_id=school_id)
        teachers = teachers.filter(school_id=school_id)
    if branch_id:
        teachers = teachers.filter(branch_id=branch_id)

    attendance = Attendance.objects.filter(date=timezone.localdate())
    invoices = StudentInvoice.objects.exclude(status="cancelled")
    if year is not None:
        attendance = attendance.filter(academic_year=year)
        invoices = invoices.filter(academic_year=year)
    if branch_id:
        attendance = attendance.filter(section__branch_id=branch_id)
        invoices = invoices.filter(student__enrollments__academic_year=year, student__enrollments__section__branch_id=branch_id)

    teacher = getattr(user, "teacher_profile", None)
    if role_code(user) == "teacher" or (teacher is not None and not user.is_staff and not user.is_superuser):
        assignment_ids = apps.get_model("teachers", "TeacherAssignment").objects.filter(
            teacher=teacher, is_active=True, academic_year=year
        ).values_list("section_id", flat=True)
        attendance = attendance.filter(section_id__in=assignment_ids)

    return _success(
        {
            "account": _account_payload(user),
            "academic_year": year.name if year else "",
            "semester": semester.name if semester else "",
            "today": timezone.localdate().isoformat(),
            "stats": {
                "students": students.count() if "students" in request.opal_mobile_modules else None,
                "guardians": families.count() if "guardians" in request.opal_mobile_modules else None,
                "teachers": teachers.count() if "teachers" in request.opal_mobile_modules else None,
                "today_attendance_events": attendance.count() if "attendance" in request.opal_mobile_modules else None,
                "open_invoices": invoices.filter(status__in=["open", "partial"]).count() if "finance" in request.opal_mobile_modules else None,
                "active_announcements": Announcement.objects.filter(is_active=True).count(),
            },
            "modules": request.opal_mobile_modules,
        }
    )


def _query(request):
    return (request.GET.get("q") or "").strip()


def _limit(request, default=100, maximum=200):
    try:
        return min(max(int(request.GET.get("limit") or default), 1), maximum)
    except (TypeError, ValueError):
        return default


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("students")
def api_students(request):
    Student = apps.get_model("students", "Student")
    Enrollment = apps.get_model("academics", "Enrollment")
    user = request.opal_mobile_user
    year = _current_year(user)
    school_id, branch_id = _scope(user)
    qs = Student.objects.filter(is_active=True)
    if year is not None:
        qs = qs.filter(enrollments__academic_year=year, enrollments__status="active")
    if branch_id:
        qs = qs.filter(enrollments__section__branch_id=branch_id)
    q = _query(request)
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(student_number__icontains=q) | Q(national_id__icontains=q))
    items = []
    for student in qs.distinct().order_by("full_name")[: _limit(request)]:
        enrollment = None
        if year is not None:
            enrollment = Enrollment.objects.select_related("grade", "section").filter(student=student, academic_year=year).first()
        class_name = ""
        if enrollment is not None:
            class_name = enrollment.grade.name
            if enrollment.section_id:
                class_name = f"{class_name} · {enrollment.section.name}"
        items.append({
            "id": student.pk,
            "title": student.full_name,
            "subtitle": f"{student.student_number} · {class_name}".strip(" ·"),
            "status": student.get_status_display(),
            "student_number": student.student_number,
            "class_name": class_name,
        })
    return _success({"items": items, "count": len(items), "school_id": school_id})


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("guardians")
def api_guardians(request):
    Family = apps.get_model("parent_portal", "Family")
    school_id, _ = _scope(request.opal_mobile_user)
    qs = Family.objects.filter(is_active=True, merged_into__isnull=True).annotate(active_children=Count("children", filter=Q(children__is_active=True)))
    if school_id:
        qs = qs.filter(school_id=school_id)
    q = _query(request)
    if q:
        qs = qs.filter(Q(guardian_name__icontains=q) | Q(phone__icontains=q) | Q(identity_number__icontains=q) | Q(family_code__icontains=q))
    items = [{
        "id": item.pk,
        "title": item.guardian_name,
        "subtitle": f"{item.phone or 'دون هاتف'} · {item.active_children} أبناء",
        "status": item.family_code or "",
    } for item in qs.order_by("guardian_name")[: _limit(request)]]
    return _success({"items": items, "count": len(items)})


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("teachers")
def api_teachers(request):
    Teacher = apps.get_model("teachers", "Teacher")
    school_id, branch_id = _scope(request.opal_mobile_user)
    qs = Teacher.objects.filter(is_active=True)
    if school_id:
        qs = qs.filter(school_id=school_id)
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    q = _query(request)
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(employee_number__icontains=q) | Q(phone__icontains=q) | Q(specialization__icontains=q))
    items = [{
        "id": item.pk,
        "title": item.full_name,
        "subtitle": f"{item.employee_number} · {item.specialization or 'معلم'}",
        "status": item.phone or "",
    } for item in qs.order_by("full_name")[: _limit(request)]]
    return _success({"items": items, "count": len(items)})


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("timetable")
def api_timetable(request):
    TimetableEntry = apps.get_model("timetable", "TimetableEntry")
    year = _current_year(request.opal_mobile_user)
    _, branch_id = _scope(request.opal_mobile_user)
    qs = TimetableEntry.objects.filter(is_active=True).select_related("section", "section__grade", "subject", "teacher", "time_slot")
    if year is not None:
        qs = qs.filter(academic_year=year)
    if branch_id:
        qs = qs.filter(section__branch_id=branch_id)
    teacher = getattr(request.opal_mobile_user, "teacher_profile", None)
    if role_code(request.opal_mobile_user) == "teacher" and teacher is not None:
        qs = qs.filter(teacher=teacher)
    day = (request.GET.get("day") or "").strip().lower()
    if day:
        qs = qs.filter(day=day)
    items = []
    for item in qs[: _limit(request, default=150, maximum=300)]:
        items.append({
            "id": item.pk,
            "title": f"{item.subject.name} · {item.section}",
            "subtitle": f"{item.get_day_display()} · {item.time_slot.start_time.strftime('%H:%M')}–{item.time_slot.end_time.strftime('%H:%M')}",
            "status": item.teacher.full_name if item.teacher else "معلم غائب",
            "day": item.day,
        })
    return _success({"items": items, "count": len(items)})


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("attendance")
def api_attendance(request):
    Attendance = apps.get_model("attendance_v2", "Attendance")
    TeacherAssignment = apps.get_model("teachers", "TeacherAssignment")
    year = _current_year(request.opal_mobile_user)
    _, branch_id = _scope(request.opal_mobile_user)
    date_text = (request.GET.get("date") or "").strip()
    try:
        target_date = date.fromisoformat(date_text) if date_text else timezone.localdate()
    except ValueError:
        return _error("صيغة التاريخ غير صحيحة.", code="invalid_date")
    qs = Attendance.objects.filter(date=target_date).select_related("student", "grade", "section")
    if year is not None:
        qs = qs.filter(academic_year=year)
    if branch_id:
        qs = qs.filter(section__branch_id=branch_id)
    teacher = getattr(request.opal_mobile_user, "teacher_profile", None)
    if role_code(request.opal_mobile_user) == "teacher" and teacher is not None:
        sections = TeacherAssignment.objects.filter(teacher=teacher, academic_year=year, is_active=True).values_list("section_id", flat=True)
        qs = qs.filter(section_id__in=sections)
    items = [{
        "id": item.pk,
        "title": item.student.full_name,
        "subtitle": f"{item.grade.name if item.grade else ''} · {item.section.name if item.section else ''}".strip(" ·"),
        "status": item.get_status_display(),
    } for item in qs[: _limit(request, default=150, maximum=300)]]
    return _success({"items": items, "count": len(items), "date": target_date.isoformat()})


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("finance")
def api_finance(request):
    StudentInvoice = apps.get_model("accounting", "StudentInvoice")
    year = _current_year(request.opal_mobile_user)
    _, branch_id = _scope(request.opal_mobile_user)
    qs = StudentInvoice.objects.exclude(status="cancelled").select_related("student", "fee_category").prefetch_related("payments")
    if year is not None:
        qs = qs.filter(academic_year=year)
    if branch_id and year is not None:
        qs = qs.filter(student__enrollments__academic_year=year, student__enrollments__section__branch_id=branch_id).distinct()
    q = _query(request)
    if q:
        qs = qs.filter(Q(student__full_name__icontains=q) | Q(student__student_number__icontains=q) | Q(invoice_number__icontains=q))
    selected = list(qs[: _limit(request, default=100, maximum=200)])
    items = []
    total_remaining = 0
    for invoice in selected:
        remaining = invoice.remaining
        total_remaining += remaining
        items.append({
            "id": invoice.pk,
            "title": invoice.student.full_name,
            "subtitle": f"{invoice.invoice_number} · {invoice.fee_category.name}",
            "status": invoice.get_status_display(),
            "amount": str(invoice.net_amount),
            "paid": str(invoice.total_paid),
            "remaining": str(remaining),
        })
    return _success({"items": items, "count": len(items), "total_remaining": str(total_remaining)})


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("exams")
def api_exams(request):
    Exam = apps.get_model("exams", "Exam")
    year = _current_year(request.opal_mobile_user)
    _, branch_id = _scope(request.opal_mobile_user)
    qs = Exam.objects.filter(is_active=True).select_related("grade", "section", "subject", "semester", "teacher_assignment", "teacher_assignment__teacher")
    if year is not None:
        qs = qs.filter(academic_year=year)
    if branch_id:
        qs = qs.filter(section__branch_id=branch_id)
    teacher = getattr(request.opal_mobile_user, "teacher_profile", None)
    if role_code(request.opal_mobile_user) == "teacher" and teacher is not None:
        qs = qs.filter(teacher_assignment__teacher=teacher)
    items = [{
        "id": item.pk,
        "title": item.name or item.get_exam_type_display(),
        "subtitle": f"{item.subject.name} · {item.section or item.grade}",
        "status": item.get_status_display(),
    } for item in qs[: _limit(request, default=120, maximum=240)]]
    return _success({"items": items, "count": len(items)})


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("documents")
def api_documents(request):
    IssuedDocument = apps.get_model("documents", "IssuedDocument")
    year = _current_year(request.opal_mobile_user)
    school_id, branch_id = _scope(request.opal_mobile_user)
    qs = IssuedDocument.objects.select_related("student", "teacher", "guardian", "template")
    if school_id and year is not None:
        qs = qs.filter(
            Q(student__enrollments__academic_year=year)
            | Q(teacher__school_id=school_id)
            | Q(guardian__school_id=school_id)
        ).distinct()
    if branch_id and year is not None:
        qs = qs.filter(
            Q(student__enrollments__academic_year=year, student__enrollments__section__branch_id=branch_id)
            | Q(teacher__branch_id=branch_id)
            | Q(guardian__school_id=school_id)
        ).distinct()
    items = []
    for item in qs[: _limit(request)]:
        owner = item.student or item.teacher or item.guardian
        items.append({
            "id": item.pk,
            "title": item.title,
            "subtitle": f"{item.document_number} · {owner or item.applicant_name}",
            "status": item.get_status_display(),
        })
    return _success({"items": items, "count": len(items)})


@require_http_methods(["GET"])
@mobile_auth_required
@_module_required("announcements")
def api_announcements(request):
    Announcement = apps.get_model("announcements", "Announcement")
    qs = Announcement.objects.filter(is_active=True)
    items = [{
        "id": item.pk,
        "title": item.title,
        "subtitle": item.message,
        "status": item.get_announcement_type_display(),
        "type": item.announcement_type,
    } for item in qs[: _limit(request)]]
    return _success({"items": items, "count": len(items)})
