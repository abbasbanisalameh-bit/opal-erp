"""Unified read-side workflow for the OPAL guardian portal.

This module keeps the existing portal behaviour intact while providing one
stable entry point for family, children, finance, attendance, marks,
documents and timetable contexts.
"""
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from admissions.financial_services import student_separated_finance_snapshot
from admissions.models import FeePayment
from attendance_v2.models import Attendance
from exams.models import StudentMark

from .academic_services import homework_for_student, student_class_rank
from .financial_services import build_guardian_annual_statement, guardian_financial_years
from .models import Family, FamilyStudent
from .financial_access import guardian_feature_allowed
from .receipt_services import build_guardian_receipt_history

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


def build_student_card(student, *, marks_allowed=True):
    from learning_platform.school_bridge import student_learning_access

    separated = student_separated_finance_snapshot(student)
    finance = separated["current"]
    paid = finance["paid"]
    remaining = finance["remaining"]
    previous_debt = separated["previous"]
    return {
        "student": student,
        "current_year": separated["current_year"],
        "previous_debt": previous_debt,
        "total": finance["total"],
        "paid": paid,
        "remaining": remaining,
        "combined_remaining": separated["combined_remaining"],
        "status": finance["status"],
        "status_label": "مسدد بالكامل" if remaining <= 0 else ("غير مسدد" if paid <= 0 else "متبقٍ جزئي"),
        "status_class": "success" if remaining <= 0 else ("danger" if paid <= 0 else "warning"),
        "attendance": Attendance.objects.filter(student=student).order_by("-date")[:5],
        "marks": StudentMark.objects.filter(student=student, exam__status__in=["published", "closed"]).select_related("exam", "exam__subject")[:5] if marks_allowed else [],
        "rank": student_class_rank(student),
        "homework": homework_for_student(student)[:5],
        "learning_access": student_learning_access(student),
    }


def build_dashboard_context(user):
    students = students_for_user(user)
    family = family_for_user(user)
    marks_allowed = guardian_feature_allowed(family, "marks")
    cards = [build_student_card(student, marks_allowed=marks_allowed) for student in students]
    return {
        "family": family,
        "marks_restricted": not marks_allowed,
        "students": students,
        "cards": cards,
        "receipt_history": build_guardian_receipt_history(students),
        "totals": {
            "students_count": len(students),
            "total": sum((card["total"] for card in cards), 0),
            "paid": sum((card["paid"] for card in cards), 0),
            "remaining": sum((card["remaining"] for card in cards), 0),
            "previous_debt": sum((card["previous_debt"]["total"] for card in cards), 0),
            "combined_remaining": sum((card["combined_remaining"] for card in cards), 0),
        },
    }


def build_student_detail_context(student):
    """Return a lightweight profile summary and direct the parent to each official service.

    Detailed finance, attendance, marks, homework and document tables live in
    their dedicated guardian gateways.  This prevents the student summary from
    becoming a second, competing route to the same information.
    """
    from learning_platform.school_bridge import student_learning_access

    separated = student_separated_finance_snapshot(student)
    finance = separated["current"]
    return {
        "student": student,
        "learning_access": student_learning_access(student),
        "rank": student_class_rank(student),
        "current_year": separated["current_year"],
        "total": finance["total"],
        "paid": finance["paid"],
        "remaining": finance["remaining"],
        "combined_remaining": separated["combined_remaining"],
        "previous_debt": separated["previous"],
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
        "current_year": next((card["current_year"] for card in cards if card["current_year"]), None),
        "previous_total": sum((card["previous_debt"]["total"] for card in cards), 0),
        "current_remaining": sum((card["remaining"] for card in cards), 0),
        "combined_remaining": sum((card["combined_remaining"] for card in cards), 0),
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
            "previous_debt": sum((card["previous_debt"]["total"] for card in cards), 0),
            "combined_remaining": sum((card["combined_remaining"] for card in cards), 0),
            "current_year": next((card["current_year"] for card in cards if card["current_year"]), None),
        },
    }
