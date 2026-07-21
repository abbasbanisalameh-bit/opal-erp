from django.test import TestCase

from documents.models import DocumentTemplate, IssuedDocument, StudentIssuedDocument

from .models import Student
from .student360 import _build_documents_profile


class StudentDocumentsProfileContractTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            student_number="LIFE-DOCUMENTS-001",
            full_name="طالب ملف الوثائق",
            grade="الأول",
            section="أ",
        )
        self.template = DocumentTemplate.objects.create(
            name="إثبات طالب",
            audience="student",
            document_type="student_certificate",
            title="إثبات طالب",
            body="محتوى الوثيقة",
        )

    def _issue(self, number, title):
        issued = IssuedDocument.objects.create(
            template=self.template,
            student=self.student,
            document_number=number,
            title=title,
            content="محتوى محفوظ",
        )
        return StudentIssuedDocument.objects.create(
            student=self.student,
            issued_document=issued,
        )

    def test_documents_profile_preserves_latest_first_history(self):
        first = self._issue("DOC-LIFE-001", "الوثيقة الأولى")
        second = self._issue("DOC-LIFE-002", "الوثيقة الثانية")

        profile = _build_documents_profile(self.student)

        self.assertEqual(profile.keys(), {"documents"})
        self.assertEqual([row.pk for row in profile["documents"]], [second.pk, first.pk])
        self.assertEqual(profile["documents"][0].issued_document.title, "الوثيقة الثانية")
        self.assertEqual(profile["documents"][0].issued_document.template_id, self.template.pk)

    def test_empty_documents_profile_is_stable(self):
        profile = _build_documents_profile(self.student)
        self.assertEqual(profile, {"documents": []})
