import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounting.models import StudentInvoice, StudentPayment
from attendance_v2.models import Attendance
from core.models import AuditLog
from documents.models import IssuedDocument
from exams.models import StudentMark
from students.models import Student

from .forms import RolePermissionFormSet, WorkflowActionForm
from .models import Notification, RolePermissionRule, WorkflowRequest
from .permissions import is_management, management_required
from .services import audit, notify, transition_workflow


def _workflow_scope(user):
    qs = WorkflowRequest.objects.select_related("requester", "assignee", "school", "branch")
    if is_management(user):
        return qs
    return qs.filter(Q(requester=user) | Q(assignee=user))


def _report_rows(code):
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
            remaining = max(invoiced - paid_amount, 0)
            rows.append([student.student_number, student.full_name, invoiced, paid_amount, remaining])
        return rows
    if code == "attendance":
        start = today - timedelta(days=29)
        summary = Attendance.objects.filter(date__gte=start).values("student__student_number", "student__full_name").annotate(
            present=Count("id", filter=Q(status="present")),
            absent=Count("id", filter=Q(status="absent")),
            late=Count("id", filter=Q(status="late")),
            excused=Count("id", filter=Q(status="excused")),
        ).order_by("student__full_name")
        return [["رقم الطالب", "الاسم", "حاضر", "غائب", "متأخر", "بعذر"], *[
            [r["student__student_number"], r["student__full_name"], r["present"], r["absent"], r["late"], r["excused"]] for r in summary
        ]]
    if code == "academic":
        summary = StudentMark.objects.filter(exam__status="published").values("student__student_number", "student__full_name").annotate(avg=Avg("mark"), exams=Count("id")).order_by("student__full_name")
        return [["رقم الطالب", "الاسم", "عدد النتائج", "متوسط العلامات"], *[
            [r["student__student_number"], r["student__full_name"], r["exams"], round(float(r["avg"] or 0), 2)] for r in summary
        ]]
    if code == "documents":
        return [["رقم الوثيقة", "العنوان", "الطالب", "تاريخ الإصدار", "المصدر"], *[
            [d.document_number, d.title, d.student.full_name if d.student else d.applicant_name, d.issued_at.strftime("%Y-%m-%d"), d.issued_by.username if d.issued_by else "-"]
            for d in IssuedDocument.objects.select_related("student", "issued_by").filter(status="active")
        ]]
    if code == "workflow":
        return [["رقم", "العنوان", "النوع", "الحالة", "الأولوية", "مقدم الطلب", "المسؤول", "التاريخ"], *[
            [w.pk, w.title, w.get_request_type_display(), w.get_status_display(), w.get_priority_display(), w.requester.username if w.requester else "-", w.assignee.username if w.assignee else "-", w.created_at.strftime("%Y-%m-%d %H:%M")]
            for w in WorkflowRequest.objects.select_related("requester", "assignee")
        ]]
    return [["لا توجد بيانات"]]


@login_required
@management_required
def enterprise_dashboard(request):
    today = timezone.localdate()
    last_30 = today - timedelta(days=29)
    workflow_qs = WorkflowRequest.objects.all()
    audit_qs = AuditLog.objects.select_related("user")
    context = {
        "pending_count": workflow_qs.filter(status__in=["new", "review", "returned"]).count(),
        "approved_count": workflow_qs.filter(status="approved").count(),
        "rejected_count": workflow_qs.filter(status="rejected").count(),
        "urgent_count": workflow_qs.filter(priority="urgent", status__in=["new", "review", "returned"]).count(),
        "unread_notifications": Notification.objects.filter(is_read=False).count(),
        "audit_today": audit_qs.filter(created_at__date=today).count(),
        "students_count": Student.objects.count(),
        "staff_count": User.objects.filter(is_active=True, is_staff=True).count(),
        "attendance_risk": Attendance.objects.filter(date__gte=last_30, status__in=["absent", "late"]).count(),
        "outstanding_invoices": StudentInvoice.objects.exclude(status__in=["paid", "cancelled"]).count(),
        "recent_workflows": workflow_qs.select_related("requester", "assignee")[:8],
        "recent_audit": audit_qs[:10],
        "status_stats": workflow_qs.values("status").annotate(total=Count("id")).order_by("status"),
        "priority_stats": workflow_qs.filter(status__in=["new", "review", "returned"]).values("priority").annotate(total=Count("id")).order_by("priority"),
    }
    audit(request, "view", "enterprise_ops.Dashboard", description="عرض لوحة التشغيل المؤسسي")
    return render(request, "enterprise_ops/dashboard.html", context)


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
            messages.error(request, exc.message)
        else:
            notify(item.requester, f"تحديث الطلب #{item.pk}", f"تم تغيير الحالة من {old} إلى {new}. {note}".strip(), "success" if new == "approved" else "warning", item.get_absolute_url())
            audit(request, "update", "enterprise_ops.WorkflowRequest", item.pk, f"إجراء {action}: {old} -> {new}. {note}")
            messages.success(request, "تم تحديث الطلب بنجاح.")
    else:
        messages.error(request, "تعذر تنفيذ الإجراء. تحقق من البيانات.")
    return redirect(item)


@login_required
def notification_list(request):
    items = request.user.opal_notifications.all()
    unread = request.GET.get("unread") == "1"
    if unread:
        items = items.filter(is_read=False)
    return render(request, "enterprise_ops/notification_list.html", {"items": items, "unread_only": unread})


@login_required
def notification_read(request, pk):
    item = get_object_or_404(request.user.opal_notifications, pk=pk)
    if not item.is_read:
        item.is_read = True
        item.read_at = timezone.now()
        item.save(update_fields=["is_read", "read_at"])
    return redirect(item.link or "enterprise_ops:notification_list")


@login_required
@require_POST
def notification_read_all(request):
    request.user.opal_notifications.filter(is_read=False).update(is_read=True, read_at=timezone.now())
    messages.success(request, "تم تعليم جميع الإشعارات كمقروءة.")
    return redirect("enterprise_ops:notification_list")


@login_required
@management_required
def audit_log(request):
    qs = AuditLog.objects.select_related("user")
    action = request.GET.get("action", "")
    q = request.GET.get("q", "").strip()
    if action:
        qs = qs.filter(action=action)
    if q:
        qs = qs.filter(Q(description__icontains=q) | Q(model_name__icontains=q) | Q(user__username__icontains=q))
    return render(request, "enterprise_ops/audit_log.html", {"items": qs[:500], "actions": AuditLog.ACTION_CHOICES, "filters": {"action": action, "q": q}})


@login_required
@management_required
def report_center(request):
    reports = [
        {"code": "students", "title": "تقرير الطلاب", "icon": "people", "description": "بيانات الطلاب والصفوف والحالة."},
        {"code": "finance", "title": "تقرير الرسوم والتحصيل", "icon": "cash-coin", "description": "الرسوم والمدفوع والمتبقي لكل طالب."},
        {"code": "attendance", "title": "تقرير الحضور 30 يومًا", "icon": "calendar-check", "description": "الحضور والغياب والتأخر."},
        {"code": "academic", "title": "تقرير الأداء الأكاديمي", "icon": "bar-chart", "description": "متوسطات العلامات وعدد النتائج."},
        {"code": "documents", "title": "تقرير الوثائق", "icon": "file-earmark-text", "description": "الوثائق المصدرة ومصادرها."},
        {"code": "workflow", "title": "تقرير الطلبات والموافقات", "icon": "diagram-3", "description": "حالة جميع الطلبات وسير العمل."},
    ]
    return render(request, "enterprise_ops/report_center.html", {"reports": reports})


@login_required
@management_required
def report_export_csv(request, code):
    rows = _report_rows(code)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="opal_{code}_{timezone.localdate()}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerows(rows)
    audit(request, "export", "enterprise_ops.Report", code, f"تصدير تقرير {code}")
    return response


@login_required
@management_required
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
            can_view = feature in {"workflow", "notifications"} or code in staff_roles
            to_create.append(RolePermissionRule(
                role_code=code, feature=feature, can_view=can_view,
                can_create=(feature == "workflow" and code != "student"),
                can_update=(feature == "workflow" and code in staff_roles),
                can_approve=(feature == "approvals" and code in management_roles),
                can_export=(feature == "reports" and code in staff_roles),
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
