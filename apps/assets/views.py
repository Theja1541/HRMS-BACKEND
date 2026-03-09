from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import CompanyAsset, AssetAssignment, AssetReturnRequest
from .serializers import (
    CompanyAssetSerializer, 
    AssetAssignmentSerializer, 
    AssetReturnRequestSerializer,
    AssetReturnRequestCreateSerializer
)
from apps.accounts.permissions import IsAdminOrHR


class AssetReturnRequestViewSet(viewsets.ModelViewSet):
    queryset = AssetReturnRequest.objects.all()
    serializer_class = AssetReturnRequestSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if user.role.upper() in ['ADMIN', 'HR', 'SUPER_ADMIN']:
            return AssetReturnRequest.objects.all()
        return AssetReturnRequest.objects.filter(employee__user=user)

    def get_serializer_class(self):
        if self.action == 'create':
            return AssetReturnRequestCreateSerializer
        return AssetReturnRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output_serializer = AssetReturnRequestSerializer(instance)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_requests(self, request):
        """Employee's own asset return requests"""
        requests = AssetReturnRequest.objects.filter(employee__user=request.user)
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrHR])
    def pending(self, request):
        """Get all pending requests (Admin/HR only)"""
        requests = AssetReturnRequest.objects.filter(status='PENDING')
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrHR])
    def approve(self, request, pk=None):
        """Approve asset return request"""
        asset_request = self.get_object()
        admin_remarks = request.data.get('admin_remarks', '')
        
        asset_request.status = 'APPROVED'
        asset_request.approved_by = request.user
        asset_request.approval_date = timezone.now()
        asset_request.admin_remarks = admin_remarks
        asset_request.save()

        serializer = self.get_serializer(asset_request)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrHR])
    def reject(self, request, pk=None):
        """Reject asset return request"""
        asset_request = self.get_object()
        admin_remarks = request.data.get('admin_remarks', '')
        
        asset_request.status = 'REJECTED'
        asset_request.approved_by = request.user
        asset_request.approval_date = timezone.now()
        asset_request.admin_remarks = admin_remarks
        asset_request.save()

        serializer = self.get_serializer(asset_request)
        return Response(serializer.data)


class CompanyAssetViewSet(viewsets.ModelViewSet):
    queryset = CompanyAsset.objects.all()
    serializer_class = CompanyAssetSerializer
    permission_classes = [IsAdminOrHR]
    pagination_class = None


class AssetAssignmentViewSet(viewsets.ModelViewSet):
    queryset = AssetAssignment.objects.all()
    serializer_class = AssetAssignmentSerializer
    permission_classes = [IsAdminOrHR]
    pagination_class = None

    def get_permissions(self):
        if self.action == 'my_assets':
            return [IsAuthenticated()]
        return [IsAdminOrHR()]

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_assets(self, request):
        """Get current user's assigned assets"""
        try:
            employee = request.user.employee_profile
            assignments = AssetAssignment.objects.filter(employee=employee, status='ASSIGNED').select_related('asset')
            data = []
            for assignment in assignments:
                data.append({
                    'id': assignment.id,
                    'asset_name': assignment.asset.asset_name,
                    'asset_type': assignment.asset.asset_type,
                    'serial_number': assignment.asset.serial_number,
                    'assigned_date': assignment.assigned_date,
                    'status': assignment.status
                })
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def employee_assets(self, request):
        """Get assets assigned to a specific employee"""
        employee_id = request.query_params.get('employee_id')
        if employee_id:
            assignments = AssetAssignment.objects.filter(employee_id=employee_id, status='ASSIGNED')
            serializer = self.get_serializer(assignments, many=True)
            return Response(serializer.data)
        return Response({'error': 'employee_id required'}, status=status.HTTP_400_BAD_REQUEST)
