import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.mail import EmailMultiAlternatives
from django.conf import settings as django_settings
from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)

User = get_user_model()
VALID_NOTIFICATION_TYPES = {"INFO", "SUCCESS", "WARNING", "ERROR"}
VALID_TARGET_ROLES = {"ADMIN", "HR", "EMPLOYEE"}

# ─── Notification type visual config ──────────────────────────────────────────
TYPE_CONFIG = {
    "INFO":    {"icon": "ℹ️",  "color": "#0369a1", "bg": "#e0f2fe", "label": "Info"},
    "SUCCESS": {"icon": "✅", "color": "#15803d", "bg": "#dcfce7", "label": "Success"},
    "WARNING": {"icon": "⚠️", "color": "#b45309", "bg": "#fef3c7", "label": "Warning"},
    "ERROR":   {"icon": "🚨", "color": "#b91c1c", "bg": "#fee2e2", "label": "Critical"},
}


# ─── Email builder ─────────────────────────────────────────────────────────────
def _build_notification_email(recipient, title, message, notif_type):
    cfg = TYPE_CONFIG.get(notif_type, TYPE_CONFIG["INFO"])
    display_name = recipient.get_full_name() or recipient.username or recipient.email
    platform_name = getattr(django_settings, "PLATFORM_NAME", "HRMS")
    login_url = getattr(django_settings, "FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/") + "/login"

    subject = f"[{cfg['label']}] {title} — {platform_name}"

    text_body = (
        f"Hello {display_name},\n\n"
        f"{title}\n\n"
        f"{message}\n\n"
        f"Log in to {platform_name}: {login_url}\n\n"
        f"Regards,\n{platform_name} Team"
    )

    html_body = (
        "<!DOCTYPE html>"
        "<html><head><meta charset=\"UTF-8\"></head>"
        "<body style=\"margin:0;padding:0;background:#f1f5f9;font-family:Arial,sans-serif;\">"
        "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">"
        "<tr><td align=\"center\" style=\"padding:32px 16px;\">"
        "<table width=\"560\" cellpadding=\"0\" cellspacing=\"0\" "
        "style=\"background:#ffffff;border-radius:14px;overflow:hidden;"
        "box-shadow:0 4px 20px rgba(15,23,42,0.10);\">"
        "<tr><td style=\"background:linear-gradient(135deg,#1e3a8a,#2563eb);"
        "padding:28px 32px;text-align:left;\">"
        f"<div style=\"font-size:28px;margin-bottom:8px;\">{cfg['icon']}</div>"
        f"<div style=\"color:white;font-size:11px;font-weight:700;letter-spacing:2px;"
        f"text-transform:uppercase;opacity:0.75;\">{platform_name} &nbsp;&middot;&nbsp; {cfg['label']} Notification</div>"
        f"<h1 style=\"margin:8px 0 0;color:white;font-size:20px;font-weight:800;line-height:1.3;\">{title}</h1>"
        "</td></tr>"
        "<tr><td style=\"padding:28px 32px;\">"
        f"<p style=\"margin:0 0 8px;color:#64748b;font-size:14px;\">Hello <strong style=\"color:#0f172a;\">{display_name}</strong>,</p>"
        f"<div style=\"background:{cfg['bg']};border-left:4px solid {cfg['color']};"
        "border-radius:8px;padding:16px 20px;margin:18px 0;\">"
        f"<p style=\"margin:0;color:#0f172a;font-size:15px;line-height:1.7;white-space:pre-wrap;\">{message}</p>"
        "</div>"
        f"<p style=\"margin:24px 0 0;text-align:center;\">"
        f"<a href=\"{login_url}\" style=\"display:inline-block;background:#2563eb;color:#fff;"
        "text-decoration:none;padding:13px 28px;border-radius:8px;font-weight:700;font-size:15px;\">"
        f"Open {platform_name} Portal &rarr;</a></p>"
        "</td></tr>"
        "<tr><td style=\"background:#f8fafc;padding:16px 32px;text-align:center;border-top:1px solid #e2e8f0;\">"
        f"<p style=\"margin:0;color:#94a3b8;font-size:12px;\">This notification was sent by your {platform_name} administrator.<br>"
        "If you have questions, contact your HR department.</p>"
        "</td></tr>"
        "</table></td></tr></table>"
        "</body></html>"
    )

    return subject, text_body, html_body


def _send_notification_email(recipient, title, message, notif_type):
    """Send a single notification email. Logs errors but does NOT raise."""
    try:
        if not recipient.email:
            return
        from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "no-reply@hrms.com")
        subject, text_body, html_body = _build_notification_email(
            recipient, title, message, notif_type
        )
        msg = EmailMultiAlternatives(subject, text_body, from_email, [recipient.email])
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send notification email to %s (user %s)", recipient.email, recipient.pk
        )


# =========================================================
# GET /notifications/my/  — current user's notifications
# =========================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_notifications(request):
    notifications = Notification.objects.filter(user=request.user)
    serializer = NotificationSerializer(notifications, many=True)
    unread_count = notifications.filter(is_read=False).count()
    return Response({
        "unread_count": unread_count,
        "notifications": serializer.data,
    })


# =========================================================
# POST /notifications/read/<id>/  — mark one as read
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user,
        )
        notification.is_read = True
        notification.save()
        return Response({"message": "Marked as read"})
    except Notification.DoesNotExist:
        return Response({"error": "Not found"}, status=404)


# =========================================================
# POST /notifications/superadmin/send/  — broadcast
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_system_notification(request):
    """
    SuperAdmin only. Body fields:
      title (required), message, type (INFO/SUCCESS/WARNING/ERROR)
      company_id, user_ids, target_roles, also_send_email
    """
    if not (request.user.is_authenticated and getattr(request.user, "role", None) == "SUPER_ADMIN"):
        return Response({"error": "SuperAdmin only"}, status=status.HTTP_403_FORBIDDEN)

    company_id      = request.data.get("company_id")
    user_ids        = request.data.get("user_ids") or []
    target_roles    = request.data.get("target_roles") or []
    title           = (request.data.get("title") or "").strip()
    message         = (request.data.get("message") or "").strip()
    notif_type      = (request.data.get("type") or "INFO").upper()
    also_send_email = bool(request.data.get("also_send_email", False))

    if not title:
        return Response({"error": "title is required"}, status=status.HTTP_400_BAD_REQUEST)
    if notif_type not in VALID_NOTIFICATION_TYPES:
        return Response({"error": "Invalid notification type."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(user_ids, list):
        return Response({"error": "user_ids must be a list."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(target_roles, list):
        return Response({"error": "target_roles must be a list."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_ids = [int(uid) for uid in user_ids]
    except (TypeError, ValueError):
        return Response(
            {"error": "user_ids must contain only numeric user IDs."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    target_roles = [str(r).upper().strip() for r in target_roles if str(r).strip()]
    invalid_roles = sorted(set(target_roles) - VALID_TARGET_ROLES)
    if invalid_roles:
        return Response(
            {"error": "Invalid target role(s).", "roles": invalid_roles},
            status=status.HTTP_400_BAD_REQUEST,
        )

    users_qs = User.objects.filter(is_active=True)
    if company_id is not None:
        users_qs = users_qs.filter(company_id=company_id)
    if target_roles:
        users_qs = users_qs.filter(role__in=target_roles)
    if user_ids:
        users_qs = users_qs.filter(id__in=user_ids)
    else:
        users_qs = users_qs.exclude(role="SUPER_ADMIN").exclude(company__isnull=True)

    recipients = list(users_qs.distinct())
    if not recipients:
        return Response(
            {"error": "No active recipients match this target."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 1. Create in-app notifications
    notif_objs = [
        Notification(
            company_id=getattr(user, "company_id", None),
            user=user,
            title=title,
            message=message,
            type=notif_type,
        )
        for user in recipients
    ]
    with transaction.atomic():
        Notification.objects.bulk_create(notif_objs)

    # 2. Optionally send emails
    email_sent_count = 0
    email_failed_count = 0
    if also_send_email:
        for user in recipients:
            try:
                _send_notification_email(user, title, message, notif_type)
                email_sent_count += 1
            except Exception:
                email_failed_count += 1
                logger.exception("Email failed for user %s", user.pk)

    response_data = {
        "created_count": len(notif_objs),
        "message": f"Notifications sent to {len(notif_objs)} user(s).",
    }
    if also_send_email:
        response_data["email_sent_count"]   = email_sent_count
        response_data["email_failed_count"] = email_failed_count
        response_data["email_message"] = (
            f"Emails sent: {email_sent_count}"
            + (f" (failed: {email_failed_count})" if email_failed_count else "")
        )

    return Response(response_data)
