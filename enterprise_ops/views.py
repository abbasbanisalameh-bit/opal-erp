import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounting.models import StudentInvoice, StudentPayment
from academics.models import Enrollment
from admissions.financial_services import student_remaining, student_total_fees, student_total_paid
from admissions.services import active_school
from attendance_v2.models import Attendance
from core.models import AuditLog
from documents.models import IssuedDocument
from exams.models import StudentMark
from parent_portal.models import FamilyStudent
from students.models import Student
from timetable.models import TimetableEntry

from .forms import (
    BroadcastMessageForm,
    FeedbackManagementForm,
    FeedbackTicketForm,
    RolePermissionFormSet,
    WorkflowActionForm,
)
from .models import BroadcastMessage, FeedbackTicket, Notification, RolePermissionRule, WorkflowRequest
from .permissions import feature_required, is_management, management_required, role_code, superuser_required
from .services import audit, management_recipients, notify, notify_management, send_broadcast_notifications, transition_workflow


def _workflow_scope(user):
    """Internal workflow scope retained for compatibility with linked modules."""
    qs = WorkflowRequest.objects.select_related("requester", "assignee", "school", "branch").exclude(
        related_app="accounting", related_model="DiscountRequest"
    )
    if is_management(user):
        return qs
    return qs.filter(Q(requester=user) | Q(assignee=user))


def _user_school_branch(user):
    try:
        return user.profile.school, user.profile.branch
    except Exception:
        teacher = getattr(user, "teacher_profile", None)
        if teacher is not None:
            return teacher.school, teacher.branch
        family = getattr(user, "family_account", None)
        if family is not None:
            return family.school, None
    return None, None


def _parent_students(user):
    return list(
        Student.objects.filter(family_links__family__user=user, family_links__is_active=True)
        .distinct()
        .order_by("full_name")
    )


def _teacher_assignments(user):
    teacher = getattr(user, "teacher_profile", None)
    if teacher is None:
        return None, []
    assignments = list(
        teacher.assignments.filter(is_active=True)
        .select_related("academic_year", "section", "section__grade", "subject")
        .order_by("section__grade__order", "section__name", "subject__name")
    )
    return teacher, assignments


def _management_report_rows(code):
    today = timezone.localdate()
    if code == "students":
        return [
            ["رقم الطالب", "الاسم", "الصف", "الشعبة", "الحالة", "الهاتف"],
            *[
                [s.student_number, s.full_name, s.grade, s.section, s.get_status_display(), s.phone]
                for s in Student.objects.order_by("full_name")
            ],
        ]
    if code == "finance":
        rows = [["رقم الطالب", "الاسم", "إجمالي الرسوم", "المدفوع", "المتبقي"]]
        for student in Student.objects.order_by("full_name"):
            invoices = StudentInvoice.objects.filter(student=student).exclude(status="cancelled").prefetch_related("payments")
            invoiced = sum((invoice.net_amount for invoice in invoices), 0)
            paid_amount = StudentPayment.objects.filter(invoice__student=student, status="posted").aggregate(total=Sum("amount"))["total"] or 0
            rows.append([student.student_number, student.full_name, invoiced, paid_amount, max(invoiced - paid_amount, 0)])
        return rows
    if code == "attendance":
        start = today - timedelta(days=29)
        summary = Attendance.objects.filter(date__gte=start).values(
            "student__student_number", "student__full_name"
        ).annotate(
            present=Count("id", filter=Q(status="present")),
            absent=Count("id", filter=Q(status="absent")),
            late=Count("id", filter=Q(status="late")),
            departed=Count("id", filter=Q(status="departed")),
        ).order_by("student__full_name")
        return [["رقم الطالب", "الاسم", "حاضر", "غائب", "متأخر", "مغادر"], *[
            [r["student__student_number"], r["student__full_name"], r["present"], r["absent"], r["late"], r["departed"]]
            for r in summary
        ]]
    if code == "academic":
        summary = StudentMark.objects.filter(exam__status__in=["published", "closed"]).values(
            "student__student_number", "student__full_name"
        ).annotate(avg=Avg("mark"), exams=Count("id")).order_by("student__full_name")
        return [["رقم الطالب", "الاسم", "عدد النتائج", "متوسط العلامات"], *[
            [r["student__student_number"], r["student__full_name"], r["exams"], round(float(r["avg"] or 0), 2)]
            for r in summary
        ]]
    if code == "documents":
        return [["رقم الوثيقة", "العنوان", "الطالب/المستفيد", "تاريخ الإصدار", "المصدر"], *[
            [
                d.document_number,
                d.title,
                d.student.full_name if d.student else d.applicant_name,
                d.issued_at.strftime("%Y-%m-%d"),
                d.issued_by.username if d.issued_by else "-",
            ]
            for d in IssuedDocument.objects.select_related("student", "issued_by").filter(status="active")
        ]]
    if code == "feedback":
        return [["الرقم", "النوع", "العنوان", "المرسل", "جودة التدريس", "الخدمات الإلكترونية", "الحالة", "التاريخ"], *[
            [
                item.pk,
                item.get_kind_display(),
                item.title,
                item.sender.username if item.sender else "-",
                item.teaching_quality_rating,
                item.electronic_services_rating,
                item.get_status_display(),
                item.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
            for item in FeedbackTicket.objects.select_related("sender")
        ]]
    return [["لا توجد بيانات"]]


def _teacher_report_rows(code, user):
    teacher, assignments = _teacher_assignments(user)
    if teacher is None:
        return [["لا توجد بيانات"]]
    if code == "teacher_timetable":
        entries = TimetableEntry.objects.filter(teacher=teacher, is_active=True).select_related(
            "section__grade", "subject", "time_slot", "academic_year"
        )
        return [["العام", "اليوم", "الحصة", "الوقت", "الصف/الشعبة", "المادة", "الغرفة"], *[
            [
                e.academic_year.name,
                e.get_day_display(),
                e.time_slot.name,
                f"{e.time_slot.start_time}-{e.time_slot.end_time}",
                str(e.section),
                e.subject.name,
                e.room or "-",
            ]
            for e in entries
        ]]
    if code == "teacher_students":
        assignment_ids = [a.pk for a in assignments]
        rows = [["العام", "الصف/الشعبة", "المادة", "رقم الطالب", "اسم الطالب"]]
        for assignment in assignments:
            enrollments = Enrollment.objects.filter(
                academic_year=assignment.academic_year,
                section=assignment.section,
                status="active",
            ).select_related("student")
            for enrollment in enrollments:
                rows.append([
                    assignment.academic_year.name,
                    str(assignment.section),
                    assignment.subject.name,
                    enrollment.student.student_number,
                    enrollment.student.full_name,
                ])
        return rows
    if code == "teacher_marks":
        marks = StudentMark.objects.filter(entered_by=user).select_related("student", "exam", "exam__subject")
        return [["الطالب", "المادة", "الامتحان", "العلامة", "الحد الأعلى", "التاريخ"], *[
            [m.student.full_name, m.exam.subject.name, m.exam.name, m.mark, m.exam.max_mark, m.updated_at.strftime("%Y-%m-%d %H:%M")]
            for m in marks
        ]]
    return _personal_audit_rows(user)


def _parent_report_rows(code, user):
    students = _parent_students(user)
    if code == "parent_children":
        return [["رقم الطالب", "الاسم", "الصف", "الشعبة", "الحالة"], *[
            [s.student_number, s.full_name, s.grade, s.section, s.get_status_display()] for s in students
        ]]
    if code == "parent_finance":
        return [["رقم الطالب", "الاسم", "إجمالي الرسوم", "المدفوع", "المتبقي"], *[
            [s.student_number, s.full_name, student_total_fees(s), student_total_paid(s), student_remaining(s)] for s in students
        ]]
    if code == "parent_attendance":
        records = Attendance.objects.filter(student__in=students).select_related("student").order_by("-date")
        return [["الطالب", "التاريخ", "الحالة", "ملاحظات"], *[
            [r.student.full_name, r.date, r.get_status_display(), r.notes] for r in records
        ]]
    if code == "parent_marks":
        records = StudentMark.objects.filter(
            student__in=students, exam__status__in=["published", "closed"]
        ).select_related("student", "exam", "exam__subject")
        return [["الطالب", "المادة", "الامتحان", "العلامة", "الحد الأعلى"], *[
            [r.student.full_name, r.exam.subject.name, r.exam.name, r.mark, r.exam.max_mark] for r in records
        ]]
    return _personal_audit_rows(user)


def _personal_audit_rows(user):
    return [["الوقت", "العملية", "الوحدة", "الوصف"], *[
        [row.created_at.strftime("%Y-%m-%d %H:%M:%S"), row.get_action_display(), row.model_name, row.description]
        for row in AuditLog.objects.filter(user=user)[:1000]
    ]]


def _report_rows(code, user):
    if is_management(user):
        return _management_report_rows(code)
    if getattr(user, "teacher_profile", None) is not None:
        return _teacher_report_rows(code, user)
    if getattr(user, "family_account", None) is not None:
        return _parent_report_rows(code, user)
    return _personal_audit_rows(user)


@login_required
@management_required
def enterprise_dashboard(request):
    today = timezone.localdate()
    feedback = FeedbackTicket.objects.select_related("sender", "assigned_to")
    context = {
        "new_feedback_count": feedback.filter(status="new").count(),
        "review_feedback_count": feedback.filter(status="review").count(),
        "resolved_feedback_count": feedback.filter(status__in=["resolved", "closed"]).count(),
        "unread_notifications": Notification.objects.filter(is_read=False).count(),
        "active_broadcasts": BroadcastMessage.objects.filter(is_active=True).count(),
        "audit_today": AuditLog.objects.filter(created_at__date=today).count(),
        "recent_feedback": feedback[:8],
        "recent_broadcasts": BroadcastMessage.objects.select_related("created_by", "specific_teacher")[:8],
    }
    audit(request, "view", "enterprise_ops.Dashboard", description="عرض مركز الإشعارات والشكاوى والتنبيهات")
    return render(request, "enterprise_ops/dashboard.html", context)


# Internal workflow URLs remain available to preserve integrations, but they are
# no longer presented as the user-facing approvals center.
@login_required
def workflow_list(request):
    qs = _workflow_scope(request.user)
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    q = request.GET.get("q", "").strip()
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(requester__username__icontains=q))
    return render(request, "enterprise_ops/workflow_list.html", {
        "items": qs,
        "status_choices": WorkflowRequest.STATUS_CHOICES,
        "priority_choices": WorkflowRequest.PRIORITY_CHOICES,
        "filters": {"status": status, "priority": priority, "q": q},
        "can_manage": is_management(request.user),
    })


@login_required
def workflow_detail(request, pk):
    item = get_object_or_404(_workflow_scope(request.user).prefetch_related("actions__actor"), pk=pk)
    return render(request, "enterprise_ops/workflow_detail.html", {
        "item": item,
        "action_form": WorkflowActionForm(),
        "can_manage": is_management(request.user),
    })


@login_required
@require_POST
def workflow_action(request, pk):
    item = get_object_or_404(_workflow_scope(request.user), pk=pk)
    if not is_management(request.user) and item.assignee_id != request.user.id:
        messages.error(request, "لا تملك صلاحية تنفيذ هذا الإجراء.")
        return redirect(item)
    form = WorkflowActionForm(request.POST)
    if form.is_valid():
        action = form.cleaned_data["action"]
        note = form.cleaned_data["note"]
        try:
            old, new = transition_workflow(item, request.user, action, note)
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
        else:
            notify(item.requester, f"تحديث الطلب #{item.pk}", f"تم تغيير الحالة من {old} إلى {new}. {note}".strip(), "success" if new == "approved" else "warning", item.get_absolute_url())
            audit(request, "update", "enterprise_ops.WorkflowRequest", item.pk, f"إجراء {action}: {old} -> {new}. {note}")
            messages.success(request, "تم تحديث الطلب بنجاح.")
    else:
        messages.error(request, "تعذر تنفيذ الإجراء. تحقق من البيانات.")
    return redirect(item)


@login_required
@feature_required("workflow", "view")
def feedback_list(request):
    items = FeedbackTicket.objects.select_related("sender", "assigned_to", "school", "branch")
    if not is_management(request.user):
        items = items.filter(sender=request.user)
    kind = request.GET.get("kind", "")
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    if kind:
        items = items.filter(kind=kind)
    if status:
        items = items.filter(status=status)
    if q:
        items = items.filter(Q(title__icontains=q) | Q(message__icontains=q) | Q(sender__username__icontains=q))
    return render(request, "enterprise_ops/feedback_list.html", {
        "items": items,
        "kind_choices": FeedbackTicket.KIND_CHOICES,
        "status_choices": FeedbackTicket.STATUS_CHOICES,
        "filters": {"kind": kind, "status": status, "q": q},
        "can_manage": is_management(request.user),
    })


@login_required
@feature_required("workflow", "create")
def feedback_create(request):
    form = FeedbackTicketForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.sender = request.user
        item.school, item.branch = _user_school_branch(request.user)
        item.save()
        link = item.get_absolute_url()
        for manager in management_recipients():
            notify(
                manager,
                f"{item.get_kind_display()} جديدة #{item.pk}",
                f"{item.title} — أرسلها {request.user.get_full_name() or request.user.username}",
                level="warning" if item.kind == "complaint" else "info",
                link=link,
                event_key=f"feedback:{item.pk}:manager:{manager.pk}",
            )
        audit(request, "create", "enterprise_ops.FeedbackTicket", item.pk, f"إرسال {item.get_kind_display()}: {item.title}")
        messages.success(request, "تم إرسال الشكوى أو الاقتراح مع التقييمين إلى الإدارة.")
        return redirect(item)
    return render(request, "enterprise_ops/feedback_form.html", {"form": form})


@login_required
@feature_required("workflow", "view")
def feedback_detail(request, pk):
    scope = FeedbackTicket.objects.select_related("sender", "assigned_to", "school", "branch")
    if not is_management(request.user):
        scope = scope.filter(sender=request.user)
    item = get_object_or_404(scope, pk=pk)
    form = FeedbackManagementForm(request.POST or None, instance=item) if is_management(request.user) else None
    if request.method == "POST" and form is not None and form.is_valid():
        before = item.status
        item = form.save(commit=False)
        if item.status in {"resolved", "closed"}:
            item.resolved_at = timezone.now()
        else:
            item.resolved_at = None
        item.save()
        notify(
            item.sender,
            f"تحديث {item.get_kind_display()} #{item.pk}",
            f"تم تحديث الحالة إلى: {item.get_status_display()}. {item.response}".strip(),
            level="success" if item.status in {"resolved", "closed"} else "info",
            link=item.get_absolute_url(),
            event_key=f"feedback-update:{item.pk}:{item.updated_at.timestamp()}",
        )
        audit(request, "update", "enterprise_ops.FeedbackTicket", item.pk, f"تحديث الحالة {before} ← {item.status}")
        messages.success(request, "تم حفظ رد الإدارة وتحديث الحالة.")
        return redirect(item)
    return render(request, "enterprise_ops/feedback_detail.html", {
        "item": item,
        "management_form": form,
        "can_manage": is_management(request.user),
    })


@login_required
@management_required
def broadcast_list(request):
    items = BroadcastMessage.objects.select_related("created_by", "specific_teacher")
    return render(request, "enterprise_ops/broadcast_list.html", {"items": items})


@login_required
@management_required
def broadcast_create(request):
    school = active_school()
    form = BroadcastMessageForm(request.POST or None, school=school)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.created_by = request.user
        item.save()
        sent = send_broadcast_notifications(item)
        audit(request, "create", "enterprise_ops.BroadcastMessage", item.pk, f"إرسال {item.get_message_type_display()} إلى {sent} مستخدم")
        messages.success(request, f"تم الإرسال إلى {sent} مستخدم وظهر في الإشعارات مع التنبيه الصوتي.")
        return redirect("enterprise_ops:broadcast_list")
    return render(request, "enterprise_ops/broadcast_form.html", {"form": form})


@login_required
@management_required
@require_POST
def broadcast_toggle(request, pk):
    item = get_object_or_404(BroadcastMessage, pk=pk)
    item.is_active = not item.is_active
    item.save(update_fields=["is_active"])
    audit(request, "update", "enterprise_ops.BroadcastMessage", item.pk, "تغيير حالة التعميم أو التنبيه")
    messages.success(request, "تم تحديث الحالة.")
    return redirect("enterprise_ops:broadcast_list")


@login_required
@management_required
@require_POST
def broadcast_delete(request, pk):
    item = get_object_or_404(BroadcastMessage, pk=pk)
    title = item.title
    item.delete()
    audit(request, "delete", "enterprise_ops.BroadcastMessage", pk, f"حذف تعميم أو تنبيه: {title}")
    messages.success(request, "تم حذف سجل التعميم أو التنبيه. الإشعارات التي وصلت للمستخدمين تبقى ضمن سجلهم.")
    return redirect("enterprise_ops:broadcast_list")


@login_required
@feature_required("notifications", "view")
def notification_list(request):
    items = request.user.opal_notifications.all()
    unread = request.GET.get("unread") == "1"
    if unread:
        items = items.filter(is_read=False)
    return render(request, "enterprise_ops/notification_list.html", {"items": items, "unread_only": unread})


@login_required
@feature_required("notifications", "view")
def notification_read(request, pk):
    item = get_object_or_404(request.user.opal_notifications, pk=pk)
    if not item.is_read:
        item.is_read = True
        item.read_at = timezone.now()
        item.save(update_fields=["is_read", "read_at"])
    return redirect(item.link or "enterprise_ops:notification_list")


@login_required
@feature_required("notifications", "view")
@require_POST
def notification_read_all(request):
    request.user.opal_notifications.filter(is_read=False).update(is_read=True, read_at=timezone.now())
    messages.success(request, "تم تعليم جميع الإشعارات كمقروءة.")
    return redirect("enterprise_ops:notification_list")


@login_required
@feature_required("notifications", "view")
@require_GET
def notification_status(request):
    unread = request.user.opal_notifications.filter(is_read=False)
    latest = unread.filter(sound_enabled=True).first()
    return JsonResponse({
        "unread_count": unread.count(),
        "latest_id": latest.pk if latest else None,
        "latest_title": latest.title if latest else "",
        "latest_level": latest.level if latest else "",
    })


@login_required
@feature_required("audit", "view")
def audit_log(request):
    qs = AuditLog.objects.select_related("user")
    if not is_management(request.user):
        qs = qs.filter(user=request.user)
    action = request.GET.get("action", "")
    q = request.GET.get("q", "").strip()
    if action:
        qs = qs.filter(action=action)
    if q:
        qs = qs.filter(Q(description__icontains=q) | Q(model_name__icontains=q) | Q(user__username__icontains=q))
    return render(request, "enterprise_ops/audit_log.html", {
        "items": qs[:500],
        "actions": AuditLog.ACTION_CHOICES,
        "filters": {"action": action, "q": q},
        "personal_scope": not is_management(request.user),
    })


@login_required
@feature_required("reports", "view")
def report_center(request):
    if is_management(request.user):
        reports = [
            {"code": "students", "title": "تقرير الطلاب", "icon": "people", "description": "بيانات الطلاب والصفوف والحالة."},
            {"code": "finance", "title": "تقرير الرسوم والتحصيل", "icon": "cash-coin", "description": "الرسوم والمدفوع والمتبقي لكل طالب."},
            {"code": "attendance", "title": "تقرير الحضور 30 يومًا", "icon": "calendar-check", "description": "الحضور والغياب والتأخر."},
            {"code": "academic", "title": "تقرير الأداء الأكاديمي", "icon": "bar-chart", "description": "متوسطات العلامات وعدد النتائج."},
            {"code": "documents", "title": "تقرير الوثائق", "icon": "file-earmark-text", "description": "الوثائق المصدرة ومصادرها."},
            {"code": "feedback", "title": "تقرير الشكاوى والاقتراحات", "icon": "chat-square-text", "description": "الحالات والتقييمات وجودة الخدمات."},
        ]
    elif getattr(request.user, "teacher_profile", None) is not None:
        reports = [
            {"code": "teacher_timetable", "title": "جدولي الدراسي", "icon": "calendar3", "description": "الحصص حسب اليوم والصف والمادة."},
            {"code": "teacher_students", "title": "طلبتي حسب التكليف", "icon": "people", "description": "الطلاب في الشعب والمواد التي أدرسها."},
            {"code": "teacher_marks", "title": "العلامات التي أدخلتها", "icon": "clipboard-data", "description": "سجل العلامات المرتبط بحساب المعلم."},
            {"code": "my_activity", "title": "سجل عملياتي", "icon": "shield-check", "description": "العمليات المسجلة على حسابي."},
        ]
    elif getattr(request.user, "family_account", None) is not None:
        reports = [
            {"code": "parent_children", "title": "بيانات الأبناء", "icon": "people", "description": "الأبناء المرتبطون بحساب ولي الأمر."},
            {"code": "parent_finance", "title": "الرسوم والمدفوع", "icon": "cash-coin", "description": "إجمالي الرسوم والمدفوع والمتبقي لكل ابن."},
            {"code": "parent_attendance", "title": "حضور الأبناء", "icon": "calendar-check", "description": "سجل الحضور والغياب والتأخر."},
            {"code": "parent_marks", "title": "علامات الأبناء", "icon": "bar-chart", "description": "النتائج المنشورة فقط."},
            {"code": "my_activity", "title": "سجل عملياتي", "icon": "shield-check", "description": "العمليات المسجلة على حسابي."},
        ]
    else:
        reports = [{"code": "my_activity", "title": "سجل عملياتي", "icon": "shield-check", "description": "العمليات المسجلة على حسابي."}]
    return render(request, "enterprise_ops/report_center.html", {"reports": reports})


@login_required
@feature_required("reports", "export")
def report_export_csv(request, code):
    allowed_codes = {report["code"] for report in _report_code_definitions(request.user)}
    if code not in allowed_codes:
        messages.error(request, "هذا التقرير غير متاح لدور المستخدم الحالي.")
        return redirect("enterprise_ops:report_center")
    rows = _report_rows(code, request.user)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="opal_{code}_{timezone.localdate()}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerows(rows)
    audit(request, "export", "enterprise_ops.Report", code, f"تصدير تقرير {code}")
    return response


def _report_code_definitions(user):
    if is_management(user):
        return [{"code": code} for code in ["students", "finance", "attendance", "academic", "documents", "feedback"]]
    if getattr(user, "teacher_profile", None) is not None:
        return [{"code": code} for code in ["teacher_timetable", "teacher_students", "teacher_marks", "my_activity"]]
    if getattr(user, "family_account", None) is not None:
        return [{"code": code} for code in ["parent_children", "parent_finance", "parent_attendance", "parent_marks", "my_activity"]]
    return [{"code": "my_activity"}]


@superuser_required
def permission_matrix(request):
    role_codes = [
        ("super_admin", "مدير النظام"), ("school_owner", "مالك المدرسة"),
        ("principal", "مدير المدرسة"), ("accountant", "مسؤول الرسوم"),
        ("secretary", "سكرتير"), ("teacher", "معلم"),
        ("parent", "ولي أمر"), ("student", "طالب"),
    ]
    features = RolePermissionRule.FEATURE_CHOICES
    existing = {(r.role_code, r.feature) for r in RolePermissionRule.objects.all()}
    to_create = []
    management_roles = {"super_admin", "school_owner", "principal"}
    staff_roles = management_roles | {"accountant", "secretary"}
    for code, _ in role_codes:
        for feature, _ in features:
            if (code, feature) in existing:
                continue
            can_view = feature in {"workflow", "notifications", "reports", "audit"} or code in staff_roles
            to_create.append(RolePermissionRule(
                role_code=code,
                feature=feature,
                can_view=can_view,
                can_create=(feature == "workflow" and code in {"teacher", "parent"}),
                can_update=(feature == "workflow" and code in staff_roles),
                can_approve=(feature == "approvals" and code in management_roles),
                can_export=(feature == "reports"),
            ))
    if to_create:
        RolePermissionRule.objects.bulk_create(to_create)
    qs = RolePermissionRule.objects.all()
    if request.method == "POST":
        formset = RolePermissionFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            formset.save()
            audit(request, "update", "enterprise_ops.RolePermissionRule", description="تحديث مصفوفة الصلاحيات")
            messages.success(request, "تم حفظ مصفوفة الصلاحيات.")
            return redirect("enterprise_ops:permission_matrix")
    else:
        formset = RolePermissionFormSet(queryset=qs)
    role_labels = dict(role_codes)
    return render(request, "enterprise_ops/permission_matrix.html", {"formset": formset, "role_labels": role_labels})
