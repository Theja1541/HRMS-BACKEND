from django.urls import path
from . import views

urlpatterns = [
    path("tickets/", views.ticket_list),
    path("tickets/create/", views.ticket_create),
    path("tickets/<int:ticket_id>/", views.ticket_detail),
]
