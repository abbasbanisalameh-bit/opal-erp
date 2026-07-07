
from django.conf import settings
from django.db import models
from core.models import School, Branch, AcademicYear
from academics.models import Grade, Section


class AdmissionApplication(models.Model):
    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("submitted", "مقدم"),
        ("under_review", "قيد المراجعة"),
        ("approved", "مقبول"),
        ("rejected", "مرفوض"),
        ("converted", "تم تحويله لطالب"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True)

    application_number = models.CharField(max_length=50, unique=True)

    student_full_name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to="admissions/photos/", blank=True, null=True)

    guardian_name = models.CharField(max_length=200)
    guardian_phone = models.CharField(max_length=30)
    guardian_email = models.EmailField(blank=True)
    guardian_job = models.CharField(max_length=150, blank=True)

    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application_number} - {self.student_full_name}"


class RegistrationSettings(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="registration_settings")
    first_payment_percent = models.DecimalField("نسبة الدفعة الأولى", max_digits=5, decimal_places=2, default=20)
    cash_discount_percent = models.DecimalField("خصم الكاش", max_digits=5, decimal_places=2, default=10)
    sibling_discount_percent = models.DecimalField("خصم الإخوة", max_digits=5, decimal_places=2, default=5)
    quran_25_percent = models.DecimalField("خصم حفظ القرآن 25", max_digits=5, decimal_places=2, default=25)
    quran_50_percent = models.DecimalField("خصم حفظ القرآن 50", max_digits=5, decimal_places=2, default=50)
    quran_75_percent = models.DecimalField("خصم حفظ القرآن 75", max_digits=5, decimal_places=2, default=75)
    quran_100_percent = models.DecimalField("خصم حفظ القرآن 100", max_digits=5, decimal_places=2, default=100)
    enable_cash_discount = models.BooleanField("تفعيل خصم الكاش", default=True)
    enable_sibling_discount = models.BooleanField("تفعيل خصم الإخوة", default=True)
    enable_quran_discount = models.BooleanField("تفعيل خصم القرآن", default=True)
    enable_admin_discount = models.BooleanField("تفعيل خصم الإدارة", default=True)
    sibling_discount_once_per_family = models.BooleanField("خصم الإخوة مرة واحدة للعائلة", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "إعدادات التسجيل والخصومات"
        verbose_name_plural = "إعدادات التسجيل والخصومات"

    def __str__(self):
        return f"إعدادات التسجيل - {self.school.name}"


class GradeFee(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="grade_fees")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, related_name="grade_fees")
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="fee_settings")
    tuition_fee = models.DecimalField("رسوم الصف", max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField("فعالة", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["grade__order", "grade__name"]
        verbose_name = "رسوم صف"
        verbose_name_plural = "رسوم الصفوف"

    def __str__(self):
        return f"{self.grade} - {self.tuition_fee}"


class TransportRoute(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="transport_routes")
    name = models.CharField("اسم الجولة", max_length=150)
    full_fee = models.DecimalField("رسوم ذهاب وعودة", max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField("فعالة", default=True)
    notes = models.TextField("ملاحظات", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "جولة مواصلات"
        verbose_name_plural = "جولات المواصلات"

    def __str__(self):
        return self.name


class StudentRegistration(models.Model):
    TRANSPORT_CHOICES = [
        ("none", "غير مشترك"),
        ("go", "ذهاب فقط"),
        ("return", "عودة فقط"),
        ("both", "ذهاب وعودة"),
    ]
    DISCOUNT_CHOICES = [
        ("none", "بدون خصم"),
        ("quran_100", "حفظ القرآن 100%"),
        ("quran_75", "حفظ القرآن 75%"),
        ("quran_50", "حفظ القرآن 50%"),
        ("quran_25", "حفظ القرآن 25%"),
        ("cash", "خصم الكاش"),
        ("sibling", "خصم الإخوة"),
        ("admin", "خصم الإدارة"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="student_registrations")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True)
    registration_number = models.CharField("رقم التسجيل", max_length=50, unique=True)

    student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="registrations")
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)

    first_name = models.CharField("الاسم الأول", max_length=100)
    father_name = models.CharField("اسم الأب", max_length=100, blank=True)
    grandfather_name = models.CharField("اسم الجد", max_length=100, blank=True)
    family_name = models.CharField("اسم العائلة", max_length=100, blank=True)
    full_name = models.CharField("الاسم الكامل", max_length=250)
    national_id = models.CharField("الرقم الوطني", max_length=50, blank=True)
    gender = models.CharField("الجنس", max_length=20, blank=True)
    birth_date = models.DateField("تاريخ الميلاد", null=True, blank=True)
    address = models.TextField("العنوان", blank=True)
    phone = models.CharField("هاتف ولي الأمر", max_length=30, blank=True)
    guardian_name = models.CharField("اسم ولي الأمر", max_length=200, blank=True)
    mother_name = models.CharField("اسم الأم", max_length=200, blank=True)
    photo = models.ImageField("صورة الطالب", upload_to="students/photos/", blank=True, null=True)

    transport_route = models.ForeignKey(TransportRoute, on_delete=models.SET_NULL, null=True, blank=True)
    transport_type = models.CharField("نوع المواصلات", max_length=20, choices=TRANSPORT_CHOICES, default="none")
    discount_type = models.CharField("نوع الخصم", max_length=20, choices=DISCOUNT_CHOICES, default="none")
    admin_discount_value = models.DecimalField("خصم الإدارة", max_digits=10, decimal_places=2, default=0)
    sibling_student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="sibling_discount_registrations")

    tuition_fee = models.DecimalField("رسوم الصف", max_digits=10, decimal_places=2, default=0)
    transport_fee = models.DecimalField("رسوم المواصلات", max_digits=10, decimal_places=2, default=0)
    discount_value = models.DecimalField("قيمة الخصم", max_digits=10, decimal_places=2, default=0)
    net_total = models.DecimalField("صافي الرسوم", max_digits=10, decimal_places=2, default=0)
    first_payment = models.DecimalField("الدفعة الأولى", max_digits=10, decimal_places=2, default=0)
    remaining_amount = models.DecimalField("المتبقي", max_digits=10, decimal_places=2, default=0)

    invoice = models.ForeignKey("accounting.StudentInvoice", on_delete=models.SET_NULL, null=True, blank=True)
    payment = models.ForeignKey("accounting.StudentPayment", on_delete=models.SET_NULL, null=True, blank=True)
    receipt = models.ForeignKey("accounting.Receipt", on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "تسجيل طالب"
        verbose_name_plural = "تسجيل الطلاب"

    def __str__(self):
        return f"{self.registration_number} - {self.full_name}"
