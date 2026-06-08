import os

def update_superadmin_views():
    filepath = r"c:\Users\Teja Darling\OneDrive\Desktop\HRMS\hrms_backend\apps\superadmin\views.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    target = """    from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "no-reply@hrms.com")

    html_content = f\"\"\"
    <div style="font-family: sans-serif; padding: 20px;">
        <h2>Login Verification</h2>
        <p>Your one-time password (OTP) is:</p>
        <h1 style="color: #2563eb; letter-spacing: 5px;">{raw_otp}</h1>
        <p>This code will expire in 10 minutes.</p>
    </div>
    \"\"\"
    text_content = f"Your login verification code is: {raw_otp}"

    _apply_smtp_to_django()
    from django.core.mail import get_connection
    with get_connection() as connection:
        msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email], connection=connection)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)"""

    replacement = """    from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "no-reply@hrms.com")
    company = getattr(user, "company", None)
    if company and company.use_company_smtp and company.from_email:
        from_email = company.from_email

    html_content = f\"\"\"
    <div style="font-family: sans-serif; padding: 20px;">
        <h2>Login Verification</h2>
        <p>Your one-time password (OTP) is:</p>
        <h1 style="color: #2563eb; letter-spacing: 5px;">{raw_otp}</h1>
        <p>This code will expire in 10 minutes.</p>
    </div>
    \"\"\"
    text_content = f"Your login verification code is: {raw_otp}"

    from apps.accounts.email_utils import get_company_email_connection
    with get_company_email_connection(company) as connection:
        msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email], connection=connection)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)"""

    if target in content:
        content = content.replace(target, replacement)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("Updated superadmin/views.py successfully.")
    else:
        print("Target not found in superadmin/views.py.")


def update_temporary_passwords():
    filepath = r"c:\Users\Teja Darling\OneDrive\Desktop\HRMS\hrms_backend\apps\accounts\services\temporary_passwords.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    target = """    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send(fail_silently=False)"""

    replacement = """    company = getattr(user, "company", None)
    from_email = settings.DEFAULT_FROM_EMAIL
    if company and getattr(company, 'use_company_smtp', False) and getattr(company, 'from_email', None):
        from_email = company.from_email
        
    from apps.accounts.email_utils import get_company_email_connection
    connection = get_company_email_connection(company)

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[user.email],
        connection=connection,
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send(fail_silently=False)"""

    if target in content:
        content = content.replace(target, replacement)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("Updated temporary_passwords.py successfully.")
    else:
        print("Target not found in temporary_passwords.py.")

def update_notifications():
    filepath = r"c:\Users\Teja Darling\OneDrive\Desktop\HRMS\hrms_backend\apps\notifications\views.py"
    if not os.path.exists(filepath):
        print("notifications/views.py not found.")
        return
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    target = """        msg = EmailMultiAlternatives(subject, text_body, from_email, [recipient.email])
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)"""

    replacement = """        company = getattr(recipient, "company", None)
        if company and getattr(company, 'use_company_smtp', False) and getattr(company, 'from_email', None):
            from_email = company.from_email
            
        from apps.accounts.email_utils import get_company_email_connection
        connection = get_company_email_connection(company)
        
        msg = EmailMultiAlternatives(subject, text_body, from_email, [recipient.email], connection=connection)
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)"""

    if target in content:
        content = content.replace(target, replacement)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("Updated notifications/views.py successfully.")
    else:
        print("Target not found in notifications/views.py.")


def update_billing_emails():
    filepath = r"c:\Users\Teja Darling\OneDrive\Desktop\HRMS\hrms_backend\apps\billing\services\email_service.py"
    if not os.path.exists(filepath):
        print("billing/services/email_service.py not found.")
        return
        
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    target = """                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=from_email,
                    to=[to_email]
                )"""

    replacement = """                company = getattr(invoice, "company", None)
                if company and getattr(company, 'use_company_smtp', False) and getattr(company, 'from_email', None):
                    from_email = company.from_email
                    
                from apps.accounts.email_utils import get_company_email_connection
                connection = get_company_email_connection(company)

                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=from_email,
                    to=[to_email],
                    connection=connection
                )"""

    if target in content:
        content = content.replace(target, replacement)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("Updated email_service.py successfully.")
    else:
        print("Target not found in email_service.py.")


if __name__ == "__main__":
    update_superadmin_views()
    update_temporary_passwords()
    update_notifications()
    update_billing_emails()
