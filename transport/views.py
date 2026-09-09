from django.contrib import messages
import re
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from parent_portal.permissions import parent_required

from accounts.workflow import is_management_user
from admissions.models import StudentRegistration, TransportRoute
from admissions.services import active_school

from .forms import TransportDriverForm, TransportFamilyLocationForm, TransportSubscriptionForm
from .models import (
    TransportAssignment,
    TransportDriver,
    TransportFamilyLocation,
    TransportTrip,
)
from .services import (
    create_driver,
    update_driver,
    establish_stable_groups,
    approve_group,
    assign_group_driver,
    move_registrations_to_group,
    prepare_today_operations,
)


def _require_management(user):
    if not is_management_user(user):
        raise PermissionDenied


def _school_for_user(user):
    """Resolve the canonical school context without creating a parallel source."""
    profile = getattr(user, "profile", None)
    school = getattr(profile, "school", None)

    if school is not None:
        return school

    # Superusers/staff may not have a school on UserProfile.
    # Fall back to the existing canonical admissions school context.
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return active_school()

    return None


@login_required
def transport_dashboard(request):
    # One transport gateway: management, driver and parent each receive
    # the role-specific workspace without creating parallel navigation doors.
    if is_management_user(request.user):
        return _management_transport_dashboard(request)

    try:
        if request.user.transport_driver:
            return driver_transport_dashboard(request)
    except Exception:
        pass

    # Resolve the guardian workspace through the canonical family workflow.
    # Do not silently swallow relation errors and bounce the user back to the
    # parent home page. A dedicated route is also available for portal links.
    from parent_portal.workflow import family_for_user
    family = family_for_user(request.user)
    if family is not None:
        return parent_transport_dashboard(request)

    raise PermissionDenied


def _management_transport_dashboard(request):
    _require_management(request.user)

    school = _school_for_user(request.user)

    routes = TransportRoute.objects.filter(
        school=school,
        is_active=True,
    ).order_by("name")

    drivers = TransportDriver.objects.filter(
        user__profile__school=school,
        is_active=True,
    ).order_by("name")

    registrations = StudentRegistration.objects.filter(
        school=school,
        transport_route__isnull=False,
    ).select_related(
        "student",
        "transport_route",
    )

    assignments = TransportAssignment.objects.filter(
        is_active=True,
        registration__school=school,
    ).select_related(
        "registration",
        "registration__student",
        "driver",
        "morning_trip",
        "return_trip",
    )

    family_locations_count = TransportFamilyLocation.objects.filter(
        family__school=school,
        is_active=True,
    ).count()

    from .models import TransportGroup
    groups_count = TransportGroup.objects.filter(route__school=school, is_stable=True).count()

    context = {
        "routes": routes,
        "drivers": drivers,
        "registrations": registrations,
        "assignments": assignments,
        "family_locations_count": family_locations_count,
        "groups_count": groups_count,
        "routes_count": routes.count(),
        "drivers_count": drivers.count(),
        "transport_students_count": registrations.count(),
        "assignments_count": assignments.count(),
    }

    return render(request, "transport/dashboard.html", context)


@login_required
def driver_list(request):
    _require_management(request.user)

    school = _school_for_user(request.user)

    drivers = TransportDriver.objects.filter(
        user__profile__school=school,
    ).select_related(
        "user",
        "user__profile",
    ).order_by("name")

    return render(
        request,
        "transport/drivers/list.html",
        {"drivers": drivers},
    )


@login_required
def driver_create(request):
    _require_management(request.user)

    school = _school_for_user(request.user)

    if school is None:
        messages.error(request, "لا توجد مدرسة مرتبطة بحساب المستخدم.")
        return redirect("transport:transport-dashboard")

    if request.method == "POST":
        form = TransportDriverForm(request.POST)

        if form.is_valid():
            driver, username, temporary_password = create_driver(
                school=school,
                name=form.cleaned_data["name"],
                phone=form.cleaned_data["phone"],
            )

            request.session["transport_driver_credentials"] = {
                "driver_id": driver.pk,
                "name": driver.name,
                "username": username,
                "temporary_password": temporary_password,
            }

            messages.success(request, "تم إنشاء السائق وحساب النظام بنجاح.")
            return redirect("transport:driver-credentials", pk=driver.pk)
    else:
        form = TransportDriverForm()

    return render(
        request,
        "transport/drivers/form.html",
        {
            "form": form,
            "title": "إضافة سائق",
        },
    )


@login_required
def driver_credentials(request, pk):
    _require_management(request.user)

    school = _school_for_user(request.user)

    driver = get_object_or_404(
        TransportDriver,
        pk=pk,
        user__profile__school=school,
    )

    credentials = request.session.pop(
        "transport_driver_credentials",
        None,
    )

    if not credentials or credentials.get("driver_id") != driver.pk:
        messages.info(
            request,
            "بيانات الدخول المؤقتة عُرضت عند إنشاء الحساب فقط.",
        )
        return redirect("transport:driver-list")

    return render(
        request,
        "transport/drivers/credentials.html",
        {
            "driver": driver,
            "credentials": credentials,
        },
    )


TRANSPORT_DRIVER_IMPERSONATOR_SESSION_KEY = "opal_transport_driver_impersonator_user_id"
TRANSPORT_DRIVER_IMPERSONATED_SESSION_KEY = "opal_transport_driver_impersonated_user_id"
TRANSPORT_DRIVER_IMPERSONATOR_SCHOOL_SESSION_KEY = "opal_transport_driver_impersonator_school_id"


@login_required
@require_POST
def driver_impersonate(request, pk):
    """Allow an authorised manager to enter the existing driver account safely."""
    from django.contrib.auth import login as auth_login
    from django.contrib.auth.models import User
    from enterprise_ops.services import audit

    _require_management(request.user)
    if request.session.get(TRANSPORT_DRIVER_IMPERSONATOR_SESSION_KEY):
        messages.error(request, "أنت داخل حساب سائق بالفعل. ارجع إلى حساب الإدارة أولًا.")
        return redirect("transport:transport-dashboard")

    school = _school_for_user(request.user)
    driver = get_object_or_404(
        TransportDriver,
        pk=pk,
        is_active=True,
        user__is_active=True,
        user__profile__school=school,
    )
    if driver.user_id == request.user.pk:
        raise PermissionDenied("لا يمكن الدخول إلى الحساب نفسه.")

    original_user = request.user
    backend = request.session.get("_auth_user_backend", "django.contrib.auth.backends.ModelBackend")
    auth_login(request, driver.user, backend=backend)
    # Django may rotate the session key during login. Re-assert the
    # impersonation context after login so the driver workspace can always
    # render the safe return-to-management action.
    request.session[TRANSPORT_DRIVER_IMPERSONATOR_SESSION_KEY] = original_user.pk
    request.session[TRANSPORT_DRIVER_IMPERSONATED_SESSION_KEY] = driver.user_id
    request.session[TRANSPORT_DRIVER_IMPERSONATOR_SCHOOL_SESSION_KEY] = school.pk if school else None
    request.session.modified = True
    audit(
        request,
        "view",
        "transport.TransportDriver",
        driver.pk,
        f"دخول إداري إلى حساب السائق {driver.name} لمراجعة واجهة السائق.",
    )
    messages.info(request, f"أنت الآن داخل حساب السائق {driver.name}. يمكنك العودة إلى حساب الإدارة من الشريط العلوي.")
    return redirect("transport:transport-dashboard")


@login_required
@require_POST
def driver_impersonate_stop(request):
    """Return from a driver session to the exact management account that started it."""
    from django.contrib.auth import login as auth_login
    from django.contrib.auth.models import User
    from enterprise_ops.services import audit

    original_user_id = request.session.get(TRANSPORT_DRIVER_IMPERSONATOR_SESSION_KEY)
    target_user_id = request.session.get(TRANSPORT_DRIVER_IMPERSONATED_SESSION_KEY)
    school_id = request.session.get(TRANSPORT_DRIVER_IMPERSONATOR_SCHOOL_SESSION_KEY)
    if not original_user_id or not target_user_id:
        messages.info(request, "لا توجد جلسة دخول إدارية إلى حساب سائق.")
        return redirect("transport:transport-dashboard")

    original_user = get_object_or_404(User, pk=original_user_id, is_active=True)
    if not is_management_user(original_user):
        raise PermissionDenied("حساب العودة لم يعد يملك صلاحية الإدارة.")

    driver = get_object_or_404(
        TransportDriver,
        user=request.user,
        pk=getattr(getattr(request.user, "transport_driver", None), "pk", None),
    )
    if driver.user_id != target_user_id or (school_id is not None and driver.user.profile.school_id != school_id):
        raise PermissionDenied("جلسة الدخول الإدارية غير صالحة لهذا السائق.")

    backend = request.session.get("_auth_user_backend", "django.contrib.auth.backends.ModelBackend")
    auth_login(request, original_user, backend=backend)
    audit(
        request,
        "view",
        "transport.TransportDriver",
        driver.pk,
        f"إنهاء الدخول الإداري إلى حساب السائق {driver.name} والعودة إلى حساب الإدارة.",
    )
    request.session.pop(TRANSPORT_DRIVER_IMPERSONATOR_SESSION_KEY, None)
    request.session.pop(TRANSPORT_DRIVER_IMPERSONATED_SESSION_KEY, None)
    request.session.pop(TRANSPORT_DRIVER_IMPERSONATOR_SCHOOL_SESSION_KEY, None)
    messages.success(request, "تم الرجوع إلى حساب الإدارة بنجاح.")
    return redirect("transport:transport-dashboard")


@login_required
def driver_edit(request, pk):
    _require_management(request.user)

    school = _school_for_user(request.user)

    driver = get_object_or_404(
        TransportDriver,
        pk=pk,
        user__profile__school=school,
    )

    if request.method == "POST":
        form = TransportDriverForm(request.POST, instance=driver)

        if form.is_valid():
            update_driver(
                driver=driver,
                name=form.cleaned_data["name"],
                phone=form.cleaned_data["phone"],
            )

            messages.success(request, "تم تحديث بيانات السائق بنجاح.")
            return redirect("transport:driver-list")
    else:
        form = TransportDriverForm(instance=driver)

    return render(
        request,
        "transport/drivers/form.html",
        {
            "form": form,
            "title": "تعديل السائق",
            "driver": driver,
        },
    )


# ============================================================
# Canonical Transport Route Management
# ============================================================

@login_required
def route_list(request):
    """Manage the canonical admissions.TransportRoute records in the transport center."""
    _require_management(request.user)
    school = _school_for_user(request.user)
    routes = TransportRoute.objects.filter(school=school).order_by("name")
    return render(
        request,
        "transport/routes/list.html",
        {"routes": routes, "school": school},
    )


@login_required
def route_create(request):
    """Create a route in the existing canonical admissions.TransportRoute table."""
    _require_management(request.user)
    school = _school_for_user(request.user)
    if school is None:
        messages.error(request, "لا توجد مدرسة مرتبطة بحساب المستخدم.")
        return redirect("transport:transport-dashboard")

    from admissions.forms import TransportRouteForm
    form = TransportRouteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        route = form.save(commit=False)
        route.school = school
        route.save()
        messages.success(request, "تم إنشاء مسار المواصلات بنجاح.")
        return redirect("transport:route-list")

    return render(
        request,
        "transport/routes/form.html",
        {"form": form, "title": "إضافة مسار", "school": school},
    )


@login_required
def route_edit(request, pk):
    """Edit only the canonical route belonging to the current school."""
    _require_management(request.user)
    school = _school_for_user(request.user)
    route = get_object_or_404(TransportRoute, pk=pk, school=school)

    from admissions.forms import TransportRouteForm
    form = TransportRouteForm(request.POST or None, instance=route)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث مسار المواصلات بنجاح.")
        return redirect("transport:route-list")

    return render(
        request,
        "transport/routes/form.html",
        {"form": form, "title": "تعديل المسار", "route": route, "school": school},
    )


@login_required
def route_toggle(request, pk):
    """Activate/deactivate a canonical route; do not delete historical route records."""
    _require_management(request.user)
    if request.method != "POST":
        return redirect("transport:route-list")
    school = _school_for_user(request.user)
    route = get_object_or_404(TransportRoute, pk=pk, school=school)
    route.is_active = not route.is_active
    route.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request,
        "تم تفعيل المسار." if route.is_active else "تم تعطيل المسار.",
    )
    return redirect("transport:route-list")


# ============================================================
# Transport Trip Management
# ============================================================

@login_required
def trip_list(request):
    _require_management(request.user)

    from .models import TransportTrip

    school = _school_for_user(request.user)

    trips = list(
        TransportTrip.objects
        .filter(school=school)
        .select_related("route", "driver")
        .order_by("-service_date", "route__name", "driver__name", "sequence", "direction", "id")
    )
    rows = {}
    for trip in trips:
        key = (trip.service_date, trip.route_id, trip.driver_id, trip.sequence)
        row = rows.setdefault(key, {
            "service_date": trip.service_date, "route": trip.route, "driver": trip.driver,
            "sequence": trip.sequence, "vehicle_label": trip.get_vehicle_type_display(),
            "morning": None, "return": None, "morning_count": 0, "return_count": 0,
        })
        if trip.direction == TransportTrip.MORNING:
            row["morning"] = trip
            row["morning_count"] = trip.assignments.filter(is_active=True).count() if hasattr(trip, "assignments") else 0
        else:
            row["return"] = trip
            row["return_count"] = trip.assignments.filter(is_active=True).count() if hasattr(trip, "assignments") else 0
    # TransportAssignment has two reverse names, so count them without assuming a
    # synthetic generic relation.
    from .models import TransportAssignment
    for row in rows.values():
        if row["morning"]:
            row["morning_count"] = TransportAssignment.objects.filter(is_active=True, morning_trip=row["morning"]).count()
        if row["return"]:
            row["return_count"] = TransportAssignment.objects.filter(is_active=True, return_trip=row["return"]).count()
    trip_rows = sorted(rows.values(), key=lambda r: (r["service_date"], r["route"].name, r["driver"].name, r["sequence"]), reverse=True)

    return render(
        request,
        "transport/trips/list.html",
        {
            "trips": trips,
            "trip_rows": trip_rows,
            "school": school,
        },
    )


@login_required
def trip_create(request):
    _require_management(request.user)

    from django.core.exceptions import ValidationError
    from .forms import TransportTripForm
    from .services import create_trip

    school = _school_for_user(request.user)

    if request.method == "POST":
        form = TransportTripForm(request.POST, school=school)

        if form.is_valid():
            try:
                create_trip(
                    school=school,
                    route=form.cleaned_data["route"],
                    driver=form.cleaned_data["driver"],
                    service_date=form.cleaned_data["service_date"],
                    direction=form.cleaned_data["direction"],
                    sequence=form.cleaned_data["sequence"],
                    vehicle_type=form.cleaned_data["vehicle_type"],
                    vehicle_description=form.cleaned_data[
                        "vehicle_description"
                    ],
                )
            except ValidationError as exc:
                if hasattr(exc, "message_dict"):
                    for field, errors in exc.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
                else:
                    for error in exc.messages:
                        form.add_error(None, error)
            else:
                messages.success(
                    request,
                    "تم إنشاء الرحلة بنجاح.",
                )
                return redirect("transport:trip-list")
    else:
        form = TransportTripForm(school=school)

    return render(
        request,
        "transport/trips/form.html",
        {
            "form": form,
            "title": "إضافة رحلة",
            "school": school,
        },
    )


@login_required
def trip_edit(request, pk):
    _require_management(request.user)

    from django.core.exceptions import ValidationError
    from django.shortcuts import get_object_or_404
    from .forms import TransportTripForm
    from .models import TransportTrip
    from .services import update_trip

    school = _school_for_user(request.user)

    trip = get_object_or_404(
        TransportTrip.objects.select_related("route", "driver"),
        pk=pk,
        school=school,
    )

    if request.method == "POST":
        form = TransportTripForm(
            request.POST,
            instance=trip,
            school=school,
        )

        if form.is_valid():
            try:
                update_trip(
                    trip=trip,
                    route=form.cleaned_data["route"],
                    driver=form.cleaned_data["driver"],
                    service_date=form.cleaned_data["service_date"],
                    direction=form.cleaned_data["direction"],
                    sequence=form.cleaned_data["sequence"],
                    vehicle_type=form.cleaned_data["vehicle_type"],
                    vehicle_description=form.cleaned_data[
                        "vehicle_description"
                    ],
                )
            except ValidationError as exc:
                if hasattr(exc, "message_dict"):
                    for field, errors in exc.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
                else:
                    for error in exc.messages:
                        form.add_error(None, error)
            else:
                messages.success(
                    request,
                    "تم تحديث الرحلة بنجاح.",
                )
                return redirect("transport:trip-list")
    else:
        form = TransportTripForm(
            instance=trip,
            school=school,
        )

    return render(
        request,
        "transport/trips/form.html",
        {
            "form": form,
            "title": "تعديل الرحلة",
            "trip": trip,
            "school": school,
        },
    )


# ============================================================
# Canonical Student Transport Subscription Management
# ============================================================

@login_required
def subscription_list(request):
    _require_management(request.user)
    school = _school_for_user(request.user)
    query = request.GET.get("q", "").strip()
    registrations = (
        StudentRegistration.objects
        .filter(school=school, student__isnull=False)
        .select_related("student", "transport_route", "grade")
        .order_by("student__full_name", "pk")
    )
    if query:
        from django.db.models import Q
        registrations = registrations.filter(
            Q(student__full_name__icontains=query)
            | Q(student__student_number__icontains=query)
            | Q(registration_number__icontains=query)
        )
    return render(request, "transport/subscriptions/list.html", {
        "registrations": registrations,
        "query": query,
        "school": school,
    })


@login_required
def subscription_edit(request, pk):
    _require_management(request.user)
    school = _school_for_user(request.user)
    registration = get_object_or_404(
        StudentRegistration.objects.select_related("student", "transport_route", "invoice"),
        pk=pk, school=school, student__isnull=False,
    )
    if request.method == "POST":
        form = TransportSubscriptionForm(request.POST, school=school, selected_registration_id=registration.pk)
        if form.is_valid():
            from django.core.exceptions import ValidationError
            from .subscription_services import update_transport_subscription
            try:
                update_transport_subscription(
                    registration=registration,
                    transport_route=form.cleaned_data["transport_route"],
                    transport_type=form.cleaned_data["transport_type"],
                    school=school,
                    user=request.user,
                )
            except ValidationError as exc:
                for error in exc.messages:
                    form.add_error(None, error)
            else:
                messages.success(request, "تم تحديث اشتراك الطالب بالمواصلات والرسوم المرتبطة به.")
                return redirect("transport:subscription-list")
    else:
        form = TransportSubscriptionForm(school=school, selected_registration_id=registration.pk)
    return render(request, "transport/subscriptions/form.html", {
        "form": form,
        "registration": registration,
        "title": "إدارة اشتراك الطالب بالمواصلات",
        "school": school,
    })



# ============================================================
# Transport Family Location Readiness
# ============================================================

@login_required
def family_location_list(request):
    """Management view of canonical transport families missing/holding a location."""
    _require_management(request.user)
    from parent_portal.models import FamilyStudent
    from .models import TransportFamilyLocation

    school = _school_for_user(request.user)
    registrations = (
        StudentRegistration.objects
        .filter(
            school=school,
            student__isnull=False,
            transport_route__isnull=False,
            transport_type__in=("go", "return", "both"),
        )
        .select_related("student", "transport_route")
        .order_by("student__full_name", "pk")
    )
    rows=[]
    seen=set()
    for reg in registrations:
        family_id=(FamilyStudent.objects.filter(student_id=reg.student_id, is_active=True).values_list("family_id", flat=True).first())
        if not family_id or family_id in seen:
            continue
        seen.add(family_id)
        family_link = FamilyStudent.objects.select_related("family").filter(family_id=family_id, is_active=True).first()
        if not family_link:
            continue
        family = family_link.family
        location = getattr(family, "transport_location", None)
        rows.append({"family": family, "location": location, "registration": reg, "extra_students": max(0, FamilyStudent.objects.filter(family_id=family_id, is_active=True).values("student_id").distinct().count() - 1)})
    return render(request, "transport/family_locations/list.html", {"rows": rows, "school": school})


@login_required
def family_location_edit(request, family_id):
    """Management editor for the single canonical transport location of a family."""
    _require_management(request.user)
    from parent_portal.models import Family, FamilyStudent

    school = _school_for_user(request.user)
    family = get_object_or_404(Family, pk=family_id, school=school, is_active=True)

    transport_student_ids = set(
        StudentRegistration.objects.filter(
            school=school,
            student__isnull=False,
            transport_route__isnull=False,
            transport_type__in=("go", "return", "both"),
        ).values_list("student_id", flat=True)
    )
    family_student_ids = set(
        FamilyStudent.objects.filter(
            family=family, is_active=True, student_id__in=transport_student_ids
        ).values_list("student_id", flat=True)
    )
    if not family_student_ids:
        raise PermissionDenied

    location = getattr(family, "transport_location", None)
    form = TransportFamilyLocationForm(request.POST or None, instance=location)
    if request.method == "POST" and form.is_valid():
        from .services import save_family_location
        try:
            save_family_location(
                family=family,
                label=form.cleaned_data["label"],
                address=form.cleaned_data["address"],
                latitude=form.cleaned_data["latitude"],
                longitude=form.cleaned_data["longitude"],
            )
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
        else:
            messages.success(request, "تم حفظ موقع الأبناء وتحديث الجولات تلقائيًا، وتم إشعار الإدارة والسائق المتأثر.")
            return redirect("transport:family-location-list")

    registrations = (
        StudentRegistration.objects.filter(
            school=school, student_id__in=family_student_ids,
            transport_route__isnull=False, transport_type__in=("go", "return", "both"),
        ).select_related("student", "transport_route").order_by("student__full_name", "pk")
    )
    return render(request, "transport/family_locations/form.html", {
        "family": family, "location": location, "form": form,
        "registrations": registrations, "school": school,
    })


@login_required
@require_POST
def request_missing_family_locations(request):
    """Send one deduplicated notification to each transport family without coordinates."""
    _require_management(request.user)
    from parent_portal.models import FamilyStudent
    from .models import TransportFamilyLocation
    from enterprise_ops.services import notify
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    school = _school_for_user(request.user)
    transport_student_ids = set(
        StudentRegistration.objects.filter(
            school=school,
            student__isnull=False,
            transport_route__isnull=False,
            transport_type__in=("go", "return", "both"),
        ).values_list("student_id", flat=True)
    )
    family_ids = set(
        FamilyStudent.objects.filter(
            family__school=school,
            family__is_active=True,
            is_active=True,
            student_id__in=transport_student_ids,
        ).values_list("family_id", flat=True)
    )
    existing = set(
        TransportFamilyLocation.objects.filter(
            family_id__in=family_ids,
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).values_list("family_id", flat=True)
    )
    sent=0
    for family in FamilyStudent.objects.filter(family_id__in=family_ids-existing).values("family_id", "family__user_id").distinct():
        user_id=family["family__user_id"]
        if not user_id:
            continue
        notify(
            get_user_model().objects.get(pk=user_id),
            "مطلوب تحديث موقع المواصلات",
            "يرجى فتح بوابة المواصلات وحفظ موقع استلام ونزول الأسرة بدقة لتتمكن المدرسة من تخطيط المحطات وتتبع الرحلة.",
            level="warning",
            link=reverse("transport:transport-dashboard"),
            event_key=f"transport-missing-location:{family['family_id']}",
        )
        sent += 1
    messages.success(request, f"تم إرسال طلب الموقع إلى {sent} أسرة تحتاج إحداثيات.")
    return redirect("transport:family-location-list")


@login_required
@require_POST
def prepare_today(request):
    """Explicit management action for the daily round preparation gateway."""
    _require_management(request.user)
    school = _school_for_user(request.user)
    if school is None:
        messages.error(request, "لا توجد مدرسة مرتبطة بحساب المستخدم.")
        return redirect("transport:transport-dashboard")

    try:
        result = prepare_today_operations(school=school)
    except Exception as exc:
        messages.error(request, f"تعذر تجهيز جولات اليوم: {exc}")
    else:
        warnings = result.get("warnings") or []
        messages.success(
            request,
            f"تم تجهيز جولات اليوم: إنشاء {result.get('created', 0)}، تحديث {result.get('updated', 0)}، وإعادة بناء {result.get('rebuilt', 0)} جولة."
        )
        for warning in warnings:
            messages.warning(request, warning)
    return redirect("transport:transport-dashboard")


# ============================================================
# Transport Planning Groups
# ============================================================

@login_required
@require_http_methods(["GET", "POST"])
def group_list(request):
    """Single management workspace for establishment, approval and manual grouping."""
    _require_management(request.user)
    from .models import TransportGroup, TransportGroupMember, TransportDriver
    school=_school_for_user(request.user)

    if request.method == "POST":
        action=request.POST.get("action")
        try:
            if action == "establish":
                result=establish_stable_groups(school=school)
                messages.success(request, f"تم تأسيس {len(result['created'])} مجموعة جغرافية مستقرة. المجموعات المثبتة لم تُمس.")
            elif action == "assign_driver":
                group=get_object_or_404(TransportGroup, pk=request.POST.get("group_id"), route__school=school, is_stable=True)
                driver_id=(request.POST.get("driver_id") or "").strip()
                if driver_id:
                    driver=get_object_or_404(TransportDriver, pk=driver_id, user__profile__school=school, is_active=True)
                    assign_group_driver(group=group, driver=driver)
                    messages.success(request, f"تم اعتماد المجموعة وإسنادها للسائق {driver.name} وتحديث الجولات تلقائيًا.")
                else:
                    approve_group(group=group)
                    messages.success(request, "تم اعتماد المجموعة وتثبيتها دون إسناد سائق حاليًا.")
            elif action == "move":
                ids=[int(x) for x in request.POST.getlist("registration_ids") if str(x).isdigit()]
                from admissions.models import StudentRegistration
                regs=list(StudentRegistration.objects.filter(pk__in=ids, school=school, transport_type__in=("go","return","both"), transport_route__isnull=False))
                target=None
                target_id=request.POST.get("target_group_id")
                if target_id:
                    target=get_object_or_404(TransportGroup, pk=target_id, route__school=school, is_stable=True)
                move_registrations_to_group(registrations=regs, target_group=target, new_group_name=request.POST.get("new_group_name"))
                messages.success(request, "تم حفظ التعديل اليدوي وتثبيت المجموعة/المجموعات المتأثرة.")
            else:
                messages.error(request, "عملية غير معروفة.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("transport:group-list")

    groups=list(TransportGroup.objects.filter(
        route__school=school, is_stable=True
    ).select_related("route","assigned_driver").prefetch_related("members__registration__student").order_by("route__name","name","pk"))
    drivers=TransportDriver.objects.filter(user__profile__school=school,is_active=True).order_by("name")
    target_groups=groups
    return render(request,"transport/groups/list.html",{
        "groups":groups,"drivers":drivers,"target_groups":target_groups,"school":school,
    })


# ============================================================
# Student Transport Assignment Management
# ============================================================

@login_required
def assignment_list(request):
    _require_management(request.user)

    from .models import TransportAssignment

    school = _school_for_user(request.user)

    assignments = (
        TransportAssignment.objects
        .filter(
            registration__school=school,
            is_active=True,
        )
        .select_related(
            "registration__student",
            "registration__transport_route",
            "driver",
            "morning_trip",
            "return_trip",
        )
        .order_by(
            "registration__transport_route__name",
            "registration__student__full_name",
        )
    )

    return render(
        request,
        "transport/assignments/list.html",
        {
            "assignments": assignments,
            "school": school,
        },
    )


@login_required
def assignment_create(request):
    _require_management(request.user)

    from django.core.exceptions import ValidationError
    from .forms import TransportAssignmentForm
    from .services import assign_registration

    school = _school_for_user(request.user)

    if request.method == "POST":
        form = TransportAssignmentForm(
            request.POST,
            school=school,
        )

        if form.is_valid():
            try:
                assignment = assign_registration(
                    registration=form.cleaned_data["registration"],
                    morning_trip=form.cleaned_data["morning_trip"],
                    return_trip=form.cleaned_data["return_trip"],
                )
            except ValidationError as exc:
                if hasattr(exc, "message_dict"):
                    for field, errors in exc.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
                else:
                    for error in exc.messages:
                        form.add_error(None, error)
            else:
                messages.success(
                    request,
                    "تم تعيين الطالب على الرحلة بنجاح.",
                )
                return redirect("transport:assignment-list")
    else:
        form = TransportAssignmentForm(
            school=school,
            selected_registration_id=request.GET.get("registration"),
        )

    return render(
        request,
        "transport/assignments/form.html",
        {
            "form": form,
            "title": "تعيين طالب على رحلة",
            "school": school,
        },
    )


@login_required
def assignment_deactivate(request, pk):
    _require_management(request.user)

    from django.shortcuts import get_object_or_404
    from .models import TransportAssignment
    from .services import deactivate_assignment

    if request.method != "POST":
        return redirect("transport:assignment-list")

    school = _school_for_user(request.user)

    assignment = get_object_or_404(
        TransportAssignment.objects.select_related(
            "registration__student"
        ),
        pk=pk,
        registration__school=school,
        is_active=True,
    )

    deactivate_assignment(assignment)

    messages.success(
        request,
        "تم إلغاء تعيين الطالب من الرحلات.",
    )

    return redirect("transport:assignment-list")

# ============================================================
# OPAL TRANSPORT — EXECUTION / FAMILY / LIVE TRACKING
# ============================================================


def _transport_trip_payload(trip, *, allowed_family_ids=None):
    """Serialize a trip defensively for management, driver and parent maps."""
    from parent_portal.models import FamilyStudent
    from .models import TransportAssignment, TransportFamilyLocation, TransportGPSPoint, TransportStudentEvent
    from .services import transport_registrations_for_trip

    if trip is None:
        return None

    registrations = transport_registrations_for_trip(trip=trip)
    registration_ids = {getattr(reg, "pk", None) for reg in registrations}
    student_ids = {getattr(getattr(reg, "student", None), "pk", None) for reg in registrations}
    student_ids.discard(None)

    family_rows = FamilyStudent.objects.filter(
        student_id__in=student_ids,
        is_active=True,
    ).values("student_id", "family_id")
    family_by_student = {}
    for row in family_rows:
        family_by_student.setdefault(row["student_id"], row["family_id"])

    events = list(
        TransportStudentEvent.objects
        .filter(trip=trip, registration_id__in=registration_ids)
        .order_by("occurred_at", "pk")
    )
    events_by_registration = {}
    for event in events:
        events_by_registration.setdefault(event.registration_id, []).append(event)

    student_rows = []
    family_ids = set()
    for registration in registrations:
        student = getattr(registration, "student", None)
        if student is None:
            continue
        family_id = family_by_student.get(student.pk)
        if allowed_family_ids is not None and family_id not in allowed_family_ids:
            continue
        if family_id:
            family_ids.add(family_id)

        student_events = events_by_registration.get(registration.pk, [])
        arrived = next((e for e in student_events if e.event_type == TransportStudentEvent.ARRIVED), None)
        boarded = next((e for e in student_events if e.event_type == TransportStudentEvent.BOARDED), None)
        dropped = next((e for e in student_events if e.event_type == TransportStudentEvent.DROPPED_OFF), None)
        missed = next((e for e in student_events if e.event_type == TransportStudentEvent.MISSED), None)

        if trip.direction == TransportTrip.MORNING:
            if boarded:
                status_key = "boarded"
            elif missed:
                status_key = "missed"
            else:
                status_key = "pending"
            completion_event = boarded
        else:
            if dropped:
                status_key = "dropped_off"
            elif boarded:
                status_key = "on_bus"
            elif missed:
                status_key = "missed"
            else:
                status_key = "pending"
            completion_event = dropped

        wait_seconds = None
        if arrived and completion_event:
            wait_seconds = max(0, int((completion_event.occurred_at - arrived.occurred_at).total_seconds()))

        labels = {
            "boarded": "صعد",
            "dropped_off": "تم التوصيل",
            "on_bus": "داخل الحافلة",
            "missed": "لم يصعد/لم يستلم",
            "pending": "متبقٍ",
        }
        student_rows.append({
            "id": student.pk,
            "name": student.full_name,
            "registration_id": registration.pk,
            "family_id": family_id,
            "status": status_key,
            "status_label": labels[status_key],
            "arrived_at": arrived.occurred_at.isoformat() if arrived else None,
            "boarded_at": boarded.occurred_at.isoformat() if boarded else None,
            "dropped_off_at": dropped.occurred_at.isoformat() if dropped else None,
            "wait_seconds": wait_seconds,
        })

    siblings_by_family = {}
    if family_ids:
        for link in (
            FamilyStudent.objects
            .filter(family_id__in=family_ids, is_active=True)
            .select_related("student")
            .order_by("student__full_name")
        ):
            siblings_by_family.setdefault(link.family_id, []).append(link.student.full_name)

    persisted_stops = list(trip.stops.all())
    stops = []
    visible_family_ids = set(family_ids)
    if allowed_family_ids is None:
        visible_family_ids = set(
            FamilyStudent.objects.filter(student_id__in=student_ids, is_active=True)
            .values_list("family_id", flat=True)
        )

    for stop in persisted_stops:
        if allowed_family_ids is not None and stop.family_id not in allowed_family_ids:
            continue
        dwell_seconds = None
        if stop.arrived_at and stop.departed_at:
            dwell_seconds = max(0, int((stop.departed_at - stop.arrived_at).total_seconds()))
        stops.append({
            "id": stop.pk,
            "sequence": stop.sequence,
            "family_id": stop.family_id,
            "label": stop.label,
            "address": stop.address,
            "latitude": float(stop.latitude),
            "longitude": float(stop.longitude),
            "arrived_at": stop.arrived_at.isoformat() if stop.arrived_at else None,
            "departed_at": stop.departed_at.isoformat() if stop.departed_at else None,
            "dwell_seconds": dwell_seconds,
            "siblings": siblings_by_family.get(stop.family_id, []),
            "virtual": False,
        })

    # Read-only fallback: a missing historical stop snapshot must never make a
    # parent map or manager/driver JSON payload empty. Persistent stops remain
    # authoritative for operational buttons; this fallback supplies markers.
    persisted_family_ids = {x["family_id"] for x in stops}
    missing_family_ids = visible_family_ids - persisted_family_ids
    if missing_family_ids:
        locations = {
            loc.family_id: loc
            for loc in TransportFamilyLocation.objects.filter(
                family_id__in=missing_family_ids,
                is_active=True,
                latitude__isnull=False,
                longitude__isnull=False,
            )
        }
        next_sequence = max((x["sequence"] for x in stops), default=0) + 1
        for family_id in sorted(locations):
            loc = locations[family_id]
            stops.append({
                "id": None,
                "sequence": next_sequence,
                "family_id": family_id,
                "label": loc.label or f"موقع الأسرة #{family_id}",
                "address": loc.address or "",
                "latitude": float(loc.latitude),
                "longitude": float(loc.longitude),
                "arrived_at": None,
                "departed_at": None,
                "dwell_seconds": None,
                "siblings": siblings_by_family.get(family_id, []),
                "virtual": True,
            })
            next_sequence += 1

    latest = TransportGPSPoint.objects.filter(trip=trip).order_by("-recorded_at").first()
    gps_points = list(
        TransportGPSPoint.objects.filter(trip=trip)
        .order_by("recorded_at")
        .values("latitude", "longitude", "recorded_at")[:500]
    )

    next_stop = next((stop for stop in stops if not stop["arrived_at"] or not stop["departed_at"]), None)

    duration_seconds = None
    if trip.started_at:
        end = trip.finished_at or timezone.now()
        duration_seconds = max(0, int((end - trip.started_at).total_seconds()))

    if trip.direction == TransportTrip.MORNING:
        completed_students = [row for row in student_rows if row["status"] == "boarded"]
        remaining_students = [row for row in student_rows if row["status"] in {"pending", "missed"}]
    else:
        completed_students = [row for row in student_rows if row["status"] == "dropped_off"]
        remaining_students = [row for row in student_rows if row["status"] == "on_bus" or row["status"] in {"pending", "missed"}]

    return {
        "id": trip.pk,
        "route": getattr(trip.route, "name", ""),
        "driver": getattr(trip.driver, "name", ""),
        "driver_phone": getattr(trip.driver, "phone", ""),
        "direction": trip.direction,
        "direction_label": trip.get_direction_display(),
        "sequence": trip.sequence,
        "service_date": trip.service_date.isoformat(),
        "status": trip.status,
        "started_at": trip.started_at.isoformat() if trip.started_at else None,
        "finished_at": trip.finished_at.isoformat() if trip.finished_at else None,
        "duration_seconds": duration_seconds,
        "latest": (
            {
                "latitude": float(latest.latitude),
                "longitude": float(latest.longitude),
                "accuracy_m": float(latest.accuracy_m) if latest.accuracy_m is not None else None,
                "speed_kmh": float(latest.speed_kmh) if latest.speed_kmh is not None else None,
                "recorded_at": latest.recorded_at.isoformat(),
            }
            if latest else None
        ),
        "gps": [
            {
                "latitude": float(point["latitude"]),
                "longitude": float(point["longitude"]),
                "recorded_at": point["recorded_at"].isoformat(),
            }
            for point in gps_points
        ],
        "stops": stops,
        "students": student_rows,
        "completed_students": completed_students,
        "remaining_students": remaining_students,
        "completed_count": len(completed_students),
        "remaining_count": len(remaining_students),
        "next_stop": next_stop,
    }


@login_required
def driver_transport_dashboard(request):
    from .models import TransportDriver, TransportTrip

    driver = get_object_or_404(
        TransportDriver,
        user=request.user,
        is_active=True,
    )
    from .services import driver_operational_trips
    trips = driver_operational_trips(driver)
    active_trip = next(
        (trip for trip in trips if trip.status == TransportTrip.ACTIVE),
        None,
    )

    # Show the driver's stop map for the active trip, or for the next planned
    # trip before it starts. This guarantees that the driver can see all station
    # points on the map instead of seeing an empty workspace until activation.
    map_trip = active_trip or next((trip for trip in trips if trip.status == TransportTrip.PLANNED), None)
    map_warning = ""
    if map_trip is not None and not map_trip.stops.exists():
        try:
            from .services import bootstrap_trip_stops_for_map
            bootstrap_result = bootstrap_trip_stops_for_map(trip=map_trip)
            if bootstrap_result.get("missing_locations"):
                map_warning = (
                    f"تعذر إظهار بعض المحطات لأن {bootstrap_result['missing_locations']} أسرة "
                    "لا تملك إحداثيات محفوظة."
                )
        except Exception as exc:
            map_warning = "تعذر تجهيز نقاط المحطات تلقائيًا؛ راجع مواقع الأسر في إدارة المواصلات."
    map_trip_payload = _transport_trip_payload(map_trip) if map_trip else None
    if map_trip is not None and map_trip_payload is not None and not map_trip_payload.get("stops"):
        # One last read-only recovery path for trips whose stop snapshot is
        # still empty after the bootstrap attempt. The payload stays valid and
        # the warning tells the driver why the map has no points.
        if not map_warning:
            map_warning = "لا توجد نقاط محطات قابلة للرسم لهذه الجولة؛ تحقق من ربط الطلاب بمواقع الأسر."

    return render(
        request,
        "transport/driver/dashboard.html",
        {
            "driver": driver,
            "trips": trips,
            "active_trip": active_trip,
            "map_trip": map_trip,
            "map_trip_payload": map_trip_payload,
            "map_warning": map_warning,
            "impersonating_management": bool(
                request.session.get(TRANSPORT_DRIVER_IMPERSONATOR_SESSION_KEY)
                and request.session.get(TRANSPORT_DRIVER_IMPERSONATED_SESSION_KEY) == request.user.pk
            ),
            "management_return_user_id": request.session.get(
                TRANSPORT_DRIVER_IMPERSONATOR_SESSION_KEY
            ),
        },
    )


@login_required
@require_POST
def driver_start_trip(request, pk):
    from django.core.exceptions import ValidationError
    from .models import TransportTrip
    from .services import rebuild_trip_stops, start_trip

    trip = get_object_or_404(
        TransportTrip,
        pk=pk,
        driver__user=request.user,
    )
    try:
        # Planned stops are rebuilt immediately before a trip starts so a
        # changed family location is reflected in the historical snapshot.
        rebuild_trip_stops(trip=trip)
        start_trip(trip=trip, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "تم بدء الرحلة وتثبيت محطات التوقف.")
    return redirect("transport:transport-dashboard")


@login_required
@require_POST
def driver_finish_trip(request, pk):
    from django.core.exceptions import ValidationError
    from .models import TransportTrip
    from .services import finish_trip

    trip = get_object_or_404(
        TransportTrip,
        pk=pk,
        driver__user=request.user,
    )
    try:
        finish_trip(trip=trip, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "تم إنهاء الرحلة وحفظ سجلها.")
    return redirect("transport:transport-dashboard")


@login_required
@require_POST
def trip_rebuild_stops(request, pk):
    _require_management(request.user)
    from django.core.exceptions import ValidationError
    from .models import TransportTrip
    from .services import rebuild_trip_stops

    school = _school_for_user(request.user)
    trip = get_object_or_404(
        TransportTrip,
        pk=pk,
        school=school,
    )
    try:
        result = rebuild_trip_stops(trip=trip)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(
            request,
            f"تم تحديث المحطات: {len(result['stops'])} محطة، "
            f"{result['groups_created']} مجموعة. "
            f"العائلات التي لا تملك موقعًا: {result['missing_locations']}.",
        )
    return redirect("transport:trip-list")


@login_required
@require_POST
def trip_stop_arrive(request, pk):
    from django.core.exceptions import ValidationError
    from .models import TransportTripStop
    from .services import mark_stop_arrived

    stop = get_object_or_404(
        TransportTripStop.objects.select_related("trip"),
        pk=pk,
        trip__driver__user=request.user,
    )
    try:
        mark_stop_arrived(stop=stop, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "تم تسجيل الوصول إلى المحطة.")
    return redirect("transport:transport-dashboard")


@login_required
@require_POST
def trip_stop_depart(request, pk):
    from django.core.exceptions import ValidationError
    from .models import TransportTripStop
    from .services import mark_stop_departed

    stop = get_object_or_404(
        TransportTripStop.objects.select_related("trip"),
        pk=pk,
        trip__driver__user=request.user,
    )
    try:
        mark_stop_departed(stop=stop, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "تم تسجيل المغادرة من المحطة.")
    return redirect("transport:transport-dashboard")


@login_required
def trip_detail(request, pk):
    _require_management(request.user)
    from .models import TransportTrip

    school = _school_for_user(request.user)
    trip = get_object_or_404(
        TransportTrip.objects.select_related("route", "driver", "planning_group"),
        pk=pk, school=school,
    )
    payload = _transport_trip_payload(trip)
    return render(
        request,
        "transport/trips/detail.html",
        {"trip": trip, "trip_payload": payload, "is_live": trip.status == TransportTrip.ACTIVE},
    )


@login_required
def manager_tracking(request):
    _require_management(request.user)
    from .services import active_trips_for_manager

    school = _school_for_user(request.user)
    trips = active_trips_for_manager(school)
    payload = []
    for trip in trips:
        try:
            payload.append(_transport_trip_payload(trip))
        except Exception:
            # One malformed historical trip must not take down the entire live map.
            payload.append({
                "id": trip.pk,
                "route": getattr(trip.route, "name", ""),
                "driver": getattr(trip.driver, "name", ""),
                "driver_phone": getattr(trip.driver, "phone", ""),
                "direction": trip.direction,
                "direction_label": trip.get_direction_display(),
                "sequence": trip.sequence,
                "service_date": trip.service_date.isoformat(),
                "status": trip.status,
                "started_at": trip.started_at.isoformat() if trip.started_at else None,
                "finished_at": trip.finished_at.isoformat() if trip.finished_at else None,
                "duration_seconds": None,
                "latest": None,
                "gps": [],
                "stops": [],
                "students": [],
                "completed_students": [],
                "remaining_students": [],
                "completed_count": 0,
                "remaining_count": 0,
                "next_stop": None,
            })
    return render(
        request,
        "transport/tracking/manager.html",
        {
            "trips": trips,
            "tracking_payload": payload,
        },
    )


@login_required
@require_GET
def tracking_api(request):
    """Role-scoped live transport data endpoint."""
    from .models import TransportTrip
    from .services import active_trip_for_parent, active_trips_for_manager

    school = _school_for_user(request.user)
    role_is_manager = is_management_user(request.user)

    if role_is_manager:
        trips = active_trips_for_manager(school)
        payload = [_transport_trip_payload(trip) for trip in trips]
    else:
        allowed_family_ids = set()
        try:
            family_id = request.user.family_account.pk
            allowed_family_ids.add(family_id)
        except Exception:
            family_id = None

        trip = None
        try:
            trip = active_trip_for_parent(request.user)
        except Exception:
            trip = None

        if trip is None:
            try:
                driver = request.user.transport_driver
            except Exception:
                driver = None
            if driver:
                trip = (
                    TransportTrip.objects
                    .filter(
                        driver=driver,
                        status=TransportTrip.ACTIVE,
                    )
                    .select_related("route", "driver")
                    .prefetch_related("stops")
                    .first()
                )

        payload = (
            [
                _transport_trip_payload(
                    trip,
                    allowed_family_ids=(
                        allowed_family_ids
                        if family_id is not None
                        else None
                    ),
                )
            ]
            if trip
            else []
        )

    return JsonResponse(
        {
            "today": timezone.localdate().isoformat(),
            "trips": payload,
        }
    )


@login_required
@require_POST
def driver_gps_ingest(request, pk):
    from django.core.exceptions import ValidationError
    from .models import TransportTrip
    from .services import record_gps_point

    trip = get_object_or_404(
        TransportTrip,
        pk=pk,
        driver__user=request.user,
        status=TransportTrip.ACTIVE,
    )
    try:
        point = record_gps_point(
            trip=trip,
            user=request.user,
            latitude=request.POST.get("latitude"),
            longitude=request.POST.get("longitude"),
            accuracy_m=request.POST.get("accuracy_m"),
            speed_kmh=request.POST.get("speed_kmh"),
        )
    except ValidationError as exc:
        return JsonResponse(
            {"ok": False, "errors": exc.messages},
            status=400,
        )
    return JsonResponse(
        {
            "ok": True,
            "recorded_at": point.recorded_at.isoformat(),
        }
    )


@parent_required
def parent_transport_dashboard(request):
    from parent_portal.workflow import family_for_user

    family = family_for_user(request.user)
    if family is None:
        return render(request, "parent_portal/no_profile.html")

    location = getattr(family, "transport_location", None)
    form = TransportFamilyLocationForm(
        request.POST or None,
        instance=location,
    )

    if request.method == "POST":
        from .services import save_family_location
        if form.is_valid():
            try:
                save_family_location(
                    family=family,
                    label=form.cleaned_data["label"],
                    address=form.cleaned_data["address"],
                    latitude=form.cleaned_data["latitude"],
                    longitude=form.cleaned_data["longitude"],
                )
            except ValidationError as exc:
                for error in exc.messages:
                    form.add_error(None, error)
            else:
                messages.success(
                    request,
                    "تم حفظ موقع استلام ونزول الأسرة، وسيُستخدم لجميع الأبناء.",
                )
                return redirect("transport:parent-transport-dashboard")

    from .services import active_trip_for_parent
    active_trip = active_trip_for_parent(request.user)
    active_trip_payload = (
        _transport_trip_payload(
            active_trip,
            allowed_family_ids={family.pk},
        )
        if active_trip
        else None
    )

    raw_phone = str(active_trip.driver.phone if active_trip else "").strip()
    whatsapp_phone = re.sub(r"\D", "", raw_phone)
    if whatsapp_phone.startswith("00"):
        whatsapp_phone = whatsapp_phone[2:]
    elif whatsapp_phone.startswith("0"):
        whatsapp_phone = "962" + whatsapp_phone[1:]

    return render(
        request,
        "transport/parent/dashboard.html",
        {
            "family": family,
            "form": form,
            "active_trip": active_trip,
            "active_trip_payload": active_trip_payload,
            "whatsapp_phone": whatsapp_phone,
            "tracking_enabled": active_trip is not None,
        },
    )
