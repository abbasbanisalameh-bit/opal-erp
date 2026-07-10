from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect

from .models import ParentProfile, Family, FamilyStudent
from .permissions import parent_required
from accounting.models import StudentInvoice
from attendance_v2.models import Attendance
from announcements.models import Announcement
from exams.models import StudentMark
from .notifications import Notification
from admissions.financial_services import (
    student_total_fees,
    student_total_paid,
    student_remaining,
    student_payment_status,
)
from admissions.models import FeePaymentAllocation, FeePayment

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
    profile = ParentProfile.objects.filter(user=user).select_related("student").first()
    return [profile.student] if profile else []


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
        "notifications": Notification.objects.filter(student=student).order_by("-created_at")[:5],
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
    marks = StudentMark.objects.filter(student=student).select_related("exam", "exam__subject")
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
    records = StudentMark.objects.filter(student__in=students).select_related("student", "exam", "exam__subject").order_by("student__full_name", "-exam__exam_date")
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
        # Enrollment uses core.AcademicYear while TimetableEntry uses
        # academics.AcademicYear. Match them by the stable year name rather
        # than passing an incompatible model instance to the queryset.
        entries = (
            TimetableEntry.objects.filter(
                section=enrollment.section,
                academic_year__name=enrollment.academic_year.name,
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

from django.contrib.admin.views.decorators import staff_member_required


@staff_member_required
def family_management(request):
    families = (
        Family.objects.select_related("user", "school")
        .prefetch_related("children__student")
        .order_by("guardian_name", "phone", "id")
    )
    return render(request, "parent_portal/family_management.html", {"families": families})
