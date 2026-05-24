"""
Fiverr Buyer Leads Scraper
Scrapes Fiverr gig pages to identify businesses that have purchased
services — these are verified buyers and warm leads.
Also finds businesses via Fiverr's public search to identify demand.
"""
import datetime
import random
import re
import time
from urllib.parse import quote_plus

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

FIVERR_SEARCH = "https://www.fiverr.com/search/gigs?query={query}&source=top-bar"


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _scrape_fiverr_gigs(keyword: str, page: int = 1) -> list[dict]:
    """
    Scrape Fiverr gig listings to understand demand and
    identify top service providers (potential competitors / referral partners).
    Each gig buyer review = a verified business that paid for the service.
    """
    query = quote_plus(keyword)
    url = f"https://www.fiverr.com/search/gigs?query={query}&page={page}"

    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=HEADERS) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                print(f"[Fiverr] HTTP {resp.status_code}")
                return []

        soup = BeautifulSoup(resp.text, "lxml")
        leads = []

        # Gig cards
        gig_cards = (
            soup.select("[class*='gig-card']")
            or soup.select("[data-impression-collected]")
            or soup.select("li.gig-wrapper")
        )

        for card in gig_cards:
            try:
                # Gig title
                title_el = card.select_one("h3") or card.select_one("[class*='title']")
                title = _clean_text(title_el.get_text()) if title_el else ""
                if not title:
                    continue

                # Seller name
                seller_el = (
                    card.select_one("[class*='seller'] a")
                    or card.select_one(".seller-name a")
                    or card.select_one("[class*='user']")
                )
                seller_name = _clean_text(seller_el.get_text()) if seller_el else "Unknown"

                # Seller profile URL
                seller_url = ""
                if seller_el and seller_el.get("href"):
                    href = seller_el["href"]
                    seller_url = (
                        f"https://www.fiverr.com{href}"
                        if href.startswith("/") else href
                    )

                # Rating + review count
                rating_el = card.select_one("[class*='rating']") or card.select_one("strong.rating")
                rating_text = _clean_text(rating_el.get_text()) if rating_el else ""

                review_el = card.select_one("[class*='count']") or card.select_one("span.count")
                review_count = _clean_text(review_el.get_text()) if review_el else ""

                # Price
                price_el = card.select_one("[class*='price']") or card.select_one(".price")
                price = _clean_text(price_el.get_text()) if price_el else ""

                # Gig link
                gig_link_el = card.select_one("a[href*='/gig/']") or card.select_one("a")
                gig_url = ""
                if gig_link_el and gig_link_el.get("href"):
                    href = gig_link_el["href"]
                    gig_url = (
                        f"https://www.fiverr.com{href}"
                        if href.startswith("/") else href
                    )

                leads.append({
                    "title": title,
                    "seller_name": seller_name,
                    "seller_url": seller_url,
                    "rating": rating_text,
                    "reviews": review_count,
                    "price": price,
                    "gig_url": gig_url,
                    "keyword": keyword,
                })

            except Exception as e:
                print(f"[Fiverr] Card parse error: {e}")
                continue

        return leads

    except Exception as e:
        print(f"[Fiverr] Fetch error: {e}")
        return []


def _save_fiverr_lead(db, item: dict) -> bool:
    """
    Save a Fiverr gig as a lead.
    The lead represents a service category/niche buyer opportunity.
    Returns True if new.
    """
    unique_name = f"[Fiverr] {item['title'][:80]}"
    existing = db.query(Lead).filter(Lead.business_name == unique_name).first()
    if existing:
        return False

    notes = (
        f"Platform: Fiverr\n"
        f"Top Seller: {item['seller_name']}\n"
        f"Rating: {item['rating']} ({item['reviews']} reviews)\n"
        f"Starting Price: {item['price']}\n"
        f"Keyword: {item['keyword']}\n\n"
        f"This gig has verified buyers — outreach these types of businesses "
        f"directly for the service: {item['title']}\n\n"
        f"Gig URL: {item['gig_url']}"
    )

    lead = Lead(
        business_name=unique_name,
        category=item["keyword"],
        website=item["gig_url"] or None,
        city="Remote",
        country="Global",
        source="fiverr",
        status="new",
        notes=notes,
        has_website=bool(item["gig_url"]),
    )
    db.add(lead)
    db.commit()
    return True


def scrape_fiverr(keyword: str, job_id: int, max_results: int = 30):
    """Main Fiverr scraper."""
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
            print(f"[Fiverr] Scraping page {page} for '{keyword}'...")
            items = _scrape_fiverr_gigs(keyword, page)

            if not items:
                print(f"[Fiverr] No more results on page {page}")
                break

            for item in items:
                if total_found >= max_results:
                    break
                total_found += 1
                if _save_fiverr_lead(db, item):
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

        print(f"[Fiverr] Done. {total_new} new leads from {total_found} gigs.")

    except Exception as e:
        print(f"[Fiverr] Fatal error: {e}")
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
