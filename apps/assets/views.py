from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdminOrHR
from apps.accounts.tenant_utils import TenantQuerysetMixin, get_current_company
from django.utils import timezone

from .models import Asset, AssetReturnRequest
from .serializers import (
    AssetSerializer,
    AssetReturnRequestSerializer,
    AssetReturnRequestCreateSerializer,
)

class AssetViewSet(viewsets.ModelViewSet):
    """CRUD for unified Asset model"""
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAdminOrHR()]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def my_assets(self, request):
        """Return assets assigned to the requesting employee"""
        employee = getattr(request.user, "employee_profile", None)
        if not employee:
            return Response({"error": "Employee profile not found"}, status=status.HTTP_400_BAD_REQUEST)
        assets = Asset.objects.filter(employee=employee)
        serializer = self.get_serializer(assets, many=True)
        return Response(serializer.data)

class AssetReturnRequestViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = AssetReturnRequest.objects.all()
    serializer_class = AssetReturnRequestSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, "role", "").upper() == "EMPLOYEE":
            return qs.filter(employee__user=user)
        company = get_current_company(self.request)
        if company is not None:
            return qs.filter(company=company)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return AssetReturnRequestCreateSerializer
        return AssetReturnRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output_serializer = AssetReturnRequestSerializer(instance)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def my_requests(self, request):
        """Employee's own asset return requests"""
        requests = AssetReturnRequest.objects.filter(employee__user=request.user)
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[IsAdminOrHR])
    def pending(self, request):
        """Get all pending requests (Admin/HR only)"""
        requests = self.get_queryset().filter(status="PENDING")
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrHR])
    def approve(self, request, pk=None):
        """Approve asset return request"""
        asset_request = self.get_object()
        admin_remarks = request.data.get("admin_remarks", "")
        asset_request.status = "APPROVED"
        asset_request.approved_by = request.user
        asset_request.approval_date = timezone.now()
        asset_request.admin_remarks = admin_remarks
        asset_request.save()
        serializer = self.get_serializer(asset_request)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrHR])
    def reject(self, request, pk=None):
        """Reject asset return request"""
        asset_request = self.get_object()
        admin_remarks = request.data.get("admin_remarks", "")
        asset_request.status = "REJECTED"
        asset_request.approved_by = request.user
        asset_request.approval_date = timezone.now()
        asset_request.admin_remarks = admin_remarks
        asset_request.save()
        serializer = self.get_serializer(asset_request)
        return Response(serializer.data)
