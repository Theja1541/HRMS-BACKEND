from rest_framework.permissions import BasePermission

class IsAdminOrHR(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in ['SUPER_ADMIN', 'ADMIN', 'HR']

class IsFinanceAdminOrHR(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in ['SUPER_ADMIN', 'ADMIN', 'HR', 'FINANCE_ADMIN']
