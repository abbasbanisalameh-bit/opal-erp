"""Configurable guardian access policy; default is alert-only."""

from decimal import Decimal

from accounting.models import StudentInvoice


def family_outstanding_balance(family):
    student_ids = family.children.filter(is_active=True).values_list("student_id", flat=True)
    invoices = (
        StudentInvoice.objects.filter(student_id__in=student_ids)
        .exclude(status="cancelled")
        .exclude(carry_forward_record__source_invoices__isnull=False)
        .distinct()
        .prefetch_related("payments")
    )
    return sum((invoice.remaining for invoice in invoices), Decimal("0"))


def guardian_feature_allowed(family, feature):
    """Attendance and essential alerts always remain available."""
    if feature in {"attendance", "alerts", "account"}:
        return True
    if family is None or family_outstanding_balance(family) <= 0:
        return True
    policy = family.financial_policy or "alert_only"
    if policy == "alert_only":
        return True
    if policy == "hide_results":
        return feature != "marks"
    if policy == "hide_certificates":
        return feature not in {"certificates", "documents"}
    if policy in {"restrict_noncritical", "exceptional_suspension"}:
        return feature not in {"marks", "certificates", "documents", "homework", "timetable"}
    return True
