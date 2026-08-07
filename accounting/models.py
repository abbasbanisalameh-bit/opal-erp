import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.finance_constants import PAYMENT_METHOD_CHOICES


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

    def refresh_from_db(self, *args, **kwargs):
        """Reload persisted fields and discard the per-instance payment cache."""
        result = super().refresh_from_db(*args, **kwargs)
        self.__dict__.pop("_opal_total_paid", None)
        return result

    @property
    def total_paid(self):
        """Return posted payments while honoring an already-prefetched relation.

        The invoice list and statement pages load payments in bulk.  Calling
        ``filter()`` on the relation here used to discard that work and issue
        several database queries per displayed invoice.  The cached value is
        local to this model instance only; it never changes accounting data.
        """
        cached_total = getattr(self, "_opal_total_paid", None)
        if cached_total is not None:
            return cached_total

        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("payments")
        payments = (
            (payment for payment in prefetched if payment.status == "posted")
            if prefetched is not None
            else self.payments.filter(status="posted")
        )
        total = sum((payment.amount for payment in payments), Decimal("0"))
        self._opal_total_paid = total
        return total

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
    STATUS_CHOICES = [("posted", "معتمدة"), ("deleted", "محذوفة بأمان"), ("reversed", "سجل سابق ملغى")]

    invoice = models.ForeignKey(StudentInvoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default="unspecified", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="posted", db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_payments")
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reversed_payments")
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="deleted_payments")
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(blank=True)
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
        # ``clean()`` may have read the invoice balance before this payment was
        # written.  Discard that per-instance display cache before syncing the
        # persisted invoice status.
        self.invoice.__dict__.pop("_opal_total_paid", None)
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

    def safe_delete(self, user, reason):
        """Remove a payment from balances without erasing its audit trail."""
        if self.status == "deleted":
            return False
        if self.status != "posted":
            raise ValidationError("لا يمكن حذف دفعة غير معتمدة.")
        if not (reason or "").strip():
            raise ValidationError("يجب كتابة سبب الحذف الآمن.")
        self.status = "deleted"
        self.deleted_by = user
        self.deleted_at = timezone.now()
        self.deletion_reason = reason.strip()
        self.save(update_fields=["status", "deleted_by", "deleted_at", "deletion_reason"])
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
        return self.payment.status != "posted"

    @property
    def is_deleted(self):
        return self.payment.status == "deleted"

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
        invoice_cache = getattr(self.invoice, "_prefetched_objects_cache", {})
        prefetched_payments = invoice_cache.get("payments")
        if prefetched_payments is None:
            payments = self.invoice.payments.filter(status="posted", payment_date__lte=self.due_date)
        else:
            payments = (
                payment
                for payment in prefetched_payments
                if payment.status == "posted" and payment.payment_date <= self.due_date
            )
        paid_before_due = sum((payment.amount for payment in payments), Decimal("0"))

        prefetched_installments = invoice_cache.get("installments")
        if prefetched_installments is None:
            installments = self.invoice.installments.filter(sequence__lt=self.sequence).exclude(status="cancelled")
        else:
            installments = (
                installment
                for installment in prefetched_installments
                if installment.sequence < self.sequence and installment.status != "cancelled"
            )
        earlier = sum((installment.amount for installment in installments), Decimal("0"))
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


class ExpenseEntry(models.Model):
    SOURCE_CHOICES = [("school", "مصروف مدرسي عام"), ("canteen", "مصروف المقصف المدرسي")]
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="expense_entries")
    expense_number = models.CharField("رقم المصروف", max_length=50, unique=True)
    expense_date = models.DateField("تاريخ المصروف", default=timezone.localdate, db_index=True)
    title = models.CharField("البيان", max_length=200)
    source = models.CharField("مصدر المصروف", max_length=20, choices=SOURCE_CHOICES, default="school", db_index=True)
    beneficiary = models.CharField("المستفيد", max_length=200, blank=True)
    amount = models.DecimalField("المبلغ", max_digits=12, decimal_places=2)
    payment_method = models.CharField("طريقة الدفع", max_length=30, choices=PAYMENT_METHOD_CHOICES)
    reference = models.CharField("المرجع", max_length=100, blank=True)
    supplier_invoice_number = models.CharField("رقم فاتورة المورد", max_length=100, blank=True, db_index=True)
    invoice_file = models.FileField("صورة الفاتورة", upload_to="finance/expense_invoices/", blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_expenses")
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="deleted_expenses")
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-expense_date", "-id"]

    def clean(self):
        super().clean()
        if self.amount is None or self.amount <= 0:
            raise ValidationError({"amount": "مبلغ المصروف يجب أن يكون أكبر من صفر."})
        if self.pk is None and not (self.supplier_invoice_number or "").strip():
            raise ValidationError({"supplier_invoice_number": "رقم فاتورة المورد إلزامي لكل مصروف جديد."})

    def __str__(self):
        return f"{self.expense_number} - {self.title}"


class MonthlyFinancialTarget(models.Model):
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="monthly_financial_targets")
    period_end = models.DateField("نهاية الشهر المالي", db_index=True)
    expected_amount = models.DecimalField("المبلغ المتوقع شهريًا", max_digits=12, decimal_places=2, default=0)
    notes = models.TextField("ملاحظات", blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end"]
        constraints = [models.UniqueConstraint(fields=["school", "period_end"], name="uniq_monthly_target_school_period")]

    def clean(self):
        super().clean()
        errors = {}
        if self.period_end:
            import calendar
            last_day = calendar.monthrange(self.period_end.year, self.period_end.month)[1]
            if self.period_end.day != last_day:
                errors["period_end"] = "يجب أن يكون تاريخ الكشف هو آخر يوم فعلي من الشهر."
        if self.expected_amount is not None and self.expected_amount < 0:
            errors["expected_amount"] = "المبلغ المتوقع لا يمكن أن يكون سالبًا."
        if errors:
            raise ValidationError(errors)


class FinancialYearClosure(models.Model):
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="financial_year_closures")
    source_year = models.OneToOneField("core.AcademicYear", on_delete=models.PROTECT, related_name="financial_closure")
    target_year = models.ForeignKey("core.AcademicYear", on_delete=models.PROTECT, related_name="incoming_financial_closures")
    total_carried = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    closed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-closed_at"]


class FinancialCarryForward(models.Model):
    STATUS_CHOICES = [
        ("open", "رصيد سابق قائم"),
        ("settled", "مسدد"),
    ]

    closure = models.ForeignKey(FinancialYearClosure, on_delete=models.PROTECT, related_name="balances")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="financial_carry_forwards")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    source_invoices = models.ManyToManyField(StudentInvoice, related_name="carry_forward_snapshots", blank=True)
    target_invoice = models.OneToOneField(
        StudentInvoice,
        on_delete=models.PROTECT,
        related_name="carry_forward_record",
        null=True,
        blank=True,
        help_text="مرجع توافق لسجلات الإصدارات السابقة فقط؛ لا تُنشأ فاتورة جديدة عند الترحيل.",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["student__full_name"]
        constraints = [models.UniqueConstraint(fields=["closure", "student"], name="uniq_closure_student_balance")]

    @property
    def remaining(self):
        sources = list(self.source_invoices.all())
        if sources:
            return sum((invoice.remaining for invoice in sources), Decimal("0"))
        if self.target_invoice_id:
            return self.target_invoice.remaining
        return Decimal("0")


class CanteenTransaction(models.Model):
    TYPE_CHOICES = [("income", "مبيعات المقصف"), ("expense", "مصروف المقصف")]

    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="canteen_transactions")
    transaction_type = models.CharField("نوع الحركة", max_length=20, choices=TYPE_CHOICES, db_index=True)
    transaction_date = models.DateField("التاريخ", default=timezone.localdate, db_index=True)
    invoice_number = models.CharField("رقم الفاتورة", max_length=100, db_index=True)
    description = models.CharField("البيان", max_length=200)
    amount = models.DecimalField("القيمة", max_digits=12, decimal_places=2)
    payment_method = models.CharField("طريقة الدفع", max_length=30, choices=PAYMENT_METHOD_CHOICES, default="cash")
    invoice_file = models.FileField("صورة الفاتورة", upload_to="finance/canteen_invoices/", blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_canteen_transactions")
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="deleted_canteen_transactions")
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-transaction_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["school", "invoice_number", "transaction_type"], name="uniq_canteen_invoice_type")
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.amount is None or self.amount <= 0:
            errors["amount"] = "قيمة الحركة يجب أن تكون أكبر من صفر."
        if not (self.invoice_number or "").strip():
            errors["invoice_number"] = "رقم الفاتورة إلزامي."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.invoice_number = (self.invoice_number or "").strip()
        self.full_clean(exclude=["created_by", "deleted_by"])
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.invoice_number}"


class MonthlyFinancialStatement(models.Model):
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="monthly_financial_statements")
    period_end = models.DateField("نهاية الشهر", db_index=True)
    opening_balance = models.DecimalField("الرصيد المدور من الشهر السابق", max_digits=14, decimal_places=2, default=0)
    fee_income = models.DecimalField("وارد الرسوم", max_digits=14, decimal_places=2, default=0)
    canteen_income = models.DecimalField("وارد المقصف", max_digits=14, decimal_places=2, default=0)
    school_expenses = models.DecimalField("المصروف المدرسي", max_digits=14, decimal_places=2, default=0)
    canteen_expenses = models.DecimalField("مصروف المقصف", max_digits=14, decimal_places=2, default=0)
    net_movement = models.DecimalField("صافي حركة الشهر", max_digits=14, decimal_places=2, default=0)
    closing_balance = models.DecimalField("الرصيد المدور للشهر التالي", max_digits=14, decimal_places=2, default=0)
    is_closed = models.BooleanField("مغلق", default=False, db_index=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end"]
        constraints = [models.UniqueConstraint(fields=["school", "period_end"], name="uniq_monthly_statement_school_period")]

    def clean(self):
        super().clean()
        if self.period_end:
            import calendar
            last_day = calendar.monthrange(self.period_end.year, self.period_end.month)[1]
            if self.period_end.day != last_day:
                raise ValidationError({"period_end": "يجب أن ينتهي الكشف في آخر يوم من الشهر."})

    def __str__(self):
        return f"{self.school} - {self.period_end}"
