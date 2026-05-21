from django.urls import path
from . import views

urlpatterns = [
    path("plans/", views.pricing_plan_list_create),
    path("plans/<int:plan_id>/", views.pricing_plan_detail),
    path("companies/<int:company_id>/assign-plan/", views.assign_plan_to_company),
    path("payments/", views.payment_list_create),
    path("payments/<int:payment_id>/", views.payment_detail),
    path("invoices/", views.invoice_list_create),
    path("invoices/<int:invoice_id>/", views.invoice_detail),
    path("subscription-alerts/", views.subscription_alerts),
]
