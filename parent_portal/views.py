from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
import csv

from .models import Family, FamilyStudent
from .services import ensure_family_account, reset_family_password
from .services import update_family_identity
from .receipt_services import build_guardian_receipt_history
from .financial_services import build_guardian_annual_statement, guardian_financial_years
from .forms import FamilyIdentityForm, ParentFamilyPersonalForm, ParentPhotoForm, ParentStudentPersonalForm
from .permissions import parent_required
from accounting.models import StudentInvoice
from attendance_v2.models import Attendance
from announcements.models import Announcement
from exams.models import StudentMark
from accounts.models import UserProfile
from .academic_services import homework_for_student, homework_rows_for_students, student_class_rank
from .parent360 import build_parent360_context
from admissions.financial_services import (
    student_total_fees,
    student_total_paid,
    student_remaining,
    student_payment_status,
)
from admissions.models import FeePaymentAllocation, FeePayment
from enterprise_ops.permissions import management_required
from enterprise_ops.services import audit
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from .duplicate_services import guardian_duplicate_groups, merge_guardian_group
from timetable.live_services import student_live_status

try:
    from documents.models import StudentIssuedDocument
except Exception:  # keeps portal safe if documents app changes later
    StudentIssuedDocument = None


def _students_for_user(user):
    """Return only students linked to the logged-in parent account."""
    family = Family.objects.filter(user=user).first()
    if family:
        return [
            link.student
            for link in FamilyStudent.objects.filter(family=family, is_active=True)
            .select_related("student")
            .order_by("student__full_name")
        ]
    return []


def _normalized_students_for_user(user):
    return _students_for_user(user)


def _family_for_user(user):
    return Family.objects.filter(user=user).first()


def _student_or_403(user, student_id):
    students = _normalized_students_for_user(user)
    allowed_ids = {student.id for student in students}
    if int(student_id) not in allowed_ids:
        raise PermissionDenied("لا تملك صلاحية الوصول إلى هذا الطالب.")
    return get_object_or_404(type(students[0]).objects.all(), pk=student_id)


def _student_card(student):
    remaining = student_remaining(student)
    status = student_payment_status(student)
    return {
        "student": student,
        "total": student_total_fees(student),
        "paid": student_total_paid(student),
        "remaining": remaining,
        "status": status,
        "status_label": "مسدد بالكامل" if remaining <= 0 else ("غير مسدد" if student_total_paid(student) <= 0 else "متبقٍ جزئي"),
        "status_class": "success" if remaining <= 0 else ("danger" if student_total_paid(student) <= 0 else "warning"),
        "attendance": Attendance.objects.filter(student=student).order_by("-date")[:5],
        "marks": StudentMark.objects.filter(student=student, exam__status__in=["published", "closed"]).select_related("exam", "exam__subject")[:5],
        "rank": student_class_rank(student),
        "homework": homework_for_student(student)[:5],
        "schedule": student_live_status(student),
    }


@parent_required
def dashboard(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")

    cards = [_student_card(student) for student in students]
    announcements = Announcement.objects.filter(is_active=True).order_by("-created_at")[:10]
    receipt_history = build_guardian_receipt_history(students)
    family = _family_for_user(request.user)
    totals = {
        "students_count": len(students),
        "total": sum((card["total"] for card in cards), 0),
        "paid": sum((card["paid"] for card in cards), 0),
        "remaining": sum((card["remaining"] for card in cards), 0),
    }
    return render(
        request,
        "parent_portal/dashboard.html",
        {
            "family": family,
            "students": students,
            "cards": cards,
            "announcements": announcements,
            "receipt_history": receipt_history,
            "totals": totals,
        },
    )


@parent_required
def parent_360(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    family = _family_for_user(request.user)
    if family is None:
        return render(request, "parent_portal/no_profile.html")
    context = build_parent360_context(family, students)
    return render(request, "parent_portal/parent_360.html", context)


@parent_required
def children(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    return render(request, "parent_portal/children.html", {"cards": [_student_card(s) for s in students]})


@parent_required
def student_detail(request, student_id):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    student = _student_or_403(request.user, student_id)
    invoices = StudentInvoice.objects.filter(student=student).select_related("fee_category").prefetch_related("payments")
    allocations = FeePaymentAllocation.objects.filter(student=student).select_related("fee_payment").order_by("-created_at")
    attendance = Attendance.objects.filter(student=student).order_by("-date")[:30]
    marks = StudentMark.objects.filter(student=student, exam__status__in=["published", "closed"]).select_related("exam", "exam__subject")
    rank = student_class_rank(student)
    homework_items = homework_for_student(student)
    docs = []
    if StudentIssuedDocument:
        docs = StudentIssuedDocument.objects.filter(student=student).select_related("issued_document")[:20]
    return render(request, "parent_portal/student_detail.html", {
        "student": student,
        "invoices": invoices,
        "allocations": allocations,
        "attendance": attendance,
        "marks": marks,
        "rank": rank,
        "homework_items": homework_items,
        "documents": docs,
        "total": student_total_fees(student),
        "paid": student_total_paid(student),
        "remaining": student_remaining(student),
    })


@parent_required
def fees(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    cards = [_student_card(student) for student in students]
    receipt_history = build_guardian_receipt_history(students)
    statement_years = guardian_financial_years(students)
    selected_year = None
    requested_year = request.GET.get("year")
    if requested_year:
        selected_year = statement_years.filter(pk=requested_year).first()
    if selected_year is None:
        selected_year = statement_years.filter(is_current=True).first() or statement_years.first()
    annual_statement = build_guardian_annual_statement(students, selected_year) if selected_year else None
    return render(
        request,
        "parent_portal/fees.html",
        {
            "family": _family_for_user(request.user),
            "cards": cards,
            "receipt_history": receipt_history,
            "statement_years": statement_years,
            "selected_year": selected_year,
            "annual_statement": annual_statement,
        },
    )


@parent_required
def attendance(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    records = Attendance.objects.filter(student__in=students).select_related("student").order_by("-date")[:120]
    return render(request, "parent_portal/attendance.html", {"records": records})


@parent_required
def marks(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    records = StudentMark.objects.filter(student__in=students, exam__status__in=["published", "closed"]).select_related("student", "exam", "exam__subject").order_by("student__full_name", "-exam__exam_date")
    ranks = {student.pk: student_class_rank(student) for student in students}
    return render(request, "parent_portal/marks.html", {"records": records, "students": students, "ranks": ranks})


@parent_required
def homework(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    return render(request, "parent_portal/homework.html", {"rows": homework_rows_for_students(students)})


@parent_required
def student_personal_update(request, student_id):
    student = _student_or_403(request.user, student_id)
    form = ParentStudentPersonalForm(request.POST or None, request.FILES or None, instance=student)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث الصورة والمعلومات الشخصية المسموح بها للطالب.")
        return redirect("parent_portal:student_detail", student_id=student.pk)
    return render(request, "parent_portal/student_personal_form.html", {"student": student, "form": form})


@parent_required
def timetable(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    from academics.models import Enrollment
    from timetable.models import TimetableEntry
    enrollments = Enrollment.objects.filter(student__in=students, status="active").select_related("student", "section", "academic_year")
    rows = []
    for enrollment in enrollments:
        entries = (
            TimetableEntry.objects.filter(
                section=enrollment.section,
                academic_year=enrollment.academic_year,
                is_active=True,
            )
            .select_related("subject", "teacher", "time_slot")
            .order_by("day", "time_slot__order")
        )
        rows.append({"student": enrollment.student, "entries": entries})
    return render(request, "parent_portal/timetable.html", {"rows": rows})

@parent_required
def documents(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    records = []
    if StudentIssuedDocument:
        records = StudentIssuedDocument.objects.filter(student__in=students).select_related("student", "issued_document")[:100]
    return render(request, "parent_portal/documents.html", {"records": records})


@parent_required
def announcements(request):
    records = Announcement.objects.filter(is_active=True).order_by("-created_at")[:100]
    return render(request, "parent_portal/announcements.html", {"records": records})


@parent_required
def account(request):
    family = _family_for_user(request.user)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    action = request.POST.get("action", "") if request.method == "POST" else ""
    family_form = ParentFamilyPersonalForm(
        request.POST if action == "personal" else None, instance=family, prefix="family"
    )
    photo_form = ParentPhotoForm(
        request.POST if action == "photo" else None,
        request.FILES if action == "photo" else None,
        instance=profile,
        prefix="photo",
    )
    password_form = PasswordChangeForm(
        request.user, request.POST if action == "password" else None, prefix="password"
    )
    for field in password_form.fields.values():
        field.widget.attrs.setdefault("class", "form-control")

    if request.method == "POST" and action == "personal" and family_form.is_valid():
        family_form.save()
        messages.success(request, "تم تحديث معلومات ولي الأمر الشخصية.")
        return redirect("parent_portal:account")
    if request.method == "POST" and action == "photo" and photo_form.is_valid():
        photo_form.save()
        messages.success(request, "تم تحديث الصورة الشخصية.")
        return redirect("parent_portal:account")
    if request.method == "POST" and action == "password" and password_form.is_valid():
        user = password_form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "تم تغيير كلمة المرور بنجاح.")
        return redirect("parent_portal:account")

    return render(request, "parent_portal/account.html", {
        "family": family,
        "profile": profile,
        "family_form": family_form,
        "photo_form": photo_form,
        "password_form": password_form,
        "form": password_form,
    })

@management_required
def family_management(request):
    families = (
        Family.objects.filter(is_active=True, merged_into__isnull=True).select_related("user", "school")
        .prefetch_related("children__student")
        .order_by("guardian_name", "phone", "id")
    )
    return render(request, "parent_portal/family_management.html", {"families": families})


@management_required
def guardian_duplicates(request):
    return render(request, "parent_portal/guardian_duplicates.html", {"groups": guardian_duplicate_groups()})


@management_required
@require_POST
def guardian_duplicate_merge(request):
    ids = [value for value in request.POST.get("family_ids", "").split(",") if value.strip().isdigit()]
    try:
        canonical, count = merge_guardian_group(
            family_ids=ids,
            canonical_id=int(request.POST.get("canonical_id", "0")),
            user=request.user,
        )
    except (ValidationError, ValueError) as exc:
        messages.error(request, getattr(exc, "messages", [str(exc)])[0])
    else:
        audit(request, "update", "parent_portal.Family", canonical.pk, f"دمج {count} ملفات مكررة في ملف ولي الأمر {canonical.pk}")
        messages.success(request, f"تم دمج {count} ملفات في الملف الأساسي مع نقل روابط الأبناء وإيقاف الحسابات المكررة.")
    return redirect("parent_portal:guardian_duplicates")


def _family_finance_context(family):
    links = list(
        FamilyStudent.objects.filter(family=family, is_active=True)
        .select_related("student")
        .order_by("student__full_name")
    )
    cards = [_student_card(link.student) for link in links]
    student_ids = [link.student_id for link in links]
    payments = list(
        FeePayment.objects.filter(allocations__student_id__in=student_ids)
        .prefetch_related("allocations__student")
        .select_related("created_by")
        .distinct()
        .order_by("-created_at")[:200]
    )
    totals = {
        "students_count": len(cards),
        "total": sum((card["total"] for card in cards), 0),
        "paid": sum((card["paid"] for card in cards), 0),
        "remaining": sum((card["remaining"] for card in cards), 0),
    }
    return {
        "family": family,
        "links": links,
        "cards": cards,
        "payments": payments,
        "receipt_history": build_guardian_receipt_history([link.student for link in links]),
        "totals": totals,
    }


@management_required
def family_detail(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    return render(request, "parent_portal/family_detail.html", _family_finance_context(family))


@management_required
def family_update(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    form = FamilyIdentityForm(request.POST or None, instance=family)
    if request.method == "POST" and form.is_valid():
        try:
            update_family_identity(
                family,
                guardian_name=form.cleaned_data["guardian_name"],
                phone=form.cleaned_data["phone"],
                identity_type=form.cleaned_data.get("identity_type", "national"),
                identity_number=form.cleaned_data.get("identity_number", ""),
                relation=form.cleaned_data.get("relation", "ولي أمر"),
            )
        except Exception as exc:
            message = getattr(exc, "messages", None)
            form.add_error(None, message[0] if message else str(exc))
        else:
            messages.success(request, "تم تحديث المصدر الرسمي لبيانات ولي الأمر ومزامنة الأبناء.")
            return redirect("parent_portal:family_detail", pk=family.pk)
    return render(request, "parent_portal/family_form.html", {"family": family, "form": form})


@management_required
def family_statement_print(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    return render(request, "parent_portal/family_statement_print.html", _family_finance_context(family))


@management_required
def family_account_create(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    if request.method != "POST":
        return redirect("parent_portal:family_detail", pk=family.pk)
    user, password, created = ensure_family_account(family)
    if not created:
        messages.info(request, "ملف ولي الأمر مرتبط بحساب مستخدم بالفعل.")
        return redirect("parent_portal:family_detail", pk=family.pk)
    return render(request, "parent_portal/family_credentials.html", {"family": family, "username": user.username, "password": password, "created": True})


@management_required
def family_account_reset(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    if request.method != "POST":
        return redirect("parent_portal:family_detail", pk=family.pk)
    user, password = reset_family_password(family)
    return render(request, "parent_portal/family_credentials.html", {"family": family, "username": user.username, "password": password, "created": False})


@management_required
def family_statement_csv(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    context = _family_finance_context(family)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="guardian-{family.pk}-statement.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["ولي الأمر", family.guardian_name, "الهاتف", family.phone, "رقم ملف ولي الأمر", family.family_code])
    writer.writerow([])
    writer.writerow(["الطالب", "الصف", "إجمالي الرسوم", "المدفوع", "المتبقي", "الحالة"])
    for card in context["cards"]:
        writer.writerow([card["student"].full_name, f'{card["student"].grade} {card["student"].section}', card["total"], card["paid"], card["remaining"], card["status_label"]])
    writer.writerow([])
    writer.writerow(["الإيصال", "التاريخ", "النوع", "المبلغ", "المتبقي بعد العملية"])
    for payment in context["payments"]:
        writer.writerow([payment.receipt_number, payment.created_at.strftime("%Y-%m-%d %H:%M"), payment.get_scope_display(), payment.total_amount, payment.total_due_after])
    return response
