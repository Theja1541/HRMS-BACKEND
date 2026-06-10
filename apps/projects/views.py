from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.utils import timezone
import datetime

from .models import Project, ProjectAssignment
from .serializers import ProjectSerializer, ProjectAssignmentSerializer
from .permissions import ProjectAccessPermission

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [ProjectAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project_status', 'priority', 'active_status', 'billing_type', 'department_id', 'project_manager']
    search_fields = ['project_name', 'project_code', 'client_name']
    ordering_fields = ['start_date', 'planned_end_date', 'due_date', 'project_value', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = Project.objects.filter(is_deleted=False)
        
        if user.role != "SUPER_ADMIN":
            qs = qs.filter(company=user.company)
            
        if user.role == "EMPLOYEE" and hasattr(user, 'employee_profile'):
            # Employee only sees assigned projects or managed projects
            qs = qs.filter(
                Q(project_manager=user) | 
                Q(assignments__employee=user.employee_profile, assignments__assignment_status='Active')
            ).distinct()
            
        return qs

    def perform_create(self, serializer):
        project = serializer.save(
            company=self.request.user.company,
            created_by=self.request.user
        )
        if project.project_manager:
            from apps.notifications.models import Notification
            Notification.objects.create(
                company=project.company,
                user=project.project_manager,
                title=f"New Project Assigned: {project.project_code}",
                message=f"You have been assigned as the Project Manager for {project.project_name}.",
                type="INFO"
            )

    def perform_update(self, serializer):
        old_status = serializer.instance.project_status
        project = serializer.save(updated_by=self.request.user)
        
        if old_status != 'Completed' and project.project_status == 'Completed':
            from apps.notifications.models import Notification
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            hr_users = User.objects.filter(company=project.company, role='HR')
            notifications = []
            if project.project_manager:
                notifications.append(Notification(
                    company=project.company, user=project.project_manager,
                    title=f"Project Completed: {project.project_code}",
                    message=f"The project {project.project_name} has been marked as Completed.",
                    type="SUCCESS"
                ))
            for hr in hr_users:
                notifications.append(Notification(
                    company=project.company, user=hr,
                    title=f"Project Completed: {project.project_code}",
                    message=f"The project {project.project_name} has been marked as Completed.",
                    type="SUCCESS"
                ))
            if notifications:
                Notification.objects.bulk_create(notifications)

    def perform_destroy(self, instance):
        # Soft delete
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save()

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        qs = self.get_queryset()
        
        total_projects = qs.count()
        active_projects = qs.filter(active_status=True).count()
        completed_projects = qs.filter(project_status='Completed').count()
        on_hold_projects = qs.filter(project_status='On Hold').count()
        
        total_value = qs.aggregate(Sum('project_value'))['project_value__sum'] or 0
        active_value = qs.filter(active_status=True).aggregate(Sum('project_value'))['project_value__sum'] or 0
        completed_value = qs.filter(project_status='Completed').aggregate(Sum('project_value'))['project_value__sum'] or 0
        
        # Employees assigned
        assignments = ProjectAssignment.objects.filter(project__in=qs, assignment_status='Active')
        total_assigned_employees = assignments.values('employee').distinct().count()
        
        # Deadlines
        now = timezone.now().date()
        end_of_month = (now.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
        due_this_month = qs.filter(due_date__gte=now, due_date__lte=end_of_month).count()
        
        overdue_projects = qs.filter(due_date__lt=now).exclude(project_status='Completed').count()
        
        status_distribution = list(qs.values('project_status').annotate(count=Count('id')))

        return Response({
            'kpi': {
                'total_projects': total_projects,
                'active_projects': active_projects,
                'completed_projects': completed_projects,
                'on_hold_projects': on_hold_projects,
                'total_value': total_value,
                'active_value': active_value,
                'completed_value': completed_value,
                'total_assigned_employees': total_assigned_employees,
                'due_this_month': due_this_month,
                'overdue_projects': overdue_projects
            },
            'charts': {
                'status_distribution': status_distribution,
            }
        })

class ProjectAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectAssignmentSerializer
    permission_classes = [ProjectAccessPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['project', 'employee', 'assignment_status']
    ordering_fields = ['assigned_date', 'hours_planned', 'hours_spent']

    def get_queryset(self):
        user = self.request.user
        qs = ProjectAssignment.objects.all()
        
        if user.role != "SUPER_ADMIN":
            qs = qs.filter(company=user.company)
            
        if user.role == "EMPLOYEE" and hasattr(user, 'employee_profile'):
            # See only own assignments or assignments for projects they manage
            qs = qs.filter(
                Q(employee=user.employee_profile) | 
                Q(project__project_manager=user)
            ).distinct()
            
        return qs

    def perform_create(self, serializer):
        assignment = serializer.save(
            company=self.request.user.company,
            created_by=self.request.user
        )
        if assignment.employee and assignment.employee.user:
            from apps.notifications.models import Notification
            Notification.objects.create(
                company=assignment.company,
                user=assignment.employee.user,
                title=f"Assigned to Project: {assignment.project.project_code}",
                message=f"You have been assigned to {assignment.project.project_name} as {assignment.project_role}.",
                type="INFO"
            )

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        assignment = self.get_object()
        assignment.assignment_status = 'Released'
        assignment.released_date = timezone.now().date()
        assignment.save()
        return Response({'status': 'assignment released'})
