from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from relocation_jobs.payments.nowpayments import public_base_url as panel_public_base_url


def smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST", "").strip())


def _smtp_from() -> str:
    raw = os.environ.get("SMTP_FROM", "").strip()
    if raw:
        return raw
    user = os.environ.get("SMTP_USER", "").strip()
    if user:
        return user
    return "noreply@localhost"


def send_email(*, to: str, subject: str, text: str) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        raise RuntimeError("SMTP is not configured")
    port = int(os.environ.get("SMTP_PORT", "587") or "587")
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    use_tls = os.environ.get("SMTP_USE_TLS", "1").lower() not in ("0", "false", "no")
    recipient = to.strip()
    if not recipient:
        raise ValueError("Recipient email is required")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _smtp_from()
    msg["To"] = recipient
    msg.set_content(text)
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)


def send_panel_email_confirm(*, to: str, token: str, base_url: str) -> None:
    origin = (base_url or panel_public_base_url() or "http://127.0.0.1:5051").rstrip("/")
    link = f"{origin}/api/auth/confirm-email?token={token}"
    send_email(
        to=to,
        subject="Confirm your Kuchup account",
        text=(
            "Thanks for signing up.\n\n"
            f"Confirm your email to sign in to the panel:\n{link}\n\n"
            "This link expires in 48 hours. If you did not create an account, you can ignore this email."
        ),
    )
