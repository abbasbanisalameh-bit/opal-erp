import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import resolve, Resolver404, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounting.models import StudentInvoice, StudentPayment
from admissions.services import active_school
from attendance_v2.analytics import build_student_attendance_summaries
from core.models import AuditLog
from documents.models import IssuedDocument
from exams.models import StudentMark
from students.models import Student

from .forms import (
    BroadcastMessageForm,
    FeedbackManagementForm,
    FeedbackTicketForm,
    RolePermissionFormSet,
    WorkflowActionForm,
)
from .models import BroadcastMessage, FeedbackTicket, RolePermissionRule, WorkflowRequest
from .permissions import (
    feature_required,
    has_feature_permission,
    is_management,
    management_required,
    role_code,
    superuser_required,
)
from .evaluation_services import MonthlyEvaluationError, submit_monthly_evaluations as save_monthly_evaluations
from .services import (
    audit,
    notify,
    notify_management,
    send_broadcast_notifications,
    transition_workflow,
    visible_notifications_for_user,
)


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
        students = list(Student.objects.filter(is_active=True).order_by("full_name"))
        summaries = build_student_attendance_summaries(
            students,
            start_date=start,
            end_date=today,
        )
        rows = [["رقم الطالب", "الاسم", "الأيام المحتسبة", "حاضر تلقائيًا", "غائب", "مغادر", "نسبة الانتظام"]]
        for student in students:
            item = summaries[student.pk]
            rows.append([
                student.student_number,
                student.full_name,
                item["total"],
                item["present_count"],
                item["absent_count"],
                item["departed_count"],
                f'{item["rate"]}%',
            ])
        return rows
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
        return [["الرقم", "النوع", "العنوان", "المرسل", "الحالة", "التاريخ"], *[
            [
                item.pk,
                item.get_kind_display(),
                item.title,
                item.sender.username if item.sender else "-",
                item.get_status_display(),
                item.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
            for item in FeedbackTicket.objects.select_related("sender")
        ]]
    return [["لا توجد بيانات"]]



@login_required
@management_required
def enterprise_dashboard(request):
    """Compatibility gateway for the former standalone communication center.

    The executive dashboard is now the single management overview.  Detailed
    complaint, broadcast and announcement pages remain unchanged and are
    opened from their interactive cards.
    """
    audit(request, "view", "dashboard.ExecutiveCommunication", description="فتح التواصل المدمج في لوحة الإدارة")
    return redirect(f"{reverse('dashboard:home')}#opal-communication-actions")


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
            notify(item.requester, f"تحديث الطلب #{item.pk}", f"تم تغيير الحالة من {old} إلى {new}. {note}".strip(), "success" if new == "approved" else "warning", item.get_absolute_url(), event_key=f"workflow-status:{item.pk}:{new}")
            audit(request, "update", "enterprise_ops.WorkflowRequest", item.pk, f"إجراء {action}: {old} -> {new}. {note}")
            messages.success(request, "تم تحديث الطلب بنجاح.")
    else:
        messages.error(request, "تعذر تنفيذ الإجراء. تحقق من البيانات.")
    return redirect(item)


@login_required
@feature_required("workflow", "view")
def feedback_list(request):
    items = FeedbackTicket.objects.select_related("sender", "assigned_to", "school", "branch")
    can_manage = is_management(request.user)
    can_submit = (not can_manage) and has_feature_permission(request.user, "workflow", "create")
    form = None
    if not can_manage:
        if request.method == "POST" and not can_submit:
            messages.error(request, "لا تملك الصلاحية لإرسال شكوى أو اقتراح.")
            return redirect("enterprise_ops:feedback_list")
        form = FeedbackTicketForm(request.POST or None) if can_submit else None
        if request.method == "POST" and form is not None and form.is_valid():
            item = form.save(commit=False)
            item.sender = request.user
            item.school, item.branch = _user_school_branch(request.user)
            sender_role = "المعلم" if hasattr(request.user, "teacher_profile") else "ولي الأمر"
            item.title = f"{item.get_kind_display()} من {sender_role}"
            item.save()
            # Management follows new complaints and suggestions from the
            # dedicated dashboard card.  Do not duplicate the same work item
            # in the personal notification bell.
            audit(request, "create", "enterprise_ops.FeedbackTicket", item.pk, f"إرسال {item.get_kind_display()}")
            messages.success(request, "تم إرسال الرسالة إلى الإدارة. ستصلك متابعة عند تحديثها.")
            return redirect("enterprise_ops:feedback_list")
        items = items.filter(sender=request.user)
    kind = status = q = ""
    if can_manage:
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
        "form": form,
        "kind_choices": FeedbackTicket.KIND_CHOICES,
        "status_choices": FeedbackTicket.STATUS_CHOICES,
        "filters": {"kind": kind, "status": status, "q": q},
        "can_manage": can_manage,
        "can_submit": can_submit,
    })


@login_required
@feature_required("workflow", "create")
def feedback_create(request):
    """Compatibility URL; the canonical user workflow is the combined page."""
    if request.method == "POST":
        return feedback_list(request)
    return redirect("enterprise_ops:feedback_list")


@login_required
@require_POST
def submit_monthly_evaluations(request):
    """Single endpoint for teacher and guardian monthly evaluations."""
    try:
        saved = save_monthly_evaluations(request.user, request.POST)
    except MonthlyEvaluationError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    if not saved:
        return JsonResponse({"ok": True, "message": "تم استكمال تقييم هذا الشهر مسبقًا."})
    audit(request, "create", "enterprise_ops.MonthlyServiceEvaluation", description="إرسال التقييم الشهري")
    return JsonResponse({"ok": True, "message": "شكرًا لك على مشاركتك في تحسين جودة المدرسة."})


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
    items = visible_notifications_for_user(request.user)
    unread = request.GET.get("unread") == "1"
    if unread:
        items = items.filter(is_read=False)
    return render(request, "enterprise_ops/notification_list.html", {"items": items, "unread_only": unread})


def _notification_destination(request, item):
    """Return a safe, resolvable local destination for a notification.

    Old, empty or malformed links fall back to the notification center rather
    than sending the user to a broken URL or an external host.
    """
    destination = (item.link or "").strip()
    if not destination:
        return None
    if not url_has_allowed_host_and_scheme(
        destination,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return None
    if not destination.startswith("/") or destination.startswith("//"):
        return None
    path = destination.split("?", 1)[0].split("#", 1)[0]
    try:
        resolve(path)
    except Resolver404:
        return None
    return destination


def _mark_notification_read(item):
    if not item.is_read:
        item.is_read = True
        item.read_at = timezone.now()
        item.save(update_fields=["is_read", "read_at"])


@login_required
@feature_required("notifications", "view")
def notification_open(request, pk):
    item = get_object_or_404(request.user.opal_notifications, pk=pk)
    _mark_notification_read(item)
    destination = _notification_destination(request, item)
    if destination:
        return redirect(destination)
    messages.info(request, "رابط هذا الإشعار قديم أو غير متاح؛ تم فتح مركز الإشعارات بدلًا منه.")
    return redirect("enterprise_ops:notification_list")


@login_required
@feature_required("notifications", "view")
@require_POST
def notification_read(request, pk):
    # Compatibility endpoint retained for older templates and saved links.
    return notification_open(request, pk)


@login_required
@feature_required("notifications", "view")
@require_POST
def notification_read_all(request):
    visible_notifications_for_user(request.user).filter(is_read=False).update(is_read=True, read_at=timezone.now())
    messages.success(request, "تم تعليم جميع الإشعارات كمقروءة.")
    return redirect("enterprise_ops:notification_list")


@login_required
@feature_required("notifications", "view")
@require_GET
def notification_status(request):
    unread = visible_notifications_for_user(request.user).filter(is_read=False)
    latest = unread.filter(sound_enabled=True).first()
    return JsonResponse({
        "unread_count": unread.count(),
        "latest_id": latest.pk if latest else None,
        "latest_title": latest.title if latest else "",
        "latest_level": latest.level if latest else "",
    })


@login_required
@management_required
@feature_required("audit", "view")
def audit_log(request):
    qs = AuditLog.objects.select_related("user")
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
        "personal_scope": False,
    })


@login_required
@management_required
@feature_required("reports", "view")
def report_center(request):
    reports = [
        {"code": "students", "title": "تقرير الطلاب", "icon": "people", "description": "بيانات الطلاب والصفوف والحالة."},
        {"code": "finance", "title": "تقرير الرسوم والتحصيل", "icon": "cash-coin", "description": "الرسوم والمدفوع والمتبقي لكل طالب."},
        {"code": "attendance", "title": "تقرير الحضور 30 يومًا", "icon": "calendar-check", "description": "أيام السجل والحضور التلقائي والغياب والمغادرة."},
        {"code": "academic", "title": "تقرير الأداء الأكاديمي", "icon": "bar-chart", "description": "متوسطات العلامات وعدد النتائج."},
        {"code": "documents", "title": "تقرير الوثائق", "icon": "file-earmark-text", "description": "الوثائق المصدرة ومصادرها."},
        {"code": "feedback", "title": "تقرير الشكاوى والاقتراحات", "icon": "chat-square-text", "description": "الحالات والتقييمات وجودة الخدمات."},
    ]
    return render(request, "enterprise_ops/report_center.html", {"reports": reports})


@login_required
@management_required
@feature_required("reports", "export")
def report_export_csv(request, code):
    allowed_codes = {"students", "finance", "attendance", "academic", "documents", "feedback"}
    if code not in allowed_codes:
        messages.error(request, "هذا التقرير غير متاح.")
        return redirect("enterprise_ops:report_center")
    rows = _management_report_rows(code)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="opal_{code}_{timezone.localdate()}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerows(rows)
    audit(request, "export", "enterprise_ops.Report", code, f"تصدير تقرير {code}")
    return response


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
