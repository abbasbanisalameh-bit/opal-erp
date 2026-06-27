from django import forms
from .models import FeeCategory, StudentInvoice, StudentPayment


class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ["name", "description", "amount", "active"]


class StudentInvoiceForm(forms.ModelForm):
    class Meta:
        model = StudentInvoice
        fields = ["student", "fee_category", "amount", "due_date", "paid"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }


class StudentPaymentForm(forms.ModelForm):
    class Meta:
        model = StudentPayment
        fields = ["invoice", "amount", "notes"]
