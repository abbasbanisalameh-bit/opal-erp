
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction, models
from django.utils import timezone
from core.identifiers import normalize_identifier
from core.models import Sequence, School, AcademicYear
from students.models import Student
from academics.models import Enrollment
from accounting.models import FeeCategory, StudentInvoice, StudentPayment, Receipt
from admissions.models import GradeFee, RegistrationSettings, StudentRegistration


TWOPLACES = Decimal("0.01")


def money(value):
    return (Decimal(value or 0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def active_school():
    return School.objects.filter(is_active=True).first() or School.objects.create(name="OPAL School")


def current_academic_year(school=None):
    school = school or active_school()
    return AcademicYear.objects.filter(school=school, is_current=True, is_closed=False).first()


def get_registration_settings(school=None):
    school = school or active_school()
    settings, _ = RegistrationSettings.objects.get_or_create(school=school)
    return settings


def next_sequence(key, prefix, padding=6):
    seq, _ = Sequence.objects.get_or_create(
        key=key,
        defaults={"prefix": prefix, "current_number": 0, "padding": padding, "yearly_reset": True},
    )
    seq.current_number += 1
    seq.padding = seq.padding or padding
    seq.save(update_fields=["current_number", "padding"])
    return f"{seq.prefix}{str(seq.current_number).zfill(seq.padding)}"


def generate_registration_number():
    year = datetime.now().year
    return next_sequence(f"registration_{year}", f"REG-{year}-", 5)


def generate_student_number():
    year = datetime.now().year
    return next_sequence(f"student_{year}", f"STU-{year}-", 5)


def generate_application_number():
    year = datetime.now().year
    return next_sequence(f"admission_{year}", f"ADM-{year}-", 6)


def generate_receipt_number():
    year = datetime.now().year
    return next_sequence(f"receipt_{year}", f"RC-{year}-", 6)


def grade_fee_amount(grade, school=None, academic_year=None):
    if not grade:
        return money(0)
    school = school or active_school()
    fee = None
    if academic_year:
        fee = GradeFee.objects.filter(school=school, grade=grade, academic_year=academic_year, is_active=True).order_by("-updated_at", "-pk").first()
    if fee is None:
        fee = GradeFee.objects.filter(school=school, grade=grade, academic_year__isnull=True, is_active=True).order_by("-updated_at", "-pk").first()
    if fee is None:
        fee = GradeFee.objects.filter(school=school, grade=grade, is_active=True).order_by("-updated_at", "-pk").first()
    return money(fee.tuition_fee if fee else 0)


def transport_fee_amount(route, transport_type):
    if not route or transport_type == "none":
        return money(0)
    full = money(route.full_fee)
    if transport_type in ("go", "return"):
        return money(full / Decimal("2"))
    if transport_type == "both":
        return full
    return money(0)


def sibling_discount_already_used(sibling_student):
    if not sibling_student:
        return False
    return StudentRegistration.objects.filter(discount_type="sibling").filter(models.Q(sibling_student=sibling_student) | models.Q(student=sibling_student)).exists()



def find_existing_siblings(*, phone="", father_name="", family_name="", mother_name="", guardian_name="", guardian_identity_type="national", guardian_identity_number="", national_id="", exclude_student_id=None):
    """Return siblings linked through the single canonical Family record.

    The guardian national/personal identifier is the authoritative family key.
    We deliberately do not infer siblings from matching names or phone numbers,
    because that can connect unrelated students.
    """
    
    identity = normalize_identifier(guardian_identity_number)
    if not identity:
        return Student.objects.none()

    qs = Student.objects.filter(
        family_links__family__identity_number=identity,
        family_links__is_active=True,
        is_active=True,
    ).distinct()
    if exclude_student_id:
        qs = qs.exclude(id=exclude_student_id)
    return qs


def sibling_discount_used_registration(siblings):
    if not siblings:
        return None
    sibling_ids = list(siblings.values_list("id", flat=True))
    return (
        StudentRegistration.objects
        .filter(discount_type="sibling")
        .filter(models.Q(student_id__in=sibling_ids) | models.Q(sibling_student_id__in=sibling_ids))
        .select_related("student", "sibling_student")
        .first()
    )


def resolve_sibling_discount_for_form(data, settings):
    siblings = find_existing_siblings(
        phone=data.get("phone") or "",
        father_name=data.get("father_name") or "",
        family_name=data.get("family_name") or "",
        mother_name=data.get("mother_name") or "",
        guardian_name=data.get("guardian_name") or "",
        guardian_identity_type=data.get("guardian_identity_type") or "national",
        guardian_identity_number=normalize_identifier(data.get("guardian_identity_number") or ""),
        national_id="",
    )

    if not siblings.exists():
        return "none", None, ""

    first_sibling = siblings.first()
    used = sibling_discount_used_registration(siblings)

    if settings.sibling_discount_once_per_family and used:
        used_student = used.student or used.sibling_student
        used_name = used_student.full_name if used_student else used.full_name
        return "none", first_sibling, f"يوجد أخ مسجل، لكن الطالب {used_name} استفاد سابقًا من خصم الإخوة، لذلك تم إلغاء خصم الإخوة لهذا الطالب."

    return "sibling", first_sibling, f"تم التعرف على أخ مسجل: {first_sibling.full_name}. تم تفعيل خصم الإخوة تلقائيًا."

def discount_amount(tuition_fee, discount_type, settings=None, admin_discount_value=0, sibling_student=None):
    settings = settings or get_registration_settings()
    tuition_fee = money(tuition_fee)
    percent = Decimal("0")
    if discount_type == "quran_100" and settings.enable_quran_discount:
        percent = settings.quran_100_percent
    elif discount_type == "quran_75" and settings.enable_quran_discount:
        percent = settings.quran_75_percent
    elif discount_type == "quran_50" and settings.enable_quran_discount:
        percent = settings.quran_50_percent
    elif discount_type == "quran_25" and settings.enable_quran_discount:
        percent = settings.quran_25_percent
    elif discount_type == "cash" and settings.enable_cash_discount:
        percent = settings.cash_discount_percent
    elif discount_type == "sibling" and settings.enable_sibling_discount:
        if settings.sibling_discount_once_per_family and sibling_discount_already_used(sibling_student):
            percent = Decimal("0")
        else:
            percent = settings.sibling_discount_percent
    elif discount_type == "admin" and settings.enable_admin_discount:
        return min(money(admin_discount_value), tuition_fee)
    return min(money(tuition_fee * Decimal(percent or 0) / Decimal("100")), tuition_fee)


def calculate_registration_totals(*, grade, transport_route=None, transport_type="none", discount_type="none", admin_discount_value=0, sibling_student=None, first_payment=None, school=None, academic_year=None):
    school = school or active_school()
    academic_year = academic_year or current_academic_year(school)
    settings = get_registration_settings(school)
    tuition = grade_fee_amount(grade, school, academic_year)
    transport = transport_fee_amount(transport_route, transport_type)
    discount = discount_amount(tuition, discount_type, settings, admin_discount_value, sibling_student)
    net_total = money(tuition + transport - discount)
    default_first_payment = money(
        net_total * Decimal(settings.first_payment_percent or 0) / Decimal("100")
    )
    # التسجيل اليدوي يعتمد الدفعة الافتراضية المحسوبة من الإعدادات.
    # نبقي التوافق مع أي تكامل يرسل قيمة موجبة صراحة، لكن الصفر/الفراغ
    # لا يعطلان الحساب التلقائي.
    if first_payment in (None, "") or money(first_payment) <= 0:
        first_payment = default_first_payment
    else:
        first_payment = min(money(first_payment), net_total)
    remaining = money(net_total - first_payment)
    return {
        "tuition_fee": tuition,
        "transport_fee": transport,
        "discount_value": discount,
        "net_total": net_total,
        "first_payment": first_payment,
        "remaining_amount": remaining,
    }


def compose_full_name(first_name, father_name="", grandfather_name="", family_name=""):
    return " ".join([p.strip() for p in [first_name, father_name, grandfather_name, family_name] if p and p.strip()])


def _registration_context(form, user, data):
    """Resolve the shared school/year/name/settings context once per registration."""
    selected_grade = data.get("grade")
    profile = getattr(user, "profile", None) if user else None
    school = (
        getattr(form, "school", None)
        or getattr(selected_grade, "school", None)
        or getattr(profile, "school", None)
        or active_school()
    )
    academic_year = getattr(form, "academic_year", None) or current_academic_year(school)
    full_name = compose_full_name(
        data.get("first_name"),
        data.get("father_name"),
        data.get("grandfather_name"),
        data.get("family_name"),
    )
    return {
        "profile": profile,
        "school": school,
        "academic_year": academic_year,
        "full_name": full_name,
        "settings": get_registration_settings(school),
    }


def _resolve_registration_discount(data, settings):
    selected_discount_type = data.get("discount_type")
    selected_sibling_student = data.get("sibling_student")
    sibling_message = ""

    # لا نطبق خصم الإخوة فوق خصم آخر، لكن إذا لم يختر المستخدم خصمًا نفعله تلقائيًا عند وجود أخ مؤهل.
    if selected_discount_type in (None, "", "none", "sibling"):
        selected_discount_type, selected_sibling_student, sibling_message = resolve_sibling_discount_for_form(
            data, settings
        )
    return selected_discount_type, selected_sibling_student, sibling_message


def _create_student_record(*, data, full_name):
    """Create the canonical student record used by the admission workflow."""
    # الرقم الوطني في التسجيل اليدوي هو رقم ولي الأمر فقط.
    # يبقى Student.national_id متاحًا لتعبئته من OpenEMIS عند المزامنة.
    student_national_id = ""
    student = Student.objects.create(
        source="manual",
        student_number=generate_student_number(),
        national_id=student_national_id,
        full_name=full_name,
        guardian_name=data.get("guardian_name") or "",
        father_name=data.get("father_name") or "",
        mother_name=data.get("mother_name") or "",
        gender=data.get("gender") or "",
        grade=getattr(data.get("grade"), "name", str(data.get("grade") or "")),
        section=getattr(data.get("section"), "name", str(data.get("section") or "")),
        phone=data.get("phone") or "",
        address=data.get("address") or "",
        enrollment_date=timezone.localdate(),
        photo=data.get("photo"),
        status="active",
        is_active=True,
    )
    return student, student_national_id


def _ensure_student_enrollment(*, student, data, academic_year):
    """Create the canonical academic enrollment when a year and grade are available."""
    if not academic_year or not data.get("grade"):
        return None
    enrollment, _ = Enrollment.objects.get_or_create(
        student=student,
        academic_year=academic_year,
        defaults={
            "grade": data.get("grade"),
            "section": data.get("section"),
            "joined_at": timezone.localdate(),
            "status": "active",
        },
    )
    return enrollment


def _create_student_and_enrollment(*, data, full_name, academic_year):
    """Create the student, then attach its academic enrollment as a separate explicit step."""
    student, student_national_id = _create_student_record(
        data=data,
        full_name=full_name,
    )
    _ensure_student_enrollment(
        student=student,
        data=data,
        academic_year=academic_year,
    )
    return student, student_national_id


def _registration_fee_category(net_total):
    """Return the canonical fee category used by the registration workflow."""
    fee_category, _ = FeeCategory.objects.get_or_create(
        name="رسوم التسجيل المدرسية",
        defaults={
            "description": "رسوم ناتجة عن تسجيل طالب جديد",
            "amount": net_total,
            "active": True,
        },
    )
    return fee_category


def _create_registration_invoice(*, student, academic_year, totals, fee_category):
    """Create the invoice that represents the final registration total."""
    return StudentInvoice.objects.create(
        student=student,
        academic_year=academic_year,
        fee_category=fee_category,
        amount=totals["net_total"],
        due_date=timezone.localdate(),
        paid=totals["remaining_amount"] <= 0,
    )


def _create_registration_receipt(payment):
    """Create the receipt linked to the initial registration payment."""
    return Receipt.objects.create(
        payment=payment,
        receipt_number=generate_receipt_number(),
    )


def _create_initial_registration_payment(*, invoice, totals, data, user):
    """Create the optional first payment and its linked receipt."""
    if totals["first_payment"] <= 0:
        return None, None

    payment = StudentPayment.objects.create(
        invoice=invoice,
        amount=totals["first_payment"],
        payment_method=data.get("payment_method") or "unspecified",
        created_by=user if getattr(user, "is_authenticated", False) else None,
        notes="دفعة تسجيل أولى",
    )
    return payment, _create_registration_receipt(payment)


def _create_registration_financial_records(*, student, academic_year, totals, data, user):
    """Create the complete financial side of a registration without changing its semantics."""
    fee_category = _registration_fee_category(totals["net_total"])
    invoice = _create_registration_invoice(
        student=student,
        academic_year=academic_year,
        totals=totals,
        fee_category=fee_category,
    )
    payment, receipt = _create_initial_registration_payment(
        invoice=invoice,
        totals=totals,
        data=data,
        user=user,
    )
    return invoice, payment, receipt


def _create_registration_record(
    *, data, user, operation_token, context, student, student_national_id,
    totals, selected_discount_type, selected_sibling_student, sibling_message,
    invoice, payment, receipt,
):
    profile = context["profile"]
    return StudentRegistration.objects.create(
        school=context["school"],
        branch=(getattr(data.get("section"), "branch", None) or getattr(profile, "branch", None)),
        academic_year=context["academic_year"],
        registration_number=generate_registration_number(),
        **({"operation_token": operation_token} if operation_token else {}),
        student=student,
        grade=data.get("grade"),
        section=data.get("section"),
        first_name=data.get("first_name"),
        father_name=data.get("father_name") or "",
        grandfather_name=data.get("grandfather_name") or "",
        family_name=data.get("family_name") or "",
        full_name=context["full_name"],
        national_id=student_national_id,
        gender=data.get("gender") or "",
        birth_date=data.get("birth_date"),
        address=data.get("address") or "",
        phone=data.get("phone") or "",
        guardian_name=data.get("guardian_name") or "",
        guardian_identity_type=data.get("guardian_identity_type") or "national",
        guardian_identity_number=normalize_identifier(data.get("guardian_identity_number") or ""),
        mother_name=data.get("mother_name") or "",
        photo=data.get("photo"),
        transport_route=data.get("transport_route"),
        transport_type=data.get("transport_type"),
        discount_type=selected_discount_type,
        admin_discount_value=data.get("admin_discount_value") or 0,
        sibling_student=selected_sibling_student,
        invoice=invoice,
        payment=payment,
        receipt=receipt,
        payment_method=data.get("payment_method") or "unspecified",
        created_by=user if getattr(user, "is_authenticated", False) else None,
        notes=((data.get("notes") or "") + ("\n" + sibling_message if sibling_message else "")),
        **totals,
    )



def _create_registration_domain_records(
    *, data, user, operation_token, context, totals,
    selected_discount_type, selected_sibling_student, sibling_message,
):
    """Persist the canonical student, finance, and registration records as one explicit stage."""
    student, student_national_id = _create_student_and_enrollment(
        data=data,
        full_name=context["full_name"],
        academic_year=context["academic_year"],
    )
    invoice, payment, receipt = _create_registration_financial_records(
        student=student,
        academic_year=context["academic_year"],
        totals=totals,
        data=data,
        user=user,
    )
    registration = _create_registration_record(
        data=data,
        user=user,
        operation_token=operation_token,
        context=context,
        student=student,
        student_national_id=student_national_id,
        totals=totals,
        selected_discount_type=selected_discount_type,
        selected_sibling_student=selected_sibling_student,
        sibling_message=sibling_message,
        invoice=invoice,
        payment=payment,
        receipt=receipt,
    )
    return registration, student

def _link_registration_parent_family(*, registration, student, data, school):
    """Link the student to the canonical family and expose one-time credentials transiently."""
    from parent_portal.services import create_or_update_parent_family_for_student

    family = create_or_update_parent_family_for_student(
        student,
        guardian_name=data.get("guardian_name") or "",
        phone=data.get("phone") or "",
        school=school,
        identity_type=data.get("guardian_identity_type") or "national",
        identity_number=data.get("guardian_identity_number") or "",
        relation="ولي أمر",
    )
    # One-time credentials are transient and are never stored in the database.
    registration.parent_initial_username = family.user.username if family and family.user else ""
    registration.parent_initial_password = getattr(family, "initial_password", "")
    return family


def _queue_registration_openemis_push(*, student, user):
    """Queue the existing OpenEMIS push without blocking a successful registration."""
    try:
        from openemis_integration.services import queue_student_push
        queue_student_push(student, user, reason="registration")
    except Exception:
        pass


def _notify_registration_guardian(registration):
    """Send the existing guardian notification after the family link is ready."""
    from parent_portal.notification_services import notify_guardian_for_registration
    notify_guardian_for_registration(registration)


def _complete_registration_integrations(*, registration, student, data, user, school):
    """Run the existing post-registration integrations in their original order."""
    _link_registration_parent_family(
        registration=registration,
        student=student,
        data=data,
        school=school,
    )
    _queue_registration_openemis_push(student=student, user=user)
    _notify_registration_guardian(registration)


@transaction.atomic
def create_student_registration(form, user=None):
    """Orchestrate the existing admission workflow through explicit internal steps."""
    data = form.cleaned_data
    operation_token = data.get("registration_token")
    if operation_token:
        existing = StudentRegistration.objects.filter(operation_token=operation_token).first()
        if existing:
            return existing

    context = _registration_context(form, user, data)
    selected_discount_type, selected_sibling_student, sibling_message = _resolve_registration_discount(
        data, context["settings"]
    )
    totals = calculate_registration_totals(
        grade=data.get("grade"),
        transport_route=data.get("transport_route"),
        transport_type=data.get("transport_type"),
        discount_type=selected_discount_type,
        admin_discount_value=data.get("admin_discount_value"),
        sibling_student=selected_sibling_student,
        # تظهر النسبة الافتراضية للمستخدم، مع اعتماد أي قيمة موجبة يعدلها قبل الحفظ.
        first_payment=data.get("first_payment"),
        school=context["school"],
        academic_year=context["academic_year"],
    )
    registration, student = _create_registration_domain_records(
        data=data,
        user=user,
        operation_token=operation_token,
        context=context,
        totals=totals,
        selected_discount_type=selected_discount_type,
        selected_sibling_student=selected_sibling_student,
        sibling_message=sibling_message,
    )
    _complete_registration_integrations(
        registration=registration,
        student=student,
        data=data,
        user=user,
        school=context["school"],
    )
    return registration
