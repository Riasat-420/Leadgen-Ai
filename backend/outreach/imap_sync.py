"""
IMAP Reply Sync Engine
Connects to the client's inbox via IMAP and checks for replies to sent outreach campaigns.
"""
import datetime
import email
from email.header import decode_header
import imaplib
from typing import Optional

from database import SessionLocal, Lead, OutreachLog, get_setting


def sync_replies() -> int:
    """
    Connect via IMAP to check for new client replies.
    Matches inbox messages against contacted leads, updates lead status,
    unschedules follow-ups, and logs the reply in OutreachLog.
    Returns the number of new replies synced.
    """
    smtp_user = get_setting("smtp_user", "")
    smtp_password = get_setting("smtp_password", "")
    imap_host = get_setting("imap_host", "")
    imap_port_str = get_setting("imap_port", "993")

    if not smtp_user or not smtp_password or not imap_host:
        print("[IMAP] IMAP credentials or host not configured. Skipping reply sync.")
        return 0

    try:
        imap_port = int(imap_port_str.strip())
    except ValueError:
        imap_port = 993

    db = SessionLocal()
    synced_count = 0
    mail = None
    try:
        print(f"[IMAP] Synchronizing: Connecting to IMAP {imap_host}:{imap_port}...")
        if imap_port == 993:
            mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        else:
            mail = imaplib.IMAP4(imap_host, imap_port)

        mail.login(smtp_user, smtp_password)
        mail.select("inbox")

        # Fetch leads that have been contacted but haven't replied
        leads_to_check = (
            db.query(Lead)
            .filter(
                Lead.email.isnot(None),
                Lead.email != "",
                Lead.status == "contacted",
                Lead.reply_received == False,
            )
            .all()
        )

        if not leads_to_check:
            print("[IMAP] No pending contacted leads to check.")
            return 0

        # Build lookup table of lowercased emails
        lead_map = {l.email.strip().lower(): l for l in leads_to_check}

        # Search for messages from the last 7 days to scan
        date_since = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%d-%b-%Y")
        status, data = mail.search(None, f'(SINCE "{date_since}")')
        
        if status != "OK" or not data or not data[0]:
            print("[IMAP] No recent messages found in inbox.")
            return 0

        mail_ids = data[0].split()
        print(f"[IMAP] Scan: Found {len(mail_ids)} recent inbox messages. Cross-referencing...")

        # Scan most recent emails first
        for mail_id in reversed(mail_ids):
            status, msg_data = mail.fetch(mail_id, "(RFC822)")
            if status != "OK":
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Parse Sender
                    from_header = msg.get("From")
                    if not from_header:
                        continue

                    from_str = str(from_header)
                    sender_email = ""
                    if "<" in from_str and ">" in from_str:
                        sender_email = from_str.split("<")[1].split(">")[0].strip().lower()
                    else:
                        sender_email = from_str.strip().lower()

                    # Match lead
                    if sender_email in lead_map:
                        lead = lead_map[sender_email]

                        # Decode Subject
                        subject_str = ""
                        subject_header = msg.get("Subject")
                        if subject_header:
                            decoded_parts = decode_header(subject_header)
                            for part, encoding in decoded_parts:
                                if isinstance(part, bytes):
                                    subject_str += part.decode(encoding or "utf-8", errors="replace")
                                else:
                                    subject_str += str(part)

                        # Extract Text Body
                        body_str = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disp = str(part.get("Content-Disposition"))
                                if content_type == "text/plain" and "attachment" not in content_disp:
                                    payload = part.get_payload(decode=True)
                                    body_str = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                                    break
                        else:
                            payload = msg.get_payload(decode=True)
                            body_str = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")

                        body_str = body_str.strip()

                        # Deduplicate log check
                        existing_log = (
                            db.query(OutreachLog)
                            .filter(
                                OutreachLog.lead_id == lead.id,
                                OutreachLog.message_type == "incoming",
                                OutreachLog.message_body == body_str,
                            )
                            .first()
                        )
                        if existing_log:
                            continue

                        # Add Incoming Log
                        log = OutreachLog(
                            lead_id=lead.id,
                            message_type="incoming",
                            message_subject=subject_str,
                            message_body=body_str,
                            status="delivered",
                            follow_up_number=0,
                            sent_at=datetime.datetime.utcnow(),
                        )
                        db.add(log)

                        # Update Lead CRM State
                        lead.reply_received = True
                        lead.reply_text = body_str
                        lead.status = "replied"
                        lead.next_followup = None  # Cancel all remaining scheduled follow-ups!
                        db.commit()
                        
                        synced_count += 1
                        print(f"[IMAP] Synced incoming reply from {lead.email}")

        if mail:
            mail.logout()
        return synced_count

    except Exception as e:
        print(f"[IMAP] Sync failure: {e}")
        return synced_count
    finally:
        db.close()
