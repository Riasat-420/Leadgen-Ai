"""
Scraper Router — Launch and monitor scraping jobs across all platforms.
Supports Google Maps, Upwork, Freelancer, LinkedIn, and Fiverr.
"""
import asyncio
import threading
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, ScrapeJob, SessionLocal
from scrapers.google_maps import scrape_google_maps
from scrapers.upwork_scraper import scrape_upwork
from scrapers.freelancer_scraper import scrape_freelancer
from scrapers.linkedin_scraper import scrape_linkedin
from scrapers.fiverr_scraper import scrape_fiverr
from config import DEFAULT_TARGETS, DEFAULT_MAX_RESULTS

router = APIRouter(prefix="/api/scrape", tags=["scraper"])


class ScrapeRequest(BaseModel):
    category: str
    city: str
    country: Optional[str] = "Unknown"
    keywords: Optional[str] = ""
    max_results: Optional[int] = DEFAULT_MAX_RESULTS


class PlatformScrapeRequest(BaseModel):
    platform: str       # upwork | freelancer | linkedin | fiverr
    keyword: str
    max_results: Optional[int] = 30


def _job_to_dict(job: ScrapeJob) -> dict:
    return {
        "id": job.id,
        "query": job.query,
        "city": job.city,
        "category": job.category,
        "country": job.country,
        "status": job.status,
        "leads_found": job.leads_found,
        "leads_scraped": job.leads_scraped,
        "progress": job.progress,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


# ── Google Maps (async via new event loop) ─────────────────

def _run_google_maps_sync(job_id: int, query: str, city: str, category: str,
                          country: str, max_results: int):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            scrape_google_maps(query, city, category, country, job_id, max_results)
        )
    finally:
        loop.close()


@router.post("/start")
def start_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks,
                 db: Session = Depends(get_db)):
    query = f"{req.category} {req.keywords} in {req.city}" if req.keywords else f"{req.category} in {req.city}"

    job = ScrapeJob(
        query=query,
        city=req.city,
        category=req.category,
        country=req.country,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        _run_google_maps_sync,
        job.id, query, req.city, req.category, req.country, req.max_results,
    )

    return {"job_id": job.id, "message": f"Google Maps scrape started for '{query}'"}


# ── Platform scrapers (Upwork, Freelancer, LinkedIn, Fiverr) ─

def _run_platform_scraper(platform: str, keyword: str, job_id: int, max_results: int):
    """Run the appropriate platform scraper in a background thread."""
    scraper_map = {
        "upwork":     scrape_upwork,
        "freelancer": scrape_freelancer,
        "linkedin":   scrape_linkedin,
        "fiverr":     scrape_fiverr,
    }
    fn = scraper_map.get(platform)
    if fn:
        fn(keyword, job_id, max_results)
    else:
        print(f"[Scraper Router] Unknown platform: {platform}")


@router.post("/platform")
def start_platform_scrape(req: PlatformScrapeRequest, background_tasks: BackgroundTasks,
                           db: Session = Depends(get_db)):
    """Launch a scraping job for Upwork, Freelancer, LinkedIn, or Fiverr."""
    platform_labels = {
        "upwork": "Upwork",
        "freelancer": "Freelancer.com",
        "linkedin": "LinkedIn",
        "fiverr": "Fiverr",
    }
    label = platform_labels.get(req.platform, req.platform.title())
    query = f"[{label}] {req.keyword}"

    job = ScrapeJob(
        query=query,
        city="Remote",
        category=req.keyword,
        country="Global",
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        _run_platform_scraper,
        req.platform, req.keyword, job.id, req.max_results,
    )

    return {
        "job_id": job.id,
        "message": f"{label} scrape started for '{req.keyword}'",
        "platform": req.platform,
    }


@router.get("/status/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if not job:
        return {"error": "Job not found"}
    return _job_to_dict(job)


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db), limit: int = 20):
    jobs = (
        db.query(ScrapeJob)
        .order_by(ScrapeJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_job_to_dict(j) for j in jobs]


@router.get("/targets")
def get_default_targets():
    """Return all pre-configured target markets across all platforms."""
    return DEFAULT_TARGETS
