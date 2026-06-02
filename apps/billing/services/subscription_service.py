from datetime import timedelta, date
from django.utils import timezone
from apps.billing.models import CompanySubscription, SubscriptionPlan
from apps.accounts.models import Company
import logging

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Manages multi-tenant subscription activation, renewal, and feature synchronization."""

    def activate_or_renew_subscription(self, company, plan, billing_cycle, start_date=None, end_date=None, trial_days=0):
        """
        Activates or renews a subscription for a tenant company.
        Updates the accounts.Company state, lifting billing suspensions.
        """
        try:
            if not start_date:
                start_date = timezone.now().date()

            # Calculate end date based on billing cycle if not provided
            if not end_date:
                if billing_cycle == "yearly":
                    end_date = start_date + timedelta(days=365)
                else:  # monthly
                    end_date = start_date + timedelta(days=30)

            # Handle Trial period if configured
            trial_start = None
            trial_end = None
            if trial_days > 0:
                trial_start = start_date
                trial_end = start_date + timedelta(days=trial_days)
                # Adjust active subscription start and end if trial is active
                start_date = trial_end
                if not end_date:
                    if billing_cycle == "yearly":
                        end_date = start_date + timedelta(days=365)
                    else:
                        end_date = start_date + timedelta(days=30)

            # Update or create the CompanySubscription
            subscription, created = CompanySubscription.objects.update_or_create(
                company=company,
                defaults={
                    "subscription_plan": plan,
                    "billing_cycle": billing_cycle,
                    "start_date": start_date,
                    "end_date": end_date,
                    "next_billing_date": end_date,
                    "is_active": True,
                    "payment_status": "paid",
                    "trial_start": trial_start,
                    "trial_end": trial_end,
                }
            )

            # Synchronize the Company tenant model immediately
            company.subscription_period_end = end_date
            company.billing_action_stopped = False

            # Update tenant allowed features/modules based on plan config
            if plan.features_json:
                # Merge with default support / settings features
                modules = dict(plan.features_json)
                modules["support"] = True
                modules["billing"] = True
                company.enabled_modules = modules
            else:
                company.enabled_modules = {
                    "attendance": True,
                    "leave": True,
                    "payroll": True,
                    "assets": True,
                    "support": True,
                    "notifications": True,
                    "billing": True,
                }

            company.save()

            logger.info(f"Successfully activated {plan.name} ({billing_cycle}) for Company: {company.name}")
            return subscription

        except Exception as e:
            logger.error(f"Failed to activate subscription for company {company.id}: {str(e)}")
            raise e

    def get_subscription_status(self, company):
        """
        Calculates subscription parameters, including active plans,
        quenched features, and remaining trial or paid days.
        """
        # Fetch the latest subscription regardless of active status to report expired/pending states properly
        subscription = CompanySubscription.objects.filter(company=company).order_by("-created_at").first()
        
        if not subscription:
            return {
                "has_active_subscription": False,
                "plan_name": "No Active Plan",
                "days_remaining": 0,
                "expired": True,
                "features": {}
            }

        today = timezone.now().date()
        
        if subscription.end_date:
            days_remaining = (subscription.end_date - today).days
            expired = today > subscription.end_date
        else:
            days_remaining = 0
            expired = True

        has_active = subscription.is_active and not expired and subscription.payment_status == "paid"

        return {
            "has_active_subscription": has_active,
            "subscription_id": subscription.id,
            "plan_name": subscription.subscription_plan.name,
            "plan_slug": subscription.subscription_plan.slug,
            "billing_cycle": subscription.billing_cycle,
            "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
            "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
            "days_remaining": max(0, days_remaining),
            "expired": expired,
            "employee_limit": subscription.subscription_plan.employee_limit,
            "features": subscription.subscription_plan.features_json,
            "trial_active": subscription.trial_end is not None and today <= subscription.trial_end,
            "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
            "payment_status": subscription.payment_status,
            "razorpay_subscription_id": subscription.razorpay_subscription_id,
            "auto_renew": subscription.auto_renew
        }
