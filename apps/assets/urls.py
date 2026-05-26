from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetViewSet, AssetReturnRequestViewSet

router = DefaultRouter()
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'return-requests', AssetReturnRequestViewSet, basename='asset-return-request')

urlpatterns = [
    path('', include(router.urls)),
]
