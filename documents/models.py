import uuid

from django.conf import settings
from django.db import models


def new_template_code():
    return f"template-{uuid.uuid4().hex[:16]}"


class DocumentTemplate(models.Model):
    AUDIENCE_CHOICES = [
        ("student", "الطالب"),
        ("candidate", "المرشح للقبول"),
        ("teacher", "المعلم"),
        ("guardian", "ولي الأمر"),
    ]
    DOCUMENT_TYPES = [
        ("student_certificate", "إثبات طالب"),
        ("student_status", "شهادة قيد"),
        ("transfer_letter", "كتاب انتقال"),
        ("acceptance_letter", "كتاب قبول"),
        ("initial_acceptance", "كتاب قبول مبدئي"),
        ("clearance", "براءة ذمة"),
        ("report_card", "كشف علامات"),
        ("custom", "وثيقة مخصصة"),
        ("teacher_experience", "شهادة خبرة"),
        ("teacher_appreciation", "شهادة تقدير"),
        ("teacher_recommendation", "كتاب توصية"),
        ("teacher_salary", "تعريف راتب"),
        ("guardian_statement", "كشف حساب ولي الأمر"),
        ("student_conduct", "شهادة حسن سيرة وسلوك"),
    ]

    code = models.SlugField(max_length=80, unique=True, default=new_template_code, editable=False)
    name = models.CharField(max_length=200)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="student", db_index=True)
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
    STATUS_CHOICES = [("active", "فعّالة"), ("cancelled", "ملغاة")]

    template = models.ForeignKey(DocumentTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True)
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_documents")
    guardian = models.ForeignKey("parent_portal.Family", on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_documents")
    candidate = models.ForeignKey("admissions.AdmissionApplication", on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_documents")
    applicant_name = models.CharField(max_length=200, blank=True)
    document_number = models.CharField(max_length=50, unique=True)
    verification_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=250)
    content = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    manager_name_snapshot = models.CharField(max_length=200, blank=True)
    manager_title_snapshot = models.CharField(max_length=120, blank=True, default="المدير العام")
    stamp_label_snapshot = models.CharField(max_length=120, blank=True, default="ختم المدرسة")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_documents")
    issued_at = models.DateTimeField(auto_now_add=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="cancelled_documents")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    replaces = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replacement_documents")

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.document_number


class DocumentSettings(models.Model):
    school = models.OneToOneField("core.School", on_delete=models.CASCADE, related_name="document_settings")
    manager_name = models.CharField("اسم المدير العام", max_length=200, blank=True)
    manager_title = models.CharField("المسمى الوظيفي", max_length=120, default="المدير العام")
    stamp_label = models.CharField("عبارة الختم", max_length=120, default="ختم المدرسة")
    footer_text = models.CharField("تذييل الوثائق", max_length=250, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"إعدادات وثائق {self.school}"


class StudentIssuedDocument(models.Model):
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="issued_documents")
    issued_document = models.ForeignKey(IssuedDocument, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("student", "issued_document")

    def __str__(self):
        return f"{self.student.full_name} - {self.issued_document.title}"
