from django.urls import path
from .views import (
    monthly_growth_analytics,
    effective_settings,
    settings_list,
    settings_update,
    test_smtp_email,
    reports_overview,
    mfa_send_otp,
    mfa_verify_otp,
)

urlpatterns = [
    path("analytics/monthly-growth/", monthly_growth_analytics),
    path("settings/effective/", effective_settings),
    path("settings/", settings_list),
    path("settings/update/", settings_update),
    path("settings/test-email/", test_smtp_email),
    path("reports/", reports_overview),
    path("mfa/send/", mfa_send_otp),
    path("mfa/verify/", mfa_verify_otp),
]
