from django.urls import path

from . import views

app_name = "accounting"

urlpatterns = [
    path("", views.finance_dashboard, name="dashboard"),
    path("fee-categories/", views.fee_category_list, name="fee_category_list"),
    path("fee-categories/<int:pk>/edit/", views.fee_category_update, name="fee_category_update"),
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/add/", views.invoice_create, name="invoice_create"),
    path("invoices/<int:invoice_id>/cancel/", views.invoice_cancel, name="invoice_cancel"),
    path("payments/add/", views.payment_create, name="payment_create"),
    path("payments/<int:payment_id>/reverse/", views.payment_reverse, name="payment_reverse"),
    path("installments/", views.installment_list, name="installment_list"),
    path("installments/add/", views.installment_create, name="installment_create"),
    path("discounts/", views.discount_list, name="discount_list"),
    path("discounts/add/", views.discount_create, name="discount_create"),
    path("discounts/<int:pk>/decide/", views.discount_decide, name="discount_decide"),
    path("student/<int:student_id>/statement/", views.student_statement, name="student_statement"),
    path("receipt/<int:receipt_id>/print/", views.receipt_print, name="receipt_print"),
    path("receipts/", views.receipt_list, name="receipt_list"),
]
