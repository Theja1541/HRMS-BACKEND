from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, ProjectAssignmentViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'assignments', ProjectAssignmentViewSet, basename='projectassignment')

urlpatterns = [
    path('', include(router.urls)),
]
