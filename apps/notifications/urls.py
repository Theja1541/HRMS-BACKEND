from django.urls import path
from . import views

urlpatterns = [
    path("my/", views.my_notifications),
    path("read/<int:notification_id>/", views.mark_notification_read),
]