from django.db import models


class FeeCategory(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class StudentInvoice(models.Model):
    student = models.ForeignKey(
        "academics.StudentRecord",
        on_delete=models.CASCADE,
        related_name="invoices"
    )

    fee_category = models.ForeignKey(
        FeeCategory,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()

    paid = models.BooleanField(default=False)

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments.all())

    @property
    def remaining(self):
        return self.amount - self.total_paid

    def __str__(self):
        return f"{self.student.full_name}"


class StudentPayment(models.Model):
    invoice = models.ForeignKey(
        StudentInvoice,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    payment_date = models.DateField(auto_now_add=True)

    notes = models.TextField(blank=True)

    def save(self,*args,**kwargs):
        super().save(*args,**kwargs)

        if self.invoice.remaining <= 0:
            self.invoice.paid = True
            self.invoice.save(update_fields=["paid"])

    def __str__(self):
        return str(self.amount)


class Receipt(models.Model):
    payment = models.OneToOneField(
        StudentPayment,
        on_delete=models.CASCADE,
        related_name="receipt"
    )

    receipt_number = models.CharField(max_length=30, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.receipt_number
