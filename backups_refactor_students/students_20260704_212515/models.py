from django.db import models
from decimal import Decimal


class Student(models.Model):
    STATUS_CHOICES = [
        ("active", "نشط"),
        ("transferred", "منقول"),
        ("graduated", "متخرج"),
        ("archived", "مؤرشف"),
    ]

    student_number = models.CharField("رقم الطالب", max_length=50, unique=True)
    national_id = models.CharField("الرقم الوطني", max_length=50, blank=True)
    full_name = models.CharField("الاسم الكامل", max_length=200)

    guardian_name = models.CharField("اسم ولي الأمر", max_length=200, blank=True)
    father_name = models.CharField("اسم الأب", max_length=200, blank=True)
    mother_name = models.CharField("اسم الأم", max_length=200, blank=True)
    gender = models.CharField("الجنس", max_length=10, blank=True)
    blood_type = models.CharField("فصيلة الدم", max_length=10, blank=True)

    grade = models.CharField("الصف", max_length=100)
    section = models.CharField("الشعبة", max_length=100, blank=True)

    phone = models.CharField("رقم الهاتف", max_length=30, blank=True)
    address = models.TextField("العنوان", blank=True)

    fees_total = models.DecimalField("الرسوم المستحقة", max_digits=10, decimal_places=2, default=0)
    fees_paid = models.DecimalField("المدفوع", max_digits=10, decimal_places=2, default=0)

    status = models.CharField("حالة الطالب", max_length=20, choices=STATUS_CHOICES, default="active")
    enrollment_date = models.DateField("تاريخ التسجيل", null=True, blank=True)
    ministry_student_id = models.CharField("رقم الطالب في الوزارة", max_length=100, blank=True)
    ministry_sync_status = models.CharField("حالة المزامنة مع الوزارة", max_length=50, blank=True, default="not_synced")
    last_ministry_sync_at = models.DateTimeField("آخر مزامنة مع الوزارة", null=True, blank=True)
    archived_at = models.DateTimeField("تاريخ الأرشفة", null=True, blank=True)

    photo = models.ImageField("صورة الطالب", upload_to="students/photos/", null=True, blank=True)

    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    @property
    def fees_remaining(self):
        return (self.fees_total or Decimal("0")) - (self.fees_paid or Decimal("0"))

    def __str__(self):
        return self.full_name
