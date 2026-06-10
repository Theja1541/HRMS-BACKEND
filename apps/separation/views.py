import csv
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.http import HttpResponse

from .models import ResignationRequest, FinalSettlement, FinalSettlementDeduction
from .serializers import ResignationRequestSerializer, FinalSettlementSerializer, FFSettlementSerializer
from apps.assets.models import AssetAssignment, AssetReturn
from .permissions import IsHRAdmin
from .notifications import notify_ff_draft, notify_ff_approved, notify_asset_overdue
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from .services.ff_settlement_service import FFSettlementService

try:
    from antigravity.views import BaseViewSet
    from antigravity.permissions import HasAnyRole
except ImportError:
    # Fallback for local environment if antigravity is not installed
    class BaseViewSet(viewsets.ModelViewSet): pass
    class HasAnyRole:
        def __init__(self, roles): self.roles = roles
        def __call__(self): return self
        def has_permission(self, request, view): return True


class BaseCompanyViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        if company:
            return self.queryset.filter(company=company)
        return self.queryset.none()

    def perform_create(self, serializer):
        company = getattr(self.request.user, 'company', None)
        serializer.save(company=company)


class ResignationRequestViewSet(BaseCompanyViewSet):
    queryset = ResignationRequest.objects.all().select_related('employee', 'employee__user')
    serializer_class = ResignationRequestSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        
        if user.role in ['SUPER_ADMIN', 'ADMIN', 'HR']:
            return qs
        
        employee = getattr(user, 'employee_profile', None)
        if employee:
            return qs.filter(employee=employee)
        return qs.none()

    def perform_create(self, serializer):
        employee = self.request.user.employee_profile
        
        timeline = [{
            "event": "Resignation Submitted",
            "description": f"Resignation submitted by {employee.full_name}",
            "date": timezone.now().isoformat()
        }]
        
        serializer.save(
            company=self.request.user.company,
            employee=employee,
            submitted_on=timezone.now(),
            status='SUBMITTED',
            timeline=timeline
        )

    @action(detail=True, methods=['patch'])
    def approve(self, request, pk=None):
        resignation = self.get_object()
        action_type = request.data.get('action', 'APPROVED')
        stage = request.data.get('stage', 'MANAGER')
        remarks = request.data.get('remarks', '')
        user = request.user

        if stage == 'MANAGER' and user.role not in ['MANAGER', 'HR', 'ADMIN', 'SUPER_ADMIN']:
            return Response({'error': 'Only Managers or HR can perform Manager approvals.'}, status=403)
        if stage == 'HR' and user.role not in ['HR', 'ADMIN', 'SUPER_ADMIN']:
            return Response({'error': 'Only HR or Admins can perform HR approvals.'}, status=403)
        if action_type == 'RELIEVED' and user.role not in ['HR', 'ADMIN', 'SUPER_ADMIN']:
            return Response({'error': 'Only HR or Admins can mark employees as relieved.'}, status=403)

        if action_type == 'APPROVED':
            if stage == 'MANAGER':
                resignation.status = 'MANAGER_APPROVED'
            elif stage == 'HR':
                resignation.status = 'HR_APPROVED'
                if hasattr(resignation.employee, 'user') and resignation.employee.user:
                    u = resignation.employee.user
                    u.is_active = False
                    u.save()
        elif action_type == 'RELIEVED':
            resignation.status = 'RELIEVED'
        else:
            resignation.status = 'REJECTED'
            if hasattr(resignation.employee, 'user') and resignation.employee.user:
                u = resignation.employee.user
                u.is_active = True
                u.save()
        
        history = list(resignation.approval_history)
        history.append({
            "stage": stage, "action": action_type, "remarks": remarks,
            "action_by": request.user.username, "date": timezone.now().isoformat()
        })
        resignation.approval_history = history

        timeline = list(resignation.timeline)
        timeline.append({
            "event": f"{stage} {action_type}", "description": remarks,
            "date": timezone.now().isoformat()
        })
        resignation.timeline = timeline
        resignation.save()

        if action_type == 'RELIEVED' or resignation.status == 'RELIEVED':
            employee_obj = resignation.employee
            employee_obj.employment_status = 'RELIEVED'
            employee_obj.save()
            
            if hasattr(employee_obj, 'user') and employee_obj.user:
                user_obj = employee_obj.user
                user_obj.is_active = False
                user_obj.save()
                
            timeline.append({
                "event": "Employee Relieved", "description": "System access revoked.",
                "date": timezone.now().isoformat()
            })
            resignation.timeline = timeline
            resignation.save()

        return Response({'status': 'success', 'new_status': resignation.status})

    @action(detail=True, methods=['get'], permission_classes=[IsHRAdmin])
    def asset_clearance_status(self, request, pk=None):
        resignation = self.get_object()
        assignments = AssetAssignment.objects.filter(employee=resignation.employee, status='ACTIVE')
        
        unreturned, damaged, lost, cleared = [], [], [], []
        total_recovery_amount = 0
        
        for assignment in assignments:
            try:
                asset_return = assignment.return_record
                cond = asset_return.condition
                
                if cond == 'GOOD' or cond == 'NEEDS_REPAIR':
                    cleared.append({'asset_id': assignment.asset.id, 'asset_name': assignment.asset.asset_name})
                else:
                    recovery = asset_return.recovery_amount if asset_return.recovery_amount is not None else assignment.asset.purchase_cost
                    if recovery is None: recovery = 0
                    total_recovery_amount += float(recovery)
                    
                    item = {
                        'asset_id': assignment.asset.id, 
                        'asset_name': assignment.asset.asset_name, 
                        'recovery_amount': asset_return.recovery_amount, 
                        'purchase_cost': assignment.asset.purchase_cost, 
                        'effective_recovery': recovery
                    }
                    if cond == 'DAMAGED':
                        damaged.append(item)
                    elif cond == 'LOST':
                        lost.append(item)
            except Exception:
                unreturned.append({'asset_id': assignment.asset.id, 'asset_name': assignment.asset.asset_name, 'assigned_date': assignment.assigned_date})
                
        return Response({
            "clearance_blocked": len(unreturned) > 0,
            "unreturned": unreturned,
            "damaged": damaged,
            "lost": lost,
            "cleared": cleared,
            "total_recovery_amount": total_recovery_amount
        })

    @action(detail=True, methods=['post'], permission_classes=[IsHRAdmin])
    def generate_ff_settlement(self, request, pk=None):
        resignation = self.get_object()
        
        if resignation.status not in ['APPROVED', 'HR_APPROVED']:
            return Response({"error": "Resignation status must be APPROVED or HR_APPROVED."}, status=400)
            
        if not resignation.last_working_day or resignation.last_working_day > timezone.localdate():
            return Response({"error": "Resignation last_working_day must be <= today."}, status=400)
            
        clearance = self.asset_clearance_status(request, pk).data
        if clearance['clearance_blocked']:
            override_reason = request.data.get('override_reason')
            if not override_reason or str(override_reason).strip() == '':
                return Response({"error": "Unreturned assets exist. override_reason required."}, status=400)
                
        with transaction.atomic():
            settlement, created = FinalSettlement.objects.get_or_create(
                resignation=resignation,
                defaults={'status': 'DRAFT'}
            )
            
            settlement.deductions.filter(deduction_type__in=['ASSET_DAMAGE', 'ASSET_LOST']).delete()
            
            assignments = AssetAssignment.objects.filter(employee=resignation.employee, status='ACTIVE')
            for assignment in assignments:
                try:
                    ret = assignment.return_record
                    if ret.condition in ['DAMAGED', 'LOST']:
                        recovery = ret.recovery_amount if ret.recovery_amount is not None else assignment.asset.purchase_cost
                        if recovery is None: recovery = 0
                        dtype = 'ASSET_DAMAGE' if ret.condition == 'DAMAGED' else 'ASSET_LOST'
                        FinalSettlementDeduction.objects.create(
                            settlement=settlement,
                            deduction_type=dtype,
                            amount=recovery,
                            asset_return=ret,
                            description=f"{assignment.asset.asset_name} - {ret.get_condition_display()}"
                        )
                except Exception:
                    pass
            
            total_deductions = sum(d.amount for d in settlement.deductions.all())
            settlement.total_deductions = total_deductions
            settlement.net_amount = settlement.total_earnings - settlement.total_deductions
            settlement.save()
            
            notify_ff_draft(settlement)
            
            serializer = FinalSettlementSerializer(settlement)
            return Response(serializer.data)


class FinalSettlementViewSet(BaseViewSet):
    queryset = FinalSettlement.objects.prefetch_related("deductions").select_related("resignation").order_by("-created_at")
    serializer_class = FFSettlementSerializer

    @action(detail=False, methods=["post"], url_path="generate",
            permission_classes=[IsAuthenticated, HasAnyRole(["HR_ADMIN", "FINANCE"])])
    def generate_ff_settlement(self, request):
        resignation_request_id = request.data.get("resignation_request_id")
        if not resignation_request_id:
            raise ValidationError({"detail": "resignation_request_id is required."})

        settlement = FFSettlementService.generate_ff_settlement(resignation_request_id, request.user)
        return Response(FFSettlementSerializer(settlement).data, status=201)

    @action(detail=False, methods=['get'])
    def history(self, request):
        qs = self.get_queryset()
        
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
            
        search = request.query_params.get('search')
        if search:
            # handle both resignation and resignation_request variations gracefully based on schema
            if hasattr(FinalSettlement, 'resignation_request'):
                qs = qs.filter(resignation_request__employee__full_name__icontains=search) | qs.filter(resignation_request__employee__employee_id__icontains=search)
            else:
                qs = qs.filter(resignation__employee__full_name__icontains=search) | qs.filter(resignation__employee__employee_id__icontains=search)
            
        export = request.query_params.get('export')
        if export == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="ff_history.csv"'
            writer = csv.writer(response)
            writer.writerow(['Settlement ID', 'Employee ID', 'Employee Name', 'Department', 'Designation', 'DOJ', 'LWD', 'Gross Amount', 'Total Deductions', 'Net Amount', 'Status', 'Approved By', 'Approved At', 'Disbursed At', 'Deduction Type', 'Deduction Desc', 'Deduction Amount'])
            
            for s in qs:
                res = getattr(s, 'resignation_request', getattr(s, 'resignation', None))
                emp = res.employee if res else None
                if not emp: continue
                
                base_row = [
                    s.id, emp.employee_id, emp.full_name, getattr(emp, 'department', ''), getattr(emp, 'designation', ''), 
                    getattr(emp, 'date_of_joining', ''), res.last_working_day, s.total_earnings, s.total_deductions, 
                    s.net_amount, s.status, s.approved_by.username if s.approved_by else '', s.approved_at, getattr(s, 'disbursed_at', '')
                ]
                deductions = list(s.deductions.all())
                if not deductions:
                    writer.writerow(base_row + ['', '', ''])
                else:
                    for d in deductions:
                        dtype = d.get_deduction_type_display() if hasattr(d, 'get_deduction_type_display') else d.deduction_type
                        writer.writerow(base_row + [dtype, getattr(d, 'description', ''), d.amount])
            return response
            
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

