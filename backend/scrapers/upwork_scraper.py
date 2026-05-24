"""
Upwork Job Scraper
Scrapes public Upwork job listings to find clients actively
hiring for web design, WordPress, SEO, and digital marketing.
These are warm leads with approved budgets.
"""
import datetime
import random
import re
import time
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from database import SessionLocal, Lead, ScrapeJob

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

UPWORK_SEARCH = "https://www.upwork.com/search/jobs/?q={query}&sort=recency"


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _scrape_upwork_page(keyword: str, page: int = 1) -> list[dict]:
    """Fetch one page of Upwork search results and parse jobs."""
    url = UPWORK_SEARCH.format(query=keyword.replace(" ", "%20"))
    if page > 1:
        url += f"&page={page}"

    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=HEADERS) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                print(f"[Upwork] HTTP {resp.status_code} for {url}")
                return []

        soup = BeautifulSoup(resp.text, "lxml")
        jobs = []

        # Upwork job cards — try multiple selectors as their HTML changes
        job_tiles = (
            soup.select("article.job-tile")
            or soup.select("[data-test='job-tile']")
            or soup.select(".job-list-item")
        )

        for tile in job_tiles:
            try:
                # Title
                title_el = (
                    tile.select_one("h2.job-tile-title a")
                    or tile.select_one("[data-test='job-title'] a")
                    or tile.select_one("h2 a")
                )
                title = _clean_text(title_el.get_text()) if title_el else ""
                if not title:
                    continue

                # Description snippet
                desc_el = (
                    tile.select_one("[data-test='job-description-text']")
                    or tile.select_one(".job-description-text")
                    or tile.select_one("p.description")
                )
                description = _clean_text(desc_el.get_text()) if desc_el else ""

                # Budget
                budget_el = (
                    tile.select_one("[data-test='budget']")
                    or tile.select_one(".job-type-label")
                    or tile.select_one("[data-test='job-type']")
                )
                budget = _clean_text(budget_el.get_text()) if budget_el else ""

                # Skills
                skill_els = tile.select(".skill-badge") or tile.select("[data-test='skill']")
                skills = ", ".join(_clean_text(s.get_text()) for s in skill_els[:8])

                # Job URL
                job_url = ""
                if title_el and title_el.get("href"):
                    href = title_el["href"]
                    job_url = f"https://www.upwork.com{href}" if href.startswith("/") else href

                # Client country (sometimes shown)
                country_el = tile.select_one("[data-test='client-country']")
                client_country = _clean_text(country_el.get_text()) if country_el else "Unknown"

                jobs.append({
                    "title": title,
                    "description": description,
                    "budget": budget,
                    "skills": skills,
                    "url": job_url,
                    "client_country": client_country,
                })
            except Exception as e:
                print(f"[Upwork] Parse error on tile: {e}")
                continue

        return jobs

    except Exception as e:
        print(f"[Upwork] Fetch error: {e}")
        return []


def _save_upwork_lead(db, job: dict, keyword: str) -> bool:
    """Save an Upwork job as a lead. Returns True if new."""
    # Use title + first 60 chars of description as unique key
    unique_name = f"[Upwork] {job['title'][:80]}"

    existing = db.query(Lead).filter(Lead.business_name == unique_name).first()
    if existing:
        return False

    notes = f"Budget: {job['budget']}\nSkills: {job['skills']}\n\nJob Description:\n{job['description']}"

    lead = Lead(
        business_name=unique_name,
        category=keyword,
        website=job["url"] or None,
        country=job["client_country"],
        city="Remote",
        source="upwork",
        status="new",
        notes=notes,
        has_website=bool(job["url"]),
    )
    db.add(lead)
    db.commit()
    return True


def scrape_upwork(keyword: str, job_id: int, max_results: int = 30):
    """Main Upwork scraper — saves leads to DB, updates job progress."""
    db = SessionLocal()
    try:
        job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
        if job:
            job.status = "running"
            job.started_at = datetime.datetime.utcnow()
            db.commit()

        total_found = 0
        total_new = 0
        page = 1

        while total_found < max_results:
            print(f"[Upwork] Scraping page {page} for '{keyword}'...")
            jobs = _scrape_upwork_page(keyword, page)

            if not jobs:
                print(f"[Upwork] No more results on page {page}")
                break

            for j in jobs:
                if total_found >= max_results:
                    break
                total_found += 1
                if _save_upwork_lead(db, j, keyword):
                    total_new += 1

                if job:
                    job.leads_scraped = total_found
                    job.leads_found = total_new
                    job.progress = min((total_found / max_results) * 100, 99)
                    db.commit()

            page += 1
            time.sleep(random.uniform(2, 4))

        if job:
            job.status = "completed"
            job.completed_at = datetime.datetime.utcnow()
            job.progress = 100
            db.commit()

        print(f"[Upwork] Done. {total_new} new leads from {total_found} jobs.")

    except Exception as e:
        print(f"[Upwork] Fatal error: {e}")
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
