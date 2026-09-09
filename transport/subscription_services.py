from django.core.exceptions import ValidationError
from django.db import transaction

from admissions.models import StudentRegistration
from admissions.services import calculate_registration_totals


@transaction.atomic
def update_transport_subscription(*, registration, transport_route, transport_type, school, user=None):
    """Update the canonical StudentRegistration transport subscription only.

    No parallel subscription model is created. Financial totals are recalculated
    through the existing admissions calculator and the linked invoice is kept
    mathematically consistent with posted payments.
    """
    registration = (
        StudentRegistration.objects
        .select_for_update()
        .select_related("student", "grade", "transport_route", "invoice")
        .get(pk=registration.pk, school=school)
    )

    if registration.student_id is None:
        raise ValidationError("لا يمكن إدارة اشتراك نقل لتسجيل لا يرتبط بطالب رسمي.")

    if transport_type == "none":
        transport_route = None

    if transport_type != "none" and transport_route is None:
        raise ValidationError("يجب اختيار المسار عند اشتراك الطالب بالمواصلات.")

    if transport_route is not None and transport_route.school_id != school.pk:
        raise ValidationError("لا يمكن اختيار مسار تابع لمدرسة أخرى.")

    changed_subscription = (
        registration.transport_route_id != getattr(transport_route, "pk", None)
        or registration.transport_type != transport_type
    )


    invoice = registration.invoice
    if invoice and invoice.status == "cancelled":
        raise ValidationError("الفاتورة المرتبطة بالتسجيل ملغاة، ولا يمكن تعديل رسوم النقل من هنا.")

    totals = calculate_registration_totals(
        grade=registration.grade,
        transport_route=transport_route,
        transport_type=transport_type,
        discount_type=registration.discount_type,
        admin_discount_value=registration.admin_discount_value,
        sibling_student=registration.sibling_student,
        first_payment=registration.first_payment,
        school=school,
        academic_year=registration.academic_year,
    )

    if invoice:
        posted_paid = invoice.total_paid
        if posted_paid > totals["net_total"]:
            raise ValidationError(
                "لا يمكن خفض إجمالي الرسوم إلى أقل من المبالغ المدفوعة فعليًا على الفاتورة."
            )

    registration.transport_route = transport_route
    registration.transport_type = transport_type
    registration.transport_fee = totals["transport_fee"]
    registration.tuition_fee = totals["tuition_fee"]
    registration.discount_value = totals["discount_value"]
    registration.net_total = totals["net_total"]

    if invoice:
        invoice.amount = totals["net_total"]
        invoice.sync_status(commit=False)
        invoice.save(update_fields=["amount", "status", "paid", "updated_at"])
        registration.remaining_amount = invoice.remaining
    else:
        registration.remaining_amount = totals["remaining_amount"]

    registration.save(update_fields=[
        "transport_route", "transport_type", "transport_fee", "tuition_fee",
        "discount_value", "net_total", "remaining_amount",
    ])
    # TransportAssignment is an operational projection, not the source of truth.
    # Reconcile it immediately after the canonical registration is saved.
    from .services import reconcile_transport_after_registration_change
    if changed_subscription:
        reconcile_transport_after_registration_change(
            registration=registration, school=school, change_reason="تحديث اشتراك المواصلات"
        )
    return registration
