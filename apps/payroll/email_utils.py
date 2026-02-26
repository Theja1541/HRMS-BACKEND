from django.core.mail import EmailMessage
from django.conf import settings
from .utils_pdf import generate_payslip_pdf_buffer


def send_payslip_email(payslip):

    pdf_buffer = generate_payslip_pdf_buffer(payslip)

    subject = f"Payslip - {payslip.month}"
    message = f"""
Dear {payslip.employee.user.username},

Please find attached your payslip for {payslip.month}.

Net Pay: ₹ {payslip.net_pay}

Regards,
HR Department
"""

    email = EmailMessage(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [payslip.employee.user.email],
    )

    email.attach(
        f"Payslip_{payslip.month}.pdf",
        pdf_buffer.getvalue(),
        "application/pdf",
    )

    email.send(fail_silently=False)
