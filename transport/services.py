from __future__ import annotations

import secrets
import string

from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import Role, UserProfile

from .models import TransportDriver


def _random_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _new_username():
    User = get_user_model()

    while True:
        username = "driver_" + secrets.token_hex(5)
        if not User.objects.filter(username=username).exists():
            return username


@transaction.atomic
def create_driver(*, school, name, phone):
    """
    Create the driver's Django identity, OPAL profile and transport profile
    as one atomic operation.

    Returns:
        (driver, username, temporary_password)
    """
    User = get_user_model()

    role = Role.objects.get(code="driver", is_active=True)

    username = _new_username()
    temporary_password = _random_password()

    user = User.objects.create_user(
        username=username,
        password=temporary_password,
        first_name=name,
    )

    UserProfile.objects.create(
        user=user,
        school=school,
        role=role,
        full_name=name,
        phone=phone,
        is_school_user=True,
    )

    driver = TransportDriver.objects.create(
        user=user,
        name=name,
        phone=phone,
        is_active=True,
    )

    return driver, username, temporary_password


@transaction.atomic
def update_driver(*, driver, name, phone):
    driver.name = name
    driver.phone = phone
    driver.save(update_fields=["name", "phone", "updated_at"])

    try:
        profile = driver.user.profile
    except Exception:
        profile = None

    if profile is not None:
        profile.full_name = name
        profile.phone = phone
        profile.save(update_fields=["full_name", "phone"])

    driver.user.first_name = name
    driver.user.save(update_fields=["first_name"])

    return driver


# ============================================================
# TRANSPORT TRIP / ASSIGNMENT SERVICES
# ============================================================

from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q


def _validate_transport_school(*, school, route=None, driver=None):
    """Ensure transport objects belong to the same school."""

    if route is not None and route.school_id != school.id:
        raise ValidationError("المسار لا يتبع المدرسة المحددة.")

    if driver is not None:
        try:
            driver_school_id = driver.user.profile.school_id
        except Exception:
            driver_school_id = None

        if driver_school_id != school.id:
            raise ValidationError("السائق لا يتبع المدرسة المحددة.")


@transaction.atomic
def create_trip(
    *,
    school,
    route,
    driver,
    service_date,
    direction,
    sequence,
    vehicle_type,
    vehicle_description="",
):
    """
    Create one operational transport trip.

    A driver may have multiple trips on the same day, but never
    more than one ACTIVE trip at the same time.
    """

    from .models import TransportTrip

    _validate_transport_school(
        school=school,
        route=route,
        driver=driver,
    )

    if route is not None and not route.is_active:
        raise ValidationError(
            "لا يمكن استخدام مسار غير نشط."
        )

    if driver is not None and not driver.is_active:
        raise ValidationError(
            "لا يمكن استخدام سائق غير نشط."
        )

    valid_directions = {
        value for value, _label in TransportTrip.DIRECTION_CHOICES
    }

    if direction not in valid_directions:
        raise ValidationError("اتجاه الرحلة غير صالح.")

    valid_vehicle_types = {
        value for value, _label in TransportTrip.VEHICLE_TYPE_CHOICES
    }

    if vehicle_type not in valid_vehicle_types:
        raise ValidationError("نوع المركبة غير صالح.")

    if not isinstance(service_date, date):
        raise ValidationError("تاريخ التشغيل غير صالح.")

    try:
        sequence = int(sequence)
    except (TypeError, ValueError):
        raise ValidationError("رقم الرحلة غير صالح.")

    if sequence < 1:
        raise ValidationError("رقم الرحلة يجب أن يبدأ من 1.")

    if not str(vehicle_description or "").strip():
        vehicle_description = ""

    if TransportTrip.objects.filter(
        driver=driver,
        service_date=service_date,
        direction=direction,
        sequence=sequence,
    ).exists():
        raise ValidationError(
            "توجد رحلة بهذا الرقم للسائق نفسه في هذا اليوم والاتجاه."
        )

    trip = TransportTrip.objects.create(
        school=school,
        route=route,
        driver=driver,
        service_date=service_date,
        direction=direction,
        sequence=sequence,
        vehicle_type=vehicle_type,
        vehicle_description=vehicle_description.strip(),
        status="planned",
    )

    return trip


@transaction.atomic
def update_trip(
    *,
    trip,
    route,
    driver,
    service_date,
    direction,
    sequence,
    vehicle_type,
    vehicle_description="",
):
    """Update a planned trip without breaking active/completed trips."""

    from .models import TransportTrip

    if trip.status in {"active", "completed"}:
        raise ValidationError(
            "لا يمكن تعديل رحلة بدأت أو اكتملت."
        )

    school = trip.school

    _validate_transport_school(
        school=school,
        route=route,
        driver=driver,
    )

    if route is not None and not route.is_active:
        raise ValidationError(
            "لا يمكن استخدام مسار غير نشط."
        )

    if driver is not None and not driver.is_active:
        raise ValidationError(
            "لا يمكن استخدام سائق غير نشط."
        )

    valid_directions = {
        value for value, _label in TransportTrip.DIRECTION_CHOICES
    }

    if direction not in valid_directions:
        raise ValidationError("اتجاه الرحلة غير صالح.")

    valid_vehicle_types = {
        value for value, _label in TransportTrip.VEHICLE_TYPE_CHOICES
    }

    if vehicle_type not in valid_vehicle_types:
        raise ValidationError("نوع المركبة غير صالح.")

    try:
        sequence = int(sequence)
    except (TypeError, ValueError):
        raise ValidationError("رقم الرحلة غير صالح.")

    if sequence < 1:
        raise ValidationError("رقم الرحلة يجب أن يبدأ من 1.")

    duplicate = TransportTrip.objects.filter(
        driver=driver,
        service_date=service_date,
        direction=direction,
        sequence=sequence,
    ).exclude(pk=trip.pk).exists()

    if duplicate:
        raise ValidationError(
            "يوجد رقم رحلة مطابق للسائق نفسه في هذا اليوم والاتجاه."
        )

    trip.route = route
    trip.driver = driver
    trip.service_date = service_date
    trip.direction = direction
    trip.sequence = sequence
    trip.vehicle_type = vehicle_type
    trip.vehicle_description = str(
        vehicle_description or ""
    ).strip()

    trip.save(
        update_fields=[
            "route",
            "driver",
            "service_date",
            "direction",
            "sequence",
            "vehicle_type",
            "vehicle_description",
            "updated_at",
        ]
    )

    return trip


def _validate_trip_for_registration(*, registration, trip):
    """Validate school, route and direction compatibility."""

    if registration.school_id != trip.school_id:
        raise ValidationError(
            "تسجيل الطالب والرحلة لا يتبعان المدرسة نفسها."
        )

    registration_route_id = registration.transport_route_id

    if not registration_route_id:
        raise ValidationError(
            "الطالب لا يملك مسار مواصلات في التسجيل الرسمي."
        )

    if registration_route_id != trip.route_id:
        raise ValidationError(
            "مسار الطالب لا يطابق مسار الرحلة."
        )

    if trip.status in {"completed", "cancelled"}:
        raise ValidationError(
            "لا يمكن تعيين طالب إلى رحلة مكتملة أو ملغاة."
        )


def _validate_direction_for_transport_type(
    *,
    transport_type,
    morning_trip=None,
    return_trip=None,
):
    """Enforce go/return/both subscription semantics."""

    if transport_type == "none":
        raise ValidationError(
            "الطالب غير مشترك في خدمة المواصلات."
        )

    if transport_type == "go":
        if morning_trip is None or return_trip is not None:
            raise ValidationError(
                "اشتراك الذهاب فقط يجب أن يرتبط برحلة ذهاب واحدة فقط."
            )

    elif transport_type == "return":
        if return_trip is None or morning_trip is not None:
            raise ValidationError(
                "اشتراك العودة فقط يجب أن يرتبط برحلة عودة واحدة فقط."
            )

    elif transport_type == "both":
        if morning_trip is None or return_trip is None:
            raise ValidationError(
                "اشتراك الذهاب والعودة يجب أن يرتبط برحلة ذهاب ورحلة عودة."
            )

    else:
        raise ValidationError(
            "نوع اشتراك المواصلات غير معروف."
        )


def _validate_trip_direction(*, trip, expected):
    if trip.direction != expected:
        if expected == "morning":
            raise ValidationError(
                "رحلة الذهاب يجب أن تكون رحلة صباحية."
            )

        raise ValidationError(
            "رحلة العودة يجب أن تكون رحلة مسائية."
        )


def _validate_same_trip_context(*, morning_trip=None, return_trip=None):
    """Both directions must belong to the same school, route and date."""

    trips = [
        trip
        for trip in (morning_trip, return_trip)
        if trip is not None
    ]

    if not trips:
        raise ValidationError("لم يتم تحديد أي رحلة.")

    first = trips[0]

    for trip in trips[1:]:
        if trip.school_id != first.school_id:
            raise ValidationError(
                "رحلتا الطالب يجب أن تتبعا المدرسة نفسها."
            )

        if trip.route_id != first.route_id:
            raise ValidationError(
                "رحلتا الطالب يجب أن تكونا على المسار نفسه."
            )

        if trip.service_date != first.service_date:
            raise ValidationError(
                "رحلتا الذهاب والعودة يجب أن تكونا في يوم التشغيل نفسه."
            )


def _validate_student_not_already_assigned(
    *,
    registration,
    morning_trip=None,
    return_trip=None,
):
    """
    Prevent the same student from appearing in more than one
    morning or return trip for the same academic year.
    """

    from .models import TransportAssignment

    student_id = registration.student_id
    academic_year_id = registration.academic_year_id

    if not student_id:
        raise ValidationError(
            "التسجيل غير مرتبط بطالب رسمي."
        )

    existing = TransportAssignment.objects.filter(
        is_active=True,
        registration__student_id=student_id,
        registration__academic_year_id=academic_year_id,
    ).exclude(
        registration_id=registration.id,
    )

    if morning_trip is not None:
        if existing.filter(
            morning_trip__isnull=False,
        ).exists():
            raise ValidationError(
                "الطالب مرتبط مسبقًا برحلة ذهاب أخرى."
            )

    if return_trip is not None:
        if existing.filter(
            return_trip__isnull=False,
        ).exists():
            raise ValidationError(
                "الطالب مرتبط مسبقًا برحلة عودة أخرى."
            )


@transaction.atomic
def assign_registration(
    *,
    registration,
    morning_trip=None,
    return_trip=None,
):
    """
    Assign one official StudentRegistration to its operational trip(s).

    Rules:
      go     -> exactly one morning trip
      return -> exactly one return trip
      both   -> one morning + one return trip
               with the SAME driver
    """

    from .models import TransportAssignment

    transport_type = registration.transport_type

    _validate_direction_for_transport_type(
        transport_type=transport_type,
        morning_trip=morning_trip,
        return_trip=return_trip,
    )

    _validate_same_trip_context(
        morning_trip=morning_trip,
        return_trip=return_trip,
    )

    for trip in (
        morning_trip,
        return_trip,
    ):
        if trip is None:
            continue

        _validate_trip_for_registration(
            registration=registration,
            trip=trip,
        )

    if morning_trip is not None:
        _validate_trip_direction(
            trip=morning_trip,
            expected="morning",
        )

    if return_trip is not None:
        _validate_trip_direction(
            trip=return_trip,
            expected="return",
        )

    if (
        morning_trip is not None
        and return_trip is not None
        and morning_trip.driver_id != return_trip.driver_id
    ):
        raise ValidationError(
            "الطالب المشترك ذهابًا وعودة يجب أن يستخدم السائق نفسه في الاتجاهين."
        )

    _validate_student_not_already_assigned(
        registration=registration,
        morning_trip=morning_trip,
        return_trip=return_trip,
    )

    existing_assignment = (
        TransportAssignment.objects
        .select_for_update()
        .filter(registration=registration)
        .first()
    )

    if existing_assignment is not None:
        if existing_assignment.is_active:
            raise ValidationError(
                "هذا التسجيل مرتبط مسبقًا بتعيين مواصلات نشط."
            )

        assignment = existing_assignment
        assignment.driver_id = (
            morning_trip.driver_id
            if morning_trip is not None
            else return_trip.driver_id
        )
        assignment.morning_trip = morning_trip
        assignment.return_trip = return_trip
        assignment.is_active = True
        assignment.save(
            update_fields=[
                "driver",
                "morning_trip",
                "return_trip",
                "is_active",
                "updated_at",
            ]
        )
        return assignment

    driver_id = (
        morning_trip.driver_id
        if morning_trip is not None
        else return_trip.driver_id
    )

    assignment = TransportAssignment.objects.create(
        registration=registration,
        driver_id=driver_id,
        morning_trip=morning_trip,
        return_trip=return_trip,
        is_active=True,
    )

    return assignment


@transaction.atomic
def deactivate_assignment(*, assignment):
    """Safely stop an operational assignment without deleting history."""

    assignment.is_active = False
    assignment.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    return assignment


# ============================================================
# OPAL TRANSPORT — TRIP EXECUTION / PLANNING / TRACKING
# ============================================================

from math import atan2, cos, radians, sin, sqrt
from django.utils import timezone
from django.db import models


def _driver_for_user(user):
    from .models import TransportDriver
    try:
        return TransportDriver.objects.select_related("user").get(
            user=user,
            is_active=True,
        )
    except TransportDriver.DoesNotExist:
        raise ValidationError("حساب المستخدم غير مرتبط بسائق مواصلات نشط.")


@transaction.atomic
def start_trip(*, trip, user):
    """Start today's planned trip for its assigned driver."""
    from .models import TransportTrip

    driver = _driver_for_user(user)

    if trip.driver_id != driver.pk:
        raise ValidationError("لا يمكنك تشغيل رحلة لا تخصك.")

    if trip.service_date != timezone.localdate():
        raise ValidationError("لا يمكن بدء رحلة خارج تاريخ التشغيل الحالي.")

    if trip.status != TransportTrip.PLANNED:
        raise ValidationError("لا يمكن بدء هذه الرحلة بالحالة الحالية.")

    now = timezone.now()
    trip.status = TransportTrip.ACTIVE
    trip.started_at = now
    trip.finished_at = None
    try:
        trip.save(update_fields=["status", "started_at", "finished_at", "updated_at"])
    except Exception as exc:
        # The database constraint protects against two active trips for one driver.
        raise ValidationError("تعذر بدء الرحلة؛ قد تكون هناك رحلة نشطة أخرى للسائق.") from exc

    return trip


@transaction.atomic
def finish_trip(*, trip, user):
    """Finish the current active trip and keep its GPS/stop history."""
    from .models import TransportTrip

    driver = _driver_for_user(user)

    if trip.driver_id != driver.pk:
        raise ValidationError("لا يمكنك إنهاء رحلة لا تخصك.")

    if trip.status != TransportTrip.ACTIVE:
        raise ValidationError("الرحلة ليست نشطة حاليًا.")

    now = timezone.now()
    trip.status = TransportTrip.COMPLETED
    trip.finished_at = now
    trip.save(update_fields=["status", "finished_at", "updated_at"])
    return trip


def _record_stop_student_events(*, stop, event_type, occurred_at):
    """Record one operational event per assigned child at a family stop."""
    from parent_portal.models import FamilyStudent
    from .models import TransportAssignment, TransportStudentEvent

    assignments = (
        TransportAssignment.objects
        .filter(is_active=True, registration__school=stop.trip.route.school)
        .filter(
            morning_trip=stop.trip if stop.trip.direction == "morning" else None,
        )
        if stop.trip.direction == "morning"
        else TransportAssignment.objects.filter(
            is_active=True,
            return_trip=stop.trip,
        )
    )
    family_student_ids = set(
        FamilyStudent.objects.filter(
            family_id=stop.family_id,
            is_active=True,
        ).values_list("student_id", flat=True)
    )
    for assignment in assignments.select_related("registration"):
        registration = assignment.registration
        if registration.student_id not in family_student_ids:
            continue
        exists = TransportStudentEvent.objects.filter(
            trip=stop.trip,
            registration=registration,
            event_type=event_type,
        ).exists()
        if not exists:
            TransportStudentEvent.objects.create(
                trip=stop.trip,
                registration=registration,
                event_type=event_type,
                occurred_at=occurred_at,
                latitude=stop.latitude,
                longitude=stop.longitude,
                notes="تم التسجيل تلقائيًا من إجراء محطة المواصلات.",
            )


@transaction.atomic
def mark_stop_arrived(*, stop, user):
    """Record arrival and create child-level arrival events for the family stop."""
    from .models import TransportTrip
    driver = _driver_for_user(user)
    if stop.trip.driver_id != driver.pk:
        raise ValidationError("هذه المحطة لا تخص رحلتك.")
    if stop.trip.status != TransportTrip.ACTIVE:
        raise ValidationError("يجب أن تكون الرحلة نشطة.")
    if stop.arrived_at is not None:
        return stop
    occurred_at = timezone.now()
    stop.arrived_at = occurred_at
    stop.save(update_fields=["arrived_at"])
    _record_stop_student_events(
        stop=stop,
        event_type="arrived",
        occurred_at=occurred_at,
    )
    return stop


@transaction.atomic
def mark_stop_departed(*, stop, user):
    """Record departure and create boarding/drop-off events for assigned children."""
    from .models import TransportTrip
    driver = _driver_for_user(user)
    if stop.trip.driver_id != driver.pk:
        raise ValidationError("هذه المحطة لا تخص رحلتك.")
    if stop.trip.status != TransportTrip.ACTIVE:
        raise ValidationError("يجب أن تكون الرحلة نشطة.")
    if stop.arrived_at is None:
        raise ValidationError("سجّل الوصول إلى المحطة أولًا.")
    if stop.departed_at is not None:
        return stop
    occurred_at = timezone.now()
    stop.departed_at = occurred_at
    stop.save(update_fields=["departed_at"])
    _record_stop_student_events(
        stop=stop,
        event_type=("boarded" if stop.trip.direction == "morning" else "dropped_off"),
        occurred_at=occurred_at,
    )
    return stop


def record_gps_point(
    *,
    trip,
    user,
    latitude,
    longitude,
    accuracy_m=None,
    speed_kmh=None,
    recorded_at=None,
):
    """Append one GPS point; only the driver of the active trip may post it."""
    from .models import TransportGPSPoint, TransportTrip

    driver = _driver_for_user(user)

    if trip.driver_id != driver.pk:
        raise ValidationError("لا يمكنك إرسال موقع لرحلة لا تخصك.")
    if trip.status != TransportTrip.ACTIVE:
        raise ValidationError("لا يمكن تسجيل GPS لرحلة غير نشطة.")

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValidationError("إحداثيات الموقع غير صالحة.") from exc

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValidationError("إحداثيات الموقع خارج النطاق الصحيح.")

    if accuracy_m in ("", None):
        accuracy_m = None
    else:
        try:
            accuracy_m = max(0.0, float(accuracy_m))
        except (TypeError, ValueError) as exc:
            raise ValidationError("دقة GPS غير صالحة.") from exc

    if speed_kmh in ("", None):
        speed_kmh = None
    else:
        try:
            speed_kmh = max(0.0, float(speed_kmh))
        except (TypeError, ValueError) as exc:
            raise ValidationError("سرعة GPS غير صالحة.") from exc

    if recorded_at is None:
        recorded_at = timezone.now()

    return TransportGPSPoint.objects.create(
        trip=trip,
        latitude=latitude,
        longitude=longitude,
        accuracy_m=accuracy_m,
        speed_kmh=speed_kmh,
        recorded_at=recorded_at,
    )


def _distance_km(a_lat, a_lon, b_lat, b_lon):
    radius = 6371.0088
    p1, p2 = radians(float(a_lat)), radians(float(b_lat))
    dlat = radians(float(b_lat) - float(a_lat))
    dlon = radians(float(b_lon) - float(a_lon))
    h = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * radius * atan2(sqrt(h), sqrt(max(0.0, 1 - h)))


def optimize_stop_order(stops):
    """Route through the configured RoutingProvider boundary."""
    from .routing import get_routing_provider
    return get_routing_provider().optimize_waypoints(stops)


@transaction.atomic
def rebuild_trip_stops(*, trip):
    """Build the historical family-location snapshot for one planned round.

    Stable group membership is deliberately not changed here.
    """
    from parent_portal.models import FamilyStudent
    from .models import TransportAssignment, TransportFamilyLocation, TransportTripStop

    if trip.status != "planned":
        raise ValidationError("لا يمكن إعادة بناء محطات جولة بدأت أو اكتملت.")
    if not trip.route.is_active:
        raise ValidationError("لا يمكن تخطيط محطات لمسار غير نشط.")

    assignment_filter = {"is_active": True}
    assignment_filter["morning_trip" if trip.direction == "morning" else "return_trip"] = trip
    assignments = TransportAssignment.objects.filter(**assignment_filter).select_related("registration")

    family_ids = []
    for assignment in assignments:
        family_id = (FamilyStudent.objects.filter(
            student_id=assignment.registration.student_id, is_active=True
        ).values_list("family_id", flat=True).first())
        if family_id:
            family_ids.append(family_id)
    family_ids = list(dict.fromkeys(family_ids))

    locations = {x.family_id: x for x in TransportFamilyLocation.objects.filter(
        family_id__in=family_ids, is_active=True
    ).select_related("family")}
    candidates, missing = [], 0
    for family_id in family_ids:
        location = locations.get(family_id)
        if location is None or location.latitude is None or location.longitude is None:
            missing += 1
            continue
        candidates.append({
            "family_id": family_id,
            "label": location.label or (f"أبناء {location.family.guardian_name}" if getattr(location, "family", None) and location.family.guardian_name else ""),
            "address": location.address or "",
            "latitude": location.latitude,
            "longitude": location.longitude,
        })

    ordered = optimize_stop_order(candidates)
    TransportTripStop.objects.filter(trip=trip).delete()
    TransportTripStop.objects.bulk_create([TransportTripStop(
        trip=trip, family_id=item["family_id"], sequence=sequence,
        label=item["label"][:200], address=item["address"],
        latitude=item["latitude"], longitude=item["longitude"],
    ) for sequence, item in enumerate(ordered, 1)])
    return {
        "trip": trip,
        "stops": list(TransportTripStop.objects.filter(trip=trip).order_by("sequence")),
        "missing_locations": missing,
        "groups_created": 0,
    }


def _stable_registration_rows(*, school):
    from admissions.models import StudentRegistration
    from parent_portal.models import FamilyStudent
    from .models import TransportFamilyLocation

    registrations = list(StudentRegistration.objects.filter(
        school=school, student__isnull=False, transport_route__isnull=False,
        transport_type__in=("go", "return", "both"),
    ).select_related("student", "transport_route").order_by("transport_route_id", "student__full_name", "pk"))
    family_by_student = {
        row["student_id"]: row["family_id"] for row in FamilyStudent.objects.filter(
            student_id__in=[r.student_id for r in registrations], is_active=True
        ).values("student_id", "family_id")
    }
    family_ids = list(set(family_by_student.values()))
    locations = {x.family_id: x for x in TransportFamilyLocation.objects.filter(
        family_id__in=family_ids, is_active=True, latitude__isnull=False, longitude__isnull=False
    )}
    rows = []
    for r in registrations:
        family_id = family_by_student.get(r.student_id)
        loc = locations.get(family_id)
        if not loc:
            continue
        rows.append({"registration": r, "family_id": family_id, "latitude": loc.latitude, "longitude": loc.longitude, "label": loc.label or "", "address": loc.address or ""})
    return rows


def _cluster_stable_rows(rows, threshold_km=2.0):
    from .routing import get_routing_provider
    provider = get_routing_provider()
    families = {}
    for row in rows:
        families.setdefault(row["family_id"], row)
    remaining = set(families)
    clusters = []
    while remaining:
        seed_id = next(iter(sorted(remaining)))
        remaining.remove(seed_id)
        cluster = [seed_id]
        changed = True
        while changed:
            changed = False
            centroid = {
                "latitude": sum(float(families[i]["latitude"]) for i in cluster) / len(cluster),
                "longitude": sum(float(families[i]["longitude"]) for i in cluster) / len(cluster),
            }
            for fid in list(remaining):
                if provider.distance_km(centroid, families[fid]) <= threshold_km:
                    remaining.remove(fid); cluster.append(fid); changed = True
        clusters.append([families[i] for i in cluster])
    return clusters


@transaction.atomic
def establish_stable_groups(*, school, threshold_km=2.0):
    """Establish persistent geographic groups once; never touches locked/manual groups."""
    from .models import TransportGroup, TransportGroupMember
    from django.utils import timezone

    # Establishment is intentionally non-destructive. Existing stable membership,
    # locked or unlocked, is preserved. Only registrations without any stable
    # membership are considered for new geographic groups.
    rows = _stable_registration_rows(school=school)
    existing_membership_ids = set(TransportGroupMember.objects.filter(
        group__route__school=school, group__is_stable=True
    ).values_list("registration_id", flat=True))

    created_groups = []
    by_route = {}
    for row in rows:
        if row["registration"].pk in existing_membership_ids:
            continue
        by_route.setdefault(row["registration"].transport_route_id, []).append(row)

    for route_id, route_rows in by_route.items():
        for index, cluster in enumerate(_cluster_stable_rows(route_rows, threshold_km=threshold_km), 1):
            first = cluster[0]
            name = first["label"] or (first["address"].split("،")[0].strip() if first["address"] else "") or f"مجموعة جغرافية {index}"
            group = TransportGroup.objects.create(
                route_id=route_id, service_date=timezone.localdate(), direction=None,
                name=name[:200], max_students=max(10, len(cluster)), source="auto",
                is_locked=False, is_stable=True,
                notes=f"تأسيس جغرافي دائم. عدد الأبناء الحالي: {len(cluster)}. المركبة والسعة يحددهما الإدارة لاحقًا.",
            )
            TransportGroupMember.objects.bulk_create([
                TransportGroupMember(group=group, registration=row["registration"]) for row in cluster
            ])
            created_groups.append(group)
    named = _repair_blank_stable_group_names(school=school)
    return {"created": created_groups, "skipped_locked": len(existing_membership_ids), "eligible": len(rows), "renamed": named}


@transaction.atomic
def approve_group(*, group):
    """Approve and lock a stable group without requiring a driver assignment."""
    if not group.is_stable:
        raise ValidationError("لا يمكن اعتماد مجموعة تاريخية.")
    group.is_locked = True
    group.save(update_fields=["is_locked", "updated_at"])
    return group


@transaction.atomic
def assign_group_driver(*, group, driver):
    if not group.is_stable:
        raise ValidationError("لا يمكن إسناد سائق لمجموعة تاريخية.")
    group.assigned_driver = driver
    group.is_locked = True
    group.save(update_fields=["assigned_driver", "is_locked", "updated_at"])
    result = synchronize_transport_operations(school=group.route.school, reason="إسناد السائق للمجموعة")
    _notify_driver(
        driver,
        title="إسناد مجموعة مواصلات",
        message=f"تم إسناد مجموعة {group.name} إليك، وتم تحديث الجولات المستقبلية تلقائيًا.",
        event_key=f"transport-group-driver:{group.pk}:{group.updated_at.isoformat()}:{driver.pk}",
    )
    return {"group": group, "operations": result}


@transaction.atomic
def move_registrations_to_group(*, registrations, target_group=None, new_group_name="مجموعة يدوية"):
    from .models import TransportGroup, TransportGroupMember
    regs = list(registrations)
    if not regs:
        raise ValidationError("اختر ابنًا واحدًا على الأقل.")
    route_ids = {r.transport_route_id for r in regs}
    if len(route_ids) != 1:
        raise ValidationError("المجموعة الواحدة يجب أن تبقى ضمن المسار الرسمي نفسه.")
    route_id = next(iter(route_ids))
    if target_group is None:
        target_group = TransportGroup.objects.create(
            route_id=route_id, service_date=timezone.localdate(), direction=None,
            name=(new_group_name or "مجموعة يدوية")[:200], max_students=max(10, len(regs)),
            source="manual", is_locked=True, is_stable=True,
            notes="مجموعة يدوية أنشأتها الإدارة.",
        )
    if target_group.route_id != route_id or not target_group.is_stable:
        raise ValidationError("المجموعة المستهدفة غير صالحة.")
    source_group_ids = set(TransportGroupMember.objects.filter(registration__in=regs).values_list("group_id", flat=True))
    TransportGroupMember.objects.filter(registration__in=regs).delete()
    TransportGroupMember.objects.bulk_create([TransportGroupMember(group=target_group, registration=r) for r in regs])
    TransportGroup.objects.filter(pk__in=source_group_ids).update(is_locked=True)
    target_group.source = "manual"; target_group.is_locked = True
    target_group.save(update_fields=["source", "is_locked", "updated_at"])
    school = target_group.route.school
    synchronize_transport_operations(school=school, reason="تعديل عضوية المجموعة")
    return target_group



@transaction.atomic
def synchronize_today_assignments(*, school):
    """Bind today's rounds from stable groups and canonical subscriptions."""
    from admissions.models import StudentRegistration
    from .models import TransportAssignment, TransportTrip, TransportGroupMember
    today = timezone.localdate()
    # Subscription changes are authoritative: cancelled/ineligible registrations
    # must not remain on future rounds. Historical trips are never rewritten.
    TransportAssignment.objects.filter(
        registration__school=school, is_active=True
    ).exclude(
        registration__transport_type__in=("go", "return", "both"),
        registration__transport_route__isnull=False,
    ).update(is_active=False, driver=None, morning_trip=None, return_trip=None, updated_at=timezone.now())

    groups = list(TransportGroupMember.objects.filter(
        group__route__school=school, group__is_stable=True, group__is_locked=True,
        group__route__is_active=True, group__assigned_driver__is_active=True,
    ).select_related("group", "group__route", "group__assigned_driver", "registration", "registration__transport_route", "registration__student"))
    by_group = {}
    for m in groups:
        if m.registration.transport_route_id != m.group.route_id or m.registration.transport_type == "none":
            continue
        by_group.setdefault(m.group_id, []).append(m.registration)

    created = updated = skipped = 0; skipped_reasons=[]
    for group_id, regs in by_group.items():
        group = groups[[x.group_id for x in groups].index(group_id)].group
        driver = group.assigned_driver
        needed = []
        if any(r.transport_type in ("go", "both") for r in regs): needed.append(TransportTrip.MORNING)
        if any(r.transport_type in ("return", "both") for r in regs): needed.append(TransportTrip.RETURN)
        trips = {}
        for direction in needed:
            trip = TransportTrip.objects.filter(school=school, service_date=today, planning_group=group, direction=direction).order_by("id").first()
            if trip is None:
                seq = (TransportTrip.objects.filter(driver=driver, service_date=today, direction=direction).order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
                trip = TransportTrip.objects.create(
                    school=school, route=group.route, driver=driver, service_date=today, direction=direction,
                    sequence=seq, vehicle_type=TransportTrip.VEHICLE_BUS, status=TransportTrip.PLANNED, planning_group=group,
                ); created += 1
            elif trip.status == TransportTrip.PLANNED and trip.driver_id != driver.pk:
                trip.driver = driver; trip.save(update_fields=["driver", "updated_at"]); updated += 1
            trips[direction]=trip

        for r in regs:
            morning = trips.get(TransportTrip.MORNING) if r.transport_type in ("go","both") else None
            returning = trips.get(TransportTrip.RETURN) if r.transport_type in ("return","both") else None
            assignment = TransportAssignment.objects.select_for_update().filter(registration=r).first()
            if assignment is None:
                TransportAssignment.objects.create(registration=r, driver_id=driver.pk, morning_trip=morning, return_trip=returning, is_active=True); created += 1
            else:
                changed=(assignment.driver_id!=driver.pk or assignment.morning_trip_id!=getattr(morning,"pk",None) or assignment.return_trip_id!=getattr(returning,"pk",None) or not assignment.is_active)
                if changed:
                    assignment.driver_id=driver.pk; assignment.morning_trip=morning; assignment.return_trip=returning; assignment.is_active=True
                    assignment.save(update_fields=["driver","morning_trip","return_trip","is_active","updated_at"]); updated += 1
    # Any active assignment that no longer belongs to a prepared stable group is
    # removed from future operational rounds, while the registration itself stays canonical.
    valid_ids = {m.registration_id for m in groups}
    TransportAssignment.objects.filter(registration__school=school, is_active=True).exclude(registration_id__in=valid_ids).update(
        is_active=False, driver=None, morning_trip=None, return_trip=None, updated_at=timezone.now()
    )
    unassigned = TransportGroupMember.objects.filter(group__route__school=school, group__is_stable=True, group__route__is_active=True, group__assigned_driver__isnull=True).count()
    if unassigned: skipped_reasons.append(f"{unassigned} مجموعة مستقرة بانتظار إسناد سائق.")
    return {"today":today,"created":created,"updated":updated,"skipped":skipped,"skipped_reasons":skipped_reasons}




def _notify_transport_change(*, school, title, message, event_key, link_name="transport:trip-list", level="info"):
    """Best-effort operational notifications; transport data remains authoritative."""
    try:
        from enterprise_ops.services import notify_management, notify
        from django.urls import reverse
        link = reverse(link_name)
        notify_management(title, message, level=level, link=link, event_key=event_key)
        return notify_management
    except Exception:
        return None


def _notify_driver(driver, *, title, message, event_key, link_name="transport:transport-dashboard"):
    try:
        from enterprise_ops.services import notify
        from django.urls import reverse
        if driver and getattr(driver, "user_id", None):
            notify(driver.user, title, message, level="info", link=reverse(link_name), event_key=event_key)
    except Exception:
        pass


def _family_registration_rows(*, family, school):
    from admissions.models import StudentRegistration
    from parent_portal.models import FamilyStudent
    student_ids = list(FamilyStudent.objects.filter(family=family, is_active=True).values_list("student_id", flat=True))
    if not student_ids:
        return []
    return list(StudentRegistration.objects.filter(
        school=school, student_id__in=student_ids, student__isnull=False,
    ).select_related("student", "transport_route"))


def _group_centroid(group):
    from .models import TransportFamilyLocation, TransportGroupMember
    from parent_portal.models import FamilyStudent
    regs = list(TransportGroupMember.objects.filter(group=group).values_list("registration__student_id", flat=True))
    family_ids = list(FamilyStudent.objects.filter(student_id__in=regs, is_active=True).values_list("family_id", flat=True))
    locs = list(TransportFamilyLocation.objects.filter(
        family_id__in=family_ids, is_active=True, latitude__isnull=False, longitude__isnull=False
    ))
    if not locs:
        return None
    return {
        "latitude": sum(float(x.latitude) for x in locs) / len(locs),
        "longitude": sum(float(x.longitude) for x in locs) / len(locs),
    }


def _repair_blank_stable_group_names(*, school):
    """Give stable groups a deterministic human-readable name without moving members."""
    from .models import TransportGroup, TransportGroupMember, TransportFamilyLocation
    from parent_portal.models import FamilyStudent

    updated = 0
    groups = (
        TransportGroup.objects
        .filter(route__school=school, is_stable=True)
        .select_related("route")
        .order_by("id")
    )
    for group in groups:
        if str(group.name or "").strip():
            continue
        member = (
            TransportGroupMember.objects
            .filter(group=group)
            .select_related("registration")
            .order_by("id")
            .first()
        )
        label = ""
        if member and member.registration.student_id:
            family_id = (
                FamilyStudent.objects
                .filter(student_id=member.registration.student_id, is_active=True)
                .values_list("family_id", flat=True)
                .first()
            )
            if family_id:
                loc = (
                    TransportFamilyLocation.objects
                    .filter(family_id=family_id, is_active=True)
                    .first()
                )
                if loc:
                    label = (loc.label or "").strip() or (loc.address or "").split("،")[0].strip()
        if not label:
            label = f"{group.route.name}".strip() or "مجموعة مواصلات"
        candidate = (f"مجموعة {label}")[:200]
        if TransportGroup.objects.filter(route=group.route, name=candidate).exclude(pk=group.pk).exists():
            candidate = (f"{candidate} #{group.pk}")[:200]
        group.name = candidate
        group.save(update_fields=["name", "updated_at"])
        updated += 1
    return updated


@transaction.atomic
def _ensure_registration_group(*, registration, school):
    """Reconcile stable membership only when the canonical route changes.

    A go/return/both change never changes the geographic group. If the official
    transport route changes, the old membership becomes invalid and the child
    is placed into an existing unlocked automatic group on the new route when
    possible; otherwise a new unapproved automatic group is created for review.
    """
    from .models import TransportGroup, TransportGroupMember, TransportFamilyLocation
    from parent_portal.models import FamilyStudent
    from django.utils import timezone

    if registration.transport_type not in ("go", "return", "both") or not registration.transport_route_id:
        return {"moved": False, "group": None, "reason": "inactive"}

    membership = TransportGroupMember.objects.filter(registration=registration).select_related("group").first()
    if membership and membership.group.route_id == registration.transport_route_id:
        return {"moved": False, "group": membership.group, "reason": "stable_group_preserved"}

    if membership and membership.group.route_id != registration.transport_route_id:
        membership.delete()

    family_id = FamilyStudent.objects.filter(
        student_id=registration.student_id, is_active=True
    ).values_list("family_id", flat=True).first()
    loc = TransportFamilyLocation.objects.filter(
        family_id=family_id, is_active=True, latitude__isnull=False, longitude__isnull=False
    ).first() if family_id else None

    candidates = list(TransportGroup.objects.filter(
        route_id=registration.transport_route_id, is_stable=True, source="auto", is_locked=False
    ).order_by("id"))
    best = None
    if loc and candidates:
        from .routing import get_routing_provider
        provider = get_routing_provider()
        point = {"latitude": loc.latitude, "longitude": loc.longitude}
        best_distance = None
        for group in candidates:
            centroid = _group_centroid(group)
            if not centroid:
                continue
            distance = provider.distance_km(point, centroid)
            if best_distance is None or distance < best_distance:
                best, best_distance = group, distance

    if best is None and candidates:
        best = candidates[0]

    if best is not None:
        TransportGroupMember.objects.create(group=best, registration=registration)
        return {"moved": True, "group": best, "reason": "route_changed_to_existing_auto_group"}

    group = TransportGroup.objects.create(
        route_id=registration.transport_route_id,
        service_date=timezone.localdate(), direction=None,
        name=(loc.label if loc else "مجموعة بانتظار التوزيع")[:200],
        max_students=10, source="auto", is_locked=False, is_stable=True,
        notes="أنشأها النظام بعد تغيير المسار وتحتاج مراجعة الإدارة قبل اعتمادها.",
    )
    TransportGroupMember.objects.create(group=group, registration=registration)
    return {"moved": True, "group": group, "reason": "route_changed_new_auto_group"}


def _cancel_empty_planned_trip(trip):
    from .models import TransportAssignment, TransportTrip
    if trip.status != TransportTrip.PLANNED:
        return False
    field = "morning_trip" if trip.direction == TransportTrip.MORNING else "return_trip"
    if not TransportAssignment.objects.filter(is_active=True, **{field: trip}).exists():
        trip.status = TransportTrip.CANCELLED
        trip.save(update_fields=["status", "updated_at"])
        return True
    return False


@transaction.atomic
def prepare_today_operations(*, school):
    """Explicit management gateway for preparing today's transport rounds.

    The underlying synchronizer remains the single source of truth. This
    gateway exists only for the one visible management action ``تجهيز جولات
    اليوم`` and never rebuilds or redistributes stable groups.
    """
    return synchronize_transport_operations(
        school=school,
        reason="تجهيز جولات اليوم",
    )


@transaction.atomic
def synchronize_transport_operations(*, school, reason="automatic"):
    """Reconcile future planned rounds from canonical subscriptions and stable groups.

    This is the only operational synchronizer. It is invoked by transport data
    changes; management does not need to prepare the day manually.
    """
    from .models import TransportAssignment, TransportTrip, TransportGroupMember
    from admissions.models import StudentRegistration
    today = timezone.localdate()
    _repair_blank_stable_group_names(school=school)
    created = updated = rebuilt = missing_locations = 0
    warnings = []

    eligible = list(StudentRegistration.objects.filter(
        school=school, student__isnull=False, transport_route__isnull=False,
        transport_type__in=("go", "return", "both"),
    ).select_related("student", "transport_route"))
    eligible_ids = {r.pk for r in eligible}

    # Remove operational assignments that no longer qualify. Historical trips are untouched.
    stale = TransportAssignment.objects.select_for_update().filter(registration__school=school, is_active=True).exclude(registration_id__in=eligible_ids)
    stale_trips = []
    for a in stale:
        stale_trips.extend([a.morning_trip, a.return_trip])
        a.is_active = False; a.driver = None; a.morning_trip = None; a.return_trip = None
        a.save(update_fields=["is_active", "driver", "morning_trip", "return_trip", "updated_at"])
    for trip in stale_trips:
        if trip: _cancel_empty_planned_trip(trip)

    groups = list(TransportGroupMember.objects.filter(
        group__route__school=school, group__is_stable=True, group__route__is_active=True,
        group__assigned_driver__is_active=True,
    ).select_related("group", "group__route", "group__assigned_driver", "registration", "registration__transport_route"))
    by_group = {}
    for member in groups:
        reg = member.registration
        if reg.pk not in eligible_ids or reg.transport_route_id != member.group.route_id:
            continue
        by_group.setdefault(member.group_id, []).append(reg)

    touched_trips = set()
    for group_id, regs in by_group.items():
        group = next(m.group for m in groups if m.group_id == group_id)
        driver = group.assigned_driver
        needs = {
            TransportTrip.MORNING: [r for r in regs if r.transport_type in ("go", "both")],
            TransportTrip.RETURN: [r for r in regs if r.transport_type in ("return", "both")],
        }
        trips = {}
        for direction, direction_regs in needs.items():
            trip = TransportTrip.objects.filter(school=school, service_date=today, planning_group=group, direction=direction, status=TransportTrip.PLANNED).order_by("id").first()
            if direction_regs and trip is None:
                seq = (TransportTrip.objects.filter(driver=driver, service_date=today, direction=direction).order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
                trip = TransportTrip.objects.create(
                    school=school, route=group.route, driver=driver, service_date=today,
                    direction=direction, sequence=seq, vehicle_type=TransportTrip.VEHICLE_BUS,
                    status=TransportTrip.PLANNED, planning_group=group,
                )
                created += 1
            trips[direction] = trip
            if trip and direction_regs:
                touched_trips.add(trip.pk)

        # One canonical assignment per registration; direction is derived from the
        # current transport_type, so stale opposite-direction references disappear immediately.
        for reg in regs:
            morning = trips.get(TransportTrip.MORNING) if reg.transport_type in ("go", "both") else None
            returning = trips.get(TransportTrip.RETURN) if reg.transport_type in ("return", "both") else None
            assignment = TransportAssignment.objects.select_for_update().filter(registration=reg).first()
            if assignment is None:
                assignment = TransportAssignment.objects.create(
                    registration=reg, driver=driver, morning_trip=morning, return_trip=returning, is_active=True
                )
                created += 1
            else:
                changed = (assignment.driver_id != driver.pk or assignment.morning_trip_id != getattr(morning, "pk", None) or assignment.return_trip_id != getattr(returning, "pk", None) or not assignment.is_active)
                if changed:
                    assignment.driver=driver; assignment.morning_trip=morning; assignment.return_trip=returning; assignment.is_active=True
                    assignment.save(update_fields=["driver", "morning_trip", "return_trip", "is_active", "updated_at"])
                    updated += 1

        for direction, trip in trips.items():
            if trip and not TransportAssignment.objects.filter(
                is_active=True, **{"morning_trip" if direction == TransportTrip.MORNING else "return_trip": trip}
            ).exists():
                _cancel_empty_planned_trip(trip)

    # Any eligible registration without an operationally assigned stable group is inactive operationally.
    grouped_ids = set(TransportGroupMember.objects.filter(
        group__route__school=school, group__is_stable=True, group__route__is_active=True,
        registration_id__in=eligible_ids,
    ).values_list("registration_id", flat=True))
    orphan_assignments = TransportAssignment.objects.select_for_update().filter(registration__school=school, is_active=True).exclude(registration_id__in=grouped_ids)
    for a in orphan_assignments:
        stale_trips.extend([a.morning_trip, a.return_trip])
        a.is_active=False; a.driver=None; a.morning_trip=None; a.return_trip=None
        a.save(update_fields=["is_active", "driver", "morning_trip", "return_trip", "updated_at"])
    for trip in stale_trips:
        if trip: _cancel_empty_planned_trip(trip)

    for trip in TransportTrip.objects.filter(pk__in=touched_trips, status=TransportTrip.PLANNED):
        result = rebuild_trip_stops(trip=trip)
        rebuilt += 1
        missing_locations += result["missing_locations"]

    return {"today": today, "created": created, "updated": updated, "rebuilt": rebuilt, "missing_locations": missing_locations, "warnings": warnings}


@transaction.atomic
def _repair_registration_operational_projection(*, registration, school):
    """Force the one-registration operational projection to match the canonical type.

    This is intentionally called after the broad synchronizer as a defensive
    invariant: changing go/return/both must never leave a stale opposite-
    direction trip on TransportAssignment. Stable group membership is retained.
    """
    from .models import TransportAssignment, TransportGroupMember, TransportTrip

    membership = (
        TransportGroupMember.objects
        .select_related("group", "group__assigned_driver", "group__route")
        .filter(
            registration=registration,
            group__is_stable=True,
            group__route__school=school,
        )
        .first()
    )
    assignment = (
        TransportAssignment.objects
        .select_for_update()
        .filter(registration=registration)
        .first()
    )

    old_trip_ids = []
    if assignment:
        old_trip_ids = [assignment.morning_trip_id, assignment.return_trip_id]

    active_type = registration.transport_type in ("go", "return", "both") and bool(registration.transport_route_id)
    if not active_type or not membership or not membership.group.assigned_driver_id:
        if assignment:
            assignment.driver = None
            assignment.morning_trip = None
            assignment.return_trip = None
            assignment.is_active = False
            assignment.save(update_fields=["driver", "morning_trip", "return_trip", "is_active", "updated_at"])
        for trip_id in old_trip_ids:
            if trip_id:
                trip = TransportTrip.objects.filter(pk=trip_id).first()
                if trip:
                    _cancel_empty_planned_trip(trip)
        return {"active": False, "morning": None, "return": None}

    group = membership.group
    driver = group.assigned_driver
    today = timezone.localdate()
    desired = {
        TransportTrip.MORNING: registration.transport_type in ("go", "both"),
        TransportTrip.RETURN: registration.transport_type in ("return", "both"),
    }
    trips = {}
    touched = []

    for direction, required in desired.items():
        trip = (
            TransportTrip.objects
            .filter(
                school=school,
                service_date=today,
                planning_group=group,
                direction=direction,
                status=TransportTrip.PLANNED,
            )
            .order_by("id")
            .first()
        )
        if required and trip is None:
            last_sequence = (
                TransportTrip.objects
                .filter(driver=driver, service_date=today, direction=direction)
                .order_by("-sequence")
                .values_list("sequence", flat=True)
                .first()
                or 0
            )
            trip = TransportTrip.objects.create(
                school=school,
                route=group.route,
                driver=driver,
                service_date=today,
                direction=direction,
                sequence=last_sequence + 1,
                vehicle_type=TransportTrip.VEHICLE_BUS,
                status=TransportTrip.PLANNED,
                planning_group=group,
            )
        trips[direction] = trip if required else None
        if trip and required:
            touched.append(trip)

    morning = trips[TransportTrip.MORNING]
    returning = trips[TransportTrip.RETURN]
    if assignment is None:
        assignment = TransportAssignment.objects.create(
            registration=registration,
            driver=driver,
            morning_trip=morning,
            return_trip=returning,
            is_active=True,
        )
    else:
        assignment.driver = driver
        assignment.morning_trip = morning
        assignment.return_trip = returning
        assignment.is_active = True
        assignment.save(update_fields=["driver", "morning_trip", "return_trip", "is_active", "updated_at"])

    for trip_id in old_trip_ids:
        if trip_id and trip_id not in {getattr(morning, "pk", None), getattr(returning, "pk", None)}:
            trip = TransportTrip.objects.filter(pk=trip_id).first()
            if trip:
                _cancel_empty_planned_trip(trip)

    for trip in touched:
        rebuild_trip_stops(trip=trip)

    return {
        "active": True,
        "morning": getattr(morning, "pk", None),
        "return": getattr(returning, "pk", None),
    }


@transaction.atomic
def reconcile_transport_after_registration_change(*, registration, school, change_reason="تغيير الاشتراك"):
    """Apply a canonical subscription change immediately to groups, rounds and notifications."""
    group_result = _ensure_registration_group(registration=registration, school=school)
    result = synchronize_transport_operations(school=school, reason=change_reason)
    projection = _repair_registration_operational_projection(registration=registration, school=school)
    result["registration_projection"] = projection
    student_name = getattr(getattr(registration, "student", None), "full_name", None) or f"التسجيل {registration.pk}"
    _notify_transport_change(
        school=school,
        title="تحديث مواصلات الأبناء",
        message=f"تم {change_reason} للابن {student_name}، وتم تحديث الجولات المستقبلية تلقائيًا.",
        event_key=f"transport-subscription:{registration.pk}:{timezone.now().isoformat()}",
    )
    return {"group": group_result, "operations": result}


@transaction.atomic
def reconcile_transport_after_family_location_change(*, family, school):
    """Accept the new location, preserve stable membership, and redraw planned routes."""
    from .models import TransportAssignment, TransportTrip

    rows = _family_registration_rows(family=family, school=school)
    registration_ids = [row.pk for row in rows]
    affected_trip_ids = set()
    if registration_ids:
        for assignment in TransportAssignment.objects.filter(
            registration_id__in=registration_ids, is_active=True
        ).only("morning_trip_id", "return_trip_id"):
            if assignment.morning_trip_id:
                affected_trip_ids.add(assignment.morning_trip_id)
            if assignment.return_trip_id:
                affected_trip_ids.add(assignment.return_trip_id)

    # Current-day rounds are reconciled internally; no manager button is needed.
    result = synchronize_transport_operations(school=school, reason="تغيير موقع الأبناء")

    rebuilt_future = 0
    missing_future = 0
    future_trips = TransportTrip.objects.filter(
        pk__in=affected_trip_ids, school=school, status=TransportTrip.PLANNED
    ).exclude(service_date=timezone.localdate())
    for trip in future_trips:
        rebuilt = rebuild_trip_stops(trip=trip)
        rebuilt_future += 1
        missing_future += rebuilt["missing_locations"]

    _notify_transport_change(
        school=school,
        title="تحديث موقع مواصلات الأبناء",
        message="تم اعتماد موقع الأبناء الجديد وإعادة ترتيب محطات الجولات المخططة تلقائيًا. لم تتغير عضوية المجموعة تلقائيًا.",
        event_key=f"transport-location:{family.pk}:{family.transport_location.updated_at.isoformat()}",
        level="info",
    )

    for trip in TransportTrip.objects.filter(
        pk__in=affected_trip_ids, status=TransportTrip.PLANNED, school=school
    ).select_related("driver"):
        _notify_driver(
            trip.driver,
            title="تحديث جولتك",
            message="تم تحديث موقع أحد أبناء جولتك وإعادة ترتيب المحطات تلقائيًا.",
            event_key=f"transport-location-driver:{family.pk}:{trip.pk}:{family.transport_location.updated_at.isoformat()}",
        )

    result.update({
        "rebuilt_future": rebuilt_future,
        "missing_future_locations": missing_future,
        # Changing a family location rebuilds stops only; it never changes
        # stable planning-group membership automatically.
        "group_membership_changed": False,
    })
    return result


def _family_for_student(student_id):
    from parent_portal.models import FamilyStudent
    return (
        FamilyStudent.objects
        .filter(student_id=student_id, is_active=True)
        .select_related("family")
        .first()
    )


def active_trip_for_parent(user):
    """Return the first active trip carrying one of the family's eligible children.

    The operational projection (TransportAssignment) is preferred, but stable
    planning-group membership is also accepted as a recovery source. This keeps
    parent tracking working for rounds created before assignments were repaired.
    """
    from parent_portal.models import FamilyStudent
    from .models import TransportAssignment, TransportGroupMember, TransportTrip

    student_ids = list(
        FamilyStudent.objects
        .filter(family__user=user, is_active=True, student__is_active=True)
        .values_list("student_id", flat=True)
    )
    if not student_ids:
        return None

    # Prefer the canonical operational projection.
    assigned_trip_ids = set()
    for trip_id in TransportAssignment.objects.filter(
        is_active=True,
        registration__student_id__in=student_ids,
    ).values_list("morning_trip_id", "return_trip_id"):
        if trip_id[0]:
            assigned_trip_ids.add(trip_id[0])
        if trip_id[1]:
            assigned_trip_ids.add(trip_id[1])

    # Recovery path for rounds where the group exists but assignment projection
    # was not materialised yet.
    group_ids = set(
        TransportGroupMember.objects
        .filter(
            registration__student_id__in=student_ids,
            registration__student__is_active=True,
            group__is_stable=True,
        )
        .values_list("group_id", flat=True)
    )

    candidates = (
        TransportTrip.objects
        .filter(status=TransportTrip.ACTIVE)
        .filter(
            Q(pk__in=assigned_trip_ids) | Q(planning_group_id__in=group_ids)
        )
        .select_related("route", "driver")
        .prefetch_related("stops")
        .order_by("started_at", "id")
        .distinct()
    )
    for trip in candidates:
        # Make sure the trip direction is actually allowed by at least one
        # canonical registration belonging to this family.
        field = "morning_trip" if trip.direction == TransportTrip.MORNING else "return_trip"
        registrations = TransportAssignment.objects.filter(
            is_active=True,
            registration__student_id__in=student_ids,
            **{field: trip},
        ).exists()
        if registrations:
            return trip
        if trip.planning_group_id:
            if TransportGroupMember.objects.filter(
                group_id=trip.planning_group_id,
                registration__student_id__in=student_ids,
                registration__student__is_active=True,
                registration__transport_type__in=(
                    ("go", "both") if trip.direction == TransportTrip.MORNING
                    else ("return", "both")
                ),
            ).exists():
                return trip
    return None

def transport_registrations_for_trip(*, trip):
    """Return canonical registrations participating in one trip.

    TransportAssignment is the primary operational projection. Stable group
    membership is a recovery source for legacy/demo rounds where assignments
    were not materialised yet. Results are deduplicated by registration id.
    """
    from .models import TransportAssignment, TransportGroupMember

    field = "morning_trip" if trip.direction == "morning" else "return_trip"
    rows = list(
        TransportAssignment.objects
        .filter(is_active=True, **{field: trip})
        .select_related("registration__student", "driver")
    )
    by_id = {row.registration_id: row for row in rows}

    if trip.planning_group_id:
        fallback = TransportGroupMember.objects.filter(
            group_id=trip.planning_group_id,
        ).select_related("registration__student")
        allowed_types = ("go", "both") if trip.direction == "morning" else ("return", "both")
        for member in fallback:
            reg = member.registration
            if reg.transport_type not in allowed_types or not reg.student_id:
                continue
            # Lightweight registration-compatible object: a real registration
            # is preferable so event and family lookups remain canonical.
            if reg.pk not in by_id:
                by_id[reg.pk] = reg

    return list(by_id.values())


def _family_student_ids_for_user(user):
    from parent_portal.models import FamilyStudent
    family = (
        FamilyStudent.objects
        .filter(family__user=user, is_active=True)
        .values_list("student_id", flat=True)
    )
    return list(family)


@transaction.atomic
def _build_trip_stops_from_assignments(*, trip):
    """
    Compatibility gateway for building trip stops from transport assignments.

    The canonical stop-building implementation is delegated to the current
    map bootstrap service.
    """
    from .models import TransportAssignment, TransportFamilyLocation, TransportTrip, TransportTripStop

    # Keep the trip operational once its assignment-derived stops are prepared.
    trip.status = TransportTrip.ACTIVE

    return bootstrap_trip_stops_for_map(trip=trip)


def bootstrap_trip_stops_for_map(*, trip):
    """Create missing stop snapshots for a planned/active trip without deleting history.

    This is a recovery path for legacy/demo trips that were created before stop
    snapshots existed. It is intentionally idempotent and never rewrites an
    existing operational stop list.
    """
    from parent_portal.models import FamilyStudent
    from .models import TransportAssignment, TransportFamilyLocation, TransportTripStop

    if trip.stops.exists():
        return {"created": 0, "missing_locations": 0}
    if trip.status not in ("planned", "active"):
        return {"created": 0, "missing_locations": 0}

    assignment_filter = {"is_active": True}
    assignment_filter["morning_trip" if trip.direction == "morning" else "return_trip"] = trip
    assignments = list(
        TransportAssignment.objects.filter(**assignment_filter).select_related("registration")
    )

    # Primary source: operational assignments.
    family_ids = []
    student_ids = []
    for assignment in assignments:
        student_id = assignment.registration.student_id
        if student_id:
            student_ids.append(student_id)
        family_id = (
            FamilyStudent.objects.filter(
                student_id=student_id, is_active=True
            ).values_list("family_id", flat=True).first()
        )
        if family_id and family_id not in family_ids:
            family_ids.append(family_id)

    # Recovery source: the trip's stable planning group. This handles legacy
    # or demo trips where the group members exist but assignments were not
    # materialized correctly. It is read-only and does not alter membership.
    if not family_ids and getattr(trip, "planning_group_id", None):
        from .models import TransportGroupMember
        group_members = (
            TransportGroupMember.objects
            .filter(group_id=trip.planning_group_id, registration__student_id__isnull=False)
            .select_related("registration")
        )
        for member in group_members:
            student_id = member.registration.student_id
            if student_id:
                student_ids.append(student_id)
            family_id = (
                FamilyStudent.objects.filter(
                    student_id=student_id, is_active=True
                ).values_list("family_id", flat=True).first()
            )
            if family_id and family_id not in family_ids:
                family_ids.append(family_id)

    locations = {
        loc.family_id: loc
        for loc in TransportFamilyLocation.objects.filter(
            family_id__in=family_ids,
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).select_related("family")
    }
    candidates = []
    missing = 0
    for family_id in family_ids:
        location = locations.get(family_id)
        if location is None:
            missing += 1
            continue
        candidates.append({
            "family_id": family_id,
            "label": location.label or (
                f"أبناء {location.family.guardian_name}"
                if getattr(location, "family", None) and location.family.guardian_name
                else ""
            ),
            "address": location.address or "",
            "latitude": location.latitude,
            "longitude": location.longitude,
        })

    ordered = optimize_stop_order(candidates)
    TransportTripStop.objects.bulk_create([
        TransportTripStop(
            trip=trip,
            family_id=item["family_id"],
            sequence=sequence,
            label=item["label"][:200],
            address=item["address"],
            latitude=item["latitude"],
            longitude=item["longitude"],
        )
        for sequence, item in enumerate(ordered, 1)
    ])
    return {"created": len(ordered), "missing_locations": missing}


def driver_operational_trips(driver):
    """Return the driver's active trip plus today's planned/active trips.

    An active trip is intentionally date-independent: a trip that crossed
    midnight must remain visible and must continue accepting GPS updates.
    Historical completed/cancelled trips are not placed in the operational
    driver workspace.
    """
    from .models import TransportTrip
    today = timezone.localdate()
    return list(
        TransportTrip.objects
        .filter(driver=driver)
        .filter(
            models.Q(status=TransportTrip.ACTIVE)
            | models.Q(service_date=today, status=TransportTrip.PLANNED)
        )
        .select_related("route", "driver")
        .prefetch_related("stops")
        .order_by(
            models.Case(
                models.When(status=TransportTrip.ACTIVE, then=models.Value(0)),
                default=models.Value(1),
                output_field=models.IntegerField(),
            ),
            "service_date",
            "direction",
            "sequence",
            "id",
        )
    )


def active_trips_for_manager(school):
    from .models import TransportTrip
    return list(
        TransportTrip.objects
        .filter(
            school=school,
            status=TransportTrip.ACTIVE,
        )
        .select_related("route", "driver")
        .prefetch_related("stops", "gps_points")
        .order_by("started_at", "direction", "sequence", "id")
    )


@transaction.atomic
def save_family_location(*, family, label, address, latitude, longitude):
    """Save the family-level location without silently changing stable membership."""
    from .models import TransportFamilyLocation
    if family is None or not family.is_active:
        raise ValidationError("ملف ولي الأمر غير نشط.")
    try:
        latitude=float(latitude); longitude=float(longitude)
    except (TypeError,ValueError) as exc:
        raise ValidationError("إحداثيات الموقع غير صالحة.") from exc
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValidationError("إحداثيات الموقع خارج النطاق الصحيح.")
    location, created = TransportFamilyLocation.objects.update_or_create(
        family=family, defaults={"label":str(label or "").strip()[:200],"address":str(address or "").strip(),"latitude":latitude,"longitude":longitude,"is_active":True}
    )
    # Location is canonical at family level; immediately reconcile transport projections.
    reconcile_transport_after_family_location_change(family=family, school=family.school)
    return location
