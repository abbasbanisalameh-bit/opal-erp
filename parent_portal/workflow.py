"""Unified read-side workflow for the OPAL guardian portal.

This module keeps the existing portal behaviour intact while providing one
stable entry point for family, children, finance, attendance, marks,
documents and timetable contexts.
"""
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from accounting.models import StudentInvoice
from admissions.financial_services import student_finance_snapshot
from admissions.models import FeePayment, FeePaymentAllocation
from announcements.models import Announcement
from attendance_v2.models import Attendance
from exams.models import StudentMark

from .academic_services import homework_for_student, student_class_rank
from .financial_services import build_guardian_annual_statement, guardian_financial_years
from .models import Family, FamilyStudent
from .receipt_services import build_guardian_receipt_history

try:
    from documents.models import StudentIssuedDocument
except Exception:
    StudentIssuedDocument = None


def students_for_user(user):
    family = Family.objects.filter(user=user).first()
    if not family:
        return []
    return [
        link.student
        for link in FamilyStudent.objects.filter(family=family, is_active=True)
        .select_related("student")
        .order_by("student__full_name")
    ]


def family_for_user(user):
    return Family.objects.filter(user=user).first()


def student_for_user_or_403(user, student_id):
    students = students_for_user(user)
    allowed_ids = {student.pk for student in students}
    if int(student_id) not in allowed_ids:
        raise PermissionDenied("لا تملك صلاحية الوصول إلى هذا الطالب.")
    return get_object_or_404(type(students[0]).objects.all(), pk=student_id)


def build_student_card(student):
    finance = student_finance_snapshot(student)
    paid = finance["paid"]
    remaining = finance["remaining"]
    return {
        "student": student,
        "total": finance["total"],
        "paid": paid,
        "remaining": remaining,
        "status": finance["status"],
        "status_label": "مسدد بالكامل" if remaining <= 0 else ("غير مسدد" if paid <= 0 else "متبقٍ جزئي"),
        "status_class": "success" if remaining <= 0 else ("danger" if paid <= 0 else "warning"),
        "attendance": Attendance.objects.filter(student=student).order_by("-date")[:5],
        "marks": StudentMark.objects.filter(student=student, exam__status__in=["published", "closed"]).select_related("exam", "exam__subject")[:5],
        "rank": student_class_rank(student),
        "homework": homework_for_student(student)[:5],
    }


def build_dashboard_context(user):
    students = students_for_user(user)
    cards = [build_student_card(student) for student in students]
    return {
        "family": family_for_user(user),
        "students": students,
        "cards": cards,
        "announcements": Announcement.objects.filter(is_active=True).order_by("-created_at")[:10],
        "receipt_history": build_guardian_receipt_history(students),
        "totals": {
            "students_count": len(students),
            "total": sum((card["total"] for card in cards), 0),
            "paid": sum((card["paid"] for card in cards), 0),
            "remaining": sum((card["remaining"] for card in cards), 0),
        },
    }


def build_student_detail_context(student):
    documents = []
    if StudentIssuedDocument:
        documents = StudentIssuedDocument.objects.filter(student=student).select_related("issued_document")[:20]
    finance = student_finance_snapshot(student)
    return {
        "student": student,
        "invoices": StudentInvoice.objects.filter(student=student).select_related("fee_category").prefetch_related("payments"),
        "allocations": FeePaymentAllocation.objects.filter(student=student).select_related("fee_payment").order_by("-created_at"),
        "attendance": Attendance.objects.filter(student=student).order_by("-date")[:30],
        "marks": StudentMark.objects.filter(student=student, exam__status__in=["published", "closed"]).select_related("exam", "exam__subject"),
        "rank": student_class_rank(student),
        "homework_items": homework_for_student(student),
        "documents": documents,
        "total": finance["total"],
        "paid": finance["paid"],
        "remaining": finance["remaining"],
    }


def build_fees_context(user, requested_year=None):
    students = students_for_user(user)
    cards = [build_student_card(student) for student in students]
    years = guardian_financial_years(students)
    selected = years.filter(pk=requested_year).first() if requested_year else None
    selected = selected or years.filter(is_current=True).first() or years.first()
    return {
        "family": family_for_user(user),
        "cards": cards,
        "receipt_history": build_guardian_receipt_history(students),
        "statement_years": years,
        "selected_year": selected,
        "annual_statement": build_guardian_annual_statement(students, selected) if selected else None,
    }


def build_family_finance_context(family):
    links = list(FamilyStudent.objects.filter(family=family, is_active=True).select_related("student").order_by("student__full_name"))
    cards = [build_student_card(link.student) for link in links]
    student_ids = [link.student_id for link in links]
    payments = list(FeePayment.objects.filter(allocations__student_id__in=student_ids).prefetch_related("allocations__student").select_related("created_by").distinct().order_by("-created_at")[:200])
    return {
        "family": family,
        "links": links,
        "cards": cards,
        "payments": payments,
        "receipt_history": build_guardian_receipt_history([link.student for link in links]),
        "totals": {
            "students_count": len(cards),
            "total": sum((card["total"] for card in cards), 0),
            "paid": sum((card["paid"] for card in cards), 0),
            "remaining": sum((card["remaining"] for card in cards), 0),
        },
    }
