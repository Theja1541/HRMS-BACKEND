import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class EmailService:
    """Sends professional transactional emails to subscribers."""

    def send_subscription_invoice_email(self, transaction, pdf_content=None, pdf_filename=None):
        """
        Sends payment confirmation and attached GST Invoice PDF to company admin.
        Supports retries upon SMTP errors.
        """
        company = transaction.company
        user_email = company.users.filter(role="ADMIN").first()
        to_email = user_email.email if user_email else settings.DEFAULT_FROM_EMAIL
        
        # If company has specific phone/email or user email
        subject = f"Invoice {transaction.invoice_number} - Payment Successful!"
        
        base_amount = transaction.amount
        gst_amount = transaction.gst_amount
        total_amount = transaction.total_amount
        currency = transaction.currency
        plan_name = transaction.subscription.subscription_plan.name if transaction.subscription else "SaaS subscription"
        billing_cycle = transaction.subscription.billing_cycle if transaction.subscription else "monthly"

        # Build premium HTML template
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,Ubuntu,Cantarell,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 10px 30px rgba(15,23,42,0.08);border:1px solid #e2e8f0;">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 100%);padding:40px 32px;text-align:center;color:#ffffff;">
              <div style="font-size:48px;margin-bottom:16px;">🎉</div>
              <h1 style="margin:0;font-size:24px;font-weight:800;letter-spacing:-0.02em;">Payment Confirmed!</h1>
              <p style="margin:8px 0 0 0;color:rgba(255,255,255,0.85);font-size:14px;font-weight:500;">
                Thank you for subscribing to HRMS Enterprise SaaS
              </p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px 40px;color:#334155;">
              <p style="margin:0 0 20px 0;font-size:16px;line-height:1.6;font-weight:500;">
                Dear {company.name} Team,
              </p>
              <p style="margin:0 0 24px 0;font-size:14px;line-height:1.6;color:#475569;">
                Your payment for the <strong>{plan_name}</strong> plan ({billing_cycle}) has been successfully processed. Your multi-tenant modules are now active and all employee database lockout states have been lifted.
              </p>

              <!-- Transaction details card -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;padding:20px;margin-bottom:28px;">
                <tr>
                  <td style="font-size:13px;color:#64748b;font-weight:700;padding-bottom:12px;text-transform:uppercase;">
                    Transaction Summary
                  </td>
                </tr>
                <tr>
                  <td>
                    <table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;line-height:1.6;color:#334155;">
                      <tr>
                        <td style="padding:6px 0;color:#64748b;">Invoice Number</td>
                        <td style="padding:6px 0;text-align:right;font-weight:700;">{transaction.invoice_number}</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0;color:#64748b;">Plan Details</td>
                        <td style="padding:6px 0;text-align:right;font-weight:700;">{plan_name} ({billing_cycle})</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0;color:#64748b;">Subtotal</td>
                        <td style="padding:6px 0;text-align:right;">{currency} {base_amount:,.2f}</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0;color:#64748b;">GST (18%)</td>
                        <td style="padding:6px 0;text-align:right;">{currency} {gst_amount:,.2f}</td>
                      </tr>
                      <tr style="font-weight:700;font-size:16px;">
                        <td style="padding:12px 0 0 0;border-top:1px dashed #cbd5e1;color:#1e3a8a;">Total Charged</td>
                        <td style="padding:12px 0 0 0;border-top:1px dashed #cbd5e1;text-align:right;color:#1e3a8a;">{currency} {total_amount:,.2f}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 28px 0;font-size:14px;line-height:1.6;color:#64748b;text-align:center;">
                📎 A GST-compliant tax invoice PDF is attached to this email for your accounting records.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f8fafc;border-top:1px solid #e2e8f0;padding:24px 40px;text-align:center;color:#64748b;font-size:12px;line-height:1.6;">
              <p style="margin:0 0 4px 0;font-weight:700;">HRMS SaaS platforms</p>
              <p style="margin:0;">Sector 62, Noida, Uttar Pradesh, 201301 | support@hrmsaas.com</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
        """

        text_body = (
            f"Dear {company.name} Team,\n\n"
            f"Your payment for the {plan_name} plan ({billing_cycle}) has been successfully processed.\n\n"
            f"Transaction Details:\n"
            f"- Invoice: {transaction.invoice_number}\n"
            f"- Subtotal: {currency} {base_amount:,.2f}\n"
            f"- GST (18%): {currency} {gst_amount:,.2f}\n"
            f"- Total: {currency} {total_amount:,.2f}\n\n"
            f"A GST-compliant tax invoice PDF is attached to this email.\n\n"
            f"Regards,\n"
            f"HRMS Platform Team"
        )

        # Send with retries (up to 3 times)
        max_retries = 3
        
        from_email = settings.DEFAULT_FROM_EMAIL
        if company and getattr(company, 'use_company_smtp', False) and getattr(company, 'from_email', None):
            from_email = company.from_email
        from apps.accounts.email_utils import get_company_email_connection
        connection = get_company_email_connection(company)
        
        for attempt in range(1, max_retries + 1):
            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=from_email,
                    to=[to_email],
                    connection=connection,
                )
                msg.attach_alternative(html_body, "text/html")
                
                # Attach Invoice PDF
                if pdf_content and pdf_filename:
                    msg.attach(pdf_filename, pdf_content, "application/pdf")
                elif hasattr(transaction, "gst_invoice") and transaction.gst_invoice.invoice_pdf:
                    transaction.gst_invoice.invoice_pdf.seek(0)
                    msg.attach(
                        transaction.invoice_number + ".pdf",
                        transaction.gst_invoice.invoice_pdf.read(),
                        "application/pdf"
                    )

                msg.send(fail_silently=False)
                logger.info(f"Successfully sent invoice email on attempt {attempt} to {to_email}")
                break
            except Exception as e:
                logger.warning(f"Failed to send email on attempt {attempt}/{max_retries}: {str(e)}")
                if attempt == max_retries:
                    # Log the final failure but do not crash the transaction activation flow
                    logger.error(f"SMTP retry limit reached. Invoice email delivery failed for transaction {transaction.id}.")
