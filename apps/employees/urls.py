from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeViewSet, employee_dashboard

router = DefaultRouter()
router.register(r"", EmployeeViewSet, basename="employees")

urlpatterns = [
    # 🔥 Put custom routes FIRST
    path("dashboard/", employee_dashboard, name="employee-dashboard"),

    # Then include router
    path("", include(router.urls)),
]