import pytest
from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

# Adjust imports based on the project structure
from apps.employees.models import Employee
from apps.separation.models import ResignationRequest, FinalSettlement, FinalSettlementDeduction
from apps.separation.services.ff_settlement_service import FFSettlementService

User = get_user_model()

@pytest.fixture
def hr_user(db):
    return User.objects.create_user(username="hr_admin", password="password", role="HR_ADMIN")

@pytest.fixture
def company(db):
    from apps.accounts.models import Company
    return Company.objects.create(name="Test Company")

@pytest.fixture
def employee(db, company):
    user = User.objects.create_user(username="emp_user", password="password", role="EMPLOYEE")
    return Employee.objects.create(
        user=user,
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
    # Added company since it's a required field in ResignationRequest model from earlier view
    return ResignationRequest.objects.create(
        company=company,
        employee=employee,
        status="CLEARANCE_PENDING",
        separation_type="RESIGNATION",
        notice_period_days=30,
        resignation_date=date(2023, 1, 1),
        last_working_day=date(2023, 1, 31)
    )

@pytest.mark.django_db
class TestFFSettlementService:
    
    def test_full_notice_served_no_deduction(self, resignation_request, hr_user):
        settlement = FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
        
        assert settlement.notice_period_shortfall_days == 0
        assert settlement.notice_shortfall_snapshot.get("applied") is False
        assert FinalSettlementDeduction.objects.filter(settlement=settlement).count() == 0

    def test_excess_notice_no_deduction(self, resignation_request, hr_user):
        resignation_request.last_working_day = date(2023, 2, 15)  # 45 days
        resignation_request.save()
        
        settlement = FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
        
        assert settlement.notice_period_shortfall_days == 0
        assert settlement.notice_shortfall_snapshot.get("applied") is False
        assert settlement.deductions.count() == 0

    def test_shortfall_10_days_correct_amount(self, resignation_request, hr_user):
        resignation_request.last_working_day = date(2023, 1, 21)  # 20 days notice given
        resignation_request.save()
        
        settlement = FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
        
        assert settlement.notice_period_shortfall_days == 10
        assert settlement.notice_shortfall_snapshot.get("applied") is True
        
        deductions = settlement.deductions.all()
        assert len(deductions) == 1
        assert deductions[0].amount == Decimal("40000.00")
        assert settlement.total_deductions == Decimal("40000.00")

    def test_termination_skips_shortfall(self, resignation_request, hr_user):
        resignation_request.separation_type = "TERMINATION"
        resignation_request.last_working_day = date(2023, 1, 5)  # 4 days
        resignation_request.save()
        
        settlement = FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
        
        assert settlement.notice_shortfall_snapshot == {}
        assert settlement.notice_period_shortfall_days == 0
        assert settlement.deductions.count() == 0

    def test_retirement_skips_shortfall(self, resignation_request, hr_user):
        resignation_request.separation_type = "RETIREMENT"
        resignation_request.last_working_day = date(2023, 1, 5)
        resignation_request.save()
        
        settlement = FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
        
        assert settlement.notice_shortfall_snapshot == {}
        assert settlement.notice_period_shortfall_days == 0
        assert settlement.deductions.count() == 0

    def test_idempotency_raises_on_second_call(self, resignation_request, hr_user):
        FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
        
        with pytest.raises(ValidationError) as exc_info:
            FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
            
        assert "already exists" in str(exc_info.value)
        assert FinalSettlement.objects.filter(resignation=resignation_request).count() == 1

    def test_wrong_status_raises(self, resignation_request, hr_user):
        resignation_request.status = "SUBMITTED"
        resignation_request.save()
        
        with pytest.raises(ValidationError) as exc_info:
            FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
            
        assert "CLEARANCE_PENDING" in str(exc_info.value)

    def test_nonexistent_id_raises(self, hr_user):
        with pytest.raises(ValidationError) as exc_info:
            FFSettlementService.generate_ff_settlement(99999, hr_user)
            
        assert "not found" in str(exc_info.value).lower()

    def test_decimal_precision_non_round_salary(self, employee, resignation_request, hr_user):
        employee.gross_salary = Decimal("100000.00")
        employee.save()
        
        resignation_request.last_working_day = date(2023, 1, 11)  # 10 days served, 20 days shortfall
        resignation_request.save()
        
        settlement = FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
        
        snapshot = settlement.notice_shortfall_snapshot
        assert snapshot["daily_rate"] == "3846.15"
        assert snapshot["deduction_amount"] == "76923.08"
        assert settlement.total_deductions == Decimal("76923.08")

    def test_snapshot_immutable_after_creation(self, resignation_request, hr_user):
        resignation_request.last_working_day = date(2023, 1, 21)  # 20 days notice served, 10 days shortfall
        resignation_request.save()
        
        settlement = FFSettlementService.generate_ff_settlement(resignation_request.id, hr_user)
        original_snapshot = settlement.notice_shortfall_snapshot.copy()
        
        assert original_snapshot["shortfall_days"] == 10
        
        # Change LWD to 30 days (0 shortfall)
        resignation_request.last_working_day = date(2023, 1, 31)
        resignation_request.save()
        
        # Refresh settlement from DB
        settlement.refresh_from_db()
        assert settlement.notice_shortfall_snapshot == original_snapshot
