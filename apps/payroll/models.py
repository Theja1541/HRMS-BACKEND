# from django.db import models
# from apps.employees.models import Employee
# from django.utils import timezone



# from django.db import models


# class SalaryStructure(models.Model):
#     employee = models.OneToOneField(
#         "employees.Employee",
#         on_delete=models.CASCADE,
#         related_name="salary_structure"
#     )

#     # Earnings
#     basic = models.DecimalField(max_digits=10, decimal_places=2)
#     da = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     hra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     conveyance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     medical = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     special_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

#     # Employee Deductions
#     pf_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=12)
#     esi_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
#     professional_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     tds = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     medical_insurance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

#     # Employer Contributions
#     employer_pf_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=12)
#     employer_esi_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
#     gratuity_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

#     def __str__(self):
#         return f"{self.employee} Salary Structure"

#     def total(self):
#         return self.basic + self.hra + self.allowances

#     def __str__(self):
#         return f"Salary - {self.employee.employee_id}"


# class Payslip(models.Model):

#     STATUS_CHOICES = (
#         ("DRAFT", "Draft"),
#         ("APPROVED", "Approved"),
#         ("PAID", "Paid"),
#         ("CANCELLED", "Cancelled"),
#     )

#     employee = models.ForeignKey(
#         Employee,
#         on_delete=models.CASCADE,
#         related_name="payslips"
#     )

#     month = models.DateField()

#     # ===============================
#     # SALARY STRUCTURE SNAPSHOT
#     # ===============================

#     basic = models.DecimalField(max_digits=12, decimal_places=2)
#     hra = models.DecimalField(max_digits=12, decimal_places=2)
#     allowances = models.DecimalField(max_digits=12, decimal_places=2)
#     fixed_deductions = models.DecimalField(max_digits=12, decimal_places=2)

#     gross_salary = models.DecimalField(max_digits=12, decimal_places=2)

#     # ===============================
#     # ATTENDANCE IMPACT
#     # ===============================

#     working_days = models.IntegerField(default=0)
#     absent_days = models.IntegerField(default=0)
#     unpaid_leave_days = models.IntegerField(default=0)
#     half_days = models.IntegerField(default=0)
#     late_days = models.IntegerField(default=0)

#     attendance_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     late_penalty = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     # ===============================
#     # FINAL PAY
#     # ===============================

#     net_pay = models.DecimalField(max_digits=12, decimal_places=2)

#     status = models.CharField(
#         max_length=20,
#         choices=STATUS_CHOICES,
#         default="DRAFT"
#     )

#     generated_on = models.DateTimeField(auto_now_add=True)
#     paid_on = models.DateTimeField(null=True, blank=True)

#     lop_days = models.IntegerField(default=0)
#     lop_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     employee_pf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     employer_pf = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     pf_applicable = models.BooleanField(default=True)
#     pf_wage_ceiling_applicable = models.BooleanField(default=True)

#     employee_esi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     employer_esi = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     professional_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     leave_encashment_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
#     leave_encashment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     bank_account_number = models.CharField(max_length=30, blank=True, null=True)
#     bank_ifsc = models.CharField(max_length=20, blank=True, null=True)
#     bank_name = models.CharField(max_length=100, blank=True, null=True)


#     class Meta:
#         unique_together = ("employee", "month")
#         ordering = ["-month"]

#     def __str__(self):
#         return f"{self.employee.employee_id} - {self.month.strftime('%Y-%m')} - {self.status}"
    
# class PayrollMonth(models.Model):

#     STATUS_CHOICES = (
#         ("OPEN", "Open"),
#         ("PROCESSING", "Processing"),
#         ("CLOSED", "Closed"),
#     )

#     year = models.IntegerField()
#     month = models.IntegerField()

#     status = models.CharField(
#         max_length=20,
#         choices=STATUS_CHOICES,
#         default="OPEN"
#     )

#     closed_on = models.DateTimeField(null=True, blank=True)

#     class Meta:
#         unique_together = ("year", "month")
#         ordering = ["-year", "-month"]

#     def __str__(self):
#         return f"{self.year}-{self.month} ({self.status})"

# class PayslipEmailLog(models.Model):

#     STATUS_CHOICES = (
#         ("PENDING", "Pending"),
#         ("SUCCESS", "Success"),
#         ("FAILED", "Failed"),
#     )

#     payslip = models.ForeignKey(
#         "Payslip",
#         on_delete=models.CASCADE,
#         related_name="email_logs"
#     )

#     email = models.EmailField()

#     status = models.CharField(
#         max_length=20,
#         choices=STATUS_CHOICES,
#         default="PENDING"
#     )

#     retry_count = models.IntegerField(default=0)

#     error_message = models.TextField(blank=True, null=True)

#     sent_at = models.DateTimeField(null=True, blank=True)

#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.email} - {self.status}"


# class ProfessionalTaxSlab(models.Model):

#     state = models.CharField(max_length=100)

#     min_salary = models.DecimalField(max_digits=12, decimal_places=2)
#     max_salary = models.DecimalField(max_digits=12, decimal_places=2)

#     pt_amount = models.DecimalField(max_digits=12, decimal_places=2)

#     class Meta:
#         ordering = ["min_salary"]

#     def __str__(self):
#         return f"{self.state} | {self.min_salary} - {self.max_salary} : {self.pt_amount}"



# class FullFinalSettlement(models.Model):

#     STATUS_CHOICES = (
#         ("DRAFT", "Draft"),
#         ("APPROVED", "Approved"),
#         ("PAID", "Paid"),
#     )

#     employee = models.ForeignKey(
#         Employee,
#         on_delete=models.CASCADE,
#         related_name="full_final_settlements"
#     )

#     last_working_date = models.DateField()

#     # Earnings
#     salary_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     leave_encashment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     # Deductions
#     notice_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     loan_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     final_amount = models.DecimalField(max_digits=12, decimal_places=2)

#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"FNF - {self.employee.first_name}"
    

# from django.db import models


# class PayrollRecord(models.Model):

#     STATUS_CHOICES = [
#         ("DRAFT", "Draft"),
#         ("APPROVED", "Approved"),
#         ("PAID", "Paid"),
#     ]

#     employee = models.ForeignKey(
#         "employees.Employee",
#         on_delete=models.CASCADE,
#         related_name="payroll_records"
#     )

#     year = models.IntegerField()
#     month = models.IntegerField()

#     # =============================
#     # Earnings
#     # =============================

#     basic = models.DecimalField(max_digits=12, decimal_places=2)
#     da = models.DecimalField(max_digits=12, decimal_places=2)
#     hra = models.DecimalField(max_digits=12, decimal_places=2)
#     conveyance = models.DecimalField(max_digits=12, decimal_places=2)
#     medical = models.DecimalField(max_digits=12, decimal_places=2)
#     special_allowance = models.DecimalField(max_digits=12, decimal_places=2)
#     gross_salary = models.DecimalField(max_digits=12, decimal_places=2)

#     # =============================
#     # Deductions
#     # =============================

#     employee_pf = models.DecimalField(max_digits=12, decimal_places=2)
#     professional_tax = models.DecimalField(max_digits=12, decimal_places=2)
#     employee_esi = models.DecimalField(max_digits=12, decimal_places=2)
#     tds = models.DecimalField(max_digits=12, decimal_places=2)
#     medical_insurance = models.DecimalField(max_digits=12, decimal_places=2)
#     attendance_deduction = models.DecimalField(max_digits=12, decimal_places=2)
#     total_deductions = models.DecimalField(max_digits=12, decimal_places=2)

#     # =============================
#     # Net Salary
#     # =============================

#     net_salary = models.DecimalField(max_digits=12, decimal_places=2)

#     # =============================
#     # Employer Contributions
#     # =============================

#     employer_pf = models.DecimalField(max_digits=12, decimal_places=2)
#     employer_esi = models.DecimalField(max_digits=12, decimal_places=2)
#     gratuity = models.DecimalField(max_digits=12, decimal_places=2)
#     total_additional_benefits = models.DecimalField(max_digits=12, decimal_places=2)

#     # =============================
#     # Final CTC
#     # =============================

#     ctc = models.DecimalField(max_digits=12, decimal_places=2)

#     status = models.CharField(
#         max_length=20,
#         choices=STATUS_CHOICES,
#         default="DRAFT"
#     )

#     generated_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         unique_together = ("employee", "year", "month")
#         ordering = ["-year", "-month"]

#     def __str__(self):
#         return f"{self.employee} - {self.month}/{self.year}"


from django.db import models
from decimal import Decimal
from apps.employees.models import Employee

# ============================================================
# SALARY STRUCTURE (Multi Component)
# ============================================================

class Salary(models.Model):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="salary"
    )

    # ================= A - EARNINGS =================
    basic = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    da = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conveyance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    medical = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    special_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ================= B - DEDUCTIONS =================
    employee_pf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    professional_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employee_esi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tds = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    medical_insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ================= C - EMPLOYER =================
    employer_pf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_esi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gratuity = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    additional_benefits = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ctc = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def calculate_totals(self):

        def to_decimal(value):
            if value in [None, "", "null"]:
                return Decimal("0")
            return Decimal(str(value))

        # earnings
        basic = to_decimal(self.basic)
        da = to_decimal(self.da)
        hra = to_decimal(self.hra)
        conveyance = to_decimal(self.conveyance)
        medical = to_decimal(self.medical)
        special_allowance = to_decimal(self.special_allowance)

        # deductions
        employee_pf = to_decimal(self.employee_pf)
        professional_tax = to_decimal(self.professional_tax)
        employee_esi = to_decimal(self.employee_esi)
        tds = to_decimal(self.tds)
        medical_insurance = to_decimal(self.medical_insurance)

        # benefits
        employer_pf = to_decimal(self.employer_pf)
        employer_esi = to_decimal(self.employer_esi)
        gratuity = to_decimal(self.gratuity)

        self.gross_salary = (
            basic + da + hra + conveyance + medical + special_allowance
        )

        self.total_deductions = (
            employee_pf + professional_tax + employee_esi + tds + medical_insurance
        )

        self.net_salary = self.gross_salary - self.total_deductions

        self.ctc = self.gross_salary + employer_pf + employer_esi + gratuity

    def save(self, *args, **kwargs):
        self.calculate_totals()
        super().save(*args, **kwargs)


# ============================================================
# PAYSLIP
# ============================================================

class Payslip(models.Model):

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("PAID", "Paid"),
        ("CANCELLED", "Cancelled"),
    ]

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="payslips"
    )

    month = models.DateField()

    # ================= EARNINGS SNAPSHOT =================

    basic = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    da = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conveyance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    medical = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    medical_insurance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ================= ATTENDANCE =================

    lop_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    lop_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ================= STATUTORY =================

    employee_pf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_pf = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    employee_esi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_esi = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    professional_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    fixed_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    paid_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("employee", "month")
        ordering = ["-month"]

    def __str__(self):
        return f"{self.employee.first_name} - {self.month.strftime('%B %Y')}"
    


class PayslipEmailLog(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    )

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE)
    email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payslip.employee} - {self.status}"
    
class PayrollMonth(models.Model):
    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("CLOSED", "Closed"),
    )

    year = models.IntegerField()
    month = models.IntegerField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="OPEN"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("year", "month")

    def __str__(self):
        return f"{self.month}/{self.year} - {self.status}"


class ProfessionalTaxSlab(models.Model):
    state = models.CharField(max_length=100)

    min_salary = models.DecimalField(max_digits=12, decimal_places=2)
    max_salary = models.DecimalField(max_digits=12, decimal_places=2)

    pt_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.state} - {self.min_salary} to {self.max_salary}"
    

class FullFinalSettlement(models.Model):

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("PAID", "Paid"),
    )

    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE)

    last_working_date = models.DateField()

    salary_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    leave_encashment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    notice_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    final_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee} - Full & Final"
    

class SalaryRevision(models.Model):

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="salary_history"
    )

    effective_from = models.DateField()

    reason = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Salary components
    basic = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    da = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conveyance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    employee_pf = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    professional_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employee_esi = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tds = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_insurance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    employer_pf = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employer_esi = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gratuity = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        return f"{self.employee} - {self.effective_from}"