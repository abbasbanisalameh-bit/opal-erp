"""Teacher payroll, advances and termination services for Update 83."""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.secondary_effects import run_secondary_effect
from enterprise_ops.services import notify
from timetable.models import TeacherAbsence, TimetableEntry

from .models import Teacher, TeacherAdvance, TeacherAssignment, TeacherPayroll


ZERO = Decimal("0.00")


def normalize_period(value):
    if isinstance(value, date):
        return value.replace(day=1)
    try:
        year, month = str(value).split("-", 1)
        return date(int(year), int(month), 1)
    except (TypeError, ValueError):
        raise ValidationError("شهر الراتب غير صالح.")


def _period_end(period):
    return date(period.year, period.month, monthrange(period.year, period.month)[1])


def _absence_deduction(teacher, period):
    rows = TeacherAbsence.objects.filter(
        teacher=teacher,
        date__range=(period, _period_end(period)),
        absence_type="unexcused",
        payroll_approved=True,
    )
    daily = (teacher.monthly_salary or ZERO) / Decimal("30")
    return sum((row.deduction_amount if row.deduction_amount > 0 else daily for row in rows), ZERO).quantize(Decimal("0.01"))


@transaction.atomic
def generate_payroll_period(*, school, period, user=None):
    period = normalize_period(period)
    created = updated = preserved = 0
    for teacher in Teacher.objects.select_for_update().filter(school=school, is_active=True).order_by("pk"):
        record = TeacherPayroll.objects.select_for_update().filter(teacher=teacher, period=period).first()
        if record and record.status in {"sent", "acknowledged", "objection", "corrected"}:
            preserved += 1
            continue
        advances_qs = TeacherAdvance.objects.select_for_update().filter(
            teacher=teacher,
            status="acknowledged",
            acknowledged_at__date__lte=_period_end(period),
        )
        if record is None:
            advances_qs = advances_qs.filter(payroll_records__isnull=True)
        else:
            advances_qs = advances_qs.filter(
                Q(payroll_records__isnull=True) | Q(payroll_records=record)
            )
        advances = list(advances_qs.distinct())
        advance_total = sum((item.amount for item in advances), ZERO)
        absence_total = _absence_deduction(teacher, period)
        if record is None:
            record = TeacherPayroll(
                teacher=teacher,
                period=period,
                due_date=date(period.year, period.month, 25),
                created_by=user if getattr(user, "is_authenticated", False) else None,
            )
            created += 1
        else:
            updated += 1
        record.base_salary = teacher.monthly_salary or ZERO
        record.advance_deduction = advance_total
        record.absence_deduction = absence_total
        record.status = "ready"
        record.save()
        record.advances.set(advances)
    return {"created": created, "updated": updated, "preserved": preserved}


@transaction.atomic
def disburse_advance(*, advance, user, payment_method, reference="", admin_note=""):
    advance = TeacherAdvance.objects.select_for_update().select_related("teacher__user").get(pk=advance.pk)
    if advance.status != "requested":
        raise ValidationError("لا يمكن صرف سلفة ليست في حالة مطلوبة.")
    advance.status = "disbursed"
    advance.disbursed_by = user
    advance.disbursed_at = timezone.now()
    advance.payment_method = payment_method
    advance.reference = (reference or "").strip()
    advance.admin_note = (admin_note or "").strip()
    advance.save()
    transaction.on_commit(lambda: run_secondary_effect(
        notify,
        advance.teacher.user,
        "تم صرف السلفة",
        f"تم صرف سلفة بقيمة {advance.amount}. يرجى الإقرار بالاستلام من بطاقة الرواتب.",
        "success",
        f"{reverse('teachers:portal_payroll')}#advance-{advance.pk}",
        event_key=f"advance-disbursed:{advance.pk}",
        label="advance notification",
    ))
    return advance


@transaction.atomic
def acknowledge_advance(*, advance, teacher):
    advance = TeacherAdvance.objects.select_for_update().get(pk=advance.pk, teacher=teacher)
    if advance.status != "disbursed":
        raise ValidationError("السلفة غير جاهزة للإقرار بالاستلام.")
    advance.status = "acknowledged"
    advance.acknowledged_at = timezone.now()
    advance.save(update_fields=["status", "acknowledged_at"])
    return advance


@transaction.atomic
def send_payroll(*, payroll, user):
    payroll = TeacherPayroll.objects.select_for_update().select_related("teacher__user").get(pk=payroll.pk)
    if payroll.status not in {"ready", "corrected"}:
        raise ValidationError("لا يرسل إلا الراتب الجاهز أو المصحح.")
    if not payroll.payment_method:
        raise ValidationError("حدد طريقة دفع الراتب قبل الإرسال.")
    now = timezone.now()
    payroll.status = "sent"
    payroll.sent_at = now
    payroll.paid_at = now
    payroll.save(update_fields=["status", "sent_at", "paid_at", "net_salary", "updated_at"])
    payroll.advances.filter(status="acknowledged").update(status="deducted", deducted_at=now)
    transaction.on_commit(lambda: run_secondary_effect(
        notify,
        payroll.teacher.user,
        "بطاقة الراتب جاهزة",
        f"تم إرسال بطاقة راتب {payroll.period:%Y-%m} بصافي {payroll.net_salary}.",
        "success",
        f"{reverse('teachers:portal_payroll')}#payroll-{payroll.pk}",
        event_key=f"payroll-sent:{payroll.pk}",
        label="payroll notification",
    ))
    return payroll


@transaction.atomic
def terminate_teacher(*, teacher, end_date, reason, user=None):
    teacher = Teacher.objects.select_for_update().select_related("user", "school").get(pk=teacher.pk)
    reason = (reason or "").strip()
    if teacher.end_date and not teacher.is_active:
        raise ValidationError("خدمة هذا المعلم منتهية مسبقًا، ولا يمكن إصدار إنهاء خدمة مكرر.")
    if not reason:
        raise ValidationError("سبب انتهاء الخدمة إلزامي.")
    if teacher.hire_date and end_date < teacher.hire_date:
        raise ValidationError("تاريخ انتهاء الخدمة لا يمكن أن يسبق تاريخ التعيين.")
    if end_date > timezone.localdate():
        raise ValidationError("لا يمكن تنفيذ إنهاء الخدمة بتاريخ مستقبلي؛ نفّذ الإجراء في تاريخ سريانه.")

    teacher.end_date = end_date
    teacher.end_reason = reason
    teacher.is_active = False
    teacher.save(update_fields=["end_date", "end_reason", "is_active"])
    assignments = TeacherAssignment.objects.filter(teacher=teacher, is_active=True).update(is_active=False)
    timetable = TimetableEntry.objects.filter(
        teacher=teacher, is_active=True, academic_year__is_closed=False
    ).update(is_active=False)
    account_deactivated = False
    if teacher.user_id and teacher.user.is_active:
        teacher.user.is_active = False
        teacher.user.save(update_fields=["is_active"])
        account_deactivated = True

    from documents.workflow import issue_teacher_termination_document

    document = issue_teacher_termination_document(teacher=teacher, user=user)
    return teacher, document, {
        "assignments_deactivated": assignments,
        "timetable_deactivated": timetable,
        "account_deactivated": account_deactivated,
    }


@transaction.atomic
def reactivate_teacher(*, teacher):
    """Reactivate the teacher and login without restoring old operations.

    Historic assignments, timetable entries and termination documents remain
    untouched.  The manager must create or activate current assignments
    deliberately after reviewing the academic year and timetable.
    """
    teacher = Teacher.objects.select_for_update().select_related("user").get(pk=teacher.pk)
    if teacher.is_active:
        raise ValidationError("المعلم نشط بالفعل.")
    teacher.is_active = True
    teacher.end_date = None
    teacher.end_reason = ""
    teacher.save(update_fields=["is_active", "end_date", "end_reason"])
    account_activated = False
    if teacher.user_id and not teacher.user.is_active:
        teacher.user.is_active = True
        teacher.user.save(update_fields=["is_active"])
        account_activated = True
    return teacher, {
        "account_activated": account_activated,
        "assignments_reactivated": 0,
        "timetable_reactivated": 0,
    }
