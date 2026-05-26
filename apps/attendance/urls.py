from django.urls import path
from .views import mark_attendance
from .views import bulk_mark_attendance
from .views import unlock_attendance
from .views import send_attendance_now
from . import views

from .views import (
    check_in,
    check_out,
    my_attendance,
    monthly_report,
    export_my_attendance
)

from .views import generate_today_attendance
from .views import edited_attendance_history


urlpatterns = [
    path("", views.attendance_list),
    path("check-in/", views.check_in),
    path("check-out/", views.check_out),
    path("my-attendance/", views.my_attendance),
    path("monthly-report/", views.monthly_report),
    path("mark/", views.mark_attendance),
    path("bulk-mark/", views.bulk_mark_attendance, name="bulk-mark"),
    path("unlock/", views.unlock_attendance, name="unlock"),
    path("my-attendance/export/", views.export_my_attendance, name="export-my-attendance"),
    
    # 🌟 Generate & Notify API
    path('generate-today/', views.generate_today_attendance, name='generate-today'),
    path('send-monthly-email/', views.send_attendance_now, name='send-monthly-email'),
    
    # 🌟 Day Status API
    path("day-status/", views.attendance_day_status, name="day-status"),
    path("dashboard-summary/", views.dashboard_summary),
    path("edited-history/", views.edited_attendance_history),
]
