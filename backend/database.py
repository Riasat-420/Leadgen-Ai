import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    Boolean, Text, DateTime
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Models ─────────────────────────────────────────────────

class Lead(Base):
    __tablename__ = "leads"

    id            = Column(Integer, primary_key=True, index=True)
    business_name = Column(String, nullable=False, index=True)
    category      = Column(String, index=True)
    phone         = Column(String)
    email         = Column(String)
    website       = Column(String)
    address       = Column(String)
    city          = Column(String, index=True)
    country       = Column(String)

    # Google Maps data
    google_rating = Column(Float)
    review_count  = Column(Integer)
    maps_url      = Column(String)

    # Website health
    has_website          = Column(Boolean, default=False)
    website_loads        = Column(Boolean)
    has_ssl              = Column(Boolean)
    load_time_ms         = Column(Integer)
    mobile_friendly      = Column(Boolean)
    has_whatsapp         = Column(Boolean)
    has_contact_form     = Column(Boolean)
    has_google_analytics = Column(Boolean)
    seo_score            = Column(Integer)
    page_title           = Column(String)
    meta_description     = Column(String)

    # AI analysis
    ai_analysis  = Column(Text)
    lead_score   = Column(Float, default=0)
    score_reason = Column(Text)
    pitch_angle  = Column(Text)
    issues_found = Column(Text)   # JSON list
    opportunities= Column(Text)   # JSON list

    # Generated messages
    cold_email_subject = Column(String)
    cold_email_body    = Column(Text)
    whatsapp_message   = Column(Text)
    followup_1         = Column(Text)
    followup_2         = Column(Text)

    # Outreach tracking
    status          = Column(String, default="new", index=True)
    emails_sent     = Column(Integer, default=0)
    last_contacted  = Column(DateTime)
    next_followup   = Column(DateTime)
    reply_received  = Column(Boolean, default=False)
    reply_text      = Column(Text)
    notes           = Column(Text)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


class OutreachLog(Base):
    __tablename__ = "outreach_logs"

    id               = Column(Integer, primary_key=True, index=True)
    lead_id          = Column(Integer, index=True)
    message_type     = Column(String)   # email | whatsapp | sms
    message_subject  = Column(String)
    message_body     = Column(Text)
    sent_at          = Column(DateTime, default=datetime.datetime.utcnow)
    status           = Column(String, default="sent")  # sent | failed | delivered
    follow_up_number = Column(Integer, default=0)      # 0 = initial


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id            = Column(Integer, primary_key=True, index=True)
    query         = Column(String)
    city          = Column(String)
    category      = Column(String)
    country       = Column(String)
    status        = Column(String, default="pending")  # pending|running|completed|failed
    leads_found   = Column(Integer, default=0)
    leads_scraped = Column(Integer, default=0)
    progress      = Column(Float, default=0)
    error_message = Column(Text)
    started_at    = Column(DateTime)
    completed_at  = Column(DateTime)
    created_at    = Column(DateTime, default=datetime.datetime.utcnow)


# ── Helpers ────────────────────────────────────────────────

def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
