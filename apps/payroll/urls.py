from django.urls import path
from . import views

urlpatterns = [

    # ============================================
    # SALARY MANAGEMENT
    # ============================================

    path("salary/set/", views.set_salary),
    path("salary/all/", views.all_salaries),
    path("salary/<int:salary_id>/update/", views.update_salary),
    path("salary/employee/<int:employee_id>/", views.get_salary_by_employee),

    # ============================================
    # PAYSLIP GENERATION
    # ============================================

    path("payslip/generate/", views.generate_payslip),
    path("payslip/bulk-generate/", views.bulk_generate_payslips),
    path("payslip/bulk-approve/", views.bulk_approve_payslips),

    # ============================================
    # PAYSLIP STATUS ACTIONS
    # ============================================

    path("payslip/approve/<int:payslip_id>/", views.approve_payslip),
    path("payslip/mark-paid/<int:payslip_id>/", views.mark_payslip_paid),
    path("payslip/cancel/<int:payslip_id>/", views.cancel_payslip),

    # ============================================
    # PAYSLIP VIEWS
    # ============================================

    path("payslip/me/", views.my_payslips),
    path("payslip/all/", views.all_payslips),
    path("payslip/pdf/<int:payslip_id>/", views.download_payslip_pdf),
    path("payslip/download-all/", views.download_all_payslips_zip),

    # ============================================
    # EMAIL SYSTEM
    # ============================================

    path("payslip/email/single/", views.send_single_payslip_email),
    path("payslip/email/bulk/", views.bulk_email_payslips),
    path("payslip/<int:payslip_id>/email-logs/", views.payslip_email_logs),

    path("email/dashboard/", views.email_dashboard),
    path("bulk-progress/<str:batch_id>/", views.bulk_email_progress),

    # ============================================
    # PAYROLL STATUS & CONTROL
    # ============================================

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
]