"""
Multi-tenant utilities: mixins and helpers for request.company and queryset filtering.
"""
from rest_framework.request import Request


def get_current_company(request):
    """
    Return the company for the current request (tenant).
    Uses request.company if set (by middleware or TenantMixin), else request.user.company.
    """
    if hasattr(request, "company") and request.company is not None:
        return request.company
    if hasattr(request, "user") and request.user.is_authenticated:
        return getattr(request.user, "company", None)
    return None


class TenantMixin:
    """
    Mixin for API viewsets: sets request.company after authentication.
    Use with ModelViewSet so get_queryset() and perform_create() can use request.company.
    JWT auth runs in the view layer, so request.company must be set here for API requests.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(request, "user", None) and request.user.is_authenticated:
            request.company = getattr(request.user, "company", None)
        else:
            request.company = None


class TenantQuerysetMixin(TenantMixin):
    """
    Mixin that (1) sets request.company and (2) filters queryset by company.
    Override get_tenant_queryset_filter() if your model uses a different company field.
    """

    tenant_company_field = "company"

    def get_tenant_queryset_filter(self):
        """Return kwargs for filtering queryset by current company."""
        company = get_current_company(self.request)
        if company is None:
            return {}
        return {self.tenant_company_field: company}

    def get_queryset(self):
        qs = super().get_queryset()
        filt = self.get_tenant_queryset_filter()
        if filt:
            return qs.filter(**filt)
        return qs

    def perform_create(self, serializer):
        company = get_current_company(self.request)
        if company is not None:
            serializer.save(**{self.tenant_company_field: company})
        else:
            serializer.save()
