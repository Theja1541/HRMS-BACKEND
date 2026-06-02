from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock

from apps.accounts.models import Company
from apps.billing.models import SubscriptionPlan, CompanySubscription, PaymentTransaction, GSTInvoice
from apps.billing.services.subscription_service import SubscriptionService

User = get_user_model()

class SubscriptionTests(APITestCase):
    """Automated integration tests for SaaS subscriptions and payment triggers."""

    def setUp(self):
        # 1. Create a tenant company
        self.company = Company.objects.create(
            name="Alpha Corp",
            company_code="ALPHA",
            phone="9876543210",
            address="Building 1, Technopark",
            state="Maharashtra",
            state_code="27",
            is_active=True,
            billing_action_stopped=True,  # Initially locked out!
        )

        # 2. Create a company admin user
        self.admin_user = User.objects.create_user(
            username="admin@alphacorp.com",
            email="admin@alphacorp.com",
            password="SecurePassword123",
            role="ADMIN",
            company=self.company,
        )

        # 3. Create active subscription plans
        self.starter_plan = SubscriptionPlan.objects.create(
            name="Starter Plan",
            slug="starter",
            description="Perfect starter kit.",
            monthly_price=Decimal("1000.00"),
            yearly_price=Decimal("10000.00"),
            gst_percentage=Decimal("18.00"),
            employee_limit=15,
            features_json={"attendance": True, "leave": True},
            razorpay_plan_id="sub_plan_mock123",
            razorpay_plan_yearly_id="sub_plan_mock456",
            is_active=True,
        )

        # Authenticate requests
        self.client.force_authenticate(user=self.admin_user)

    def test_get_subscription_plans(self):
        """Verify public endpoints return active pricing plans."""
        # Log out to ensure it is public
        self.client.force_authenticate(user=None)
        url = reverse("get_subscription_plans")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "starter")

    @patch("apps.billing.services.razorpay_service.RazorpayService.create_razorpay_subscription")
    def test_create_order_math_and_paise(self, mock_create_subscription):
        """Verify calculations: 18% GST addition, conversion of INR total to Paise, and creation of transaction records."""
        # Mock Razorpay subscription response
        mock_create_subscription.return_value = {
            "id": "sub_mock123",
            "status": "created",
        }

        url = reverse("create_razorpay_order")
        data = {
            "plan_id": self.starter_plan.id,
            "billing_cycle": "monthly",
        }
        
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["razorpay_order_id"], "sub_mock123")
        self.assertEqual(response.data["amount"], 118000)  # Rs 1180 (1000 base + 180 GST) in Paise

        # Verify transaction saved in database
        transaction = PaymentTransaction.objects.get(razorpay_order_id="sub_mock123")
        self.assertEqual(transaction.amount, Decimal("1000.00"))
        self.assertEqual(transaction.gst_amount, Decimal("180.00"))
        self.assertEqual(transaction.total_amount, Decimal("1180.00"))
        self.assertEqual(transaction.payment_status, PaymentTransaction.STATUS_PENDING)

    @patch("apps.billing.services.razorpay_service.RazorpayService.verify_subscription_signature")
    def test_verify_payment_success_lifts_lockout(self, mock_verify_signature):
        """Verify that successful payment verification activates the subscription and lifts the tenant lockout."""
        mock_verify_signature.return_value = True

        # Precreate a pending transaction in database
        transaction = PaymentTransaction.objects.create(
            company=self.company,
            razorpay_order_id="sub_verify123",
            amount=Decimal("1000.00"),
            gst_amount=Decimal("180.00"),
            total_amount=Decimal("1180.00"),
            payment_status=PaymentTransaction.STATUS_PENDING
        )

        # Precreate pending company subscription
        CompanySubscription.objects.create(
            company=self.company,
            subscription_plan=self.starter_plan,
            billing_cycle="monthly",
            is_active=False,
            payment_status="pending",
            razorpay_subscription_id="sub_verify123"
        )

        url = reverse("verify_payment")
        data = {
            "razorpay_order_id": "sub_verify123",
            "razorpay_payment_id": "pay_mock123",
            "razorpay_signature": "sig_mock123",
            "plan_id": self.starter_plan.id,
            "billing_cycle": "monthly",
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

        # Confirm lockout lifted on Company
        self.company.refresh_from_db()
        self.assertFalse(self.company.billing_action_stopped)
        self.assertIsNotNone(self.company.subscription_period_end)

        # Confirm subscription active
        subscription = CompanySubscription.objects.get(company=self.company)
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.subscription_plan, self.starter_plan)

        # Confirm GST Invoice created
        invoice = GSTInvoice.objects.get(payment_transaction=transaction)
        self.assertEqual(invoice.total, Decimal("1180.00"))
        self.assertIsNotNone(invoice.invoice_pdf)
