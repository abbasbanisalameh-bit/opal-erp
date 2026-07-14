from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from students.models import Student

from .models import IssuedDocument, StudentIssuedDocument


class DocumentVerificationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", password="x", is_staff=True)
        self.student = Student.objects.create(student_number="D-1", full_name="طالب وثيقة", grade="الأول")
        self.document = IssuedDocument.objects.create(
            student=self.student, applicant_name=self.student.full_name, document_number="DOC-001",
            title="إثبات طالب", content="محتوى", issued_by=self.user
        )
        StudentIssuedDocument.objects.create(student=self.student, issued_document=self.document)

    def test_public_verification_page(self):
        url = reverse("documents:verify", args=[self.document.document_number, self.document.verification_code])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DOC-001")

    def test_cancel_document_keeps_verification_record(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("documents:document_cancel", args=[self.document.pk]), {"reason": "إعادة إصدار"})
        self.assertEqual(response.status_code, 302)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "cancelled")
        verify = self.client.get(reverse("documents:verify", args=[self.document.document_number, self.document.verification_code]))
        self.assertContains(verify, "ملغاة")
