from django.urls import path, include

try:
    from antigravity.routers import DefaultRouter
except ImportError:
    # Fallback for local environment
    from rest_framework.routers import DefaultRouter

from .views import ResignationRequestViewSet, FinalSettlementViewSet

router = DefaultRouter()
router.register(r'requests', ResignationRequestViewSet, basename='separation-requests')
router.register(r'settlements', FinalSettlementViewSet, basename='separation-settlements')

urlpatterns = [
    path('', include(router.urls)),
]
