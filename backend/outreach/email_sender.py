"""
Email Outreach Engine
Sends cold emails and automated follow-up sequences via Gmail SMTP.
Injects tracking pixel and tracked links for open/click analytics.
Uses APScheduler to automatically send follow-ups on schedule.
"""
import datetime
import re
import smtplib
import ssl
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from urllib.parse import quote_plus

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    GMAIL_USER, GMAIL_APP_PASSWORD, SENDER_NAME,
    MAX_EMAILS_PER_DAY, FOLLOWUP_DAY_1, FOLLOWUP_DAY_2,
    TRACKING_BASE_URL,
)
from database import SessionLocal, Lead, OutreachLog, get_setting


def _wrap_links_with_tracking(html_body: str, tracking_id: str) -> str:
    """Replace all <a href> links with tracked redirect URLs."""
    def replace_link(match):
        original_url = match.group(1)
        if "localhost" in original_url or "track" in original_url:
            return match.group(0)  # Don't double-wrap tracking links
        encoded = quote_plus(original_url)
        tracked = f"{TRACKING_BASE_URL}/api/track/click/{tracking_id}?url={encoded}"
        return f'href="{tracked}"'
    return re.sub(r'href="(https?://[^"]+)"', replace_link, html_body)


def _build_mime_email(
    to_email: str,
    subject: str,
    body: str,
    tracking_id: str,
    from_email: str,
    from_name: str,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{from_name} <{from_email}>"
    msg["To"]      = to_email

    # Plain text part
    text_part = MIMEText(body, "plain", "utf-8")

    # HTML part with tracking pixel + tracked links
    html_body = body.replace("\n", "<br>")
    html_body = _wrap_links_with_tracking(html_body, tracking_id)

    pixel_url = f"{TRACKING_BASE_URL}/api/track/open/{tracking_id}"

    html_part = MIMEText(
        f"""<html><body style="font-family:Arial,sans-serif;font-size:15px;color:#222;max-width:600px;margin:auto;">
<p>{html_body}</p>
<hr style="border:none;border-top:1px solid #eee;margin-top:30px;">
<p style="font-size:12px;color:#888;">
To unsubscribe, reply with "unsubscribe" in the subject line.
</p>
<!-- Tracking pixel -->
<img src="{pixel_url}" width="1" height="1" alt="" style="display:none;" />
</body></html>""",
        "html",
        "utf-8",
    )

    msg.attach(text_part)
    msg.attach(html_part)
    return msg


def send_email(
    to_email: str,
    subject: str,
    body: str,
    lead_id: int,
    follow_up_number: int = 0,
) -> bool:
    """
    Send an email via Gmail SMTP or Custom SMTP settings.
    Logs result to OutreachLog table.
    Returns True on success.
    """
    smtp_host = get_setting("smtp_host", "smtp.gmail.com")
    
    # Port default logic
    encryption = get_setting("smtp_encryption", "ssl")
    default_port = "465" if encryption == "ssl" else "587"
    smtp_port_str = get_setting("smtp_port", default_port)
    smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else (465 if encryption == "ssl" else 587)
    
    smtp_user = get_setting("smtp_user", GMAIL_USER)
    smtp_password = get_setting("smtp_password", GMAIL_APP_PASSWORD)
    smtp_sender_name = get_setting("smtp_sender_name", SENDER_NAME)

    if not smtp_user or not smtp_password:
        print("[Email] SMTP credentials not configured (neither database settings nor .env)")
        return False

    db = SessionLocal()
    try:
        # Generate unique tracking ID for this email
        tracking_id = uuid.uuid4().hex

        msg = _build_mime_email(to_email, subject, body, tracking_id, smtp_user, smtp_sender_name)

        # Connection and delivery
        if encryption == "ssl":
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15, context=ctx) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, to_email, msg.as_string())
        elif encryption == "starttls":
            ctx = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, to_email, msg.as_string())

        # Log success with tracking ID
        log = OutreachLog(
            lead_id=lead_id,
            message_type="email",
            message_subject=subject,
            message_body=body,
            status="sent",
            follow_up_number=follow_up_number,
            tracking_id=tracking_id,
            email_opened=False,
            open_count=0,
            link_clicked=False,
        )
        db.add(log)

        # Update lead
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.emails_sent    = (lead.emails_sent or 0) + 1
            lead.last_contacted = datetime.datetime.utcnow()
            lead.status         = "contacted"

            # Schedule follow-ups
            if follow_up_number == 0:
                lead.next_followup = datetime.datetime.utcnow() + datetime.timedelta(days=FOLLOWUP_DAY_1)
            elif follow_up_number == 1:
                lead.next_followup = datetime.datetime.utcnow() + datetime.timedelta(days=FOLLOWUP_DAY_2)
            else:
                lead.next_followup = None

        db.commit()
        print(f"[Email] OK: Sent to {to_email} (follow-up #{follow_up_number})")
        return True

    except smtplib.SMTPAuthenticationError:
        print("[Email] ERROR: Gmail authentication failed -- check App Password")
        _log_failure(db, lead_id, subject, body, follow_up_number, "auth_error")
        return False
    except Exception as e:
        print(f"[Email] ERROR: Error sending to {to_email}: {e}")
        _log_failure(db, lead_id, subject, body, follow_up_number, str(e))
        return False
    finally:
        db.close()


def _log_failure(db, lead_id, subject, body, follow_up_number, error):
    try:
        log = OutreachLog(
            lead_id=lead_id,
            message_type="email",
            message_subject=subject,
            message_body=body,
            status=f"failed:{error}",
            follow_up_number=follow_up_number,
        )
        db.add(log)
        db.commit()
    except Exception:
        pass


# ── Daily Email Limit Check ────────────────────────────────

def emails_sent_today() -> int:
    """Count emails sent today."""
    db = SessionLocal()
    try:
        today = datetime.datetime.utcnow().date()
        start = datetime.datetime(today.year, today.month, today.day)
        count = (
            db.query(OutreachLog)
            .filter(
                OutreachLog.message_type == "email",
                OutreachLog.status == "sent",
                OutreachLog.sent_at >= start,
            )
            .count()
        )
        return count
    finally:
        db.close()


def can_send_email() -> bool:
    return emails_sent_today() < MAX_EMAILS_PER_DAY


# ── Automated Follow-up Scheduler ─────────────────────────

def _run_follow_ups():
    """
    APScheduler job: runs every hour.
    First checks IMAP for any replies to avoid sending follow-ups to responded leads.
    Then finds leads whose follow-up date has passed and sends the next message.
    """
    try:
        from outreach.imap_sync import sync_replies
        print("[Scheduler] Pre-Scheduler Sync: Syncing IMAP inbox replies...")
        synced = sync_replies()
        print(f"[Scheduler] Pre-Scheduler Sync completed. Synced {synced} replies.")
    except Exception as e:
        print(f"[Scheduler] Pre-Scheduler Sync error: {e}")

    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        due_leads = (
            db.query(Lead)
            .filter(
                Lead.next_followup <= now,
                Lead.next_followup.isnot(None),
                Lead.reply_received == False,
                Lead.email.isnot(None),
                Lead.status == "contacted",
            )
            .all()
        )

        for lead in due_leads:
            if not can_send_email():
                print("[Scheduler] Daily email limit reached, pausing follow-ups")
                break

            emails_sent = lead.emails_sent or 0
            follow_up_number = emails_sent  # 1 = first follow-up, 2 = second

            if follow_up_number == 1 and lead.followup_1:
                subject = f"Re: {lead.cold_email_subject or 'My previous email'}"
                body    = lead.followup_1
            elif follow_up_number == 2 and lead.followup_2:
                subject = f"Re: {lead.cold_email_subject or 'Final follow-up'}"
                body    = lead.followup_2
            else:
                # No more follow-ups
                lead.next_followup = None
                lead.status = "follow_up_complete"
                db.commit()
                continue

            success = send_email(lead.email, subject, body, lead.id, follow_up_number)
            if not success:
                # Retry tomorrow
                lead.next_followup = now + datetime.timedelta(days=1)
                db.commit()

    except Exception as e:
        print(f"[Scheduler] Follow-up job error: {e}")
    finally:
        db.close()


# ── Scheduler Setup ────────────────────────────────────────

_scheduler: Optional[BackgroundScheduler] = None

def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_follow_ups,
        trigger=IntervalTrigger(hours=1),
        id="followup_job",
        replace_existing=True,
    )
    _scheduler.start()
    print("[Scheduler] Follow-up scheduler started (runs hourly)")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[Scheduler] Stopped")
