from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.accounts.permissions import IsAdmin, IsSuperAdmin
from .models import AuditLog


@api_view(['GET'])
@permission_classes([IsAdmin])
def audit_logs(request):
    company = getattr(request.user, "company", None)
    qs = AuditLog.objects.all().order_by('-timestamp')[:100]
    if company is not None:
        qs = qs.filter(company=company)
    data = [
        {
            "id": log.id,
            "user": log.user.username if log.user else "Anonymous",
            "action": log.action,
            "model": log.model_name,
            "ip": log.ip_address,
            "time": log.timestamp,
            "description": log.description or "",
        }
        for log in qs
    ]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def audit_logs_superadmin(request):
    """Cross-tenant audit logs for SuperAdmin with optional filters and pagination."""
    qs = AuditLog.objects.select_related("user", "company").order_by("-timestamp")

    company_id = request.query_params.get("company_id")
    if company_id:
        qs = qs.filter(company_id=company_id)
    action = request.query_params.get("action")
    if action:
        qs = qs.filter(action=action.upper())
    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(user_id=user_id)

    page_size = min(int(request.query_params.get("page_size", 50)), 100)
    page = int(request.query_params.get("page", 1))
    start = (page - 1) * page_size
    end = start + page_size
    logs = list(qs[start:end])

    data = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "username": log.user.username if log.user else "Anonymous",
            "company_id": log.company_id,
            "company_name": log.company.name if log.company else None,
            "action": log.action,
            "model_name": log.model_name,
            "object_id": log.object_id,
            "description": log.description or "",
            "ip_address": str(log.ip_address) if log.ip_address else None,
            "timestamp": log.timestamp,
        }
        for log in logs
    ]
    return Response({
        "results": data,
        "page": page,
        "page_size": page_size,
        "count": len(data),
    })
