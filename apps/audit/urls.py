from django.urls import path
from .views import audit_logs, audit_logs_superadmin

urlpatterns = [
    path("logs/", audit_logs),
    path("logs/superadmin/", audit_logs_superadmin),
]
