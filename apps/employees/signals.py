from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Employee
from apps.payroll.models import Salary

@receiver(post_save, sender=Employee)
def create_salary_for_employee(sender, instance, created, **kwargs):
    if created:
        Salary.objects.create(
            employee=instance,
            basic=instance.basic_salary,
            hra=0,
            allowances=instance.allowances,
            deductions=instance.deductions,
        )
