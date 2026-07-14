from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse

from core.models import Branch, School


class WorkflowRequest(models.Model):
    TYPE_CHOICES = [
        ("general", "طلب عام"),
        ("student", "طلب طالب"),
        ("parent", "طلب ولي أمر"),
        ("teacher", "طلب معلم"),
        ("discount", "طلب خصم"),
        ("document", "طلب وثيقة"),
        ("leave", "طلب إجازة"),
        ("maintenance", "طلب صيانة"),
        ("transfer", "طلب نقل طالب"),
        ("withdrawal", "طلب انسحاب طالب"),
        ("reenrollment", "طلب إعادة قيد"),
        ("payment_correction", "طلب تصحيح دفعة"),
        ("mark_change", "طلب تعديل نتيجة"),
    ]
    STATUS_CHOICES = [
        ("new", "جديد"),
        ("review", "قيد المراجعة"),
        ("approved", "معتمد"),
        ("rejected", "مرفوض"),
        ("returned", "معاد للاستكمال"),
        ("archived", "مؤرشف"),
    ]
    PRIORITY_CHOICES = [
        ("low", "منخفضة"),
        ("normal", "عادية"),
        ("high", "مرتفعة"),
        ("urgent", "عاجلة"),
    ]

    request_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default="general")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    requester = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="workflow_requests")
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_workflow_requests")
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new", db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal", db_index=True)
    related_app = models.CharField(max_length=80, blank=True)
    related_model = models.CharField(max_length=80, blank=True)
    related_object_id = models.CharField(max_length=80, blank=True)
    due_date = models.DateField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("approve_workflowrequest", "Can approve workflow request"),
            ("archive_workflowrequest", "Can archive workflow request"),
        ]

    def __str__(self):
        return f"#{self.pk} - {self.title}"

    def get_absolute_url(self):
        return reverse("enterprise_ops:workflow_detail", args=[self.pk])


class ApprovalAction(models.Model):
    ACTION_CHOICES = [
        ("submit", "إرسال"),
        ("review", "بدء المراجعة"),
        ("approve", "اعتماد"),
        ("reject", "رفض"),
        ("return", "إعادة للاستكمال"),
        ("archive", "أرشفة"),
        ("comment", "تعليق"),
    ]
    workflow = models.ForeignKey(WorkflowRequest, on_delete=models.CASCADE, related_name="actions")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    note = models.TextField(blank=True)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Notification(models.Model):
    LEVEL_CHOICES = [
        ("info", "معلومة"),
        ("success", "نجاح"),
        ("warning", "تنبيه"),
        ("danger", "عاجل"),
    ]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="opal_notifications")
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="info")
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read", "-created_at"], name="enterprise__recipie_dcb2f2_idx")]

    def __str__(self):
        return self.title


class ReportPreset(models.Model):
    CATEGORY_CHOICES = [
        ("students", "الطلاب"),
        ("finance", "الرسوم والتحصيل"),
        ("attendance", "الحضور"),
        ("academic", "الأكاديمي"),
        ("documents", "الوثائق"),
        ("operations", "التشغيل"),
    ]
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    code = models.SlugField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)
    allowed_roles = models.CharField(max_length=300, blank=True, help_text="Role codes separated by commas")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class RolePermissionRule(models.Model):
    FEATURE_CHOICES = [
        ("workflow", "الطلبات وسير العمل"),
        ("approvals", "الموافقات"),
        ("notifications", "الإشعارات"),
        ("audit", "سجل العمليات"),
        ("reports", "التقارير"),
        ("executive", "اللوحة التنفيذية"),
        ("students", "إدارة الطلاب"),
        ("academics", "الشؤون الأكاديمية"),
        ("attendance", "الحضور"),
        ("exams", "الامتحانات"),
        ("finance", "الرسوم المدرسية"),
        ("documents", "الوثائق"),
        ("timetable", "الجدول الدراسي"),
    ]
    role_code = models.CharField(max_length=50)
    feature = models.CharField(max_length=30, choices=FEATURE_CHOICES)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_update = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)
    can_export = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("role_code", "feature")
        ordering = ["role_code", "feature"]

    def __str__(self):
        return f"{self.role_code} - {self.get_feature_display()}"
