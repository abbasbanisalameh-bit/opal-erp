
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
import json
from .models import AdmissionApplication, StudentRegistration, GradeFee, TransportRoute
from .forms import GradeFeeForm, TransportRouteForm, RegistrationSettingsForm, DirectStudentRegistrationForm
from .services import active_school, get_registration_settings, calculate_registration_totals, create_student_registration, current_academic_year


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
    registration = get_object_or_404(StudentRegistration.objects.select_related("student", "receipt", "grade", "section", "school"), pk=pk)
    return render(request, "admissions/registration_receipt.html", {"registration": registration})


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
