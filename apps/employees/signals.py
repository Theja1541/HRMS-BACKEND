from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.payroll.models import Salary
from .models import Employee

@receiver(post_save, sender=Employee)
def create_salary_for_employee(sender, instance, created, **kwargs):
    if created:
        try:
            Salary.objects.get_or_create(
                employee=instance,
                defaults={
                    "basic": 0,
                    "da": 0,
                    "hra": 0,
                    "conveyance": 0,
                    "medical": 0,
                    "special_allowance": 0,
                    "employee_pf": 0,
                    "professional_tax": 0,
                    "employee_esi": 0,
                    "tds": 0,
                    "medical_insurance": 0,
                    "employer_pf": 0,
                    "employer_esi": 0,
                    "gratuity": 0,
                },
            )
        except Exception as exc:
            # If DB schema is not migrated (missing columns) or other DB error occurs,
            # log and continue so employee creation does not fail.
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Could not create Salary for employee %s: %s", instance.id, exc)
