from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from enterprise_ops.permissions import management_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db import models
import json
import uuid
from .models import AdmissionApplication, StudentRegistration, GradeFee, TransportRoute, FeePayment
from .forms import CandidateApplicationForm, GradeFeeForm, TransportRouteForm, RegistrationSettingsForm, DirectStudentRegistrationForm
from .services import (
    active_school, get_registration_settings, calculate_registration_totals,
    create_student_registration, current_academic_year,
    find_existing_siblings, sibling_discount_used_registration, generate_application_number,
)
from .financial_services import (
    search_students, find_sibling_students, student_total_fees, student_total_paid,
    student_remaining, student_payment_status, create_siblings_fee_payment,
    build_family_payment_preview, safe_delete_fee_payment, safe_delete_registration_payment,
)
from core.finance_constants import ACTIVE_PAYMENT_METHOD_CHOICES
from enterprise_ops.services import audit
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from students.models import Student
from parent_portal.models import Family
from parent_portal.services import initial_parent_password, normalize_phone
from core.identifiers import normalize_identifier
from accounting.models import Receipt


def can_manage_registration(user):
    return user.is_superuser or user.is_staff


@management_required
def admission_list(request):
    registrations = StudentRegistration.objects.select_related("student", "grade", "section", "receipt").all()
    applications = AdmissionApplication.objects.all()[:20]
    return render(request, "admissions/admission_list.html", {"registrations": registrations, "applications": applications})


@management_required
def candidate_list(request):
    query = request.GET.get("q", "").strip()
    candidates = AdmissionApplication.objects.filter(status="candidate").select_related("school", "academic_year", "grade", "section")
    if query:
        candidates = candidates.filter(
            models.Q(student_full_name__icontains=query)
            | models.Q(guardian_name__icontains=query)
            | models.Q(guardian_phone__icontains=query)
            | models.Q(application_number__icontains=query)
        )
    return render(request, "admissions/candidate_list.html", {"candidates": candidates, "query": query})


@management_required
def candidate_create(request):
    school = active_school()
    academic_year = current_academic_year(school)
    form = CandidateApplicationForm(request.POST or None, request.FILES or None, school=school, academic_year=academic_year)
    if request.method == "POST" and form.is_valid():
        candidate = form.save(commit=False)
        candidate.school = school
        candidate.academic_year = academic_year
        candidate.application_number = generate_application_number()
        candidate.status = "candidate"
        candidate.save()
        audit(request, "create", "admissions.AdmissionApplication", candidate.pk, f"إضافة مرشح للقبول {candidate.student_full_name}")
        messages.success(request, "تم حفظ المرشح دون إنشاء طالب أو تسجيل دراسي فعلي.")
        return redirect("admissions:candidate_detail", pk=candidate.pk)
    return render(request, "admissions/candidate_form.html", {"form": form, "title": "إضافة طالب مرشح للقبول"})


@management_required
def candidate_update(request, pk):
    candidate = get_object_or_404(AdmissionApplication, pk=pk, status="candidate")
    form = CandidateApplicationForm(request.POST or None, request.FILES or None, instance=candidate, school=candidate.school, academic_year=candidate.academic_year)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request, "update", "admissions.AdmissionApplication", candidate.pk, f"تحديث مرشح للقبول {candidate.student_full_name}")
        messages.success(request, "تم تحديث بيانات المرشح.")
        return redirect("admissions:candidate_detail", pk=candidate.pk)
    return render(request, "admissions/candidate_form.html", {"form": form, "title": "تعديل بيانات المرشح", "candidate": candidate})


@management_required
def candidate_detail(request, pk):
    candidate = get_object_or_404(
        AdmissionApplication.objects.select_related("school", "academic_year", "grade", "section"),
        pk=pk, status="candidate",
    )
    return render(request, "admissions/candidate_detail.html", {
        "candidate": candidate,
        "documents": candidate.issued_documents.select_related("template").all(),
    })


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
    school = active_school()
    settings = get_registration_settings(school)
    settings_form = RegistrationSettingsForm(instance=settings, prefix="settings")
    current_year = current_academic_year(school)
    if current_year is None:
        messages.warning(request, "لا يوجد عام دراسي مفتوح ومفعّل حاليًا.")
    grade_fee_form = GradeFeeForm(prefix="grade_fee", school=school, academic_year=current_year)
    route_form = TransportRouteForm(prefix="route")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "settings":
            settings_form = RegistrationSettingsForm(request.POST, instance=settings, prefix="settings")
            if settings_form.is_valid():
                settings_form.save()
                messages.success(request, "تم حفظ إعدادات الخصومات والدفعة الأولى.")
                return redirect("admissions:registration_settings")
        elif action == "grade_fee":
            messages.info(request, "رسوم الصفوف تُدار من الهيكل الدراسي الموحد.")
            return redirect("academics:academic_structure")
        elif action == "route":
            route_form = TransportRouteForm(request.POST, prefix="route")
            if route_form.is_valid():
                item = route_form.save(commit=False)
                item.school = school
                item.save()
                messages.success(request, "تم حفظ جولة المواصلات.")
                return redirect("admissions:registration_settings")
    return render(request, "admissions/registration_settings.html", {
        "settings_form": settings_form,
        "grade_fee_form": grade_fee_form,
        "route_form": route_form,
        "grade_fees": GradeFee.objects.filter(school=school).select_related("grade", "academic_year"),
        "routes": TransportRoute.objects.filter(school=school),
    })


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
def fee_payment_create(request):
    query = request.GET.get("q", "").strip()
    student_id = request.GET.get("student") or request.POST.get("student")
    selected_student = Student.objects.filter(pk=student_id).first() if student_id else None
    search_results = search_students(query) if query and not selected_student else []
    siblings_data = []
    has_unpaid_other_siblings = False

    if selected_student:
        siblings = find_sibling_students(selected_student)
        for student in siblings:
            row = {
                "student": student,
                "total": student_total_fees(student),
                "paid": student_total_paid(student),
                "remaining": student_remaining(student),
                "status": student_payment_status(student),
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
        "family_total_remaining": sum((row["remaining"] for row in siblings_data), 0),
        "has_payable_siblings": any(row["remaining"] > 0 for row in siblings_data),
        "has_unpaid_other_siblings": has_unpaid_other_siblings,
        "payment_methods": ACTIVE_PAYMENT_METHOD_CHOICES,
        "selected_payment_method": request.POST.get("payment_method", "cash"),
        "operation_token": request.POST.get("operation_token") or str(uuid.uuid4()),
    })


@login_required
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
def fee_payment_preview_api(request):
    student = get_object_or_404(Student, pk=request.GET.get("student"))
    amount = request.GET.get("amount") or "0"
    try:
        preview = build_family_payment_preview(student, amount)
        return JsonResponse({
            "ok": True,
            "amount": str(preview["amount"]),
            "allocated_total": str(preview["allocated_total"]),
            "unused_amount": str(preview["unused_amount"]),
            "due_before": str(preview["due_before"]),
            "due_after": str(preview["due_after"]),
            "is_valid": preview["is_valid"],
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
def fee_payment_receipt(request, pk):
    fee_payment = get_object_or_404(
        FeePayment.objects.select_related("school", "main_student", "created_by").prefetch_related("allocations__student"),
        pk=pk,
    )
    if fee_payment.is_deleted:
        messages.error(request, "هذا الإيصال محذوف بأمان ولا يمكن طباعته.")
        return redirect("admissions:fee_payment_archive")
    receiver_name, receiver_title = receiver_identity(fee_payment.created_by)
    return render(request, "admissions/fee_payment_receipt.html", {
        "fee_payment": fee_payment,
        "receipt_copies": ["نسخة المدرسة", "نسخة ولي الأمر"],
        "receiver_name": receiver_name,
        "receiver_title": receiver_title,
    })


@login_required
def fee_payment_archive(request):
    show_deleted = request.GET.get("show_deleted") == "1"
    payments = FeePayment.objects.select_related("main_student", "created_by", "deleted_by").prefetch_related("allocations")
    registrations = StudentRegistration.objects.select_related("student", "receipt__payment", "created_by", "grade")
    registration_receipt_ids = StudentRegistration.objects.exclude(receipt_id=None).values_list("receipt_id", flat=True)
    legacy_receipts = Receipt.objects.exclude(pk__in=registration_receipt_ids).select_related(
        "payment__invoice__student", "payment__created_by", "payment__deleted_by"
    )
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
def student_financial_record(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    invoices = student.invoices.select_related("fee_category").prefetch_related("payments").all()
    allocations = student.fee_payment_allocations.filter(fee_payment__is_deleted=False).select_related("fee_payment", "fee_payment__created_by")
    registrations = student.registrations.select_related("receipt", "created_by").all()
    return render(request, "admissions/student_financial_record.html", {
        "student": student,
        "invoices": invoices,
        "allocations": allocations,
        "registrations": registrations,
        "total_fees": student_total_fees(student),
        "total_paid": student_total_paid(student),
        "remaining": student_remaining(student),
    })
