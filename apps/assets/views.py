from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction

from apps.accounts.permissions import IsAdminOrHR
from apps.accounts.tenant_utils import TenantQuerysetMixin, get_current_company

from .models import AssetCategory, Asset, AssetAssignment, AssetReturn, AssetMaintenance, AssetHistory, AssetRequest
from .serializers import (
    AssetCategorySerializer,
    AssetSerializer,
    AssetAssignmentSerializer,
    AssetReturnSerializer,
    AssetMaintenanceSerializer,
    AssetHistorySerializer,
    AssetRequestSerializer,
    AssetRequestCreateSerializer
)


class AssetCategoryViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrHR]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def perform_create(self, serializer):
        company = get_current_company(self.request)
        serializer.save(company=company)


class AssetViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status', 'vendor_name']
    search_fields = ['asset_name', 'asset_code', 'serial_number', 'asset_tag']
    ordering_fields = ['created_at', 'purchase_date']

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminOrHR()]

    def perform_create(self, serializer):
        company = get_current_company(self.request)
        asset = serializer.save(company=company, created_by=self.request.user)
        # Create History
        AssetHistory.objects.create(
            company=company,
            asset=asset,
            action_type="CREATED",
            performed_by=self.request.user,
            description="Asset created"
        )

    def perform_update(self, serializer):
        asset = serializer.save()
        company = get_current_company(self.request)
        AssetHistory.objects.create(
            company=company,
            asset=asset,
            action_type="UPDATED",
            performed_by=self.request.user,
            description="Asset details updated"
        )


class AssetAssignmentViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = AssetAssignment.objects.all()
    serializer_class = AssetAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminOrHR()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        
        # Determine if Admin or HR
        is_admin_or_hr = getattr(user, 'role', '') in ['ADMIN', 'HR']

        # If not Admin/HR, restrict to own assignments
        if not is_admin_or_hr:
            if hasattr(user, 'employee_profile'):
                qs = qs.filter(employee=user.employee_profile)
            else:
                return qs.none()
        
        # If explicitly asking for my_assignments
        my_assignments = self.request.query_params.get('my_assignments')
        if my_assignments == 'true' and hasattr(user, 'employee_profile'):
            qs = qs.filter(employee=user.employee_profile)

        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        company = get_current_company(self.request)
        assignment = serializer.save(company=company, assigned_by=self.request.user)
        
        # Update asset status
        asset = assignment.asset
        asset.status = "ASSIGNED"
        asset.save()

        # Create history
        AssetHistory.objects.create(
            company=company,
            asset=asset,
            action_type="ASSIGNED",
            employee=assignment.employee,
            performed_by=self.request.user,
            description=f"Assigned to {assignment.employee}"
        )

    @transaction.atomic
    def perform_update(self, serializer):
        old_status = serializer.instance.status
        assignment = serializer.save()
        
        # If status changed to RETURNED via direct edit
        if old_status == "ACTIVE" and assignment.status == "RETURNED":
            asset = assignment.asset
            asset.status = "AVAILABLE"
            asset.save()
            
            AssetHistory.objects.create(
                company=assignment.company,
                asset=asset,
                action_type="RETURNED",
                employee=assignment.employee,
                performed_by=self.request.user,
                description=f"Assignment manually marked as Returned via assignment edit."
            )


class AssetReturnViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = AssetReturn.objects.all()
    serializer_class = AssetReturnSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    @transaction.atomic
    def perform_create(self, serializer):
        company = get_current_company(self.request)
        asset_return = serializer.save(company=company)
        
        # Update Assignment status
        assignment = asset_return.assignment
        assignment.status = "RETURNED"
        assignment.save()

        # Update Asset status based on condition
        asset = assignment.asset
        condition = asset_return.condition
        if condition == "GOOD":
            asset.status = "AVAILABLE"
        elif condition == "NEEDS_REPAIR":
            asset.status = "MAINTENANCE"
        elif condition == "DAMAGED":
            asset.status = "DAMAGED"
        elif condition == "LOST":
            asset.status = "LOST"
        asset.save()

        # Create History
        AssetHistory.objects.create(
            company=company,
            asset=asset,
            action_type="RETURNED",
            employee=asset_return.returned_by,
            performed_by=self.request.user,
            description=f"Returned in {condition} condition"
        )


class AssetMaintenanceViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = AssetMaintenance.objects.all()
    serializer_class = AssetMaintenanceSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    @transaction.atomic
    def perform_create(self, serializer):
        company = get_current_company(self.request)
        maintenance = serializer.save(company=company, created_by=self.request.user)

        asset = maintenance.asset
        if maintenance.status in ["OPEN", "IN_PROGRESS"]:
            asset.status = "MAINTENANCE"
            asset.save()

        AssetHistory.objects.create(
            company=company,
            asset=asset,
            action_type="MAINTENANCE",
            performed_by=self.request.user,
            description=f"Maintenance logged: {maintenance.maintenance_type}"
        )

    @transaction.atomic
    def perform_update(self, serializer):
        maintenance = serializer.save()
        asset = maintenance.asset

        if maintenance.status == "COMPLETED":
            asset.status = "AVAILABLE"
            asset.save()

        AssetHistory.objects.create(
            company=maintenance.company,
            asset=asset,
            action_type="UPDATED",
            performed_by=self.request.user,
            description=f"Maintenance updated to {maintenance.status}"
        )


class AssetHistoryViewSet(TenantQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AssetHistory.objects.all()
    serializer_class = AssetHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['asset', 'action_type']
    ordering_fields = ['action_date']
    ordering = ['-action_date']


from rest_framework.views import APIView

class AssetDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = get_current_company(request)
        assets = Asset.objects.filter(company=company)
        
        data = {
            "total_assets": assets.count(),
            "available_assets": assets.filter(status="AVAILABLE").count(),
            "assigned_assets": assets.filter(status="ASSIGNED").count(),
            "maintenance_assets": assets.filter(status="MAINTENANCE").count(),
            "lost_assets": assets.filter(status="LOST").count(),
            "damaged_assets": assets.filter(status="DAMAGED").count(),
            "retired_assets": assets.filter(status="RETIRED").count(),
        }
        return Response(data)

class AssetRequestViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = AssetRequest.objects.all()
    serializer_class = AssetRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'request_type']
    ordering_fields = ['request_date', 'approval_date']
    ordering = ['-request_date']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'role', '') in ['ADMIN', 'HR']:
            return qs
        if hasattr(user, 'employee_profile'):
            return qs.filter(employee=user.employee_profile)
        return qs.none()

    def get_serializer_class(self):
        if self.action == 'create':
            return AssetRequestCreateSerializer
        return AssetRequestSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, 'employee_profile'):
            raise serializers.ValidationError({"error": "User does not have an associated employee profile."})
        serializer.save(
            company=get_current_company(self.request),
            employee=user.employee_profile,
            status="PENDING"
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrHR])
    @transaction.atomic
    def approve(self, request, pk=None):
        asset_req = self.get_object()
        if asset_req.status != "PENDING":
            return Response({"error": f"Cannot approve request with status {asset_req.status}"}, status=status.HTTP_400_BAD_REQUEST)
        
        admin_remarks = request.data.get('admin_remarks', '')
        asset_req.status = "APPROVED"
        asset_req.admin_remarks = admin_remarks
        asset_req.approval_date = timezone.now()
        asset_req.approved_by = request.user
        asset_req.save()

        # Perform the actual action
        if asset_req.request_type == "ALLOCATION":
            if not asset_req.asset:
                return Response({"error": "No asset specified in allocation request"}, status=status.HTTP_400_BAD_REQUEST)
            if asset_req.asset.status != "AVAILABLE":
                return Response({"error": "Asset is not available for allocation"}, status=status.HTTP_400_BAD_REQUEST)
            
            assignment = AssetAssignment.objects.create(
                company=asset_req.company,
                asset=asset_req.asset,
                employee=asset_req.employee,
                assigned_by=request.user,
                remarks=admin_remarks
            )
            # Update asset status
            asset_req.asset.status = "ASSIGNED"
            asset_req.asset.save()
            # Log history
            AssetHistory.objects.create(
                company=asset_req.company,
                asset=asset_req.asset,
                action_type="ASSIGNED",
                employee=asset_req.employee,
                performed_by=request.user,
                description=f"Assigned via approved allocation request. {admin_remarks}"
            )
        
        elif asset_req.request_type == "RETURN":
            if not asset_req.asset:
                return Response({"error": "No asset specified in return request"}, status=status.HTTP_400_BAD_REQUEST)
            
            assignment = AssetAssignment.objects.filter(
                asset=asset_req.asset, employee=asset_req.employee, status="ACTIVE"
            ).first()

            if not assignment:
                return Response({"error": "No active assignment found for this asset and employee"}, status=status.HTTP_400_BAD_REQUEST)

            condition = request.data.get('condition', 'GOOD')
            AssetReturn.objects.create(
                company=asset_req.company,
                assignment=assignment,
                returned_by=asset_req.employee,
                condition=condition,
                remarks=admin_remarks
            )
            assignment.status = "RETURNED"
            assignment.save()

            if condition == "GOOD":
                asset_req.asset.status = "AVAILABLE"
            elif condition == "NEEDS_REPAIR":
                asset_req.asset.status = "MAINTENANCE"
            elif condition == "LOST":
                asset_req.asset.status = "LOST"
            elif condition == "DAMAGED":
                asset_req.asset.status = "DAMAGED"
            asset_req.asset.save()

            AssetHistory.objects.create(
                company=asset_req.company,
                asset=asset_req.asset,
                action_type="RETURNED",
                employee=asset_req.employee,
                performed_by=request.user,
                description=f"Returned via approved request. Condition: {condition}. {admin_remarks}"
            )

        return Response(AssetRequestSerializer(asset_req).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrHR])
    def reject(self, request, pk=None):
        asset_req = self.get_object()
        if asset_req.status != "PENDING":
            return Response({"error": f"Cannot reject request with status {asset_req.status}"}, status=status.HTTP_400_BAD_REQUEST)
        
        admin_remarks = request.data.get('admin_remarks', '')
        asset_req.status = "REJECTED"
        asset_req.admin_remarks = admin_remarks
        asset_req.approval_date = timezone.now()
        asset_req.approved_by = request.user
        asset_req.save()

        return Response(AssetRequestSerializer(asset_req).data)
