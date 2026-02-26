from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Payslip, PayslipEmailLog
from .email_utils import send_payslip_email


@shared_task(bind=True, max_retries=5)
def send_payslip_email_task(self, payslip_id, batch_id=None):
    """
    Background task to send payslip email.

    Features:
    - Email logging
    - Retry with exponential backoff
    - Bulk progress tracking
    - Real-time WebSocket update
    """

    channel_layer = get_channel_layer()

    try:
        # ==================================================
        # Fetch Payslip
        # ==================================================
        payslip = Payslip.objects.get(id=payslip_id)
        email_address = payslip.employee.user.email

        # ==================================================
        # Create Email Log (PENDING)
        # ==================================================
        log = PayslipEmailLog.objects.create(
            payslip=payslip,
            email=email_address,
            status="PENDING",
            retry_count=self.request.retries
        )

        # ==================================================
        # Send Email
        # ==================================================
        send_payslip_email(payslip)

        # ==================================================
        # Mark SUCCESS
        # ==================================================
        log.status = "SUCCESS"
        log.sent_at = timezone.now()
        log.save(update_fields=["status", "sent_at"])

        # ==================================================
        # Bulk Progress Tracking (SUCCESS)
        # ==================================================
        if batch_id:
            cache.incr(f"bulk_{batch_id}_completed")

        # ==================================================
        # Real-Time WebSocket Update
        # ==================================================
        async_to_sync(channel_layer.group_send)(
            "email_dashboard",
            {
                "type": "email_update",
                "data": {
                    "status": "SUCCESS",
                    "payslip_id": payslip.id,
                    "employee": payslip.employee.user.username,
                }
            }
        )

        return f"Email sent successfully to {email_address}"

    except ObjectDoesNotExist:
        return "Payslip not found"

    except Exception as exc:

        # ==================================================
        # Log FAILURE
        # ==================================================
        try:
            log.status = "FAILED"
            log.retry_count = self.request.retries
            log.error_message = str(exc)
            log.save(update_fields=["status", "retry_count", "error_message"])
        except Exception:
            pass

        # ==================================================
        # Bulk Progress Tracking (FAILED)
        # ==================================================
        if batch_id:
            cache.incr(f"bulk_{batch_id}_failed")

        # ==================================================
        # Real-Time WebSocket Update
        # ==================================================
        async_to_sync(channel_layer.group_send)(
            "email_dashboard",
            {
                "type": "email_update",
                "data": {
                    "status": "FAILED",
                    "payslip_id": payslip_id,
                }
            }
        )

        # ==================================================
        # Retry with Exponential Backoff
        # ==================================================
        retry_delay = 2 ** self.request.retries

        raise self.retry(
            exc=exc,
            countdown=retry_delay
        )