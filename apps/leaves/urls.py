# apps/leaves/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("types/", views.leave_types),
    path("apply/", views.apply_leave),
    path("approve/<int:leave_id>/", views.approve_leave),
    path("reject/<int:leave_id>/", views.reject_leave),
    path("my-balance/", views.my_leave_balance),
    path("all/", views.all_leave_requests),
    path("me/", views.my_leaves),
]