"""
Leads Router — CRUD operations for the leads database.
"""
import json
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Lead, OutreachLog, SessionLocal
from scrapers.website_checker import check_website, score_lead
from ai.analyzer import analyze_lead, generate_messages

router = APIRouter(prefix="/api/leads", tags=["leads"])


# ── Pydantic Schemas ───────────────────────────────────────

class LeadStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None
    email: Optional[str] = None
    reply_text: Optional[str] = None
    reply_received: Optional[bool] = None


def _lead_to_dict(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "business_name": lead.business_name,
        "category": lead.category,
        "phone": lead.phone,
        "email": lead.email,
        "website": lead.website,
        "address": lead.address,
        "city": lead.city,
        "country": lead.country,
        "google_rating": lead.google_rating,
        "review_count": lead.review_count,
        "maps_url": lead.maps_url,
        "has_website": lead.has_website,
        "website_loads": lead.website_loads,
        "has_ssl": lead.has_ssl,
        "load_time_ms": lead.load_time_ms,
        "mobile_friendly": lead.mobile_friendly,
        "has_whatsapp": lead.has_whatsapp,
        "has_contact_form": lead.has_contact_form,
        "has_google_analytics": lead.has_google_analytics,
        "seo_score": lead.seo_score,
        "page_title": lead.page_title,
        "meta_description": lead.meta_description,
        "ai_analysis": lead.ai_analysis,
        "lead_score": lead.lead_score,
        "score_reason": lead.score_reason,
        "pitch_angle": lead.pitch_angle,
        "issues_found": json.loads(lead.issues_found) if lead.issues_found else [],
        "opportunities": json.loads(lead.opportunities) if lead.opportunities else [],
        "cold_email_subject": lead.cold_email_subject,
        "cold_email_body": lead.cold_email_body,
        "whatsapp_message": lead.whatsapp_message,
        "followup_1": lead.followup_1,
        "followup_2": lead.followup_2,
        "status": lead.status,
        "emails_sent": lead.emails_sent,
        "last_contacted": lead.last_contacted.isoformat() if lead.last_contacted else None,
        "next_followup": lead.next_followup.isoformat() if lead.next_followup else None,
        "reply_received": lead.reply_received,
        "reply_text": lead.reply_text,
        "notes": lead.notes,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


# ── Endpoints ──────────────────────────────────────────────

@router.get("")
def list_leads(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = db.query(Lead)
    if status:
        q = q.filter(Lead.status == status)
    if city:
        q = q.filter(Lead.city.ilike(f"%{city}%"))
    if category:
        q = q.filter(Lead.category.ilike(f"%{category}%"))
    if min_score is not None:
        q = q.filter(Lead.lead_score >= min_score)
    if search:
        q = q.filter(
            Lead.business_name.ilike(f"%{search}%")
            | Lead.address.ilike(f"%{search}%")
            | Lead.email.ilike(f"%{search}%")
        )

    total = q.count()
    leads = (
        q.order_by(Lead.lead_score.desc(), Lead.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "leads": [_lead_to_dict(l) for l in leads],
    }


@router.get("/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    logs = (
        db.query(OutreachLog)
        .filter(OutreachLog.lead_id == lead_id)
        .order_by(OutreachLog.sent_at.desc())
        .all()
    )
    data = _lead_to_dict(lead)
    data["outreach_logs"] = [
        {
            "id": l.id,
            "message_type": l.message_type,
            "message_subject": l.message_subject,
            "message_body": l.message_body,
            "sent_at": l.sent_at.isoformat() if l.sent_at else None,
            "status": l.status,
            "follow_up_number": l.follow_up_number,
        }
        for l in logs
    ]
    return data


@router.patch("/{lead_id}")
def update_lead(lead_id: int, update: LeadStatusUpdate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if update.status:
        lead.status = update.status
    if update.notes is not None:
        lead.notes = update.notes
    if update.email is not None:
        lead.email = update.email
    if update.reply_text is not None:
        lead.reply_text = update.reply_text
    if update.reply_received is not None:
        lead.reply_received = update.reply_received
        if update.reply_received:
            lead.status = "replied"
    db.commit()
    return _lead_to_dict(lead)


@router.delete("/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return {"message": "Lead deleted"}


def _do_analyze(lead_id: int):
    """Background: website check + AI analysis + scoring."""
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return

        lead.status = "analyzing"
        db.commit()

        # Website check
        website_data = {}
        if lead.has_website and lead.website:
            website_data = check_website(lead.website)
            lead.website_loads        = website_data.get("website_loads")
            lead.has_ssl              = website_data.get("has_ssl")
            lead.load_time_ms         = website_data.get("load_time_ms")
            lead.mobile_friendly      = website_data.get("mobile_friendly")
            lead.has_whatsapp         = website_data.get("has_whatsapp")
            lead.has_contact_form     = website_data.get("has_contact_form")
            lead.has_google_analytics = website_data.get("has_google_analytics")
            lead.seo_score            = website_data.get("seo_score")
            lead.page_title           = website_data.get("page_title")
            lead.meta_description     = website_data.get("meta_description")

        # Score
        lead_dict   = {c.name: getattr(lead, c.name) for c in Lead.__table__.columns}
        score, reason = score_lead(lead_dict, website_data)
        lead.lead_score   = score
        lead.score_reason = reason

        # AI analysis
        analysis = analyze_lead({**lead_dict, **website_data})
        lead.issues_found = json.dumps(analysis.get("issues_found", []))
        lead.opportunities= json.dumps(analysis.get("opportunities", []))
        lead.pitch_angle  = analysis.get("pitch_angle", "")
        lead.ai_analysis  = json.dumps(analysis)
        lead.status       = "analyzed"
        db.commit()

    except Exception as e:
        print(f"[Analyze] Error for lead {lead_id}: {e}")
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.status = "new"
            db.commit()
    finally:
        db.close()


def _do_generate_messages(lead_id: int):
    """Background: generate AI messages for a lead."""
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return
        analysis = json.loads(lead.ai_analysis) if lead.ai_analysis else {}
        lead_dict = {c.name: getattr(lead, c.name) for c in Lead.__table__.columns}
        msgs = generate_messages(lead_dict, analysis)
        lead.cold_email_subject = msgs.get("email_subject")
        lead.cold_email_body    = msgs.get("cold_email")
        lead.whatsapp_message   = msgs.get("whatsapp_message")
        lead.followup_1         = msgs.get("followup_1")
        lead.followup_2         = msgs.get("followup_2")
        lead.status             = "message_ready"
        db.commit()
    except Exception as e:
        print(f"[MsgGen] Error for lead {lead_id}: {e}")
    finally:
        db.close()



@router.post("/{lead_id}/analyze")
def analyze_lead_endpoint(
    lead_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    background_tasks.add_task(_do_analyze, lead_id)
    return {"message": "Analysis started", "lead_id": lead_id}


@router.post("/{lead_id}/generate-messages")
def generate_messages_endpoint(
    lead_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.ai_analysis:
        raise HTTPException(status_code=400, detail="Run analysis first")
    background_tasks.add_task(_do_generate_messages, lead_id)
    return {"message": "Message generation started", "lead_id": lead_id}
