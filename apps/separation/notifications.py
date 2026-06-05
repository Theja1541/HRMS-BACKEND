import logging

logger = logging.getLogger(__name__)

def notify_ff_draft(settlement):
    """
    Send email to settlement.employee.email with:
    - Subject: 'Your F&F Settlement is ready for review'
    - Body: breakdown of gross_amount, each deduction line with type and amount, net_amount
    - Note: Employee has 48 hours to raise a dispute before HR approves
    """
    try:
        employee_email = getattr(settlement.resignation.employee, 'email', None)
        if employee_email:
            logger.info(f"Mock sending draft F&F email to {employee_email}")
            # Actual email sending logic would go here
    except Exception as e:
        logger.error(f"Failed to send notify_ff_draft: {e}")

def notify_ff_approved(settlement):
    """
    Send email to settlement.employee.email with:
    - Subject: 'Your F&F Settlement has been approved'
    - Body: final net_amount, approved_by name, approved_at, disbursed_at (if set)
    - Attach relieving letter PDF if available
    """
    try:
        employee_email = getattr(settlement.resignation.employee, 'email', None)
        if employee_email:
            logger.info(f"Mock sending approved F&F email to {employee_email}")
            # Actual email sending logic would go here
    except Exception as e:
        logger.error(f"Failed to send notify_ff_approved: {e}")

def notify_asset_overdue(resignation, unreturned_assets):
    """
    Send alert email to:
    - HR team email address (from Django settings: HRMS_HR_EMAIL)
    - resignation.employee.reporting_manager.email
    Content: list of all UNRETURNED assets, employee name, last_working_day
    """
    try:
        employee_name = getattr(resignation.employee, 'full_name', 'Employee')
        logger.info(f"Mock sending asset overdue alert for {employee_name} with {len(unreturned_assets)} unreturned assets")
        # Actual email sending logic would go here
    except Exception as e:
        logger.error(f"Failed to send notify_asset_overdue: {e}")
