from .models import AuditLog


def log_action(request, action, model_name, object_id=None, description="", company=None, user_override=None):
    """Record an audit log entry. Use user_override when the acting user is not request.user (e.g. login)."""
    ip = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
    user = user_override if user_override is not None else (
        request.user if request and getattr(request, "user", None) and request.user.is_authenticated else None
    )
    if company is None and user and getattr(user, "company", None):
        company = user.company
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=str(object_id) if object_id is not None else None,
        description=description or "",
        ip_address=ip,
        company=company,
    )
