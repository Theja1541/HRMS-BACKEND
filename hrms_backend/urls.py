"""
URL configuration for hrms_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse   # ✅ FIX
from rest_framework_simplejwt.views import TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static


def home(request):
    return JsonResponse({
        "status": "HRMS Backend is running 🚀"
    })

def api_test(request):
    return JsonResponse({
        "status": "OK",
        "message": "HRMS Backend is running successfully"
    })

def health_check(request):
    return JsonResponse({
        "status": "SUCCESS",
        "backend": "HRMS Backend is running perfectly 🚀"
    })

urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),

    path('api/test/', api_test),
    path('api/health/', health_check),

    path('api/accounts/', include('apps.accounts.urls')),
    path('api/employees/', include('apps.employees.urls')),
    path('api/attendance/', include('apps.attendance.urls')),
    path('api/leaves/', include('apps.leaves.urls')),
    path('api/audit/', include('apps.audit.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/payroll/', include('apps.payroll.urls')),

    path("api/accounts/token/refresh/", TokenRefreshView.as_view()),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
