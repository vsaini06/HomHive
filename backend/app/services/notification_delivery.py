"""Optional single-household demo email delivery for persisted in-app alerts."""
from __future__ import annotations

from email.message import EmailMessage
from datetime import timedelta
import logging
import os
import smtplib
import ssl
from uuid import uuid4
from sqlalchemy import select

from app.services.autonomous_lifecycle import (
    AutonomousAlertRecord, AutonomousTaskEventRecord, AutonomousTaskRecord, utcnow,
)

logger = logging.getLogger(__name__)


def email_ready(config=None):
    env = config if config is not None else os.environ
    keys = ('HOMHIVE_EMAIL_HOUSEHOLD_ID', 'HOMHIVE_EMAIL_TO', 'HOMHIVE_EMAIL_FROM',
            'HOMHIVE_SMTP_USERNAME', 'HOMHIVE_SMTP_PASSWORD')
    return env.get('HOMHIVE_EMAIL_ENABLED', '').lower() == 'true' and all(env.get(k) for k in keys)


def send_due_alerts(sessions, *, config=None, smtp_factory=None, maximum=5):
    """Explicit opt-in. Delivery event deduplicates successful sends; failures are retryable.

    Only one configured household receives email. No image content or tokens are sent.
    SMTP is at-least-once after a process crash. Use one worker for the demo.
    """
    env = config if config is not None else os.environ
    if not email_ready(env):
        return 0
    household = env['HOMHIVE_EMAIL_HOUSEHOLD_ID']
    host = env.get('HOMHIVE_SMTP_HOST', 'smtp.gmail.com')
    port = int(env.get('HOMHIVE_SMTP_PORT', '465'))
    send = smtp_factory or (lambda: smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=12))
    delivered = 0
    with sessions.begin() as db:
        alerts = db.scalars(select(AutonomousAlertRecord).where(
            AutonomousAlertRecord.household_id == household,
            AutonomousAlertRecord.created_at >= utcnow() - timedelta(hours=24),
            AutonomousAlertRecord.kind.in_(['suggestion', 'reminder', 'progress', 'completed']))
            .order_by(AutonomousAlertRecord.created_at).limit(100)
            .with_for_update(skip_locked=True)).all()
        for alert in alerts:
            if delivered >= maximum:
                break
            task = db.get(AutonomousTaskRecord, (household, alert.task_id))
            if task is None or (alert.kind in ("suggestion", "reminder")
                                and task.state in ("completed", "dismissed")):
                continue
            already = db.scalar(select(AutonomousTaskEventRecord.event_id).where(
                AutonomousTaskEventRecord.household_id == household,
                AutonomousTaskEventRecord.task_id == alert.task_id,
                AutonomousTaskEventRecord.media_id == alert.id,
                AutonomousTaskEventRecord.kind == 'email_delivery'))
            if already:
                continue
            msg = EmailMessage()
            msg['From'] = env['HOMHIVE_EMAIL_FROM']
            msg['To'] = env['HOMHIVE_EMAIL_TO']
            msg['Subject'] = 'HomHive: ' + alert.title[:150].replace('\r', ' ').replace('\n', ' ')
            msg.set_content(alert.title + '\n\n' + alert.detail + '\n\nOpen HomHive to see evidence and task status.')
            try:
                with send() as smtp:
                    smtp.login(env['HOMHIVE_SMTP_USERNAME'], env['HOMHIVE_SMTP_PASSWORD'])
                    smtp.send_message(msg)
            except (smtplib.SMTPException, OSError, TimeoutError) as exc:
                logger.warning('Optional HomHive email delivery unavailable: %s', type(exc).__name__)
                break
            db.add(AutonomousTaskEventRecord(
                event_id=str(uuid4()), household_id=household, task_id=alert.task_id,
                media_id=alert.id, kind='email_delivery',
                detail={'alert_kind': alert.kind}, created_at=utcnow()))
            delivered += 1
    return delivered
