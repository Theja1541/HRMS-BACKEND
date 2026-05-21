from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication

from .services import is_module_enabled


MODULE_PATHS = {
    "/api/leaves/": ("leave", "Leave Management"),
    "/api/payroll/": ("payroll", "Payroll"),
    "/api/assets/": ("assets", "Asset Management"),
    "/api/attendance/": ("attendance", "Attendance"),
    "/api/support/": ("support", "Support Tickets"),
}


class ModuleFeatureFlagMiddleware:
    """
    Blocks disabled platform modules at the API boundary.
    Super Admin remains exempt so they can inspect the platform.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        module_name = None
        module_label = None
        for prefix, module in MODULE_PATHS.items():
            if request.path.startswith(prefix):
                module_name, module_label = module
                break

        if module_name and not is_module_enabled(module_name):
            user = getattr(request, "user", None)
            if not getattr(user, "is_authenticated", False):
                try:
                    authenticated = self.jwt_auth.authenticate(request)
                    if authenticated:
                        user, _token = authenticated
                except Exception:
                    user = None

            if getattr(user, "is_authenticated", False):
                role = str(getattr(user, "role", "")).upper()
                if role != "SUPER_ADMIN":
                    return JsonResponse(
                        {
                            "detail": (
                                f"{module_label} module is disabled by Super Admin settings."
                            )
                        },
                        status=403,
                    )

        return self.get_response(request)
