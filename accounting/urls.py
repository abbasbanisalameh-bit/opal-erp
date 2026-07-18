from django.urls import path

from . import views

app_name = "accounting"

urlpatterns = [
    path("", views.finance_dashboard, name="dashboard"),
    path("fee-categories/", views.retired_finance_screen, name="fee_category_list"),
    path("fee-categories/<int:pk>/edit/", views.retired_finance_screen, name="fee_category_update"),
    path("invoices/", views.retired_finance_screen, name="invoice_list"),
    path("invoices/add/", views.retired_finance_screen, name="invoice_create"),
    path("invoices/<int:invoice_id>/cancel/", views.invoice_cancel, name="invoice_cancel"),
    path("payments/add/", views.retired_finance_screen, name="payment_create"),
    path("payments/<int:payment_id>/reverse/", views.payment_reverse, name="payment_reverse"),
    path("payments/<int:payment_id>/safe-delete/", views.payment_safe_delete, name="payment_safe_delete"),
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/<int:pk>/safe-delete/", views.expense_safe_delete, name="expense_safe_delete"),
    path("monthly-report/", views.monthly_report, name="monthly_report"),
    path("financial-year-close/", views.financial_year_close, name="financial_year_close"),
    path("installments/", views.retired_finance_screen, name="installment_list"),
    path("installments/add/", views.retired_finance_screen, name="installment_create"),
    path("discounts/", views.retired_finance_screen, name="discount_list"),
    path("discounts/add/", views.retired_finance_screen, name="discount_create"),
    path("discounts/<int:pk>/decide/", views.retired_finance_screen, name="discount_decide"),
    path("student/<int:student_id>/statement/", views.student_statement, name="student_statement"),
    path("receipt/<int:receipt_id>/print/", views.receipt_print, name="receipt_print"),
    path("receipts/", views.retired_receipts_screen, name="receipt_list"),
]
