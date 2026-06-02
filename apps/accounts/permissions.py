from rest_framework.permissions import BasePermission


def normalize_role(value):
    """Return uppercase role string for comparisons; empty string if missing."""
    if value is None:
        return ""
    return str(value).strip().upper()


class IsSuperAdmin(BasePermission):
    """Platform-level Super Admin only. No company_id."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", "").upper() == "SUPER_ADMIN"
        )


class IsCompanyAdmin(BasePermission):
    """Company Admin only (role=ADMIN). Must have company_id. Excludes Super Admin."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        role = getattr(request.user, "role", "").upper()
        if role != "ADMIN":
            return False
        return getattr(request.user, "company_id", None) is not None


class IsCompanyAdminOrHR(BasePermission):
    """Company-scoped Admin or HR only. Excludes Super Admin."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        role = getattr(request.user, "role", "").upper()
        if role not in {"ADMIN", "HR"}:
            return False
        return getattr(request.user, "company_id", None) is not None


class IsAdmin(BasePermission):
    """Admin or Super Admin (for views that both can access)."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", "").upper() in ["ADMIN", "SUPER_ADMIN"]
        )


class IsHR(BasePermission):
    """HR, Admin, or Super Admin."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", "").upper() in ["HR", "ADMIN", "SUPER_ADMIN"]
        )


class IsEmployee(BasePermission):
    """Employee role only."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", "").upper() == "EMPLOYEE"
        )


class IsAdminOrHR(BasePermission):
    """Admin or HR (company-scoped). Super Admin included for cross-tenant access."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", "").upper() in ["ADMIN", "HR", "SUPER_ADMIN"]
        )


class RequireCompanyForNonSuperAdmin(BasePermission):
    """
    For non–Super Admin users, require request.user.company_id to be set.
    Use together with other permissions to ensure tenant context.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", "").upper() == "SUPER_ADMIN":
            return True
        return getattr(request.user, "company_id", None) is not None


def user_can_access_company(request, company_id):
    """Return True if request.user can access the given company (tenant isolation)."""
    if not request.user.is_authenticated:
        return False
    if getattr(request.user, "role", "").upper() == "SUPER_ADMIN":
        return True
    return getattr(request.user, "company_id", None) == company_id


class IsTenantObjectOrSuperAdmin(BasePermission):
    """
    Object-level permission: allow access only if object belongs to user's company,
    or user is Super Admin. Use in views that expose a single object (e.g. by ID).
    Override get_tenant_object_company(obj) if the object's company is not obj.company.
    """

    def get_tenant_object_company(self, request, view, obj):
        return getattr(obj, "company", None)

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", "").upper() == "SUPER_ADMIN":
            return True
        company = self.get_tenant_object_company(request, view, obj)
        if company is None:
            return False
        return getattr(request.user, "company_id", None) == company.id


def check_company_module_permission(request, module_name, action_name, page_name=None):
    """
    Checks if the company of the logged-in user has permission for `action_name` in `module_name`.
    If `page_name` is provided, it checks the page's enabled status and granular `page_actions` settings.
    Super Admins are exempt from this restriction.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False

    if getattr(user, "role", "").upper() == "SUPER_ADMIN":
        return True

    company = getattr(user, "company", None)
    if not company:
        return True  # Default to True if no company context exists

    enabled_modules = getattr(company, "enabled_modules", None)
    if not enabled_modules or not isinstance(enabled_modules, dict):
        return True

    # Standardize module key (e.g. leaves -> leave)
    comp_key = "leave" if module_name == "leaves" else module_name
    module_config = enabled_modules.get(comp_key)
    if module_config is None:
        return True

    if isinstance(module_config, bool):
        return module_config

    if isinstance(module_config, dict):
        if module_config.get("enabled") is False:
            return False

        # If page_name is specified, check both page-level visibility and page action
        if page_name:
            pages = module_config.get("pages", {})
            if pages.get(page_name) is False:
                return False

            page_actions = module_config.get("page_actions", {})
            if page_actions and page_name in page_actions:
                actions = page_actions.get(page_name, {})
                if action_name in actions:
                    return actions[action_name] is True

        # Fallback to module-level actions
        actions = module_config.get("actions", {})
        if action_name in actions:
            return actions[action_name] is True

    return True