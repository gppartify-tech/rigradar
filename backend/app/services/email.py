"""Sending e-mails over SMTP.

Development: leave SMTP_HOST empty and e-mails are only written to the log, or run
Mailpit (included in docker-compose) and open http://localhost:8025 to read them.
Production: point SMTP_* at any provider (Gmail with an app password, SendGrid, ...).
"""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Notification, User

log = logging.getLogger(__name__)


def send_email(to: str, subject: str, text: str, html_body: str | None = None) -> bool:
    if not settings.smtp_host:
        log.info("E-mail (SMTP not configured) to=%s subject=%r\n%s", to, subject, text)
        return False
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    if settings.smtp_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    try:
        if settings.smtp_starttls and not settings.smtp_ssl:
            server.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password or "")
        server.send_message(msg)
    finally:
        server.quit()
    return True


def send_notification_email(db: Session, notification_id: int) -> bool:
    note = db.get(Notification, notification_id)
    if note is None or note.email_sent:
        return False
    user = db.get(User, note.user_id)
    if user is None or not user.email_notifications:
        return False
    link = f"{settings.frontend_url}{note.link or '/notifications'}"
    text = f"{note.body}\n\nView it: {link}\n\n- {settings.app_name}"
    body = f"""
    <div style="font-family:system-ui,sans-serif;max-width:520px;margin:auto;padding:24px">
      <h2 style="margin:0 0 12px;color:#1e1b4b">{html.escape(note.title)}</h2>
      <p style="font-size:15px;color:#334155;line-height:1.5">{html.escape(note.body)}</p>
      <p><a href="{html.escape(link)}" style="display:inline-block;background:#4f46e5;color:#fff;
         padding:10px 18px;border-radius:8px;text-decoration:none">View product</a></p>
      <p style="font-size:12px;color:#94a3b8">You get this e-mail because the item is on your
         {html.escape(settings.app_name)} wishlist. Turn e-mails off in your profile settings.</p>
    </div>"""
    sent = send_email(user.email, f"[{settings.app_name}] {note.title}", text, body)
    note.email_sent = sent
    return sent
