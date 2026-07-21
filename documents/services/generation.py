from __future__ import annotations

from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal

from core.models import AcademicYear
from exams.services import annual_report
from accounting.models import StudentInvoice, StudentPayment

from ..models import DocumentSettings, IssuedDocument, StudentIssuedDocument
from ..utils import generate_document_number


class SafeValues(dict):
    def __missing__(self, key):
        return "—"


def document_settings_for(school):
    return DocumentSettings.objects.get_or_create(school=school)[0]


def _year_for_school(school):
    return AcademicYear.objects.filter(school=school, is_current=True).first() or AcademicYear.objects.filter(school=school).first()


def student_values(student, extras=None):
    enrollments = list(student.enrollments.select_related("academic_year", "grade").order_by("academic_year__start_date"))
    current = next((item for item in reversed(enrollments) if item.status == "active"), enrollments[-1] if enrollments else None)
    first = enrollments[0] if enrollments else None
    school = current.academic_year.school if current else None
    family_link = student.family_links.filter(is_active=True).select_related("family").first()
    values = SafeValues({
        "school_name": getattr(school, "official_name", "") or getattr(school, "name", "مدرسة أوبال الدولية"),
        "student_name": student.full_name,
        "national_id": student.national_id or "غير مسجل",
        "registration_date": student.enrollment_date or getattr(first, "joined_at", None) or "غير محدد",
        "first_grade": getattr(getattr(first, "grade", None), "name", "غير محدد"),
        "current_grade": getattr(getattr(current, "grade", None), "name", student.grade or "غير محدد"),
        "academic_year": getattr(getattr(current, "academic_year", None), "name", "غير محدد"),
        "guardian_name": getattr(getattr(family_link, "family", None), "guardian_name", student.guardian_name or "ولي الأمر"),
        "target_school": "المدرسة المحددة",
        "target_grade": "الصف المحدد",
    })
    values.update(extras or {})
    return school, current, values


def candidate_values(candidate, extras=None):
    school = candidate.school
    year = candidate.academic_year or _year_for_school(school)
    values = SafeValues({
        "school_name": school.official_name or school.name,
        "candidate_name": candidate.student_full_name,
        "candidate_grade": getattr(candidate.grade, "name", "غير محدد"),
        "guardian_name": candidate.guardian_name,
        "academic_year": getattr(year, "name", "غير محدد"),
    })
    values.update(extras or {})
    return school, values


def teacher_values(teacher, extras=None):
    values = SafeValues({
        "school_name": teacher.school.official_name or teacher.school.name,
        "teacher_name": teacher.full_name,
        "teacher_national_id": teacher.national_id or "غير مسجل",
        "specialization": teacher.specialization or "التعليم",
        "hire_date": teacher.hire_date or "غير محدد",
        "teacher_end_date": teacher.end_date or timezone.localdate(),
        "monthly_salary": teacher.monthly_salary,
    })
    values.update(extras or {})
    return teacher.school, values


def guardian_values(family, extras=None):
    students = [link.student for link in family.children.filter(is_active=True).select_related("student")]
    year = _year_for_school(family.school)
    rows = [_student_year_finance(student, year) for student in students]
    total = sum((row["total"] for row in rows), Decimal("0.00"))
    paid = sum((row["paid"] for row in rows), Decimal("0.00"))
    remaining = sum((row["remaining"] for row in rows), Decimal("0.00"))
    values = SafeValues({
        "school_name": family.school.official_name or family.school.name,
        "guardian_name": family.guardian_name,
        "children_names": "، ".join(student.full_name for student in students) or "لا يوجد أبناء",
        "academic_year": getattr(year, "name", "غير محدد"),
        "statement_total": f"{total:.2f}",
        "statement_paid": f"{paid:.2f}",
        "statement_remaining": f"{remaining:.2f}",
    })
    values.update(extras or {})
    return family.school, students, year, values


def render_body(template, values):
    return template.body.format_map(SafeValues({key: str(value) for key, value in values.items()}))


def report_payload(student, year):
    if not year:
        return {}
    report = annual_report(student=student, academic_year=year)
    rows = []
    subjects = {}
    for term in report["terms"]:
        for row in term["rows"]:
            key = row["subject"].pk
            target = subjects.setdefault(key, {"subject": row["subject"].name, "first": {}, "second": {}, "final_total": "0.00"})
            target[term["semester"].code] = {item["exam_type"]: str(item["mark"]) for item in row["assessments"]}
            target[term["semester"].code]["total"] = str(row["total"])
    rows.extend(subjects.values())
    return {"kind": "report_card", "academic_year": year.name, "rows": rows, "annual_average": str(report["annual_average"])}


def guardian_payload(family, students, year):
    rows = [{"student": student.full_name, **{key: str(value) for key, value in _student_year_finance(student, year).items()}} for student in students]
    return {"kind": "guardian_statement", "academic_year": getattr(year, "name", ""), "rows": rows}


def _student_year_finance(student, year):
    invoices = StudentInvoice.objects.filter(student=student).exclude(status="cancelled")
    if year:
        invoices = invoices.filter(academic_year=year)
    invoices = list(invoices)
    invoice_ids = [invoice.pk for invoice in invoices]
    total = sum((invoice.net_amount for invoice in invoices), Decimal("0.00"))
    paid = StudentPayment.objects.filter(invoice_id__in=invoice_ids, status="posted").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    paid = min(paid, total)
    return {"total": total, "paid": paid, "remaining": max(total - paid, Decimal("0.00"))}


def create_issued_document(*, template, title, content, user, school, student=None, teacher=None, guardian=None, candidate=None, payload=None):
    settings = document_settings_for(school)
    document = IssuedDocument.objects.create(
        template=template,
        student=student,
        teacher=teacher,
        guardian=guardian,
        candidate=candidate,
        applicant_name=(getattr(student, "full_name", "") or getattr(teacher, "full_name", "") or getattr(candidate, "student_full_name", "") or getattr(guardian, "guardian_name", "")),
        document_number=generate_document_number(),
        title=title,
        content=content,
        payload=payload or {},
        manager_name_snapshot=settings.manager_name,
        manager_title_snapshot=settings.manager_title,
        stamp_label_snapshot=settings.stamp_label,
        issued_by=user,
    )
    if student:
        StudentIssuedDocument.objects.get_or_create(student=student, issued_document=document)
    return document
