from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetReturnRequestViewSet, CompanyAssetViewSet, AssetAssignmentViewSet

router = DefaultRouter()
router.register(r'return-requests', AssetReturnRequestViewSet, basename='asset-return-request')
router.register(r'company-assets', CompanyAssetViewSet, basename='company-asset')
router.register(r'assignments', AssetAssignmentViewSet, basename='asset-assignment')

urlpatterns = [
    path('', include(router.urls)),
]
