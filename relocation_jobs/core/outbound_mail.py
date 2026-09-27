from __future__ import annotations

import os

import requests

from relocation_jobs.payments.nowpayments import public_base_url as panel_public_base_url

_BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def brevo_configured() -> bool:
    return bool(os.environ.get("BREVO_API_KEY", "").strip()) and bool(
        os.environ.get("BREVO_FROM_EMAIL", "").strip()
    )


def send_transactional_email(*, to: str, subject: str, text: str) -> None:
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    from_email = os.environ.get("BREVO_FROM_EMAIL", "").strip()
    if not api_key or not from_email:
        raise RuntimeError("Brevo is not configured")
    recipient = to.strip()
    if not recipient:
        raise ValueError("Recipient email is required")
    from_name = os.environ.get("BREVO_FROM_NAME", "").strip() or "Kuchup"
    response = requests.post(
        _BREVO_SEND_URL,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": api_key,
        },
        json={
            "sender": {"name": from_name, "email": from_email},
            "to": [{"email": recipient}],
            "subject": subject,
            "textContent": text,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError("Brevo send failed")


def send_panel_email_confirm(*, to: str, token: str, base_url: str) -> None:
    origin = (base_url or panel_public_base_url() or "http://127.0.0.1:5051").rstrip("/")
    link = f"{origin}/api/auth/confirm-email?token={token}"
    send_transactional_email(
        to=to,
        subject="Confirm your Kuchup account",
        text=(
            "Thanks for signing up.\n\n"
            f"Confirm your email to sign in to the panel:\n{link}\n\n"
            "This link expires in 48 hours. If you did not create an account, you can ignore this email."
        ),
    )
