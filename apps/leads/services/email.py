"""Resend client — delivers the lead magnet and nurture emails."""
import requests
from django.conf import settings

API_URL = "https://api.resend.com/emails"


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.RESEND_API_KEY and settings.RESEND_FROM_EMAIL)


def send_email(to: str, subject: str, html: str) -> dict:
    """Send a single email via Resend. Returns the API response JSON."""
    if not is_configured():
        raise NotConfigured("Set RESEND_API_KEY and RESEND_FROM_EMAIL in your .env")

    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to],
            "subject": subject,
            "html": html,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
