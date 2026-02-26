from django.urls import path
from .views import mark_attendance
from .views import bulk_mark_attendance
from .views import unlock_attendance
from . import views

from .views import (
    check_in,
    check_out,
    my_attendance,
    monthly_report
)

urlpatterns = [
    path("", views.attendance_list),
    path("check-in/", views.check_in),
    path("check-out/", views.check_out),
    path("my-attendance/", views.my_attendance),
    path("monthly-report/", views.monthly_report),
    path("mark/", views.mark_attendance),
    path("bulk-mark/", views.bulk_mark_attendance),
    path("unlock/", views.unlock_attendance),
]