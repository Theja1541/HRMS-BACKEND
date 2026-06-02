from django.urls import path
from apps.billing import views_subscription

urlpatterns = [
    path("plans/", views_subscription.get_subscription_plans, name="get_subscription_plans"),
    path("current/", views_subscription.get_current_subscription, name="get_current_subscription"),
]
