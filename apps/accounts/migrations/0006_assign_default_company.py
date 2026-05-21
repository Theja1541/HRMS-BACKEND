# Data migration: create default company and assign all existing records to it

from django.db import migrations


def assign_default_company(apps, schema_editor):
    Company = apps.get_model("accounts", "Company")
    User = apps.get_model("accounts", "User")

    default_company, _ = Company.objects.get_or_create(
        company_code="DEFAULT",
        defaults={
            "name": "Default Company",
            "email": "",
            "phone": "",
            "address": "Migrated from single-tenant installation.",
            "is_active": True,
        },
    )

    User.objects.filter(company__isnull=True).update(company=default_company)

    # Employees
    Employee = apps.get_model("employees", "Employee")
    Employee.objects.filter(company__isnull=True).update(company=default_company)

    # CustomRole, CustomDepartment
    CustomRole = apps.get_model("employees", "CustomRole")
    CustomDepartment = apps.get_model("employees", "CustomDepartment")
    CustomRole.objects.filter(company__isnull=True).update(company=default_company)
    CustomDepartment.objects.filter(company__isnull=True).update(company=default_company)

    # Attendance
    Attendance = apps.get_model("attendance", "Attendance")
    Holiday = apps.get_model("attendance", "Holiday")
    WorkCalendar = apps.get_model("attendance", "WorkCalendar")
    Shift = apps.get_model("attendance", "Shift")
    Attendance.objects.filter(company__isnull=True).update(company=default_company)
    Holiday.objects.filter(company__isnull=True).update(company=default_company)
    WorkCalendar.objects.filter(company__isnull=True).update(company=default_company)
    Shift.objects.filter(company__isnull=True).update(company=default_company)

    # Payroll
    Salary = apps.get_model("payroll", "Salary")
    Payslip = apps.get_model("payroll", "Payslip")
    PayrollMonth = apps.get_model("payroll", "PayrollMonth")
    ProfessionalTaxSlab = apps.get_model("payroll", "ProfessionalTaxSlab")
    FullFinalSettlement = apps.get_model("payroll", "FullFinalSettlement")
    SalaryRevision = apps.get_model("payroll", "SalaryRevision")
    Salary.objects.filter(company__isnull=True).update(company=default_company)
    Payslip.objects.filter(company__isnull=True).update(company=default_company)
    PayrollMonth.objects.filter(company__isnull=True).update(company=default_company)
    ProfessionalTaxSlab.objects.filter(company__isnull=True).update(company=default_company)
    FullFinalSettlement.objects.filter(company__isnull=True).update(company=default_company)
    SalaryRevision.objects.filter(company__isnull=True).update(company=default_company)

    # Leaves
    LeaveType = apps.get_model("leaves", "LeaveType")
    LeaveRequest = apps.get_model("leaves", "LeaveRequest")
    LeaveHoliday = apps.get_model("leaves", "Holiday")
    LeaveType.objects.filter(company__isnull=True).update(company=default_company)
    LeaveRequest.objects.filter(company__isnull=True).update(company=default_company)
    LeaveHoliday.objects.filter(company__isnull=True).update(company=default_company)

    # Notifications, Assets, Audit
    Notification = apps.get_model("notifications", "Notification")
    CompanyAsset = apps.get_model("assets", "CompanyAsset")
    AssetAssignment = apps.get_model("assets", "AssetAssignment")
    AssetReturnRequest = apps.get_model("assets", "AssetReturnRequest")
    AuditLog = apps.get_model("audit", "AuditLog")
    Notification.objects.filter(company__isnull=True).update(company=default_company)
    CompanyAsset.objects.filter(company__isnull=True).update(company=default_company)
    AssetAssignment.objects.filter(company__isnull=True).update(company=default_company)
    AssetReturnRequest.objects.filter(company__isnull=True).update(company=default_company)
    AuditLog.objects.filter(company__isnull=True).update(company=default_company)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_add_company_tenant"),
        ("employees", "0013_add_company_tenant"),
        ("attendance", "0013_add_company_tenant"),
        ("payroll", "0024_add_company_tenant"),
        ("leaves", "0010_add_company_tenant"),
        ("notifications", "0002_add_company_tenant"),
        ("assets", "0003_add_company_tenant"),
        ("audit", "0002_add_company_tenant"),
    ]

    operations = [
        migrations.RunPython(assign_default_company, noop),
    ]
