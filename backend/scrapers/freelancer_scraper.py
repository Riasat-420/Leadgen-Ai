"""
Freelancer.com Project Scraper
Scrapes public Freelancer.com project listings to find clients
posting jobs for web design, WordPress, SEO, and digital marketing.
"""
import datetime
import random
import re
import time

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

FREELANCER_SEARCH = "https://www.freelancer.com/jobs/{category}/"

# Map keyword → Freelancer category slug
KEYWORD_TO_SLUG = {
    "website design": "website-design",
    "web design": "website-design",
    "wordpress": "wordpress",
    "seo": "search-engine-optimization",
    "digital marketing": "internet-marketing",
    "logo design": "logo-design",
    "web development": "php",
    "mobile app": "mobile-phone",
}


def _keyword_to_slug(keyword: str) -> str:
    kw = keyword.lower().strip()
    for k, v in KEYWORD_TO_SLUG.items():
        if k in kw:
            return v
    # Fallback: slugify
    return re.sub(r"[^a-z0-9]+", "-", kw).strip("-")


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _scrape_freelancer_page(keyword: str, page: int = 1) -> list[dict]:
    """Fetch one page of Freelancer project listings."""
    slug = _keyword_to_slug(keyword)
    url = FREELANCER_SEARCH.format(category=slug)
    if page > 1:
        url += f"?page={page}"

    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=HEADERS) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                print(f"[Freelancer] HTTP {resp.status_code} for {url}")
                return []

        soup = BeautifulSoup(resp.text, "lxml")
        projects = []

        # Project rows
        rows = (
            soup.select(".JobSearchCard-item")
            or soup.select("[class*='project-list'] li")
            or soup.select(".project-details")
        )

        for row in rows:
            try:
                # Title
                title_el = (
                    row.select_one(".JobSearchCard-primary-heading a")
                    or row.select_one("a.project-title")
                    or row.select_one("h2 a, h3 a")
                )
                title = _clean_text(title_el.get_text()) if title_el else ""
                if not title:
                    continue

                # URL
                project_url = ""
                if title_el and title_el.get("href"):
                    href = title_el["href"]
                    project_url = (
                        f"https://www.freelancer.com{href}"
                        if href.startswith("/") else href
                    )

                # Description
                desc_el = (
                    row.select_one(".JobSearchCard-primary-description")
                    or row.select_one(".project-details-text")
                )
                description = _clean_text(desc_el.get_text()) if desc_el else ""

                # Budget
                budget_el = (
                    row.select_one(".JobSearchCard-secondary-price")
                    or row.select_one("[class*='amount']")
                )
                budget = _clean_text(budget_el.get_text()) if budget_el else ""

                # Skills/tags
                skill_els = row.select(".JobSearchCard-primary-tagsLink") or row.select(".tags a")
                skills = ", ".join(_clean_text(s.get_text()) for s in skill_els[:8])

                # Bids count (proxy for how competitive the project is)
                bids_el = row.select_one(".JobSearchCard-secondary-entry")
                bids = _clean_text(bids_el.get_text()) if bids_el else ""

                projects.append({
                    "title": title,
                    "description": description,
                    "budget": budget,
                    "skills": skills,
                    "url": project_url,
                    "bids": bids,
                })
            except Exception as e:
                print(f"[Freelancer] Parse error: {e}")
                continue

        return projects

    except Exception as e:
        print(f"[Freelancer] Fetch error: {e}")
        return []


def _save_freelancer_lead(db, project: dict, keyword: str) -> bool:
    """Save a Freelancer project as a lead. Returns True if new."""
    unique_name = f"[Freelancer] {project['title'][:80]}"

    existing = db.query(Lead).filter(Lead.business_name == unique_name).first()
    if existing:
        return False

    notes = (
        f"Budget: {project['budget']}\n"
        f"Skills: {project['skills']}\n"
        f"Bids: {project['bids']}\n\n"
        f"Project Description:\n{project['description']}"
    )

    lead = Lead(
        business_name=unique_name,
        category=keyword,
        website=project["url"] or None,
        city="Remote",
        country="Global",
        source="freelancer",
        status="new",
        notes=notes,
        has_website=bool(project["url"]),
    )
    db.add(lead)
    db.commit()
    return True


def scrape_freelancer(keyword: str, job_id: int, max_results: int = 30):
    """Main Freelancer.com scraper."""
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
            print(f"[Freelancer] Scraping page {page} for '{keyword}'...")
            projects = _scrape_freelancer_page(keyword, page)

            if not projects:
                print(f"[Freelancer] No more results on page {page}")
                break

            for p in projects:
                if total_found >= max_results:
                    break
                total_found += 1
                if _save_freelancer_lead(db, p, keyword):
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

        print(f"[Freelancer] Done. {total_new} new leads from {total_found} projects.")

    except Exception as e:
        print(f"[Freelancer] Fatal error: {e}")
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
