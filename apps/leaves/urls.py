from django.urls import path
from . import views
from .views import cancel_leave, leave_detail

urlpatterns = [
    path("types/", views.leave_types),
    path("manage-types/", views.manage_leave_types),
    path("manage-types/<int:leave_type_id>/", views.update_leave_type),
    path("apply/", views.apply_leave),
    path("approve/<int:leave_id>/", views.approve_leave),
    path("reject/<int:leave_id>/", views.reject_leave),
    path("cancel/<int:leave_id>/", views.cancel_leave),
    path("detail/<int:leave_id>/", views.leave_detail),
    path("my-balance/", views.my_leave_balance),
    path("all/", views.all_leave_requests),
    path("requests/", views.all_leave_requests),
    path("me/", views.my_leaves),
    path("dashboard/", views.leave_dashboard),
    path("calendar/", views.leave_calendar),
    path("debug/", views.debug_leaves),
    path("analytics/", views.leave_analytics),
]