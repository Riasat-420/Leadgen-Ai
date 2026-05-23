"""
Dashboard Router — Aggregate stats for the overview dashboard.
"""
import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Lead, OutreachLog, ScrapeJob

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    # Lead counts by status
    total_leads  = db.query(Lead).count()
    new_leads    = db.query(Lead).filter(Lead.status == "new").count()
    analyzed     = db.query(Lead).filter(Lead.status.in_(["analyzed", "message_ready"])).count()
    contacted    = db.query(Lead).filter(Lead.status == "contacted").count()
    replied      = db.query(Lead).filter(Lead.status.in_(["replied", "interested"])).count()
    interested   = db.query(Lead).filter(Lead.status == "interested").count()
    closed       = db.query(Lead).filter(Lead.status == "closed").count()

    # High priority leads (score >= 7)
    hot_leads = db.query(Lead).filter(Lead.lead_score >= 7).count()

    # Email stats
    emails_sent = db.query(OutreachLog).filter(OutreachLog.status == "sent").count()

    # Today's emails
    today = datetime.datetime.utcnow().date()
    start_of_day = datetime.datetime(today.year, today.month, today.day)
    emails_today = (
        db.query(OutreachLog)
        .filter(OutreachLog.status == "sent", OutreachLog.sent_at >= start_of_day)
        .count()
    )

    # Scrape jobs
    total_jobs    = db.query(ScrapeJob).count()
    running_jobs  = db.query(ScrapeJob).filter(ScrapeJob.status == "running").count()

    # Conversion rate
    conversion = round((replied / contacted * 100), 1) if contacted > 0 else 0

    # Top leads (score desc)
    top_leads = (
        db.query(Lead)
        .filter(Lead.lead_score > 0)
        .order_by(Lead.lead_score.desc())
        .limit(5)
        .all()
    )
    top_leads_data = [
        {
            "id": l.id,
            "business_name": l.business_name,
            "city": l.city,
            "category": l.category,
            "lead_score": l.lead_score,
            "status": l.status,
            "website": l.website,
        }
        for l in top_leads
    ]

    # Recent leads (10)
    recent = (
        db.query(Lead)
        .order_by(Lead.created_at.desc())
        .limit(10)
        .all()
    )
    recent_data = [
        {
            "id": l.id,
            "business_name": l.business_name,
            "city": l.city,
            "category": l.category,
            "lead_score": l.lead_score,
            "status": l.status,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in recent
    ]

    # Leads by city
    by_city = (
        db.query(Lead.city, func.count(Lead.id).label("count"))
        .group_by(Lead.city)
        .order_by(func.count(Lead.id).desc())
        .limit(10)
        .all()
    )

    # Score distribution
    score_dist = {
        "0-3": db.query(Lead).filter(Lead.lead_score < 3).count(),
        "3-5": db.query(Lead).filter(Lead.lead_score >= 3, Lead.lead_score < 5).count(),
        "5-7": db.query(Lead).filter(Lead.lead_score >= 5, Lead.lead_score < 7).count(),
        "7-10": db.query(Lead).filter(Lead.lead_score >= 7).count(),
    }

    return {
        "leads": {
            "total": total_leads,
            "new": new_leads,
            "analyzed": analyzed,
            "contacted": contacted,
            "replied": replied,
            "interested": interested,
            "closed": closed,
            "hot": hot_leads,
        },
        "outreach": {
            "emails_sent": emails_sent,
            "emails_today": emails_today,
            "daily_limit": 50,
            "conversion_rate": conversion,
        },
        "scraping": {
            "total_jobs": total_jobs,
            "running_jobs": running_jobs,
        },
        "top_leads": top_leads_data,
        "recent_leads": recent_data,
        "by_city": [{"city": r[0], "count": r[1]} for r in by_city],
        "score_distribution": score_dist,
    }
