"""
Scraper Router — Launch and monitor Google Maps scraping jobs.
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, ScrapeJob, SessionLocal
from scrapers.google_maps import scrape_google_maps
from config import DEFAULT_TARGETS, DEFAULT_MAX_RESULTS

router = APIRouter(prefix="/api/scrape", tags=["scraper"])


class ScrapeRequest(BaseModel):
    category: str
    city: str
    country: Optional[str] = "Unknown"
    max_results: Optional[int] = DEFAULT_MAX_RESULTS


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


def _run_scraper_sync(job_id: int, query: str, city: str, category: str,
                      country: str, max_results: int):
    """Runs the async scraper in a new event loop (for BackgroundTasks thread)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            scrape_google_maps(query, city, category, country, job_id, max_results)
        )
    finally:
        loop.close()


@router.post("/start")
def start_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    query = f"{req.category} in {req.city}"

    # Create job record
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

    # Launch in background
    background_tasks.add_task(
        _run_scraper_sync,
        job.id, query, req.city, req.category, req.country, req.max_results,
    )

    return {"job_id": job.id, "message": f"Scrape started for '{query}'"}


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
    """Return the pre-configured target markets."""
    return DEFAULT_TARGETS
