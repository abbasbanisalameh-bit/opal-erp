from django.urls import path
from . import views

app_name = "accounting"

urlpatterns = [
    path("", views.finance_dashboard, name="dashboard"),
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/add/", views.invoice_create, name="invoice_create"),
    path("payments/add/", views.payment_create, name="payment_create"),
    path("student/<int:student_id>/statement/", views.student_statement, name="student_statement"),
]
