from django import forms

from .models import TransportDriver


class TransportDriverForm(forms.ModelForm):
    class Meta:
        model = TransportDriver
        fields = ("name", "phone")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "اسم السائق",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "رقم الهاتف",
                    "dir": "ltr",
                }
            ),
        }
        labels = {
            "name": "اسم السائق",
            "phone": "رقم الهاتف",
        }

    def clean_name(self):
        value = self.cleaned_data["name"].strip()
        if not value:
            raise forms.ValidationError("يرجى إدخال اسم السائق.")
        return value

    def clean_phone(self):
        return self.cleaned_data["phone"].strip()


# ============================================================
# Transport Trip Management
# ============================================================

from django import forms
from django.db.models import Q

from admissions.models import TransportRoute
from transport.models import TransportDriver, TransportTrip


class TransportTripForm(forms.ModelForm):
    class Meta:
        model = TransportTrip
        fields = [
            "route",
            "driver",
            "service_date",
            "direction",
            "sequence",
            "vehicle_type",
            "vehicle_description",
        ]
        widgets = {
            "service_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d",
            ),
            "sequence": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "vehicle_description": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "وصف اختياري للمركبة",
                }
            ),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.school = school

        if school is None:
            self.fields["route"].queryset = TransportRoute.objects.none()
            self.fields["driver"].queryset = TransportDriver.objects.none()
            return

        route_qs = TransportRoute.objects.filter(
            school=school
        )

        driver_qs = TransportDriver.objects.filter(
            user__profile__school=school
        )

        # في الإضافة: المسارات والسائقون النشطون فقط.
        # في التعديل: نسمح بإظهار العنصر الحالي حتى لا تختفي
        # البيانات الحالية إذا أصبح غير نشط لاحقًا.
        if self.instance and self.instance.pk:
            route_qs = route_qs.filter(
                Q(is_active=True) | Q(pk=self.instance.route_id)
            )
            driver_qs = driver_qs.filter(
                Q(is_active=True) | Q(pk=self.instance.driver_id)
            )
        else:
            route_qs = route_qs.filter(is_active=True)
            driver_qs = driver_qs.filter(is_active=True)

        self.fields["route"].queryset = route_qs.order_by("name")
        self.fields["driver"].queryset = driver_qs.order_by("name")

        self.fields["route"].label = "المسار"
        self.fields["driver"].label = "السائق"
        self.fields["service_date"].label = "تاريخ الرحلة"
        self.fields["direction"].label = "اتجاه الرحلة"
        self.fields["sequence"].label = "رقم الرحلة"
        self.fields["vehicle_type"].label = "نوع المركبة"
        self.fields["vehicle_description"].label = "وصف المركبة"


# ============================================================
# Student Transport Assignment
# ============================================================

from admissions.models import StudentRegistration, TransportRoute


class TransportAssignmentForm(forms.Form):
    registration = forms.ModelChoiceField(
        queryset=StudentRegistration.objects.none(),
        label="الطالب",
        empty_label="اختر الطالب",
    )

    morning_trip = forms.ModelChoiceField(
        queryset=TransportTrip.objects.none(),
        label="رحلة الذهاب",
        required=False,
        empty_label="— اختر رحلة الذهاب —",
    )

    return_trip = forms.ModelChoiceField(
        queryset=TransportTrip.objects.none(),
        label="رحلة العودة",
        required=False,
        empty_label="— اختر رحلة العودة —",
    )

    def __init__(
        self,
        *args,
        school=None,
        selected_registration_id=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.school = school

        registrations = (
            StudentRegistration.objects
            .filter(
                school=school,
                transport_type__in=("go", "return", "both"),
                transport_route__isnull=False,
            )
            .select_related(
                "student",
                "transport_route",
            )
            .order_by("student_id")
        )

        self.fields["registration"].queryset = registrations

        self.fields["registration"].label_from_instance = (
            lambda obj:
            f"{obj.student} — {obj.transport_route}"
        )

        # ----------------------------------------------------
        # الرحلات الأساسية:
        # المدرسة + المخطط لها + المسار الرسمي
        # ----------------------------------------------------

        from django.utils import timezone
        trips = (
            TransportTrip.objects
            .filter(
                school=school,
                status="planned",
                service_date__gte=timezone.localdate(),
            )
            .select_related(
                "route",
                "driver",
            )
        )

        selected = None

        # عند GET:
        # /transport/assignments/add/?registration=123
        if selected_registration_id:
            try:
                selected = registrations.get(
                    pk=int(selected_registration_id)
                )
            except (
                TypeError,
                ValueError,
                StudentRegistration.DoesNotExist,
            ):
                selected = None

        # عند POST نأخذ الطالب من البيانات نفسها.
        if selected is None and self.data:
            registration_id = self.data.get("registration")

            if registration_id:
                try:
                    selected = registrations.get(
                        pk=int(registration_id)
                    )
                except (
                    TypeError,
                    ValueError,
                    StudentRegistration.DoesNotExist,
                ):
                    selected = None

        # ----------------------------------------------------
        # لا نعرض الرحلات إلا بعد تحديد الطالب.
        # ----------------------------------------------------

        if selected is None:
            self.fields["morning_trip"].queryset = (
                trips.none()
            )
            self.fields["return_trip"].queryset = (
                trips.none()
            )

            self.fields["morning_trip"].help_text = (
                "اختر الطالب أولًا لعرض رحلات الذهاب المتوافقة."
            )

            self.fields["return_trip"].help_text = (
                "اختر الطالب أولًا لعرض رحلات العودة المتوافقة."
            )

        else:
            route_id = selected.transport_route_id

            compatible_trips = trips.filter(
                route_id=route_id,
            )

            transport_type = selected.transport_type

            if transport_type in ("go", "both"):
                morning = compatible_trips.filter(
                    direction="morning",
                ).order_by(
                    "service_date",
                    "sequence",
                    "id",
                )
            else:
                morning = compatible_trips.none()

            if transport_type in ("return", "both"):
                returning = compatible_trips.filter(
                    direction="return",
                ).order_by(
                    "service_date",
                    "sequence",
                    "id",
                )
            else:
                returning = compatible_trips.none()

            self.fields["morning_trip"].queryset = morning
            self.fields["return_trip"].queryset = returning

            self.fields["morning_trip"].label_from_instance = (
                lambda obj:
                f"#{obj.sequence} | {obj.service_date} | "
                f"{obj.driver.name}"
            )

            self.fields["return_trip"].label_from_instance = (
                lambda obj:
                f"#{obj.sequence} | {obj.service_date} | "
                f"{obj.driver.name}"
            )

            if transport_type == "go":
                self.fields["return_trip"].help_text = (
                    "هذا الطالب مشترك بالذهاب فقط."
                )

            elif transport_type == "return":
                self.fields["morning_trip"].help_text = (
                    "هذا الطالب مشترك بالعودة فقط."
                )

        # ----------------------------------------------------
        # المحافظة على الطالب المختار بعد إعادة تحميل الصفحة
        # ----------------------------------------------------

        if selected is not None:
            self.initial["registration"] = selected.pk

    def clean(self):
        cleaned = super().clean()

        registration = cleaned.get("registration")
        morning_trip = cleaned.get("morning_trip")
        return_trip = cleaned.get("return_trip")

        if not registration:
            return cleaned

        transport_type = registration.transport_type

        if transport_type == "go":
            if not morning_trip:
                self.add_error(
                    "morning_trip",
                    "هذا الطالب مشترك بالذهاب، ويجب اختيار رحلة صباحية."
                )

            if return_trip:
                self.add_error(
                    "return_trip",
                    "هذا الطالب مشترك بالذهاب فقط، ولا يمكن تعيين رحلة عودة."
                )

        elif transport_type == "return":
            if morning_trip:
                self.add_error(
                    "morning_trip",
                    "هذا الطالب مشترك بالعودة فقط، ولا يمكن تعيين رحلة صباحية."
                )

            if not return_trip:
                self.add_error(
                    "return_trip",
                    "هذا الطالب مشترك بالعودة، ويجب اختيار رحلة عودة."
                )

        elif transport_type == "both":
            if not morning_trip:
                self.add_error(
                    "morning_trip",
                    "الطالب مشترك ذهابًا وعودة، ويجب اختيار رحلة صباحية."
                )

            if not return_trip:
                self.add_error(
                    "return_trip",
                    "الطالب مشترك ذهابًا وعودة، ويجب اختيار رحلة عودة."
                )

        else:
            self.add_error(
                "registration",
                "هذا التسجيل غير مشترك بخدمة المواصلات."
            )

        selected_trips = [
            trip
            for trip in (morning_trip, return_trip)
            if trip is not None
        ]

        for trip in selected_trips:
            if trip.school_id != self.school.id:
                raise forms.ValidationError(
                    "لا يمكن استخدام رحلة تابعة لمدرسة أخرى."
                )

            if (
                registration.transport_route_id
                and trip.route_id != registration.transport_route_id
            ):
                raise forms.ValidationError(
                    "رحلة الطالب يجب أن تكون على نفس المسار الرسمي المسجل للطالب."
                )

            if trip.status != "planned":
                raise forms.ValidationError(
                    "لا يمكن تعيين الطالب على رحلة غير مخططة."
                )

        if morning_trip and return_trip:

            if morning_trip.driver_id != return_trip.driver_id:
                self.add_error(
                    "return_trip",
                    "الطالب ذهابًا وعودة يجب أن يكون مع نفس السائق في الاتجاهين."
                )

            if morning_trip.service_date != return_trip.service_date:
                self.add_error(
                    "return_trip",
                    "رحلة الذهاب والعودة يجب أن تكونا في نفس التاريخ."
                )

        return cleaned


# ============================================================
# OPAL TRANSPORT — FAMILY LOCATION
# ============================================================

from .models import TransportFamilyLocation


class TransportFamilyLocationForm(forms.ModelForm):
    class Meta:
        model = TransportFamilyLocation
        fields = ("label", "address", "latitude", "longitude")
        labels = {
            "label": "وصف الموقع",
            "address": "العنوان",
            "latitude": "خط العرض",
            "longitude": "خط الطول",
        }
        widgets = {
            "label": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "مثال: شارع الجامعة - قرب المدرسة",
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "العنوان أو وصف أقرب معلم",
                }
            ),
            "latitude": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.000001",
                    "inputmode": "decimal",
                    "dir": "ltr",
                }
            ),
            "longitude": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.000001",
                    "inputmode": "decimal",
                    "dir": "ltr",
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get("latitude")
        longitude = cleaned.get("longitude")

        if latitude is None or longitude is None:
            self.add_error(None, "يجب تحديد خط العرض وخط الطول لموقع الاستلام.")
            return cleaned

        if not (-90 <= float(latitude) <= 90):
            self.add_error("latitude", "خط العرض يجب أن يكون بين -90 و90.")

        if not (-180 <= float(longitude) <= 180):
            self.add_error("longitude", "خط الطول يجب أن يكون بين -180 و180.")

        if not cleaned.get("label") and not cleaned.get("address"):
            self.add_error(None, "أدخل وصف الموقع أو العنوان.")

        return cleaned

# ============================================================
# Canonical Student Transport Subscription Management
# ============================================================

class TransportSubscriptionForm(forms.Form):
    registration = forms.ModelChoiceField(
        queryset=StudentRegistration.objects.none(),
        label="الطالب",
        empty_label="اختر الطالب",
    )
    transport_route = forms.ModelChoiceField(
        queryset=TransportRoute.objects.none(),
        label="مسار المواصلات",
        required=False,
        empty_label="— اختر المسار —",
    )
    transport_type = forms.ChoiceField(
        label="نوع المواصلات",
        choices=StudentRegistration.TRANSPORT_CHOICES,
        initial="none",
    )

    def __init__(self, *args, school=None, selected_registration_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school
        registrations = (
            StudentRegistration.objects
            .filter(school=school, student__isnull=False)
            .select_related("student", "transport_route", "grade")
            .order_by("student__full_name", "pk")
        )
        routes = TransportRoute.objects.filter(school=school).order_by("name")
        self.fields["registration"].queryset = registrations
        self.fields["transport_route"].queryset = routes
        self.fields["registration"].label_from_instance = lambda obj: (
            f"{obj.student.full_name} — {obj.registration_number}"
        )

        selected = None
        raw_id = selected_registration_id
        if raw_id is None and self.data:
            raw_id = self.data.get("registration")
        if raw_id:
            try:
                selected = registrations.get(pk=int(raw_id))
            except (TypeError, ValueError, StudentRegistration.DoesNotExist):
                selected = None

        if selected is not None and not self.is_bound:
            self.initial.update({
                "registration": selected.pk,
                "transport_route": selected.transport_route_id,
                "transport_type": selected.transport_type,
            })

    def clean(self):
        cleaned = super().clean()
        registration = cleaned.get("registration")
        route = cleaned.get("transport_route")
        transport_type = cleaned.get("transport_type")
        if not registration:
            return cleaned
        if transport_type == "none":
            cleaned["transport_route"] = None
        elif route is None:
            self.add_error("transport_route", "اختر مسار المواصلات للطالب المشترك.")
        elif route.school_id != self.school.pk:
            raise forms.ValidationError("لا يمكن اختيار مسار تابع لمدرسة أخرى.")
        return cleaned
