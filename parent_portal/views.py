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
from .forms import FamilyIdentityForm
from .permissions import parent_required
from accounting.models import StudentInvoice
from attendance_v2.models import Attendance
from announcements.models import Announcement
from exams.models import StudentMark
from .parent360 import build_parent360_context
from admissions.financial_services import (
    student_total_fees,
    student_total_paid,
    student_remaining,
    student_payment_status,
)
from admissions.models import FeePaymentAllocation, FeePayment
from enterprise_ops.permissions import management_required

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
        "marks": StudentMark.objects.filter(student=student).select_related("exam", "exam__subject")[:5],
    }


@parent_required
def dashboard(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")

    cards = [_student_card(student) for student in students]
    announcements = Announcement.objects.filter(is_active=True).order_by("-created_at")[:10]
    payments = (
        FeePayment.objects.filter(allocations__student__in=students)
        .distinct()
        .order_by("-created_at")[:10]
    )
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
            "payments": payments,
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
    marks = StudentMark.objects.filter(student=student, exam__status="published").select_related("exam", "exam__subject")
    docs = []
    if StudentIssuedDocument:
        docs = StudentIssuedDocument.objects.filter(student=student).select_related("issued_document")[:20]
    return render(request, "parent_portal/student_detail.html", {
        "student": student,
        "invoices": invoices,
        "allocations": allocations,
        "attendance": attendance,
        "marks": marks,
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
    payments = FeePayment.objects.filter(allocations__student__in=students).distinct().order_by("-created_at")
    return render(request, "parent_portal/fees.html", {"cards": cards, "payments": payments})


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
    records = StudentMark.objects.filter(student__in=students, exam__status="published").select_related("student", "exam", "exam__subject").order_by("student__full_name", "-exam__exam_date")
    return render(request, "parent_portal/marks.html", {"records": records})


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
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "تم تغيير كلمة المرور بنجاح.")
            return redirect("parent_portal:account")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "parent_portal/account.html", {"family": family, "form": form})

@management_required
def family_management(request):
    families = (
        Family.objects.select_related("user", "school")
        .prefetch_related("children__student")
        .order_by("guardian_name", "phone", "id")
    )
    return render(request, "parent_portal/family_management.html", {"families": families})


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
    return {"family": family, "links": links, "cards": cards, "payments": payments, "totals": totals}


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
        messages.info(request, "الأسرة مرتبطة بحساب مستخدم بالفعل.")
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
    response["Content-Disposition"] = f'attachment; filename="family-{family.pk}-statement.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["ولي الأمر", family.guardian_name, "الهاتف", family.phone, "رمز الأسرة", family.family_code])
    writer.writerow([])
    writer.writerow(["الطالب", "الصف", "إجمالي الرسوم", "المدفوع", "المتبقي", "الحالة"])
    for card in context["cards"]:
        writer.writerow([card["student"].full_name, f'{card["student"].grade} {card["student"].section}', card["total"], card["paid"], card["remaining"], card["status_label"]])
    writer.writerow([])
    writer.writerow(["الإيصال", "التاريخ", "النوع", "المبلغ", "المتبقي بعد العملية"])
    for payment in context["payments"]:
        writer.writerow([payment.receipt_number, payment.created_at.strftime("%Y-%m-%d %H:%M"), payment.get_scope_display(), payment.total_amount, payment.total_due_after])
    return response
