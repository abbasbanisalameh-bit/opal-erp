from django.db import models


class DocumentTemplate(models.Model):
    DOCUMENT_TYPES = [
        ("student_certificate", "إثبات طالب"),
        ("student_status", "شهادة قيد"),
        ("transfer_letter", "كتاب انتقال"),
        ("acceptance_letter", "كتاب قبول"),
        ("initial_acceptance", "كتاب قبول مبدئي"),
        ("clearance", "براءة ذمة"),
        ("report_card", "كشف علامات"),
        ("custom", "وثيقة مخصصة"),
    ]

    name = models.CharField(max_length=200)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=250)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class IssuedDocument(models.Model):
    template = models.ForeignKey(DocumentTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    student = models.ForeignKey("academics.StudentRecord", on_delete=models.SET_NULL, null=True, blank=True)
    applicant_name = models.CharField(max_length=200, blank=True)

    document_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=250)
    content = models.TextField()

    issued_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.document_number

class StudentIssuedDocument(models.Model):
    student = models.ForeignKey(
        "academics.StudentRecord",
        on_delete=models.CASCADE,
        related_name="issued_documents"
    )

    issued_document = models.ForeignKey(
        IssuedDocument,
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.full_name} - {self.issued_document.title}"
