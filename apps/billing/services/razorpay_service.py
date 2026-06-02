import razorpay
import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

class RazorpayService:
    """Wrapper service around Razorpay SDK APIs."""

    def __init__(self):
        self.key_id = getattr(settings, "RAZORPAY_KEY_ID", None)
        self.key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", None)

        if not self.key_id or not self.key_secret:
            logger.warning("Razorpay credentials are not fully configured in settings.")

    @property
    def client(self):
        if not self.key_id or not self.key_secret:
            raise ImproperlyConfigured("Razorpay key_id and key_secret must be set in Django settings.")
        return razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_order(self, amount_paise, currency="INR", receipt=None):
        """
        Create a new Razorpay order.
        amount_paise must be an integer (e.g. 10000 = Rs 100)
        """
        try:
            data = {
                "amount": int(amount_paise),
                "currency": currency,
                "payment_capture": 1  # Auto capture
            }
            if receipt:
                data["receipt"] = str(receipt)

            order = self.client.order.create(data=data)
            logger.info(f"Successfully created Razorpay order: {order.get('id')}")
            return order
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {str(e)}")
            raise e

    def create_razorpay_plan(self, name, price_inr, period="monthly", description=""):
        """
        Creates a new plan in Razorpay for recurring subscriptions.
        price_inr is the recurring amount to be billed.
        """
        try:
            period_val = "monthly" if period == "monthly" else "yearly"
            data = {
                "period": period_val,
                "interval": 1,
                "item": {
                    "name": name,
                    "amount": int(price_inr * 100),  # Convert to paise
                    "currency": "INR",
                    "description": description[:250] if description else f"{name} {period_val} plan"
                }
            }
            rzp_plan = self.client.plan.create(data=data)
            logger.info(f"Successfully created Razorpay plan {rzp_plan.get('id')} for {name}")
            return rzp_plan.get("id")
        except Exception as e:
            logger.error(f"Error creating Razorpay plan: {str(e)}")
            raise e

    def create_razorpay_subscription(self, plan_id, trial_days=0):
        """
        Creates a recurring subscription order in Razorpay.
        """
        try:
            import time
            data = {
                "plan_id": plan_id,
                "customer_notify": 1,
                "quantity": 1,
                "total_count": 60 if trial_days == 0 else 61,  # Number of billing cycles
            }
            if trial_days > 0:
                # start_at is end of trial
                data["start_at"] = int(time.time()) + (trial_days * 86400)

            rzp_sub = self.client.subscription.create(data=data)
            logger.info(f"Successfully created Razorpay subscription {rzp_sub.get('id')}")
            return rzp_sub
        except Exception as e:
            logger.error(f"Error creating Razorpay subscription: {str(e)}")
            raise e

    def verify_payment_signature(self, razorpay_order_id, razorpay_payment_id, razorpay_signature):
        """Verify the transaction's signature securely using HMAC SHA256."""
        try:
            params_dict = {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            }
            # verify_payment_signature raises SignatureVerificationError if invalid
            self.client.utility.verify_payment_signature(params_dict)
            logger.info(f"Razorpay signature verified successfully for order: {razorpay_order_id}")
            return True
        except razorpay.errors.SignatureVerificationError as e:
            logger.warning(f"Razorpay signature verification failed for order {razorpay_order_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error verifying signature: {str(e)}")
            return False

    def verify_subscription_signature(self, razorpay_payment_id, razorpay_subscription_id, razorpay_signature):
        """
        Verifies the signature returned by Razorpay Checkout for recurring Subscriptions.
        Uses HMAC SHA256 with the Razorpay Key Secret.
        """
        try:
            import hmac
            import hashlib
            msg = f"{razorpay_payment_id}|{razorpay_subscription_id}".encode("utf-8")
            key = self.key_secret.encode("utf-8")
            generated_signature = hmac.new(key, msg, hashlib.sha256).hexdigest()

            is_valid = hmac.compare_digest(generated_signature, razorpay_signature)
            if is_valid:
                logger.info(f"Razorpay subscription signature verified successfully for sub: {razorpay_subscription_id}")
            else:
                logger.warning(f"Razorpay subscription signature verification failed for sub: {razorpay_subscription_id}")
            return is_valid
        except Exception as e:
            logger.error(f"Unexpected error verifying subscription signature: {str(e)}")
            return False

    def verify_webhook_signature(self, body_bytes, signature_header, webhook_secret=None):
        """Verify the webhook payload's signature securely."""
        try:
            secret = webhook_secret or getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
            if not secret:
                raise ImproperlyConfigured("RAZORPAY_WEBHOOK_SECRET must be configured to verify webhooks.")
            
            # verify_webhook_signature returns None or raises SignatureVerificationError
            self.client.utility.verify_webhook_signature(
                body_bytes.decode("utf-8"),
                signature_header,
                secret
            )
            return True
        except Exception as e:
            logger.warning(f"Razorpay Webhook signature verification failed: {str(e)}")
            return False

