from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError

class Project(models.Model):
    BILLING_TYPE_CHOICES = (
        ('Quarterly Price', 'Quarterly Price'),
        ('Fixed Price', 'Fixed Price'),
        ('Monthly Price', 'Monthly Price'),
    )

    PAYMENT_TERMS_CHOICES = (
        ('Monthly', 'Monthly'),
        ('Quarterly', 'Quarterly'),
        ('Milestone Based', 'Milestone Based'),
    )

    STATUS_CHOICES = (
        ('Not Started', 'Not Started'),
        ('In Progress', 'In Progress'),
        ('On Hold', 'On Hold'),
        ('Completed', 'Completed'),
    )

    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    )

    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='projects')
    # Using simple CharField for department_id since the main Employee model uses a CharField for department.
    # If a real CustomDepartment FK is needed we would use `apps.accounts.models.CustomDepartment`, 
    # but since the prompt specified it as BIGINT FK, I will use a generic IntegerField or FK to CustomDepartment if it existed.
    # Actually, in apps/employees/models.py `department` is a CharField. So let's just make it CharField or FK to CustomDepartment.
    # Let's use CharField to match Employee.department for simplicity, unless the user strictly meant BIGINT FK to a departments table.
    department_id = models.BigIntegerField(null=True, blank=True)
    
    project_code = models.CharField(max_length=50)
    project_name = models.CharField(max_length=255)
    project_description = models.TextField(blank=True, null=True)
    
    client_name = models.CharField(max_length=255, blank=True, null=True)
    client_contact_person = models.CharField(max_length=255, blank=True, null=True)
    client_email = models.CharField(max_length=255, blank=True, null=True)
    client_phone = models.CharField(max_length=20, blank=True, null=True)
    
    sales_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_projects'
    )
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_projects'
    )
    
    project_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    billing_type = models.CharField(max_length=50, choices=BILLING_TYPE_CHOICES, blank=True, null=True)
    payment_terms = models.CharField(max_length=50, choices=PAYMENT_TERMS_CHOICES, blank=True, null=True)
    
    start_date = models.DateField(blank=True, null=True)
    planned_end_date = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    
    project_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Not Started')
    priority = models.CharField(max_length=50, choices=PRIORITY_CHOICES, default='Medium')
    
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    actual_completion_date = models.DateField(null=True, blank=True)
    active_status = models.BooleanField(default=True)
    remarks = models.TextField(blank=True, null=True)
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_projects'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_projects'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'projects'
        constraints = [
            models.UniqueConstraint(fields=['company', 'project_code'], name='unique_company_project_code')
        ]
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['project_code']),
            models.Index(fields=['project_manager']),
            models.Index(fields=['project_status']),
            models.Index(fields=['active_status']),
            models.Index(fields=['planned_end_date']),
        ]

    def __str__(self):
        return f"[{self.project_code}] {self.project_name}"

class ProjectAssignment(models.Model):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='project_assignments')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='project_assignments')
    
    project_role = models.CharField(max_length=100)
    assigned_date = models.DateField(default=timezone.now)
    hours_planned = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    hours_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    assignment_status = models.CharField(max_length=50, default='Active')
    released_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_assignments'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_assignments'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project_assignments'
        constraints = [
            models.UniqueConstraint(fields=['project', 'employee'], name='unique_project_employee')
        ]
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['project']),
            models.Index(fields=['employee']),
        ]

    def clean(self):
        super().clean()
        if hasattr(self, 'project') and hasattr(self, 'employee'):
            # Fetch the employee's user's company or a custom multi-tenant logic for employees
            employee_company_id = None
            if self.employee.user and self.employee.user.company_id:
                employee_company_id = self.employee.user.company_id
            
            if employee_company_id and self.project.company_id != employee_company_id:
                raise ValidationError("Employee cannot be assigned to another company's project.")

    def __str__(self):
        return f"{self.employee.employee_id} - {self.project.project_code}"
