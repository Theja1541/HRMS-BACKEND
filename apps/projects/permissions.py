from rest_framework import permissions

class ProjectAccessPermission(permissions.BasePermission):
    """
    Super Admin - Full Access Across All Companies
    Company Admin - Full Access Within Company
    HR - Create/Edit/View Projects, Assign Employees
    Project Manager - Manage Assigned Projects, Update Progress, Update Hours
    Employee - View Assigned Projects Only
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        role = request.user.role
        
        if role in ["SUPER_ADMIN", "ADMIN", "HR"]:
            return True
            
        # Project Managers and Employees can list/view, but filtering will be applied in the queryset.
        if role in ["EMPLOYEE", "PROJECT_MANAGER"] and request.method in permissions.SAFE_METHODS:
            return True
            
        # Project Managers can edit assignments or update progress
        if role == "EMPLOYEE" and hasattr(request.user, 'employee_profile'):
            # Some actions might be allowed, but generally handled by object permissions
            return True

        return True

    def has_object_permission(self, request, view, obj):
        role = request.user.role

        if role == "SUPER_ADMIN":
            return True

        # Tenant Isolation
        if role != "SUPER_ADMIN":
            if hasattr(obj, 'company_id') and obj.company_id != request.user.company_id:
                return False
            if hasattr(obj, 'project') and obj.project.company_id != request.user.company_id:
                return False

        if role in ["ADMIN", "HR"]:
            return True

        if role == "EMPLOYEE":
            # For Employee (could be PM or regular member on this project)
            if hasattr(obj, 'assignments'):
                # it's a project
                is_pm = obj.project_manager_id == request.user.id
                is_assigned = obj.assignments.filter(employee__user=request.user, assignment_status='Active').exists()
                
                if request.method in permissions.SAFE_METHODS:
                    return is_pm or is_assigned
                
                # PM can manage assigned projects
                if is_pm:
                    return True
                    
            elif hasattr(obj, 'project'):
                # it's an assignment
                is_pm = obj.project.project_manager_id == request.user.id
                is_assigned = obj.employee.user_id == request.user.id
                
                if request.method in permissions.SAFE_METHODS:
                    return is_pm or is_assigned
                    
                # PM can manage assignments
                if is_pm:
                    return True

        return False
