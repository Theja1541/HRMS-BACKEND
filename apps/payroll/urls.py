from django.urls import path
from . import views
from .views import (
    set_salary,
    ctc_yearly_breakdown,
    payroll_summary,
    export_payroll_excel,
    export_payroll_pdf,
    download_payslip_pdf,
)

urlpatterns = [

    # Salary
    path("salary/set/", views.set_salary),
    path("salary/all/", views.all_salaries),
    path("salary/<int:salary_id>/update/", views.update_salary),
    path("salary/employee/<int:employee_id>/", views.get_salary_by_employee),

    # Salary Revision
    path("salary-revisions/", views.create_salary_revision),
    path("salary-revisions/employee/<int:employee_id>/", views.employee_salary_history),

    # Payslip
    path("payslip/generate/", views.generate_payslip),
    path("payslip/bulk-generate/", views.bulk_generate_payslips),
    path("payslip/bulk-approve/", views.bulk_approve_payslips),

    path("payslip/approve/<int:payslip_id>/", views.approve_payslip),
    path("payslip/mark-paid/<int:payslip_id>/", views.mark_payslip_paid),
    path("payslip/cancel/<int:payslip_id>/", views.cancel_payslip),

    path("payslip/me/", views.my_payslips),
    path("payslip/all/", views.all_payslips),
    path("payslip/pdf/<int:payslip_id>/", views.download_payslip_pdf),
    path("payslip/download-all/", views.download_all_payslips_zip),

    # Email
    path("payslip/email/single/", views.send_single_payslip_email),
    path("payslip/email/bulk/", views.bulk_email_payslips),

    # Payroll
    path("status/", views.payroll_status),
    path("reopen/", views.reopen_payroll_month),
    path("dashboard-summary/", views.payroll_dashboard_summary),

    # ============================================
    # PAYROLL REPORTS
    # ============================================

    path("reports/epf/", views.epf_report),
    path("reports/esi/", views.esi_report),
    path("reports/pt/", views.pt_report),
    path("reports/epfo-ecr/", views.epfo_ecr_file),
    path("reports/esic-upload/", views.esic_upload_file),
    path("reports/form16/", views.generate_form16),
    path("reports/neft-file/", views.generate_neft_file),
    path("reports/neft/", views.generate_neft_file),
    path("full-final/generate/", views.generate_full_final),
    path("salary/ctc-yearly/", views.ctc_yearly_breakdown),
    path("my-summary/", views.my_payroll_summary),

    # ============================================
    # PAYROLL SUMMARY
    # ============================================

    path("summary/", payroll_summary, name="payroll-summary"),
    path("export/excel/", export_payroll_excel, name="export-payroll-excel"),
    path("export/pdf/", export_payroll_pdf, name="export-payroll-pdf"),

]