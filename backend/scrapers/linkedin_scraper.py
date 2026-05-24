"""
LinkedIn Company Scraper
Uses Google search (site:linkedin.com/company) to find public
LinkedIn company pages, then visits them to extract company info.
No login required — only public data.
"""
import datetime
import random
import re
import time
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from database import SessionLocal, Lead, ScrapeJob
from scrapers.email_extractor import extract_emails_from_website

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

GOOGLE_SEARCH = "https://www.google.com/search?q=site:linkedin.com/company+{query}&num=20"


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _google_linkedin_search(keyword: str, page: int = 0) -> list[str]:
    """
    Use Google to find LinkedIn company URLs for a keyword.
    Returns list of linkedin.com/company/... URLs.
    """
    query = quote_plus(f'site:linkedin.com/company "{keyword}"')
    url = f"https://www.google.com/search?q={query}&num=20"
    if page > 0:
        url += f"&start={page * 20}"

    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers=HEADERS) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                print(f"[LinkedIn] Google search returned {resp.status_code}")
                return []

        soup = BeautifulSoup(resp.text, "lxml")
        urls = []

        # Extract LinkedIn URLs from search results
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            # Google wraps URLs — extract from /url?q=...
            if "/url?q=" in href:
                href = href.split("/url?q=")[1].split("&")[0]
            if "linkedin.com/company/" in href and href not in urls:
                # Clean tracking params
                href = href.split("?")[0]
                urls.append(href)

        return urls[:20]

    except Exception as e:
        print(f"[LinkedIn] Google search error: {e}")
        return []


def _scrape_linkedin_company(url: str) -> dict | None:
    """
    Scrape a public LinkedIn company page.
    Returns company data dict or None.
    """
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers=HEADERS) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None

        soup = BeautifulSoup(resp.text, "lxml")

        # Company name
        name_el = (
            soup.select_one("h1.top-card-layout__title")
            or soup.select_one("[class*='company-name']")
            or soup.select_one("h1")
        )
        name = _clean_text(name_el.get_text()) if name_el else ""
        if not name or len(name) < 2:
            return None

        # Industry / tagline
        tagline_el = (
            soup.select_one(".top-card-layout__first-subline")
            or soup.select_one("[class*='industry']")
            or soup.select_one(".company-tagline")
        )
        industry = _clean_text(tagline_el.get_text()) if tagline_el else ""

        # Description
        desc_el = (
            soup.select_one("[class*='description']")
            or soup.select_one(".core-section-container__content p")
        )
        description = _clean_text(desc_el.get_text())[:500] if desc_el else ""

        # Company website (often listed on public pages)
        website_el = soup.find("a", href=re.compile(r"^https?://(?!.*linkedin\.com)"))
        website = website_el.get("href", "").split("?")[0] if website_el else ""

        # Employee count
        employee_el = soup.find(string=re.compile(r"\d+.*employee", re.I))
        employees = _clean_text(str(employee_el)) if employee_el else ""

        # City / country from URL slug or page
        location_el = soup.select_one("[class*='headquarters']") or soup.find(
            string=re.compile(r"Headquarters", re.I)
        )
        location = ""
        if location_el:
            parent = location_el.parent if hasattr(location_el, "parent") else None
            if parent:
                location = _clean_text(parent.get_text()).replace("Headquarters", "").strip()

        # Try to get email from their website
        email = None
        if website and website.startswith("http"):
            try:
                email = extract_emails_from_website(website)
            except Exception:
                pass

        return {
            "name": name,
            "industry": industry,
            "description": description,
            "website": website or None,
            "employees": employees,
            "location": location,
            "linkedin_url": url,
            "email": email,
        }

    except Exception as e:
        print(f"[LinkedIn] Scrape error for {url}: {e}")
        return None


def _save_linkedin_lead(db, data: dict, keyword: str) -> bool:
    """Save a LinkedIn company as a lead. Returns True if new."""
    name = data["name"]
    existing = db.query(Lead).filter(Lead.business_name == name).first()
    if existing:
        return False

    # Parse city/country from location string
    city, country = "Unknown", "Unknown"
    if data.get("location"):
        parts = data["location"].split(",")
        if len(parts) >= 2:
            city = parts[0].strip()
            country = parts[-1].strip()
        elif len(parts) == 1:
            city = parts[0].strip()

    notes = (
        f"Industry: {data.get('industry', '')}\n"
        f"Employees: {data.get('employees', '')}\n"
        f"LinkedIn: {data.get('linkedin_url', '')}\n\n"
        f"{data.get('description', '')}"
    )

    lead = Lead(
        business_name=name,
        category=data.get("industry") or keyword,
        website=data.get("website"),
        email=data.get("email"),
        city=city,
        country=country,
        source="linkedin",
        status="new",
        notes=notes,
        has_website=bool(data.get("website")),
    )
    db.add(lead)
    db.commit()
    return True


def scrape_linkedin(keyword: str, job_id: int, max_results: int = 20):
    """Main LinkedIn scraper."""
    db = SessionLocal()
    try:
        job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
        if job:
            job.status = "running"
            job.started_at = datetime.datetime.utcnow()
            db.commit()

        total_found = 0
        total_new = 0
        page = 0
        processed_urls: set[str] = set()

        while total_found < max_results:
            print(f"[LinkedIn] Searching Google page {page + 1} for '{keyword}'...")
            urls = _google_linkedin_search(keyword, page)

            if not urls:
                print("[LinkedIn] No more results from Google")
                break

            for url in urls:
                if total_found >= max_results:
                    break
                if url in processed_urls:
                    continue
                processed_urls.add(url)

                print(f"[LinkedIn] Scraping: {url}")
                data = _scrape_linkedin_company(url)

                if data and data.get("name"):
                    total_found += 1
                    if _save_linkedin_lead(db, data, keyword):
                        total_new += 1

                    if job:
                        job.leads_scraped = total_found
                        job.leads_found = total_new
                        job.progress = min((total_found / max_results) * 100, 99)
                        db.commit()

                time.sleep(random.uniform(1.5, 3.0))

            page += 1
            time.sleep(random.uniform(3, 6))  # Polite delay between Google pages

        if job:
            job.status = "completed"
            job.completed_at = datetime.datetime.utcnow()
            job.progress = 100
            db.commit()

        print(f"[LinkedIn] Done. {total_new} new leads from {total_found} companies.")

    except Exception as e:
        print(f"[LinkedIn] Fatal error: {e}")
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
