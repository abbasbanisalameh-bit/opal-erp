from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from .models import ParentProfile
from accounting.models import StudentInvoice
from attendance_v2.models import Attendance
from announcements.models import Announcement
from exams.models import Exam, StudentMark
from .messages_models import ParentMessage
from .notifications import Notification


@login_required
def dashboard(request):
    try:
        profile = ParentProfile.objects.get(user=request.user)
    except ParentProfile.DoesNotExist:
        return render(request, "parent_portal/no_profile.html")

    student = profile.student

    invoices = StudentInvoice.objects.filter(student=student)

    attendance = Attendance.objects.filter(
        student=student
    ).order_by("-date")[:20]

    announcements = Announcement.objects.order_by("-id")[:10]

    exams = Exam.objects.order_by("-id")[:10]

    return render(
        request,
        "parent_portal/dashboard.html",
        {
            "student": student,
            "invoices": invoices,
            "attendance": attendance,
            "announcements": announcements,
            "exams": exams,
            "messages":ParentMessage.objects.filter(student=student)[:10],
            "notifications":Notification.objects.filter(student=student)[:10],
            "marks": StudentMark.objects.filter(
                student=student
            ).select_related("exam"),
        },
    )
