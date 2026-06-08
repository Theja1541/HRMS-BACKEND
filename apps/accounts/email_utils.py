import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.core.mail import get_connection

def _get_fernet():
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"hrms_smtp_salt",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
    return Fernet(key)

def encrypt_smtp_password(password: str) -> str:
    if not password:
        return ""
    f = _get_fernet()
    return f.encrypt(password.encode()).decode()

def decrypt_smtp_password(encrypted_password: str) -> str:
    if not encrypted_password:
        return ""
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_password.encode()).decode()
    except Exception:
        return ""

def get_company_email_connection(company):
    """
    Returns an SMTP connection configured for the company if they have it enabled and set up.
    Otherwise, returns the default global connection.
    """
    if company and getattr(company, 'use_company_smtp', False) and getattr(company, 'smtp_host', None):
        password = decrypt_smtp_password(company.smtp_password)
        return get_connection(
            host=company.smtp_host,
            port=company.smtp_port,
            username=company.smtp_username,
            password=password,
            use_tls=company.smtp_use_tls,
        )
    return get_connection()
