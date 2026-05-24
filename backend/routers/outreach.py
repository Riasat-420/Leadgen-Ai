"""
Outreach Router — Send emails, track replies, manage follow-ups.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db, Lead, OutreachLog
from outreach.email_sender import send_email, can_send_email, emails_sent_today

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


class SendEmailRequest(BaseModel):
    lead_id: int
    to_email: str
    subject: Optional[str] = None
    body: Optional[str] = None
    follow_up_number: int = 0


class ReplyUpdate(BaseModel):
    reply_text: str


@router.post("/send-email")
def send_email_endpoint(req: SendEmailRequest, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == req.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not can_send_email():
        raise HTTPException(
            status_code=429,
            detail=f"Daily email limit reached ({emails_sent_today()} sent today)"
        )

    # Use provided subject/body or fall back to generated messages
    subject = req.subject or lead.cold_email_subject or f"Quick question about {lead.business_name}"
    body    = req.body or lead.cold_email_body or ""

    if not body:
        raise HTTPException(status_code=400, detail="No message body — generate messages first")

    to_email = req.to_email or lead.email
    if not to_email:
        raise HTTPException(status_code=400, detail="No email address for this lead")

    success = send_email(to_email, subject, body, req.lead_id, req.follow_up_number)
    db.refresh(lead)

    return {
        "success": success,
        "emails_sent_today": emails_sent_today(),
        "lead_status": lead.status,
    }


@router.post("/{lead_id}/reply")
def mark_reply(lead_id: int, update: ReplyUpdate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.reply_received = True
    lead.reply_text     = update.reply_text
    lead.next_followup  = None
    lead.status         = "replied"
    db.commit()
    return {"message": "Reply recorded", "lead_id": lead_id}


@router.get("/logs")
def get_outreach_logs(
    db: Session = Depends(get_db),
    lead_id: Optional[int] = None,
    limit: int = 50,
):
    q = db.query(OutreachLog)
    if lead_id:
        q = q.filter(OutreachLog.lead_id == lead_id)
    logs = q.order_by(OutreachLog.sent_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "lead_id": l.lead_id,
            "message_type": l.message_type,
            "message_subject": l.message_subject,
            "sent_at": l.sent_at.isoformat() if l.sent_at else None,
            "status": l.status,
            "follow_up_number": l.follow_up_number,
        }
        for l in logs
    ]


@router.get("/stats")
def outreach_stats(db: Session = Depends(get_db)):
    total_sent = db.query(OutreachLog).filter(OutreachLog.status == "sent").count()
    failed     = db.query(OutreachLog).filter(OutreachLog.status.like("failed%")).count()
    replied    = db.query(Lead).filter(Lead.reply_received == True).count()
    interested = db.query(Lead).filter(Lead.status == "interested").count()
    return {
        "total_emails_sent": total_sent,
        "failed": failed,
        "replies_received": replied,
        "interested": interested,
        "sent_today": emails_sent_today(),
        "daily_limit": 50,
    }


# ── Conversational Inbox & Sync ───────────────────────────
from outreach.imap_sync import sync_replies


@router.post("/inbox/sync")
def sync_inbox_endpoint():
    synced = sync_replies()
    return {"message": "Sync completed successfully", "new_messages": synced}


@router.get("/inbox/conversations")
def get_inbox_conversations(db: Session = Depends(get_db)):
    leads = (
        db.query(Lead)
        .filter(
            (Lead.emails_sent > 0)
            | (Lead.reply_received == True)
            | (Lead.status.in_(["contacted", "replied", "interested", "closed"]))
        )
        .all()
    )
    
    conversations = []
    for lead in leads:
        latest_log = (
            db.query(OutreachLog)
            .filter(OutreachLog.lead_id == lead.id)
            .order_by(OutreachLog.sent_at.desc())
            .first()
        )
        
        last_message = ""
        last_time = lead.updated_at.isoformat() if lead.updated_at else None
        
        if latest_log:
            last_message = (
                latest_log.message_body[:80] + "..."
                if len(latest_log.message_body) > 80
                else latest_log.message_body
            )
            last_time = latest_log.sent_at.isoformat() if latest_log.sent_at else None
            
        conversations.append({
            "id": lead.id,
            "business_name": lead.business_name,
            "email": lead.email,
            "status": lead.status,
            "reply_received": lead.reply_received,
            "last_message": last_message,
            "last_message_time": last_time,
            "last_message_type": latest_log.message_type if latest_log else "email"
        })
        
    conversations.sort(key=lambda x: x["last_message_time"] or "", reverse=True)
    return conversations


@router.get("/inbox/conversations/{lead_id}/thread")
def get_conversation_thread(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    logs = (
        db.query(OutreachLog)
        .filter(OutreachLog.lead_id == lead_id)
        .order_by(OutreachLog.sent_at.asc())
        .all()
    )
    
    thread = [
        {
            "id": l.id,
            "message_type": l.message_type,  # email | incoming
            "message_subject": l.message_subject,
            "message_body": l.message_body,
            "sent_at": l.sent_at.isoformat() if l.sent_at else None,
            "status": l.status,
            "follow_up_number": l.follow_up_number
        }
        for l in logs
    ]
    
    return {
        "lead": {
            "id": lead.id,
            "business_name": lead.business_name,
            "email": lead.email,
            "status": lead.status
        },
        "thread": thread
    }
