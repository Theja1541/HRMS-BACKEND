from django.urls import path
from apps.billing import views_subscription

urlpatterns = [
    path("create-order/", views_subscription.create_razorpay_order, name="create_razorpay_order"),
    path("verify/", views_subscription.verify_payment, name="verify_payment"),
    path("history/", views_subscription.get_payment_history, name="get_payment_history"),
    path("webhook/", views_subscription.razorpay_webhook, name="razorpay_webhook"),
]
