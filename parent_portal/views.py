from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from .models import ParentProfile, Family, FamilyStudent
from accounting.models import StudentInvoice
from attendance_v2.models import Attendance
from announcements.models import Announcement
from exams.models import Exam, StudentMark
from .messages_models import ParentMessage
from .notifications import Notification
from admissions.financial_services import student_total_fees, student_total_paid, student_remaining, student_payment_status
from admissions.models import FeePaymentAllocation, FeePayment


def _students_for_user(user):
    family = Family.objects.filter(user=user).first()
    if family:
        return [link.student for link in family.children.select_related("student").filter(is_active=True)]
    profile = ParentProfile.objects.filter(user=user).select_related("student").first()
    return [profile.student] if profile else []


@login_required
def dashboard(request):
    students = _students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")

    cards = []
    for student in students:
        cards.append({
            "student": student,
            "total": student_total_fees(student),
            "paid": student_total_paid(student),
            "remaining": student_remaining(student),
            "status": student_payment_status(student),
            "attendance": Attendance.objects.filter(student=student).order_by("-date")[:5],
            "marks": StudentMark.objects.filter(student=student).select_related("exam")[:5],
            "notifications": Notification.objects.filter(student=student)[:5],
        })

    announcements = Announcement.objects.order_by("-id")[:10]
    payments = FeePayment.objects.filter(allocations__student__in=students).distinct().order_by("-created_at")[:10]
    return render(request, "parent_portal/dashboard.html", {"students": students, "cards": cards, "announcements": announcements, "payments": payments})


@login_required
def student_detail(request, student_id):
    students = _students_for_user(request.user)
    student = get_object_or_404(type(students[0]).objects.all(), pk=student_id) if students else None
    if student not in students:
        return render(request, "parent_portal/no_profile.html")
    invoices = StudentInvoice.objects.filter(student=student).select_related("fee_category").prefetch_related("payments")
    allocations = FeePaymentAllocation.objects.filter(student=student).select_related("fee_payment")
    attendance = Attendance.objects.filter(student=student).order_by("-date")[:30]
    marks = StudentMark.objects.filter(student=student).select_related("exam")
    return render(request, "parent_portal/student_detail.html", {
        "student": student,
        "invoices": invoices,
        "allocations": allocations,
        "attendance": attendance,
        "marks": marks,
        "total": student_total_fees(student),
        "paid": student_total_paid(student),
        "remaining": student_remaining(student),
    })
