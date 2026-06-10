import pytest
from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.separation.models import ResignationRequest

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def hr_user(db):
    return User.objects.create_user(username="hr_admin", password="password", role="HR_ADMIN")

@pytest.fixture
def finance_user(db):
    return User.objects.create_user(username="finance", password="password", role="FINANCE")

@pytest.fixture
def employee_user(db):
    return User.objects.create_user(username="emp_user", password="password", role="EMPLOYEE")

@pytest.fixture
def company(db):
    from apps.accounts.models import Company
    return Company.objects.create(name="Test Company")

@pytest.fixture
def employee(db, employee_user, company):
    return Employee.objects.create(
        user=employee_user,
        full_name="John Doe",
        employee_id="E001",
        gross_salary=Decimal("104000.00"),
        basic_salary=Decimal("50000.00"),
        date_of_joining=date(2020, 1, 1),
        employment_type="FULL_TIME",
        notice_period_days=30
    )

@pytest.fixture
def resignation_request(db, employee, company):
    return ResignationRequest.objects.create(
        company=company,
        employee=employee,
        status="CLEARANCE_PENDING",
        separation_type="RESIGNATION",
        notice_period_days=30,
        resignation_date=date(2023, 1, 1),
        last_working_day=date(2023, 1, 21)  # 20 days notice -> 10 days shortfall
    )

@pytest.mark.django_db
class TestFFSettlementAPI:
    URL = "/api/separation/settlements/generate/"

    def test_hr_admin_can_generate(self, api_client, hr_user, resignation_request):
        api_client.force_authenticate(user=hr_user)
        response = api_client.post(self.URL, {"resignation_request_id": resignation_request.id})
        
        assert response.status_code == 201
        assert "deductions" in response.data
        assert len(response.data["deductions"]) == 1

    def test_finance_can_generate(self, api_client, finance_user, resignation_request):
        api_client.force_authenticate(user=finance_user)
        response = api_client.post(self.URL, {"resignation_request_id": resignation_request.id})
        
        assert response.status_code == 201

    def test_employee_role_forbidden(self, api_client, employee_user, resignation_request):
        api_client.force_authenticate(user=employee_user)
        response = api_client.post(self.URL, {"resignation_request_id": resignation_request.id})
        
        assert response.status_code == 403

    def test_unauthenticated_forbidden(self, api_client, resignation_request):
        response = api_client.post(self.URL, {"resignation_request_id": resignation_request.id})
        
        assert response.status_code == 401

    def test_missing_body_field(self, api_client, hr_user):
        api_client.force_authenticate(user=hr_user)
        response = api_client.post(self.URL, {})
        
        assert response.status_code == 400
        assert "required" in str(response.data.get("detail", "")).lower()

    def test_wrong_status_400(self, api_client, hr_user, resignation_request):
        resignation_request.status = "SUBMITTED"
        resignation_request.save()
        
        api_client.force_authenticate(user=hr_user)
        response = api_client.post(self.URL, {"resignation_request_id": resignation_request.id})
        
        assert response.status_code == 400
        assert "CLEARANCE_PENDING" in str(response.data)

    def test_double_call_400(self, api_client, hr_user, resignation_request):
        api_client.force_authenticate(user=hr_user)
        api_client.post(self.URL, {"resignation_request_id": resignation_request.id})
        
        response = api_client.post(self.URL, {"resignation_request_id": resignation_request.id})
        assert response.status_code == 400
        assert "already exists" in str(response.data)

    def test_response_shape(self, api_client, hr_user, resignation_request):
        api_client.force_authenticate(user=hr_user)
        response = api_client.post(self.URL, {"resignation_request_id": resignation_request.id})
        
        assert response.status_code == 201
        
        expected_keys = {
            "id", "resignation_request_id", "total_earnings", "total_deductions", 
            "net_amount", "status", "notice_period_shortfall_days", 
            "notice_shortfall_snapshot", "deductions"
        }
        actual_keys = set(response.data.keys())
        
        assert expected_keys.issubset(actual_keys)
