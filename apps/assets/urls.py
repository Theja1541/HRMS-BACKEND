from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AssetCategoryViewSet,
    AssetViewSet,
    AssetAssignmentViewSet,
    AssetReturnViewSet,
    AssetMaintenanceViewSet,
    AssetHistoryViewSet,
    AssetDashboardAPIView,
    AssetRequestViewSet
)

router = DefaultRouter()
router.register(r'categories', AssetCategoryViewSet, basename='assetcategory')
router.register(r'assignments', AssetAssignmentViewSet, basename='assetassignment')
router.register(r'returns', AssetReturnViewSet, basename='assetreturn')
router.register(r'maintenance', AssetMaintenanceViewSet, basename='assetmaintenance')
router.register(r'history', AssetHistoryViewSet, basename='assethistory')
router.register(r'requests', AssetRequestViewSet, basename='assetrequest')
router.register(r'', AssetViewSet, basename='asset')  # Must be last

urlpatterns = [
    path('dashboard/', AssetDashboardAPIView.as_view(), name='asset-dashboard'),
    path('', include(router.urls)),
]
