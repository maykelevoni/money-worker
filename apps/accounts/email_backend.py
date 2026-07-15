"""Django email backend that delivers through Resend's HTTP API.

Lets Django's built-in mail (e.g. password reset) go out over the same Resend
integration and API key the rest of the app already uses — no SMTP config.
Reuses apps.leads.services.email.send_email.
"""
from django.core.mail.backends.base import BaseEmailBackend

from apps.leads.services import email as resend


def _as_html(message):
    """Prefer an explicit text/html alternative; else wrap the plain body so
    line breaks survive in an email client."""
    for content, mimetype in getattr(message, "alternatives", []) or []:
        if mimetype == "text/html":
            return content
    body = (message.body or "").replace("\n", "<br>")
    return f'<div style="font-family:Arial,Helvetica,sans-serif;line-height:1.6">{body}</div>'


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent = 0
        for message in email_messages:
            html = _as_html(message)
            for recipient in message.recipients():
                try:
                    resend.send_email(to=recipient, subject=message.subject, html=html)
                    sent += 1
                except Exception:
                    if not self.fail_silently:
                        raise
        return sent
