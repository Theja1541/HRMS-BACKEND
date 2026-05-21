"""
Tenant and subscription lockout middleware for multi-tenant SaaS.
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse


class TenantMiddleware(MiddlewareMixin):
    """
    After authentication, set request.company = request.user.company.
    Unauthenticated requests get request.company = None.
    """

    def process_request(self, request):
        request.company = None
        if hasattr(request, "user") and request.user.is_authenticated:
            request.company = getattr(request.user, "company", None)


class SubscriptionLockoutMiddleware(MiddlewareMixin):
    """
    Blocks all requests from non-SUPER_ADMIN users if their company
    has billing_action_stopped = True, except for support, branding, logout and refresh token.
    """

    def process_request(self, request):
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        # Super Admin is globally exempt
        if getattr(request.user, "role", "") == "SUPER_ADMIN":
            return None

        company = getattr(request.user, "company", None)
        if not company or not getattr(company, "billing_action_stopped", False):
            return None

        # Check if the path is in the exempt list
        path = request.path
        exempt_prefixes = [
            "/api/support/",
            "/api/accounts/company-branding",
            "/api/accounts/logout",
            "/api/accounts/token/refresh",
            "/api/auth/logout",
            "/api/auth/token/refresh",
        ]

        if any(path.startswith(prefix) for prefix in exempt_prefixes):
            return None

        # Return 402 Payment Required
        return JsonResponse(
            {
                "detail": "Your company's subscription has expired and actions have been suspended. Please contact your Super Admin or access Billing/Support.",
                "billing_action_stopped": True,
            },
            status=402,
        )
