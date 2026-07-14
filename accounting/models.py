import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def new_invoice_number():
    return f"INV-{uuid.uuid4().hex[:12].upper()}"


class FeeCategory(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StudentInvoice(models.Model):
    STATUS_CHOICES = [
        ("open", "مفتوحة"),
        ("partial", "مدفوعة جزئيًا"),
        ("paid", "مدفوعة"),
        ("cancelled", "ملغاة"),
    ]

    invoice_number = models.CharField(max_length=50, unique=True, default=new_invoice_number, editable=False)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="invoices")
    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.SET_NULL, null=True, blank=True, related_name="student_invoices")
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField()
    issue_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    paid = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_invoices")
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="cancelled_invoices")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        indexes = [models.Index(fields=["status", "due_date"])]

    def clean(self):
        super().clean()
        errors = {}
        if self.amount is not None and self.amount < 0:
            errors["amount"] = "قيمة الرسوم لا يمكن أن تكون سالبة."
        if self.discount_amount is not None and self.discount_amount < 0:
            errors["discount_amount"] = "قيمة الخصم لا يمكن أن تكون سالبة."
        if self.amount is not None and self.discount_amount is not None and self.discount_amount > self.amount:
            errors["discount_amount"] = "الخصم لا يمكن أن يتجاوز قيمة الرسوم."
        if errors:
            raise ValidationError(errors)

    @property
    def net_amount(self):
        return max((self.amount or Decimal("0")) - (self.discount_amount or Decimal("0")), Decimal("0"))

    @property
    def total_paid(self):
        return sum((p.amount for p in self.payments.filter(status="posted")), Decimal("0"))

    @property
    def remaining(self):
        if self.status == "cancelled":
            return Decimal("0")
        return max(self.net_amount - self.total_paid, Decimal("0"))

    @property
    def is_overdue(self):
        return self.status not in {"paid", "cancelled"} and self.due_date < timezone.localdate()

    def sync_status(self, commit=True):
        if self.status == "cancelled":
            self.paid = False
        elif self.remaining <= 0:
            self.status = "paid"
            self.paid = True
        elif self.total_paid > 0:
            self.status = "partial"
            self.paid = False
        else:
            self.status = "open"
            self.paid = False
        if commit and self.pk:
            type(self).objects.filter(pk=self.pk).update(status=self.status, paid=self.paid)
        return self.status

    def __str__(self):
        return f"{self.invoice_number} - {self.student.full_name}"


class StudentPayment(models.Model):
    STATUS_CHOICES = [("posted", "مرحلة"), ("reversed", "معكوسة")]

    invoice = models.ForeignKey(StudentInvoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="posted", db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_payments")
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reversed_payments")
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-payment_date", "-id"]

    def clean(self):
        super().clean()
        if self.amount is None or self.amount <= 0:
            raise ValidationError({"amount": "مبلغ الدفعة يجب أن يكون أكبر من صفر."})
        if self.invoice_id and self.invoice.status == "cancelled":
            raise ValidationError("لا يمكن تسجيل دفعة على رسوم ملغاة.")
        if self.status == "posted" and self.invoice_id:
            remaining = self.invoice.remaining
            if self.pk:
                old = type(self).objects.filter(pk=self.pk, status="posted").values_list("amount", flat=True).first() or Decimal("0")
                remaining += old
            if self.amount > remaining:
                raise ValidationError({"amount": f"المبلغ يتجاوز المتبقي ({remaining})."})

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)
        self.invoice.sync_status()
        return result

    def reverse(self, user, reason):
        if self.status == "reversed":
            return False
        if not reason.strip():
            raise ValidationError("يجب كتابة سبب عكس الدفعة.")
        self.status = "reversed"
        self.reversed_by = user
        self.reversed_at = timezone.now()
        self.reversal_reason = reason.strip()
        self.save(update_fields=["status", "reversed_by", "reversed_at", "reversal_reason"])
        self.invoice.sync_status()
        return True

    def __str__(self):
        return str(self.amount)


class Receipt(models.Model):
    payment = models.OneToOneField(StudentPayment, on_delete=models.PROTECT, related_name="receipt")
    receipt_number = models.CharField(max_length=30, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_void(self):
        return self.payment.status == "reversed"

    def __str__(self):
        return self.receipt_number


class Installment(models.Model):
    STATUS_CHOICES = [("pending", "مستحق"), ("paid", "مسدد"), ("overdue", "متأخر"), ("cancelled", "ملغى")]

    invoice = models.ForeignKey(StudentInvoice, on_delete=models.CASCADE, related_name="installments")
    sequence = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=100)
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date", "sequence"]
        unique_together = ("invoice", "sequence")

    @property
    def calculated_status(self):
        if self.status == "cancelled":
            return "cancelled"
        paid_before_due = sum(
            (p.amount for p in self.invoice.payments.filter(status="posted", payment_date__lte=self.due_date)),
            Decimal("0"),
        )
        earlier = sum(
            (i.amount for i in self.invoice.installments.filter(sequence__lt=self.sequence).exclude(status="cancelled")),
            Decimal("0"),
        )
        if paid_before_due >= earlier + self.amount:
            return "paid"
        if self.due_date < timezone.localdate():
            return "overdue"
        return "pending"

    def refresh_status(self):
        new = self.calculated_status
        if new != self.status:
            self.status = new
            self.save(update_fields=["status"])
        return new

    def __str__(self):
        return f"{self.invoice} - {self.title}"


class DiscountRequest(models.Model):
    STATUS_CHOICES = [("pending", "قيد المراجعة"), ("approved", "معتمد"), ("rejected", "مرفوض")]

    invoice = models.ForeignKey(StudentInvoice, on_delete=models.CASCADE, related_name="discount_requests")
    requested_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="requested_discounts")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="decided_discounts")
    decision_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.requested_amount <= 0:
            raise ValidationError({"requested_amount": "قيمة الخصم يجب أن تكون أكبر من صفر."})
        if self.invoice_id and self.requested_amount > self.invoice.amount:
            raise ValidationError({"requested_amount": "قيمة الخصم لا يمكن أن تتجاوز الرسوم."})

    def __str__(self):
        return f"خصم {self.invoice} - {self.requested_amount}"
