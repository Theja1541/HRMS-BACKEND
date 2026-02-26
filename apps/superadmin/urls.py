from django.urls import path
from .views import monthly_growth_analytics

urlpatterns = [
    path("analytics/monthly-growth/", monthly_growth_analytics),
]
