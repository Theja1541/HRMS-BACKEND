from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'vendors', views.VendorViewSet, basename='vendor')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'transactions', views.TransactionViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', views.dashboard_summary, name='daybook-dashboard'),
    path('reports/vendor-payments/', views.vendor_payments_report, name='vendor-payments'),
    path('reports/expense-summary/', views.expense_summary_report, name='expense-summary'),
    path('reports/gst-transactions/', views.gst_transactions_report, name='gst-transactions'),
    path('reports/monthly/', views.monthly_report, name='monthly-report'),
]
