from .models import AuditLog


def log_action(request, action, model_name, object_id=None, description=""):
    ip = request.META.get("REMOTE_ADDR")

    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=model_name,
        object_id=object_id,
        description=description,
        ip_address=ip
    )
