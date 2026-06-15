import smtplib
import threading
from email.message import EmailMessage

from config import Config


def email_delivery_config_error():
    if not Config.EMAIL_ENABLED:
        return "EMAIL_ENABLED is false"

    missing = [
        name
        for name, value in {
            "SMTP_HOST": Config.SMTP_HOST,
            "SMTP_USERNAME": Config.SMTP_USERNAME,
            "SMTP_PASSWORD": Config.SMTP_PASSWORD,
            "EMAIL_FROM": Config.EMAIL_FROM,
        }.items()
        if not value
    ]
    if missing:
        return f"Missing email configuration: {', '.join(missing)}"

    return None


def is_email_delivery_configured():
    return email_delivery_config_error() is None


def _send_email_sync(to_email: str, subject: str, text_body: str):
    """Internal function that actually sends the email (blocking)."""
    msg = EmailMessage()
    msg["From"] = Config.EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body)

    try:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15) as server:
            if Config.SMTP_USE_TLS:
                server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            server.send_message(msg)
        print(f"Email sent successfully to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {str(e)}")


def send_email(*, to_email: str, subject: str, text_body: str):
    """Non-blocking email send - runs in background thread."""
    config_error = email_delivery_config_error()
    if config_error:
        return False, config_error

    thread = threading.Thread(
        target=_send_email_sync,
        args=(to_email, subject, text_body),
        daemon=True,
    )
    thread.start()

    return True, None


def send_verification_email(*, to_email: str, verification_link: str):
    subject = "Verify your Agri Guide account"
    text_body = (
        "Welcome to Agri Guide!\n\n"
        "Please verify your email address by clicking the link below:\n\n"
        f"{verification_link}\n\n"
        "If you did not create an account, you can ignore this email.\n"
    )
    return send_email(to_email=to_email, subject=subject, text_body=text_body)
