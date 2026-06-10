from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Project
from apps.notifications.models import Notification
from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task
def check_project_deadlines():
    today = timezone.now().date()
    
    # Check intervals
    intervals = {
        15: "15 Days",
        7: "7 Days",
        3: "3 Days",
        1: "1 Day"
    }

    active_projects = Project.objects.filter(is_deleted=False).exclude(project_status='Completed')

    for project in active_projects:
        if not project.due_date:
            continue
            
        remaining_days = (project.due_date - today).days

        # Overdue
        if remaining_days < 0:
            notify_users(
                project, 
                f"Project Overdue: {project.project_code}", 
                f"The project {project.project_name} is overdue by {abs(remaining_days)} days.",
                type="ERROR"
            )
        # Upcoming deadlines
        elif remaining_days in intervals:
            notify_users(
                project,
                f"Upcoming Deadline: {project.project_code}",
                f"The project {project.project_name} is due in {intervals[remaining_days]}.",
                type="WARNING"
            )

def notify_users(project, title, message, type="INFO"):
    users_to_notify = set()
    
    # Project Manager
    if project.project_manager:
        users_to_notify.add(project.project_manager)
        
    # Assigned Employees
    for assignment in project.assignments.filter(assignment_status='Active'):
        if assignment.employee and assignment.employee.user:
            users_to_notify.add(assignment.employee.user)
            
    notifications = []
    for user in users_to_notify:
        notifications.append(Notification(
            company=project.company,
            user=user,
            title=title,
            message=message,
            type=type
        ))
        
    if notifications:
        Notification.objects.bulk_create(notifications)
