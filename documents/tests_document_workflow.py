from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from academics.models import Enrollment, Grade, Subject
from admissions.models import AdmissionApplication
from core.models import AcademicYear, School
from students.models import Student
from exams.models import Exam, StudentMark

from .models import DocumentTemplate, IssuedDocument
from .services.generation import report_payload


class DocumentWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("document-manager", password="x", is_staff=True)
        self.school = School.objects.create(name="مدرسة أوبال", official_name="مدرسة أوبال الدولية", is_active=True)
        self.year = AcademicYear.objects.create(
            school=self.school, name="2026/2027", start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30), is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="الصف الأول")
        self.client.force_login(self.user)

    def test_candidate_creation_does_not_create_student(self):
        response = self.client.post(reverse("admissions:candidate_create"), {
            "student_full_name": "طالب مرشح", "guardian_name": "ولي المرشح",
            "guardian_phone": "0791000000", "grade": self.grade.pk,
        })
        self.assertEqual(response.status_code, 302)
        candidate = AdmissionApplication.objects.get()
        self.assertEqual(candidate.status, "candidate")
        self.assertEqual(Student.objects.count(), 0)

    def test_student_document_is_issued_from_editable_default(self):
        student = Student.objects.create(
            student_number="DOC-W-1", national_id="N-1", full_name="طالب الوثيقة",
            grade=self.grade.name, enrollment_date=date(2026, 9, 1),
        )
        Enrollment.objects.create(student=student, academic_year=self.year, grade=self.grade, status="active")
        template = DocumentTemplate.objects.get(code="student-proof")
        response = self.client.post(reverse("documents:issue_student", args=[student.pk]), {
            "template": template.pk, "title": "إثبات طالب مخصص",
            "content": "نص راجعه المدير قبل الإصدار",
        })
        self.assertEqual(response.status_code, 302)
        document = IssuedDocument.objects.get(student=student)
        self.assertEqual(document.content, "نص راجعه المدير قبل الإصدار")
        self.assertEqual(document.template.code, "student-proof")
        self.assertTrue(student.issued_documents.filter(issued_document=document).exists())

    def test_document_and_candidate_management_pages_render(self):
        for url in (
            reverse("documents:template_list"), reverse("documents:settings"),
            reverse("admissions:candidate_list"),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_report_payload_snapshots_every_exam_and_term_total(self):
        student = Student.objects.create(student_number="REPORT-DOC", full_name="طالب كشف", grade=self.grade.name)
        Enrollment.objects.create(student=student, academic_year=self.year, grade=self.grade, status="active")
        subject = Subject.objects.create(name="الرياضيات", grade=self.grade)
        for semester_code in ("first", "second"):
            semester = self.year.semesters.get(code=semester_code)
            for exam_type, mark in zip(("first", "second", "third", "final"), (18, 17, 16, 35)):
                exam = Exam.objects.create(
                    exam_type=exam_type, academic_year=self.year, semester=semester,
                    grade=self.grade, subject=subject, status="open",
                )
                StudentMark.objects.create(exam=exam, student=student, mark=mark)
        payload = report_payload(student, self.year)
        self.assertEqual(payload["rows"][0]["first"]["first"], "18.00")
        self.assertEqual(payload["rows"][0]["first"]["total"], "86.00")
        self.assertEqual(payload["rows"][0]["second"]["final"], "35.00")
