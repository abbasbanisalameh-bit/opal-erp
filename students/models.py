from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.identifiers import normalize_identifier


class Student(models.Model):
    STATUS_CHOICES = [
        ("active", "نشط"),
        ("transferred", "منقول"),
        ("graduated", "متخرج"),
        ("archived", "مؤرشف"),
    ]
    SOURCE_CHOICES = [
        ("manual", "إدخال OPAL"),
        ("openemis", "OpenEMIS"),
    ]

    student_number = models.CharField("رقم الطالب", max_length=50, unique=True)
    source = models.CharField("مصدر السجل", max_length=20, choices=SOURCE_CHOICES, default="manual")
    national_id = models.CharField("الرقم الوطني", max_length=50, blank=True, db_index=True)
    full_name = models.CharField("الاسم الكامل", max_length=200)

    guardian_name = models.CharField("اسم ولي الأمر", max_length=200, blank=True)
    father_name = models.CharField("اسم الأب", max_length=200, blank=True)
    mother_name = models.CharField("اسم الأم", max_length=200, blank=True)
    gender = models.CharField("الجنس", max_length=10, blank=True)
    blood_type = models.CharField("فصيلة الدم", max_length=10, blank=True)

    # These two fields are compatibility/display snapshots only. The authoritative
    # placement is academics.Enrollment.
    grade = models.CharField("الصف", max_length=100)
    section = models.CharField("الشعبة", max_length=100, blank=True)

    phone = models.CharField("رقم الهاتف", max_length=30, blank=True)
    address = models.TextField("العنوان", blank=True)
    medical_notes = models.TextField("ملاحظات صحية", blank=True)

    status = models.CharField("حالة الطالب", max_length=20, choices=STATUS_CHOICES, default="active")
    enrollment_date = models.DateField("تاريخ التسجيل", null=True, blank=True)
    ministry_student_id = models.CharField("رقم الطالب في الوزارة", max_length=100, blank=True, db_index=True)
    openemis_data = models.JSONField("بيانات OpenEMIS الكاملة", default=dict, blank=True)
    ministry_sync_status = models.CharField("حالة المزامنة مع الوزارة", max_length=50, blank=True, default="not_synced")
    last_ministry_sync_at = models.DateTimeField("آخر مزامنة مع الوزارة", null=True, blank=True)
    archived_at = models.DateTimeField("تاريخ الأرشفة", null=True, blank=True)
    is_active = models.BooleanField("نشط", default=True)
    is_demo = models.BooleanField("بيانات تجريبية", default=False, db_index=True, editable=False)

    photo = models.ImageField("صورة الطالب", upload_to="students/photos/", null=True, blank=True)

    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["national_id"],
                condition=~Q(national_id=""),
                name="uniq_student_national_id",
            ),
            models.UniqueConstraint(
                fields=["ministry_student_id"],
                condition=~Q(ministry_student_id=""),
                name="uniq_student_ministry_id",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        normalized_national = normalize_identifier(self.national_id)
        normalized_ministry = normalize_identifier(self.ministry_student_id)
        if normalized_national and type(self).objects.filter(national_id=normalized_national).exclude(pk=self.pk).exists():
            errors["national_id"] = "الرقم الوطني مرتبط بطالب آخر. افتح ملف الطالب الموجود بدل إنشاء سجل مكرر."
        if normalized_ministry and type(self).objects.filter(ministry_student_id=normalized_ministry).exclude(pk=self.pk).exists():
            errors["ministry_student_id"] = "الرقم الوزاري مرتبط بطالب آخر."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.national_id = normalize_identifier(self.national_id)
        self.ministry_student_id = normalize_identifier(self.ministry_student_id)
        return super().save(*args, **kwargs)

    @property
    def fees_total(self):
        from admissions.financial_services import student_total_fees
        return student_total_fees(self)

    @property
    def fees_paid(self):
        from admissions.financial_services import student_total_paid
        return student_total_paid(self)

    @property
    def fees_remaining(self):
        return max((self.fees_total or Decimal("0")) - (self.fees_paid or Decimal("0")), Decimal("0"))

    def __str__(self):
        return self.full_name
