from django.conf import settings
from django.db import models
from core.models import School


class OpenEMISSettings(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="openemis_settings")
    is_enabled = models.BooleanField("تفعيل التكامل", default=False)
    base_url = models.URLField("رابط OpenEMIS / API", blank=True)
    username = models.CharField("اسم المستخدم", max_length=200, blank=True)
    password = models.CharField("كلمة المرور / Token", max_length=300, blank=True)
    client_id = models.CharField("Client ID", max_length=200, blank=True)
    client_secret = models.CharField("Client Secret", max_length=300, blank=True)
    auto_push_registration = models.BooleanField("إرسال الطالب بعد التسجيل تلقائيًا", default=False)
    auto_pull_student = models.BooleanField("سحب بيانات الطالب من OpenEMIS عند توفر الرقم الوزاري", default=False)
    sync_guardians = models.BooleanField("مزامنة بيانات ولي الأمر", default=True)
    last_tested_at = models.DateTimeField("آخر اختبار اتصال", null=True, blank=True)
    last_sync_at = models.DateTimeField("آخر مزامنة", null=True, blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "إعدادات OpenEMIS"
        verbose_name_plural = "إعدادات OpenEMIS"

    def __str__(self):
        return f"OpenEMIS - {self.school.name}"


class OpenEMISSyncLog(models.Model):
    OPERATION_CHOICES = [
        ("push_student", "إرسال طالب"),
        ("pull_student", "سحب طالب"),
        ("update_student", "تحديث طالب"),
        ("sync_guardian", "مزامنة ولي الأمر"),
        ("test_connection", "اختبار اتصال"),
    ]
    STATUS_CHOICES = [
        ("pending", "معلق"),
        ("success", "ناجح"),
        ("failed", "فشل"),
        ("skipped", "تم التجاوز"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="openemis_logs")
    student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="openemis_logs")
    operation = models.CharField("العملية", max_length=50, choices=OPERATION_CHOICES)
    status = models.CharField("الحالة", max_length=30, choices=STATUS_CHOICES, default="pending")
    message = models.TextField("الرسالة", blank=True)
    request_payload = models.JSONField("بيانات الإرسال", default=dict, blank=True)
    response_payload = models.JSONField("بيانات الاستجابة", default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "سجل مزامنة OpenEMIS"
        verbose_name_plural = "سجلات مزامنة OpenEMIS"

    def __str__(self):
        return f"{self.get_operation_display()} - {self.get_status_display()}"
