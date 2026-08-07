import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from enterprise_ops.permissions import management_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
import json
import uuid
from .models import StudentRegistration, GradeFee, TransportRoute, FeePayment
from .forms import GradeFeeForm, TransportRouteForm, RegistrationSettingsForm, DirectStudentRegistrationForm
from .services import (
    active_school, get_registration_settings, calculate_registration_totals,
    current_academic_year, find_existing_siblings,
    sibling_discount_used_registration,
)
from .workflow import create_student_registration
from .financial_services import (
    search_students, find_sibling_students,
    student_separated_finance_snapshot, students_current_year_finance_snapshots,
    create_siblings_fee_payment,
    build_family_payment_preview, safe_delete_fee_payment, safe_delete_registration_payment,
)
from core.finance_constants import ACTIVE_PAYMENT_METHOD_CHOICES
from enterprise_ops.services import audit
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from students.models import Student
from parent_portal.models import Family
from parent_portal.services import normalize_phone
from core.identifiers import normalize_identifier
from accounting.models import Receipt
from accounting.previous_debt_services import (
    create_previous_debt_payment,
    previous_debt_receipt_breakdown,
    resolve_current_year_for_student,
    student_previous_debt_snapshot,
)


logger = logging.getLogger(__name__)


def can_manage_registration(user):
    return user.is_superuser or user.is_staff


@management_required
def admission_list(request):
    registrations = StudentRegistration.objects.select_related("student", "grade", "section", "receipt").all()
    return render(request, "admissions/admission_list.html", {"registrations": registrations})



@management_required
def direct_registration(request):
    school = active_school()
    academic_year = current_academic_year(school)
    if academic_year is None:
        messages.error(request, "لا يوجد عام دراسي مفتوح ومفعّل. فعّل العام من شاشة الأعوام قبل تسجيل الطلاب.")
    if request.method == "POST":
        form = DirectStudentRegistrationForm(request.POST, request.FILES, school=school, academic_year=academic_year)
        if form.is_valid():
            registration = create_student_registration(form, request.user)
            password = getattr(registration, "parent_initial_password", "")
            if password:
                request.session[f"parent_credentials_{registration.pk}"] = {
                    "username": getattr(registration, "parent_initial_username", ""),
                    "password": password,
                }
            messages.success(request, "تم تسجيل الطالب وإنشاء الإيصال بنجاح.")
            return redirect("admissions:registration_receipt", pk=registration.pk)
    else:
        form = DirectStudentRegistrationForm(school=school, academic_year=academic_year)

    settings = get_registration_settings(school)
    grade_fees = {
        str(item.grade_id): float(item.tuition_fee)
        for item in GradeFee.objects.filter(school=school, academic_year=academic_year, is_active=True).order_by("-updated_at", "-pk")
    }
    route_fees = {str(item.id): float(item.full_fee) for item in TransportRoute.objects.filter(school=school, is_active=True)}
    return render(request, "admissions/direct_registration.html", {
        "form": form,
        "settings": settings,
        "grade_fees_json": json.dumps(grade_fees),
        "route_fees_json": json.dumps(route_fees),
        "academic_year": academic_year,
    })


@management_required
def registration_receipt(request, pk):
    registration = get_object_or_404(
        StudentRegistration.objects.select_related("student", "payment", "receipt", "grade", "section", "school", "created_by"),
        pk=pk
    )
    if registration.payment_id and registration.payment.status != "posted":
        messages.error(request, "دفعة هذا التسجيل محذوفة بأمان ولا يمكن طباعة إيصالها.")
        return redirect("admissions:fee_payment_archive")
    receiver_name, receiver_title = receiver_identity(registration.created_by)
    digits = normalize_phone(registration.phone)
    parent_family = None
    guardian_identity = normalize_identifier(registration.guardian_identity_number)
    if guardian_identity:
        parent_family = Family.objects.filter(
            school=registration.school,
            identity_number=guardian_identity,
        ).select_related("user").first()
    if parent_family is None and digits:
        parent_family = Family.objects.filter(phone__icontains=digits[-9:]).select_related("user").first()
    if parent_family is None and registration.guardian_name:
        parent_family = Family.objects.filter(guardian_name__iexact=registration.guardian_name).select_related("user").first()
    credentials = request.session.pop(f"parent_credentials_{registration.pk}", {})
    parent_username = credentials.get("username") or (parent_family.user.username if parent_family and parent_family.user else "-")
    parent_initial_password = credentials.get("password") or "-"
    return render(request, "admissions/registration_receipt.html", {
        "registration": registration,
        "receipt_copies": ["نسخة المدرسة", "نسخة ولي الأمر"],
        "receiver_name": receiver_name,
        "receiver_title": receiver_title,
        "parent_family": parent_family,
        "parent_username": parent_username,
        "parent_initial_password": parent_initial_password,
    })


def receiver_identity(user):
    if not user:
        return "-", ""
    profile = getattr(user, "profile", None)
    name = getattr(profile, "full_name", "") or user.username
    title = getattr(getattr(profile, "role", None), "name", "") or ""
    return name, title


@login_required
@user_passes_test(can_manage_registration)
def registration_settings(request):
    """رابط توافق قديم؛ إعدادات التسجيل أصبحت ضمن إعدادات النظام الموحدة."""
    return redirect("core:system_settings")


@login_required
def registration_calculate_api(request):
    from academics.models import Grade
    grade = Grade.objects.filter(pk=request.GET.get("grade")).first()
    route = TransportRoute.objects.filter(pk=request.GET.get("transport_route")).first()
    totals = calculate_registration_totals(
        grade=grade,
        transport_route=route,
        transport_type=request.GET.get("transport_type", "none"),
        discount_type=request.GET.get("discount_type", "none"),
        admin_discount_value=request.GET.get("admin_discount_value", 0),
        first_payment=request.GET.get("first_payment") or None,
    )
    return JsonResponse({k: str(v) for k, v in totals.items()})


@login_required
def sibling_check_api(request):
    school = active_school()
    settings = get_registration_settings(school)
    siblings = find_existing_siblings(
        phone=request.GET.get("phone", "").strip(),
        father_name=request.GET.get("father_name", "").strip(),
        family_name=request.GET.get("family_name", "").strip(),
        mother_name=request.GET.get("mother_name", "").strip(),
        guardian_name=request.GET.get("guardian_name", "").strip(),
        guardian_identity_type=request.GET.get("guardian_identity_type", "national").strip(),
        guardian_identity_number=request.GET.get("guardian_identity_number", "").strip(),
    )
    if not siblings.exists():
        return JsonResponse({"has_sibling": False, "apply_discount": False, "message": "", "sibling_id": ""})

    first_sibling = siblings.first()
    used = sibling_discount_used_registration(siblings)

    if settings.sibling_discount_once_per_family and used:
        used_student = used.student or used.sibling_student
        used_name = used_student.full_name if used_student else used.full_name
        return JsonResponse({
            "has_sibling": True,
            "apply_discount": False,
            "sibling_id": first_sibling.id,
            "sibling_name": first_sibling.full_name,
            "message": f"يوجد أخ مسجل: {first_sibling.full_name}. لكن الطالب {used_name} استفاد سابقًا من خصم الإخوة، لذلك تم إلغاء خصم الإخوة لهذا الطالب.",
        })

    return JsonResponse({
        "has_sibling": True,
        "apply_discount": True,
        "sibling_id": first_sibling.id,
        "sibling_name": first_sibling.full_name,
        "message": f"تم التعرف على أخ مسجل: {first_sibling.full_name}. تم تفعيل خصم الإخوة تلقائيًا.",
    })


@login_required
@management_required
def fee_payment_create(request):
    school = active_school()
    academic_year = current_academic_year(school)
    query = request.GET.get("q", "").strip()
    student_id = request.GET.get("student") or request.POST.get("student")
    selected_student = Student.objects.filter(pk=student_id).first() if student_id else None
    search_results = search_students(query) if query and not selected_student else []
    siblings_data = []
    has_unpaid_other_siblings = False

    if selected_student:
        siblings = list(find_sibling_students(selected_student))
        finance_snapshots = students_current_year_finance_snapshots(
            siblings,
            academic_year=academic_year,
        )
        for student in siblings:
            finance = finance_snapshots[student.pk]
            previous_debt = student_previous_debt_snapshot(
                student,
                academic_year=academic_year,
            )
            row = {
                "student": student,
                "total": finance["total"],
                "paid": finance["paid"],
                "remaining": finance["remaining"],
                "status": finance["status"],
                "previous_debt": previous_debt,
                "combined_remaining": finance["remaining"] + previous_debt["total"],
            }
            siblings_data.append(row)
            if student.pk != selected_student.pk and row["remaining"] > 0:
                has_unpaid_other_siblings = True

    if request.method == "POST" and selected_student:
        amount = request.POST.get("amount") or "0"
        notes = request.POST.get("notes") or ""
        payment_method = request.POST.get("payment_method") or ""
        operation_token = request.POST.get("operation_token") or str(uuid.uuid4())
        try:
            fee_payment = create_siblings_fee_payment(
                main_student=selected_student,
                amount=amount,
                user=request.user,
                payment_method=payment_method,
                operation_token=operation_token,
                notes=notes,
            )
            payment_label = "دفعة عن جميع الإخوة" if fee_payment.scope == "all_siblings" else "دفعة الطالب"
            messages.success(request, f"تم تسجيل {payment_label} وإصدار الإيصال بنجاح.")
            return redirect("admissions:fee_payment_receipt", pk=fee_payment.pk)
        except Exception as exc:
            message = getattr(exc, "messages", None)
            messages.error(request, message[0] if message else f"تعذر تسجيل الدفعة: {exc}")

    return render(request, "admissions/fee_payment_form.html", {
        "query": query,
        "search_results": search_results,
        "selected_student": selected_student,
        "siblings_data": siblings_data,
        "current_year": academic_year,
        "family_total_current_remaining": sum((row["remaining"] for row in siblings_data), 0),
        "family_total_previous_remaining": sum((row["previous_debt"]["total"] for row in siblings_data), 0),
        "family_total_combined_remaining": sum((row["combined_remaining"] for row in siblings_data), 0),
        # Compatibility alias: the ordinary payment limit is current-year only.
        "family_total_remaining": sum((row["remaining"] for row in siblings_data), 0),
        "has_payable_siblings": any(row["remaining"] > 0 for row in siblings_data),
        "has_unpaid_other_siblings": has_unpaid_other_siblings,
        "payment_methods": ACTIVE_PAYMENT_METHOD_CHOICES,
        "selected_payment_method": request.POST.get("payment_method", "cash"),
        "operation_token": request.POST.get("operation_token") or str(uuid.uuid4()),
    })


@login_required
@management_required
def previous_debt_payment(request, student_id):
    school = active_school()
    academic_year = current_academic_year(school)
    student = get_object_or_404(
        Student.objects.filter(
            Q(enrollments__academic_year__school=school)
            | Q(invoices__academic_year__school=school)
        ).distinct(),
        pk=student_id,
    )
    snapshot = student_previous_debt_snapshot(student, academic_year=academic_year)
    if not snapshot["has_debt"]:
        messages.info(request, "لا توجد متبقيات رسوم سابقة على هذا الطالب.")
        return redirect("students:student_360", pk=student.pk)

    operation_token = request.POST.get("operation_token") or str(uuid.uuid4())
    selected_payment_method = request.POST.get("payment_method", "cash")
    if request.method == "POST":
        try:
            fee_payment = create_previous_debt_payment(
                student=student,
                amount=request.POST.get("amount") or "0",
                user=request.user,
                payment_method=selected_payment_method,
                operation_token=operation_token,
                notes=request.POST.get("notes") or "",
                academic_year=academic_year,
            )
            audit(
                request,
                "create",
                "admissions.FeePayment",
                fee_payment.pk,
                f"دفعة من متبقيات الرسوم السابقة للطالب {student.full_name} بقيمة {fee_payment.total_amount}",
            )
            messages.success(request, "تم تسجيل دفعة متبقيات الرسوم السابقة وإصدار الإيصال بنجاح.")
            return redirect("admissions:fee_payment_receipt", pk=fee_payment.pk)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            snapshot = student_previous_debt_snapshot(student, academic_year=academic_year)
        except Exception:
            logger.exception("Previous-debt payment failed for student_id=%s", student.pk)
            messages.error(request, "تعذر تسجيل دفعة متبقيات الرسوم السابقة. لم تُحفظ أي دفعة جزئية.")
            snapshot = student_previous_debt_snapshot(student, academic_year=academic_year)

    return render(request, "admissions/previous_debt_payment.html", {
        "student": student,
        "previous_debt": snapshot,
        "payment_methods": ACTIVE_PAYMENT_METHOD_CHOICES,
        "selected_payment_method": selected_payment_method,
        "operation_token": operation_token,
    })


@login_required
@management_required
def fee_payment_search_api(request):
    query = request.GET.get("q", "").strip()
    results = search_students(query) if query else []
    payload = []
    for student in results:
        family_link = student.family_links.filter(is_active=True).select_related("family").first()
        family = family_link.family if family_link else None
        payload.append({
            "id": student.pk,
            "student_number": student.student_number,
            "full_name": student.full_name,
            "guardian_name": student.guardian_name or getattr(family, "guardian_name", "") or "-",
            "guardian_identity": getattr(family, "identity_number", "") or "-",
            "national_id": student.national_id or "-",
            "phone": student.phone or getattr(family, "phone", "") or "-",
            "grade": student.grade or "-",
        })
    return JsonResponse({"results": payload})


@login_required
@management_required
def fee_payment_preview_api(request):
    student = get_object_or_404(Student, pk=request.GET.get("student"))
    amount = request.GET.get("amount") or "0"
    try:
        preview = build_family_payment_preview(
            student,
            amount,
            academic_year=current_academic_year(active_school()),
        )
        return JsonResponse({
            "ok": True,
            "amount": str(preview["amount"]),
            "allocated_total": str(preview["allocated_total"]),
            "unused_amount": str(preview["unused_amount"]),
            "due_before": str(preview["due_before"]),
            "due_after": str(preview["due_after"]),
            "is_valid": preview["is_valid"],
            "academic_year": preview["academic_year"].name,
            "rows": [
                {
                    "student_id": row["student"].pk,
                    "student_name": row["student"].full_name,
                    "total": str(row["total"]),
                    "paid_before": str(row["paid"]),
                    "remaining_before": str(row["remaining"]),
                    "allocated": str(row["allocated"]),
                    "remaining_after": str(row["remaining_after"]),
                    "status_after": row["status_after"],
                    "status_after_label": row["status_after_label"],
                }
                for row in preview["rows"]
            ],
        })
    except Exception as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)


@login_required
@management_required
def fee_payment_receipt(request, pk):
    fee_payment = get_object_or_404(
        FeePayment.objects.select_related("school", "main_student", "created_by").prefetch_related(
            "allocations__student",
            "allocations__invoice__academic_year",
        ),
        pk=pk,
    )
    if fee_payment.is_deleted:
        messages.error(request, "هذا الإيصال محذوف بأمان ولا يمكن طباعته.")
        return redirect("admissions:fee_payment_archive")
    receiver_name, receiver_title = receiver_identity(fee_payment.created_by)
    receipt_allocations = list(fee_payment.allocations.all())
    allocation_count = len(receipt_allocations)
    receipt_academic_year = next(
        (
            allocation.invoice.academic_year
            for allocation in receipt_allocations
            if allocation.invoice_id and allocation.invoice.academic_year_id
        ),
        None,
    )
    receipt_density = "very-dense" if allocation_count > 7 else ("dense" if allocation_count > 4 else "")
    previous_debt_receipt = previous_debt_receipt_breakdown(fee_payment)
    return render(request, "admissions/fee_payment_receipt.html", {
        "fee_payment": fee_payment,
        "receipt_copies": ["نسخة المدرسة", "نسخة ولي الأمر"],
        "receiver_name": receiver_name,
        "receiver_title": receiver_title,
        "receipt_density": receipt_density,
        "previous_debt_receipt": previous_debt_receipt,
        "receipt_academic_year": receipt_academic_year,
    })


@login_required
@management_required
def fee_payment_archive(request):
    show_deleted = request.GET.get("show_deleted") == "1"
    payments = FeePayment.objects.select_related("main_student", "created_by", "deleted_by").prefetch_related("allocations").order_by("-created_at", "-pk")
    registrations = StudentRegistration.objects.select_related("student", "receipt__payment", "created_by", "grade").order_by("-created_at", "-pk")
    registration_receipt_ids = StudentRegistration.objects.exclude(receipt_id=None).values_list("receipt_id", flat=True)
    legacy_receipts = Receipt.objects.exclude(pk__in=registration_receipt_ids).select_related(
        "payment__invoice__student", "payment__created_by", "payment__deleted_by"
    ).order_by("-created_at", "-pk")
    if not show_deleted:
        payments = payments.filter(is_deleted=False)
        registrations = registrations.filter(payment__status="posted")
        legacy_receipts = legacy_receipts.filter(payment__status="posted")
    return render(request, "admissions/fee_payment_archive.html", {"payments": payments, "registrations": registrations, "legacy_receipts": legacy_receipts, "show_deleted": show_deleted})


@login_required
@management_required
@require_POST
def fee_payment_safe_delete(request, pk):
    payment = get_object_or_404(FeePayment, pk=pk)
    reason = request.POST.get("reason", "").strip()
    try:
        changed = safe_delete_fee_payment(fee_payment=payment, user=request.user, reason=reason)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        if changed:
            audit(request, "delete", "admissions.FeePayment", payment.pk, f"حذف آمن للإيصال {payment.receipt_number}: {reason}")
            messages.success(request, "تم حذف الإيصال بأمان وتحديث الأرصدة مع الاحتفاظ بسجل العملية.")
        else:
            messages.info(request, "الإيصال محذوف بأمان مسبقًا.")
    return redirect("admissions:fee_payment_archive")


@login_required
@management_required
@require_POST
def registration_payment_safe_delete(request, pk):
    registration = get_object_or_404(StudentRegistration, pk=pk)
    reason = request.POST.get("reason", "").strip()
    try:
        changed = safe_delete_registration_payment(registration=registration, user=request.user, reason=reason)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        if changed:
            audit(request, "delete", "admissions.StudentRegistration", registration.pk, f"حذف آمن لدفعة التسجيل: {reason}")
            messages.success(request, "تم حذف دفعة التسجيل بأمان وتحديث رصيد الطالب.")
        else:
            messages.info(request, "دفعة التسجيل محذوفة مسبقًا.")
    return redirect("admissions:fee_payment_archive")


@login_required
@management_required
def student_financial_record(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    current_year = resolve_current_year_for_student(student)
    invoices = list(
        student.invoices.select_related("fee_category", "academic_year")
        .exclude(carry_forward_record__source_invoices__isnull=False)
        .distinct()
        .prefetch_related("payments")
        .all()
    )
    allocations = student.fee_payment_allocations.filter(
        fee_payment__is_deleted=False,
        amount__gt=0,
    ).select_related(
        "fee_payment",
        "fee_payment__created_by",
        "invoice__academic_year",
    )
    registrations = student.registrations.select_related("receipt", "created_by").all()
    finance = student_separated_finance_snapshot(student, academic_year=current_year)
    current_invoices = [
        invoice for invoice in invoices
        if current_year is not None and invoice.academic_year_id == current_year.pk
    ]
    previous_invoices = [
        invoice for invoice in invoices
        if current_year is not None
        and invoice.academic_year_id
        and invoice.academic_year.start_date < current_year.start_date
    ]
    other_invoices = [
        invoice for invoice in invoices
        if invoice not in current_invoices and invoice not in previous_invoices
    ]
    return render(request, "admissions/student_financial_record.html", {
        "student": student,
        "invoices": invoices,
        "current_invoices": current_invoices,
        "previous_invoices": previous_invoices,
        "other_invoices": other_invoices,
        "allocations": allocations,
        "registrations": registrations,
        "current_year": current_year,
        "finance": finance,
        "previous_debt": finance["previous"],
        "total_fees": finance["current"]["total"],
        "total_paid": finance["current"]["paid"],
        "remaining": finance["current"]["remaining"],
    })
