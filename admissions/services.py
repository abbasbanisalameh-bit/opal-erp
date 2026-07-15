
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
    return AcademicYear.objects.filter(school=school, is_current=True).first() or AcademicYear.objects.filter(school=school).order_by("-start_date").first()


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
    from parent_portal.models import FamilyStudent

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
        national_id=data.get("national_id") or "",
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
    if first_payment in (None, ""):
        first_payment = money(net_total * Decimal(settings.first_payment_percent or 0) / Decimal("100"))
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


@transaction.atomic
def create_student_registration(form, user=None):
    data = form.cleaned_data
    selected_grade = data.get("grade")
    profile = getattr(user, "profile", None) if user else None
    school = (
        getattr(form, "school", None)
        or getattr(selected_grade, "school", None)
        or getattr(profile, "school", None)
        or active_school()
    )
    academic_year = getattr(form, "academic_year", None) or current_academic_year(school)
    full_name = compose_full_name(data.get("first_name"), data.get("father_name"), data.get("grandfather_name"), data.get("family_name"))
    settings = get_registration_settings(school)

    # OPAL: التعرف الذكي على الإخوة
    selected_discount_type = data.get("discount_type")
    selected_sibling_student = data.get("sibling_student")
    sibling_message = ""

    # لا نطبق خصم الإخوة فوق خصم آخر، لكن إذا لم يختر المستخدم خصمًا نفعله تلقائيًا عند وجود أخ مؤهل.
    if selected_discount_type in (None, "", "none", "sibling"):
        resolved_discount, resolved_sibling, sibling_message = resolve_sibling_discount_for_form(data, settings)
        selected_discount_type = resolved_discount
        selected_sibling_student = resolved_sibling

    totals = calculate_registration_totals(
        grade=data.get("grade"),
        transport_route=data.get("transport_route"),
        transport_type=data.get("transport_type"),
        discount_type=selected_discount_type,
        admin_discount_value=data.get("admin_discount_value"),
        sibling_student=selected_sibling_student,
        first_payment=data.get("first_payment"),
        school=school,
        academic_year=academic_year,
    )
    national_id = normalize_identifier(data.get("national_id") or "")
    if national_id and Student.objects.filter(national_id=national_id).exists():
        raise ValueError("الرقم الوطني مرتبط بطالب موجود. استخدم سجل الطالب الحالي.")

    student = Student.objects.create(
        source="manual",
        student_number=generate_student_number(),
        national_id=national_id,
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
    if academic_year and data.get("grade"):
        Enrollment.objects.get_or_create(
            student=student,
            academic_year=academic_year,
            defaults={"grade": data.get("grade"), "section": data.get("section"), "joined_at": timezone.localdate(), "status": "active"},
        )

    fee_category, _ = FeeCategory.objects.get_or_create(
        name="رسوم التسجيل المدرسية",
        defaults={"description": "رسوم ناتجة عن تسجيل طالب جديد", "amount": totals["net_total"], "active": True},
    )
    invoice = StudentInvoice.objects.create(
        student=student,
        academic_year=academic_year,
        fee_category=fee_category,
        amount=totals["net_total"],
        due_date=timezone.localdate(),
        paid=totals["remaining_amount"] <= 0,
    )
    payment = None
    receipt = None
    if totals["first_payment"] > 0:
        payment = StudentPayment.objects.create(invoice=invoice, amount=totals["first_payment"], notes="دفعة تسجيل أولى")
        receipt = Receipt.objects.create(payment=payment, receipt_number=generate_receipt_number())

    registration = StudentRegistration.objects.create(
        school=school,
        branch=(getattr(data.get("section"), "branch", None) or getattr(profile, "branch", None)),
        academic_year=academic_year,
        registration_number=generate_registration_number(),
        student=student,
        grade=data.get("grade"),
        section=data.get("section"),
        first_name=data.get("first_name"),
        father_name=data.get("father_name") or "",
        grandfather_name=data.get("grandfather_name") or "",
        family_name=data.get("family_name") or "",
        full_name=full_name,
        national_id=data.get("national_id") or "",
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
        created_by=user if getattr(user, "is_authenticated", False) else None,
        notes=((data.get("notes") or "") + ("\n" + sibling_message if sibling_message else "")),
        **totals,
    )

    # إنشاء/تحديث حساب ولي الأمر وربط جميع الأبناء بحساب واحد.
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

    # تجهيز سجل مزامنة OpenEMIS بدون تعطيل التسجيل إذا لم تكن بيانات الربط متوفرة.
    try:
        from openemis_integration.services import queue_student_push
        queue_student_push(student, user, reason="registration")
    except Exception:
        pass
    return registration
