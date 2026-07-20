from django import forms

from core.finance_constants import ACTIVE_PAYMENT_METHOD_CHOICES
from core.models import AcademicYear

from .models import CanteenTransaction, DiscountRequest, ExpenseEntry, FeeCategory, Installment, MonthlyFinancialTarget, StudentInvoice, StudentPayment


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
        fields = ["invoice", "amount", "payment_method", "payment_date", "reference", "notes"]
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


class ExpenseEntryForm(StyledModelForm):
    payment_method = forms.ChoiceField(label="طريقة الدفع", choices=ACTIVE_PAYMENT_METHOD_CHOICES)

    class Meta:
        model = ExpenseEntry
        fields = ["expense_date", "source", "title", "beneficiary", "amount", "payment_method", "supplier_invoice_number", "invoice_file", "reference", "notes"]
        widgets = {
            "expense_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier_invoice_number"].required = True
        self.fields["supplier_invoice_number"].help_text = "لا يُحفظ أي مصروف جديد دون رقم فاتورة مورد."


class CanteenTransactionForm(StyledModelForm):
    payment_method = forms.ChoiceField(label="طريقة الدفع", choices=ACTIVE_PAYMENT_METHOD_CHOICES)

    class Meta:
        model = CanteenTransaction
        fields = ["transaction_date", "invoice_number", "description", "amount", "payment_method", "invoice_file", "notes"]
        widgets = {
            "transaction_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class MonthlyFinancialTargetForm(StyledModelForm):
    class Meta:
        model = MonthlyFinancialTarget
        fields = ["expected_amount", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class FinancialYearClosureForm(forms.Form):
    source_year = forms.ModelChoiceField(label="العام المراد إغلاقُه ماليًا", queryset=AcademicYear.objects.none())
    target_year = forms.ModelChoiceField(label="العام الذي تُرحّل إليه الأرصدة", queryset=AcademicYear.objects.none())
    notes = forms.CharField(label="ملاحظات", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    confirmation = forms.CharField(label="التأكيد", help_text="اكتب: إغلاق مالي")

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        years = AcademicYear.objects.filter(school=school).order_by("-start_date") if school else AcademicYear.objects.none()
        self.fields["source_year"].queryset = years.filter(is_closed=True)
        self.fields["target_year"].queryset = years.filter(is_closed=False)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field.widget, forms.Select) else "form-control")

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"].strip()
        if value != "إغلاق مالي":
            raise forms.ValidationError("اكتب العبارة إغلاق مالي للتأكيد.")
        return value
