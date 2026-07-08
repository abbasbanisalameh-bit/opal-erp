from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
import json
from .models import AdmissionApplication, StudentRegistration, GradeFee, TransportRoute, FeePayment
from .forms import GradeFeeForm, TransportRouteForm, RegistrationSettingsForm, DirectStudentRegistrationForm
from .services import (
    active_school, get_registration_settings, calculate_registration_totals,
    create_student_registration, current_academic_year,
    find_existing_siblings, sibling_discount_used_registration,
)
from .financial_services import (
    search_students, find_sibling_students, student_total_fees, student_total_paid,
    student_remaining, student_payment_status, create_siblings_fee_payment,
)
from students.models import Student
from parent_portal.models import Family
from parent_portal.services import initial_parent_password, normalize_phone


def can_manage_registration(user):
    return user.is_superuser or user.is_staff


@login_required
def admission_list(request):
    registrations = StudentRegistration.objects.select_related("student", "grade", "section", "receipt").all()
    applications = AdmissionApplication.objects.all()[:20]
    return render(request, "admissions/admission_list.html", {"registrations": registrations, "applications": applications})


@login_required
def direct_registration(request):
    if request.method == "POST":
        form = DirectStudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            registration = create_student_registration(form, request.user)
            messages.success(request, "تم تسجيل الطالب وإنشاء الإيصال بنجاح.")
            return redirect("admissions:registration_receipt", pk=registration.pk)
    else:
        form = DirectStudentRegistrationForm()

    school = active_school()
    academic_year = current_academic_year(school)
    settings = get_registration_settings(school)
    grade_fees = {str(item.grade_id): float(item.tuition_fee) for item in GradeFee.objects.filter(school=school, is_active=True)}
    route_fees = {str(item.id): float(item.full_fee) for item in TransportRoute.objects.filter(school=school, is_active=True)}
    return render(request, "admissions/direct_registration.html", {
        "form": form,
        "settings": settings,
        "grade_fees_json": json.dumps(grade_fees),
        "route_fees_json": json.dumps(route_fees),
        "academic_year": academic_year,
    })


@login_required
def registration_receipt(request, pk):
    registration = get_object_or_404(
        StudentRegistration.objects.select_related("student", "receipt", "grade", "section", "school", "created_by"),
        pk=pk
    )
    receiver_name, receiver_title = receiver_identity(registration.created_by)
    digits = normalize_phone(registration.phone)
    parent_family = None
    if digits:
        parent_family = Family.objects.filter(phone__icontains=digits[-9:]).select_related("user").first()
    if parent_family is None and registration.guardian_name:
        parent_family = Family.objects.filter(guardian_name__iexact=registration.guardian_name).select_related("user").first()
    parent_username = parent_family.user.username if parent_family and parent_family.user else "-"
    parent_initial_password = initial_parent_password(registration.phone)
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
    grade_fee_form = GradeFeeForm(prefix="grade_fee")
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
            grade_fee_form = GradeFeeForm(request.POST, prefix="grade_fee")
            if grade_fee_form.is_valid():
                item = grade_fee_form.save(commit=False)
                item.school = school
                item.save()
                messages.success(request, "تم حفظ رسوم الصف.")
                return redirect("admissions:registration_settings")
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
        national_id=request.GET.get("national_id", "").strip(),
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
            "message": f"يوجد أخ مسجل: {first_sibling.full_name}. لكن الطالب {used_name} استفاد سابقًا من خصم الإخوة، لذلك تم إلغاء خصم الإخوة لهذا الطالب.",
        })

    return JsonResponse({
        "has_sibling": True,
        "apply_discount": True,
        "sibling_id": first_sibling.id,
        "message": f"تم التعرف على أخ مسجل: {first_sibling.full_name}. تم تفعيل خصم الإخوة تلقائيًا.",
    })


@login_required
def fee_payment_create(request):
    query = request.GET.get("q", "").strip()
    student_id = request.GET.get("student") or request.POST.get("student")
    selected_student = Student.objects.filter(pk=student_id).first() if student_id else None
    search_results = search_students(query) if query and not selected_student else []
    siblings_data = []

    if selected_student:
        siblings = find_sibling_students(selected_student)
        for student in siblings:
            siblings_data.append({
                "student": student,
                "total": student_total_fees(student),
                "paid": student_total_paid(student),
                "remaining": student_remaining(student),
                "status": student_payment_status(student),
            })

    if request.method == "POST" and selected_student:
        amount = request.POST.get("amount") or "0"
        notes = request.POST.get("notes") or ""
        try:
            fee_payment = create_siblings_fee_payment(main_student=selected_student, amount=amount, user=request.user, notes=notes)
            messages.success(request, "تم تسجيل دفعة عن جميع الإخوة وإصدار الإيصال بنجاح.")
            return redirect("admissions:fee_payment_receipt", pk=fee_payment.pk)
        except Exception as exc:
            messages.error(request, f"تعذر تسجيل الدفعة: {exc}")

    return render(request, "admissions/fee_payment_form.html", {
        "query": query,
        "search_results": search_results,
        "selected_student": selected_student,
        "siblings_data": siblings_data,
    })


@login_required
def fee_payment_receipt(request, pk):
    fee_payment = get_object_or_404(
        FeePayment.objects.select_related("school", "main_student", "created_by").prefetch_related("allocations__student"),
        pk=pk,
    )
    receiver_name, receiver_title = receiver_identity(fee_payment.created_by)
    return render(request, "admissions/fee_payment_receipt.html", {
        "fee_payment": fee_payment,
        "receipt_copies": ["نسخة المدرسة", "نسخة ولي الأمر"],
        "receiver_name": receiver_name,
        "receiver_title": receiver_title,
    })


@login_required
def fee_payment_archive(request):
    payments = FeePayment.objects.select_related("main_student", "created_by").prefetch_related("allocations").all()
    registrations = StudentRegistration.objects.select_related("student", "receipt", "created_by", "grade").all()
    return render(request, "admissions/fee_payment_archive.html", {"payments": payments, "registrations": registrations})


@login_required
def student_financial_record(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    invoices = student.invoices.select_related("fee_category").prefetch_related("payments").all()
    allocations = student.fee_payment_allocations.select_related("fee_payment", "fee_payment__created_by").all()
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
