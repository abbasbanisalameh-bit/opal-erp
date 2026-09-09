from django.db import models
from django.conf import settings
from students.models import Student

class DriverProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='driver_profile')
    phone_number = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    license_number = models.CharField(max_length=50, verbose_name='رقم الرخصة')
    vehicle_details = models.CharField(max_length=100, verbose_name='معلومات المركبة')
    is_active_driver = models.BooleanField(default=True, verbose_name='سائق نشط')

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username}'

class TransportRoute(models.Model):
    name = models.CharField(max_length=100, verbose_name='اسم المسار')
    driver = models.ForeignKey(DriverProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='routes', verbose_name='السائق')
    description = models.TextField(blank=True, verbose_name='الوصف')

    def __str__(self):
        return self.name

class StudentTransportInfo(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='transport_info', verbose_name='الطالب')
    route = models.ForeignKey(TransportRoute, on_delete=models.SET_NULL, null=True, blank=True, related_name='students', verbose_name='المسار')
    pickup_address = models.TextField(blank=True, verbose_name='عنوان التواجد')
    latitude = models.FloatField(null=True, blank=True, verbose_name='خط العرض')
    longitude = models.FloatField(null=True, blank=True, verbose_name='خط الطول')
    is_active = models.BooleanField(default=True, verbose_name='مفعل')

    def __str__(self):
        return str(self.student)

# ============================================================
# OPAL TRANSPORT — OPERATIONAL DOMAIN / STEP 1
# ============================================================

class TransportDriver(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transport_driver",
        verbose_name="حساب النظام",
    )
    name = models.CharField(
        max_length=150,
        verbose_name="اسم السائق",
    )
    phone = models.CharField(
        max_length=30,
        verbose_name="رقم الهاتف",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "سائق مواصلات"
        verbose_name_plural = "سائقو المواصلات"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "name"], name="transport_t_is_acti_106a68_idx"),
        ]

    def __str__(self):
        return self.name


class TransportFamilyLocation(models.Model):
    family = models.OneToOneField(
        "parent_portal.Family",
        on_delete=models.CASCADE,
        related_name="transport_location",
        verbose_name="العائلة",
    )
    label = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="وصف الموقع",
    )
    address = models.TextField(
        blank=True,
        verbose_name="العنوان",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="خط العرض",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="خط الطول",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "موقع مواصلات للعائلة"
        verbose_name_plural = "مواقع مواصلات العائلات"

    def __str__(self):
        return self.label or self.address or f"Family #{self.family_id}"


class TransportTrip(models.Model):
    MORNING = "morning"
    RETURN = "return"

    DIRECTION_CHOICES = [
        (MORNING, "ذهاب صباحي"),
        (RETURN, "عودة مسائية"),
    ]

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (PLANNED, "مخططة"),
        (ACTIVE, "نشطة"),
        (COMPLETED, "مكتملة"),
        (CANCELLED, "ملغاة"),
    ]

    VEHICLE_CAR = "car"
    VEHICLE_BUS = "bus"
    VEHICLE_MINIBUS = "minibus"
    VEHICLE_COACH = "coach"

    VEHICLE_TYPE_CHOICES = [
        (VEHICLE_CAR, "سيارة"),
        (VEHICLE_BUS, "حافلة"),
        (VEHICLE_MINIBUS, "باص صغير"),
        (VEHICLE_COACH, "باص كبير"),
    ]

    school = models.ForeignKey(
        "core.School",
        on_delete=models.PROTECT,
        related_name="transport_trips",
        verbose_name="المدرسة",
    )
    route = models.ForeignKey(
        "admissions.TransportRoute",
        on_delete=models.PROTECT,
        related_name="operational_trips",
        verbose_name="المسار",
    )
    driver = models.ForeignKey(
        TransportDriver,
        on_delete=models.PROTECT,
        related_name="trips",
        verbose_name="السائق",
    )
    service_date = models.DateField(
        verbose_name="تاريخ الرحلة",
    )
    direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        verbose_name="الاتجاه",
    )
    sequence = models.PositiveIntegerField(
        default=1,
        verbose_name="رقم الرحلة",
    )
    planning_group = models.ForeignKey(
        "transport.TransportGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trips",
        verbose_name="مجموعة التخطيط",
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        verbose_name="نوع المركبة",
    )
    vehicle_description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="وصف المركبة",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PLANNED,
        verbose_name="الحالة",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="وقت الانطلاق",
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="وقت الانتهاء",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "رحلة مواصلات"
        verbose_name_plural = "رحلات المواصلات"
        ordering = ["service_date", "direction", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "driver",
                    "service_date",
                    "direction",
                    "sequence",
                ],
                name="uniq_transport_trip_driver_day_direction_seq",
            ),
            models.UniqueConstraint(
                fields=["driver"],
                condition=models.Q(status="active"),
                name="uniq_active_transport_trip_per_driver",
            ),
        ]
        indexes = [
            models.Index(
                fields=["school", "service_date", "direction", "status"],
                name="transport_t_school__f6bd36_idx",
            ),
            models.Index(
                fields=["driver", "service_date", "direction"],
                name="transport_t_driver__fbc14a_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.route.name} — "
            f"{self.get_direction_display()} — "
            f"{self.service_date} — #{self.sequence}"
        )


class TransportAssignment(models.Model):
    """
    Operational transport assignment for one official
    StudentRegistration.

    The registration remains the source of transport subscription.
    This model only answers: which driver/trips operate that
    subscription.
    """
    registration = models.OneToOneField(
        "admissions.StudentRegistration",
        on_delete=models.PROTECT,
        related_name="transport_assignment",
        verbose_name="التسجيل",
    )
    driver = models.ForeignKey(
        TransportDriver,
        on_delete=models.PROTECT,
        related_name="student_assignments",
        null=True,
        blank=True,
        verbose_name="السائق",
    )
    morning_trip = models.ForeignKey(
        TransportTrip,
        on_delete=models.PROTECT,
        related_name="morning_assignments",
        null=True,
        blank=True,
        verbose_name="رحلة الذهاب",
    )
    return_trip = models.ForeignKey(
        TransportTrip,
        on_delete=models.PROTECT,
        related_name="return_assignments",
        null=True,
        blank=True,
        verbose_name="رحلة العودة",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تكليف مواصلات"
        verbose_name_plural = "تكليفات المواصلات"
        indexes = [
            models.Index(fields=["driver", "is_active"], name="transport_t_driver__aec154_idx"),
        ]

    def __str__(self):
        return f"تكليف مواصلات #{self.pk}"


class TransportTripStop(models.Model):
    """
    Historical snapshot of a family's pickup/drop-off location
    for a specific trip.
    """
    trip = models.ForeignKey(
        TransportTrip,
        on_delete=models.CASCADE,
        related_name="stops",
        verbose_name="الرحلة",
    )
    family = models.ForeignKey(
        "parent_portal.Family",
        on_delete=models.PROTECT,
        related_name="transport_trip_stops",
        verbose_name="العائلة",
    )
    sequence = models.PositiveIntegerField(
        verbose_name="ترتيب المحطة",
    )
    label = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="اسم المحطة",
    )
    address = models.TextField(
        blank=True,
        verbose_name="العنوان",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="خط العرض",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="خط الطول",
    )
    arrived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="وقت الوصول",
    )
    departed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="وقت المغادرة",
    )

    class Meta:
        verbose_name = "محطة رحلة مواصلات"
        verbose_name_plural = "محطات رحلات المواصلات"
        ordering = ["trip", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip", "sequence"],
                name="uniq_transport_stop_sequence",
            ),
            models.UniqueConstraint(
                fields=["trip", "family"],
                name="uniq_transport_stop_family",
            ),
        ]
        indexes = [
            models.Index(fields=["trip", "sequence"], name="transport_t_trip_id_fa12a5_idx"),
            models.Index(fields=["family"], name="transport_t_family__463dd9_idx"),
        ]

    def __str__(self):
        return f"الرحلة {self.trip_id} — المحطة {self.sequence}"


class TransportGPSPoint(models.Model):
    """
    Historical GPS points used to reconstruct the actual trip path.
    """
    trip = models.ForeignKey(
        TransportTrip,
        on_delete=models.CASCADE,
        related_name="gps_points",
        verbose_name="الرحلة",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="خط العرض",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name="خط الطول",
    )
    accuracy_m = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="دقة الموقع بالمتر",
    )
    speed_kmh = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="السرعة كم/ساعة",
    )
    recorded_at = models.DateTimeField(
        verbose_name="وقت التسجيل",
    )

    class Meta:
        verbose_name = "نقطة GPS"
        verbose_name_plural = "نقاط GPS"
        ordering = ["recorded_at"]
        indexes = [
            models.Index(fields=["trip", "recorded_at"], name="transport_t_trip_id_d41fdf_idx"),
        ]

    def __str__(self):
        return f"GPS {self.trip_id} @ {self.recorded_at}"


class TransportStudentEvent(models.Model):
    ARRIVED = "arrived"
    BOARDED = "boarded"
    DROPPED_OFF = "dropped_off"
    MISSED = "missed"

    EVENT_CHOICES = [
        (ARRIVED, "وصل إلى المحطة"),
        (BOARDED, "صعد إلى المركبة"),
        (DROPPED_OFF, "تم إنزاله"),
        (MISSED, "لم يصعد/لم يستلم"),
    ]

    trip = models.ForeignKey(
        TransportTrip,
        on_delete=models.CASCADE,
        related_name="student_events",
        verbose_name="الرحلة",
    )
    registration = models.ForeignKey(
        "admissions.StudentRegistration",
        on_delete=models.PROTECT,
        related_name="transport_events",
        verbose_name="التسجيل",
    )
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_CHOICES,
        verbose_name="نوع الحدث",
    )
    occurred_at = models.DateTimeField(
        verbose_name="وقت الحدث",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    notes = models.TextField(
        blank=True,
        verbose_name="ملاحظات",
    )

    class Meta:
        verbose_name = "حدث مواصلات للطالب"
        verbose_name_plural = "أحداث المواصلات للطلاب"
        ordering = ["occurred_at"]
        indexes = [
            models.Index(
                fields=["trip", "registration", "occurred_at"],
                name="transport_t_trip_id_c2f1a7_idx",
            ),
            models.Index(
                fields=["registration", "event_type"],
                name="transport_t_registr_d53db7_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.registration_id} — "
            f"{self.get_event_type_display()}"
        )


class TransportGroup(models.Model):
    """
    Manager-facing proximity grouping.

    This is planning data only. It does not replace Student,
    StudentRegistration, FamilyStudent, or TransportAssignment.
    """
    route = models.ForeignKey(
        "admissions.TransportRoute",
        on_delete=models.PROTECT,
        related_name="transport_groups",
        verbose_name="المسار",
    )
    service_date = models.DateField(
        verbose_name="تاريخ التشغيل",
    )
    direction = models.CharField(
        max_length=20,
        choices=TransportTrip.DIRECTION_CHOICES,
        null=True,
        blank=True,
        verbose_name="الاتجاه",
    )
    name = models.CharField(
        max_length=200,
        verbose_name="اسم المجموعة",
    )
    max_students = models.PositiveIntegerField(
        default=10,
        verbose_name="الحد التقريبي للطلاب",
    )
    source = models.CharField(
        max_length=20,
        choices=[("auto", "تلقائية"), ("manual", "يدوية")],
        default="auto",
        verbose_name="مصدر المجموعة",
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name="مثبتة",
    )
    assigned_driver = models.ForeignKey(
        TransportDriver,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transport_groups",
        verbose_name="السائق المسند",
    )
    is_stable = models.BooleanField(
        default=False,
        verbose_name="مجموعة مستقرة",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="ملاحظات",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "مجموعة مواصلات"
        verbose_name_plural = "مجموعات المواصلات"
        indexes = [
            models.Index(
                fields=["route", "service_date", "direction"],
                name="transport_t_route_i_d829d4_idx",
            ),
            models.Index(fields=["route", "is_stable", "is_locked"], name="transport_g_route_i_5b7d6a_idx"),
        ]

    def __str__(self):
        return self.name


class TransportGroupMember(models.Model):
    """Stable membership bridge; the official registration remains canonical."""
    group = models.ForeignKey(
        TransportGroup, on_delete=models.CASCADE, related_name="members",
        verbose_name="مجموعة المواصلات",
    )
    registration = models.ForeignKey(
        "admissions.StudentRegistration", on_delete=models.PROTECT,
        related_name="transport_group_memberships", verbose_name="التسجيل",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "عضو مجموعة مواصلات"
        verbose_name_plural = "أعضاء مجموعات المواصلات"
        constraints = [
            models.UniqueConstraint(fields=["group", "registration"], name="uniq_transport_group_member"),
            models.UniqueConstraint(fields=["registration"], name="uniq_transport_registration_group_membership"),
        ]

    def __str__(self):
        return f"{self.group.name} — {self.registration_id}"
