
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from core.choices import STUDENT_GENDER_CHOICES
from core.finance_constants import PAYMENT_METHOD_CHOICES


CURRENT_YEAR_FEE_NOTE_PREFIX = "دفعة رسوم السنة الحالية"
PREVIOUS_YEARS_FEE_NOTE_PREFIX = "دفعة من متبقيات الرسوم السابقة"
LEGACY_PREVIOUS_YEARS_FEE_NOTE_PREFIXES = ("دفعة من الذمم السابقة",)


class RegistrationSettings(models.Model):
    school = models.OneToOneField("core.School", on_delete=models.CASCADE, related_name="registration_settings")
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
    sibling_discount_once_per_family = models.BooleanField("خصم الإخوة مرة واحدة لكل ولي أمر", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "إعدادات التسجيل والخصومات"
        verbose_name_plural = "إعدادات التسجيل والخصومات"

    def __str__(self):
        return f"إعدادات التسجيل - {self.school.name}"


class GradeFee(models.Model):
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="grade_fees")
    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.SET_NULL, null=True, blank=True, related_name="grade_fees")
    grade = models.ForeignKey("academics.Grade", on_delete=models.CASCADE, related_name="fee_settings")
    tuition_fee = models.DecimalField("رسوم الصف", max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField("فعالة", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["grade__order", "grade__name"]
        verbose_name = "رسوم صف"
        verbose_name_plural = "رسوم الصفوف"

    def __str__(self):
        return f"{self.grade} - {self.tuition_fee}"

    def clean(self):
        super().clean()
        errors = {}
        if self.academic_year_id and self.academic_year.is_closed:
            errors["academic_year"] = "العام الدراسي مغلق ولا يقبل تعديل رسوم الصفوف."
        if self.academic_year_id and self.school_id and self.academic_year.school_id != self.school_id:
            errors["academic_year"] = "العام الدراسي لا يتبع المدرسة المحددة."
        if self.grade_id and self.school_id and self.grade.school_id != self.school_id:
            errors["grade"] = "الصف لا يتبع المدرسة المحددة."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class TransportRoute(models.Model):
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="transport_routes")
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

    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="student_registrations")
    branch = models.ForeignKey("core.Branch", on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.SET_NULL, null=True, blank=True)
    registration_number = models.CharField("رقم التسجيل", max_length=50, unique=True)
    operation_token = models.UUIDField("معرف عملية التسجيل", unique=True, editable=False, default=uuid.uuid4)

    student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="registrations")
    grade = models.ForeignKey("academics.Grade", on_delete=models.SET_NULL, null=True)
    section = models.ForeignKey("academics.Section", on_delete=models.SET_NULL, null=True, blank=True)

    first_name = models.CharField("الاسم الأول", max_length=100)
    father_name = models.CharField("اسم الأب", max_length=100, blank=True)
    grandfather_name = models.CharField("اسم الجد", max_length=100, blank=True)
    family_name = models.CharField("الاسم الأخير", max_length=100, blank=True)
    full_name = models.CharField("الاسم الكامل", max_length=250)
    national_id = models.CharField("الرقم الوطني للطالب (OpenEMIS)", max_length=50, blank=True)
    gender = models.CharField("الجنس", max_length=20, choices=STUDENT_GENDER_CHOICES, blank=True)
    birth_date = models.DateField("تاريخ الميلاد", null=True, blank=True)
    address = models.TextField("العنوان", blank=True)
    phone = models.CharField("هاتف ولي الأمر", max_length=30, blank=True)
    guardian_name = models.CharField("اسم ولي الأمر", max_length=200, blank=True)
    guardian_identity_type = models.CharField("نوع هوية ولي الأمر", max_length=20, choices=[("national", "رقم وطني أردني"), ("personal", "رقم شخصي لغير الأردني"), ("other", "معرف آخر")], default="national")
    guardian_identity_number = models.CharField("رقم هوية ولي الأمر", max_length=50, blank=True)
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
    payment_method = models.CharField("طريقة الدفع", max_length=30, choices=PAYMENT_METHOD_CHOICES, default="unspecified")
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
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                condition=models.Q(student__isnull=False, academic_year__isnull=False),
                name="uniq_registration_per_student_year",
            )
        ]

    def __str__(self):
        return f"{self.registration_number} - {self.full_name}"



class FeePayment(models.Model):
    PAYMENT_SCOPE_CHOICES = [
        ("single", "دفعة طالب"),
        ("all_siblings", "دفعة عن جميع الإخوة"),
    ]

    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="fee_payments")
    receipt_number = models.CharField("رقم الإيصال", max_length=50, unique=True)
    operation_token = models.UUIDField("معرف العملية", unique=True, editable=False, default=uuid.uuid4)
    scope = models.CharField("نوع الدفعة", max_length=30, choices=PAYMENT_SCOPE_CHOICES, default="single")
    main_student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="main_fee_payments")
    guardian_name = models.CharField("اسم ولي الأمر", max_length=200, blank=True)
    phone = models.CharField("هاتف ولي الأمر", max_length=50, blank=True)
    total_amount = models.DecimalField("مبلغ الدفعة", max_digits=10, decimal_places=2, default=0)
    total_due_before = models.DecimalField("إجمالي المتبقي قبل الدفعة", max_digits=10, decimal_places=2, default=0)
    total_due_after = models.DecimalField("إجمالي المتبقي بعد الدفعة", max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField("طريقة الدفع", max_length=30, choices=PAYMENT_METHOD_CHOICES, default="unspecified")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField("محذوف بأمان", default=False, db_index=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="deleted_fee_payments")
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField("سبب الحذف", blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "إيصال دفعة رسوم"
        verbose_name_plural = "إيصالات دفعات الرسوم"

    def __str__(self):
        return f"{self.receipt_number} - {self.total_amount}"

    @property
    def payment_period(self):
        """Return a durable, display-only classification for the receipt.

        The classification is stored in the operation note instead of a second
        balance table.  Allocations and their linked invoices remain the source
        of every financial amount.
        """
        notes = self.notes or ""
        if notes.startswith(
            (PREVIOUS_YEARS_FEE_NOTE_PREFIX, *LEGACY_PREVIOUS_YEARS_FEE_NOTE_PREFIXES)
        ):
            return "previous"
        if notes.startswith(CURRENT_YEAR_FEE_NOTE_PREFIX):
            return "current"
        return "legacy"

    @property
    def payment_period_label(self):
        return {
            "previous": "متبقيات السنوات السابقة",
            "current": "رسوم السنة الحالية",
            "legacy": "دفعة رسوم سابقة غير مصنفة",
        }[self.payment_period]


class FeePaymentAllocation(models.Model):
    fee_payment = models.ForeignKey(FeePayment, on_delete=models.CASCADE, related_name="allocations")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="fee_payment_allocations")
    invoice = models.ForeignKey("accounting.StudentInvoice", on_delete=models.SET_NULL, null=True, blank=True)
    accounting_payment = models.ForeignKey("accounting.StudentPayment", on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField("المدفوع في هذا الإيصال", max_digits=10, decimal_places=2, default=0)
    total_fees = models.DecimalField("إجمالي رسوم الطالب", max_digits=10, decimal_places=2, default=0)
    paid_before = models.DecimalField("المدفوع سابقًا", max_digits=10, decimal_places=2, default=0)
    remaining_before = models.DecimalField("المتبقي قبل الدفعة", max_digits=10, decimal_places=2, default=0)
    remaining_after = models.DecimalField("المتبقي بعد الدفعة", max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["student__full_name"]
        verbose_name = "توزيع دفعة"
        verbose_name_plural = "توزيعات الدفعات"

    def __str__(self):
        return f"{self.student} - {self.amount}"
