from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.accounts.permissions import IsAdmin
from .models import AuditLog


@api_view(['GET'])
@permission_classes([IsAdmin])
def audit_logs(request):
    logs = AuditLog.objects.all().order_by('-timestamp')[:100]

    data = [
        {
            "user": log.user.username if log.user else "Anonymous",
            "action": log.action,
            "model": log.model_name,
            "ip": log.ip_address,
            "time": log.timestamp,
        }
        for log in logs
    ]

    return Response(data)
