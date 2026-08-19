"""邮件发送：有 SMTP 则发信，否则打日志（开发可用）"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_mail(to: str, subject: str, body: str, *, html: Optional[str] = None) -> bool:
    if not settings.SMTP_HOST:
        logger.info(
            "mail[console] to=%s subject=%s\n%s",
            to,
            subject,
            body,
        )
        return True

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("SMTP send failed to=%s", to)
        return False
