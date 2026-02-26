from django.db import models
from apps.employees.models import Employee
from django.utils import timezone



class Salary(models.Model):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="salary"
    )
    basic = models.DecimalField(max_digits=12, decimal_places=2)
    hra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    esi_applicable = models.BooleanField(default=True)

    tax_regime = models.CharField(
    max_length=10,
    choices=[("OLD", "Old"), ("NEW", "New")],
    default="NEW"
)

    def total(self):
        return self.basic + self.hra + self.allowances

    def __str__(self):
        return f"Salary - {self.employee.employee_id}"


class Payslip(models.Model):

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("PAID", "Paid"),
        ("CANCELLED", "Cancelled"),
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="payslips"
    )

    month = models.DateField()

    # ===============================
    # SALARY STRUCTURE SNAPSHOT
    # ===============================

    basic = models.DecimalField(max_digits=12, decimal_places=2)
    hra = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2)
    fixed_deductions = models.DecimalField(max_digits=12, decimal_places=2)

    gross_salary = models.DecimalField(max_digits=12, decimal_places=2)

    # ===============================
    # ATTENDANCE IMPACT
    # ===============================

    working_days = models.IntegerField(default=0)
    absent_days = models.IntegerField(default=0)
    unpaid_leave_days = models.IntegerField(default=0)
    half_days = models.IntegerField(default=0)
    late_days = models.IntegerField(default=0)

    attendance_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    late_penalty = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ===============================
    # FINAL PAY
    # ===============================

    net_pay = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT"
    )

    generated_on = models.DateTimeField(auto_now_add=True)
    paid_on = models.DateTimeField(null=True, blank=True)

    lop_days = models.IntegerField(default=0)
    lop_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    employee_pf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_pf = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    pf_applicable = models.BooleanField(default=True)
    pf_wage_ceiling_applicable = models.BooleanField(default=True)

    employee_esi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_esi = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    professional_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    leave_encashment_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    leave_encashment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    bank_account_number = models.CharField(max_length=30, blank=True, null=True)
    bank_ifsc = models.CharField(max_length=20, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)


    class Meta:
        unique_together = ("employee", "month")
        ordering = ["-month"]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.month.strftime('%Y-%m')} - {self.status}"
    
class PayrollMonth(models.Model):

    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("PROCESSING", "Processing"),
        ("CLOSED", "Closed"),
    )

    year = models.IntegerField()
    month = models.IntegerField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="OPEN"
    )

    closed_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("year", "month")
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.year}-{self.month} ({self.status})"

class PayslipEmailLog(models.Model):

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    )

    payslip = models.ForeignKey(
        "Payslip",
        on_delete=models.CASCADE,
        related_name="email_logs"
    )

    email = models.EmailField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    retry_count = models.IntegerField(default=0)

    error_message = models.TextField(blank=True, null=True)

    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} - {self.status}"


class ProfessionalTaxSlab(models.Model):

    state = models.CharField(max_length=100)

    min_salary = models.DecimalField(max_digits=12, decimal_places=2)
    max_salary = models.DecimalField(max_digits=12, decimal_places=2)

    pt_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["min_salary"]

    def __str__(self):
        return f"{self.state} | {self.min_salary} - {self.max_salary} : {self.pt_amount}"



class FullFinalSettlement(models.Model):

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("PAID", "Paid"),
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="full_final_settlements"
    )

    last_working_date = models.DateField()

    # Earnings
    salary_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    leave_encashment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Deductions
    notice_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    final_amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FNF - {self.employee.first_name}"