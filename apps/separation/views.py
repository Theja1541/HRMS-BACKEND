from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from .models import ResignationRequest, FinalSettlement
from .serializers import ResignationRequestSerializer, FinalSettlementSerializer

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
        
        # Initialize timeline
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

        # Role-based validation
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
                # Deactivate user upon HR approval to block login
                if hasattr(resignation.employee, 'user') and resignation.employee.user:
                    u = resignation.employee.user
                    u.is_active = False
                    u.save()
        elif action_type == 'RELIEVED':
            resignation.status = 'RELIEVED'
        else:
            resignation.status = 'REJECTED'
            # Reactivate user in case they were previously deactivated (e.g. by an accidental HR approval)
            if hasattr(resignation.employee, 'user') and resignation.employee.user:
                u = resignation.employee.user
                u.is_active = True
                u.save()
        
        # Append to approval history
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

        # Handle Relieving Logic if manually triggered early
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


class FinalSettlementViewSet(BaseCompanyViewSet):
    queryset = FinalSettlement.objects.all().select_related('resignation', 'resignation__company')
    serializer_class = FinalSettlementSerializer
    
    def get_queryset(self):
        # Override to filter via the related ResignationRequest company
        company = getattr(self.request.user, 'company', None)
        if company:
            return self.queryset.filter(resignation__company=company)
        return self.queryset.none()
    
    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        settlement = serializer.save()
        # Automatically trigger relieving workflow when settlement is PAID
        if settlement.status == 'PAID':
            with transaction.atomic():
                resignation = settlement.resignation
                if resignation.status != 'RELIEVED':
                    resignation.status = 'RELIEVED'
                    
                    # Append to timeline
                    timeline = list(resignation.timeline)
                    timeline.append({
                        "event": "Settlement Paid", "description": "Final settlement processed and paid.",
                        "date": timezone.now().isoformat()
                    })
                    timeline.append({
                        "event": "Employee Relieved", "description": "System access revoked automatically after settlement.",
                        "date": timezone.now().isoformat()
                    })
                    resignation.timeline = timeline
                    resignation.save()

                    # Deactivate User and Mark Employee as RELIEVED
                    employee_obj = resignation.employee
                    employee_obj.employment_status = 'RELIEVED'
                    employee_obj.save()
                    
                    if hasattr(employee_obj, 'user') and employee_obj.user:
                        user_obj = employee_obj.user
                        user_obj.is_active = False
                        user_obj.save()
