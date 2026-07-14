from django import forms

from .models import DiscountRequest, FeeCategory, Installment, StudentInvoice, StudentPayment


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-check-input" if getattr(field.widget, "input_type", "") == "checkbox" else "form-control"
            field.widget.attrs.setdefault("class", css)


class FeeCategoryForm(StyledModelForm):
    class Meta:
        model = FeeCategory
        fields = ["name", "description", "amount", "active"]


class StudentInvoiceForm(StyledModelForm):
    class Meta:
        model = StudentInvoice
        fields = ["student", "academic_year", "fee_category", "amount", "due_date", "notes"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}


class StudentPaymentForm(StyledModelForm):
    class Meta:
        model = StudentPayment
        fields = ["invoice", "amount", "payment_date", "reference", "notes"]
        widgets = {"payment_date": forms.DateInput(attrs={"type": "date"})}


class InstallmentForm(StyledModelForm):
    class Meta:
        model = Installment
        fields = ["invoice", "sequence", "title", "due_date", "amount", "notes"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}


class DiscountRequestForm(StyledModelForm):
    class Meta:
        model = DiscountRequest
        fields = ["invoice", "requested_amount", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}
