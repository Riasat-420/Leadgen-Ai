"""
Google Maps Lead Scraper
Uses Playwright (headless Chromium) to search Google Maps and extract
business information. Includes anti-detection measures.
"""
import asyncio
import random
import re
import datetime
from typing import Optional

from playwright.async_api import async_playwright, Page

from database import SessionLocal, Lead, ScrapeJob
from config import SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX
from scrapers.email_extractor import extract_emails_from_website

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
    "Gecko/20100101 Firefox/124.0",
]


async def _rand_delay():
    await asyncio.sleep(random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX))


async def _extract_business_details(page: Page, city: str, category: str, country: str) -> Optional[dict]:
    """Extract business details from the currently open Google Maps side panel."""
    try:
        await asyncio.sleep(random.uniform(1.0, 2.0))

        # ── Business name ─────────────────────────────────
        name = ""
        for sel in ['h1.DUwDvf', 'h1[class*="fontHeadlineLarge"]', 'h1']:
            el = await page.query_selector(sel)
            if el:
                name = (await el.inner_text()).strip()
                if name:
                    break
        if not name:
            return None

        # ── Category ──────────────────────────────────────
        detected_category = category
        for sel in ['button[jsaction*="category"]', 'button.DkEaL',
                    'div[class*="fontBodyMedium"] button']:
            el = await page.query_selector(sel)
            if el:
                txt = (await el.inner_text()).strip()
                if txt and len(txt) < 60:
                    detected_category = txt
                    break

        # ── Rating ────────────────────────────────────────
        rating = None
        for sel in ['div.F7nice > span > span[aria-hidden]',
                    'span.ceNzKf', 'span[aria-hidden="true"]']:
            el = await page.query_selector(sel)
            if el:
                try:
                    rating = float((await el.inner_text()).strip().replace(',', '.'))
                    if 0 < rating <= 5:
                        break
                    rating = None
                except Exception:
                    pass

        # ── Review count ──────────────────────────────────
        review_count = None
        el = await page.query_selector('span[aria-label*="review"]')
        if el:
            label = await el.get_attribute('aria-label') or ""
            nums = re.findall(r'[\d,]+', label)
            if nums:
                review_count = int(nums[0].replace(',', ''))

        # ── Address ───────────────────────────────────────
        address = ""
        el = await page.query_selector('button[data-item-id="address"]')
        if el:
            address = (await el.inner_text()).strip()
        if not address:
            el = await page.query_selector('[data-tooltip="Copy address"]')
            if el:
                address = (await el.inner_text()).strip()

        # ── Phone ─────────────────────────────────────────
        phone = ""
        for sel in ['button[data-item-id*="phone:tel"]',
                    'button[data-tooltip="Copy phone number"]']:
            el = await page.query_selector(sel)
            if el:
                phone = (await el.inner_text()).strip()
                if phone:
                    break

        # ── Website ───────────────────────────────────────
        website = ""
        el = await page.query_selector('a[data-item-id="authority"]')
        if el:
            website = await el.get_attribute('href') or ""
        if not website:
            el = await page.query_selector('a[data-tooltip="Open website"]')
            if el:
                website = await el.get_attribute('href') or ""

        # ── Maps URL ──────────────────────────────────────
        maps_url = page.url

        # ── Email (from website crawl) ──────────────────────
        email = None
        if website and website.startswith("http"):
            try:
                email = extract_emails_from_website(website)
                if email:
                    print(f"[Scraper] Email found for {name}: {email}")
            except Exception as e:
                print(f"[Scraper] Email extraction error for {name}: {e}")

        return {
            "business_name": name,
            "category": detected_category,
            "phone": phone or None,
            "email": email or None,
            "website": website or None,
            "address": address or None,
            "city": city,
            "country": country,
            "google_rating": rating,
            "review_count": review_count,
            "maps_url": maps_url,
            "has_website": bool(website and website.startswith("http")),
            "source": "google_maps",
        }

    except Exception as e:
        print(f"[Scraper] extract error: {e}")
        return None


def _save_lead(db, data: dict) -> bool:
    """Save lead to DB if not already present. Returns True if new."""
    existing = (
        db.query(Lead)
        .filter(Lead.business_name == data["business_name"],
                Lead.city == data["city"])
        .first()
    )
    if existing:
        return False

    lead = Lead(**data)
    db.add(lead)
    db.commit()
    return True


async def scrape_google_maps(
    query: str,
    city: str,
    category: str,
    country: str,
    job_id: int,
    max_results: int = 30,
):
    """
    Main scraper function. Runs inside a background thread.
    Launches Playwright, scrapes Google Maps, saves leads to DB.
    """
    db = SessionLocal()
    try:
        # Mark job as running
        job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
        if job:
            job.status = "running"
            job.started_at = datetime.datetime.utcnow()
            db.commit()

        scraped_count = 0
        new_count = 0

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox",
                      "--disable-blink-features=AutomationControlled"],
            )
            ctx = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1366, "height": 768},
                locale="en-US",
            )
            # Mask webdriver property
            await ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await ctx.new_page()

            # Navigate
            search_query = query.replace(" ", "+")
            url = f"https://www.google.com/maps/search/{search_query}/"
            print(f"[Scraper] Navigating to: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await _rand_delay()

            # Accept consent if present (EU/CA)
            for btn_text in ["Accept all", "Agree", "I agree"]:
                try:
                    btn = page.get_by_role("button", name=btn_text)
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    pass

            # Wait for results feed
            try:
                await page.wait_for_selector('[role="feed"]', timeout=20000)
            except Exception:
                print("[Scraper] Could not find results feed")
                raise RuntimeError("Google Maps results did not load")

            processed_urls = set()

            while scraped_count < max_results:
                # Collect result links
                items = await page.query_selector_all('[role="feed"] a[href*="/maps/place/"]')
                new_items = [it for it in items if await it.get_attribute("href") not in processed_urls]

                if not new_items and scraped_count > 0:
                    # Try scrolling to load more
                    feed = await page.query_selector('[role="feed"]')
                    if feed:
                        await feed.evaluate("el => el.scrollBy(0, 600)")
                        await asyncio.sleep(2)
                        items = await page.query_selector_all('[role="feed"] a[href*="/maps/place/"]')
                        new_items = [it for it in items
                                     if await it.get_attribute("href") not in processed_urls]
                    if not new_items:
                        break

                for item in new_items:
                    if scraped_count >= max_results:
                        break

                    href = await item.get_attribute("href")
                    if not href or href in processed_urls:
                        continue
                    processed_urls.add(href)

                    try:
                        await item.click()
                        await asyncio.sleep(random.uniform(2, 3.5))

                        lead_data = await _extract_business_details(
                            page, city, category, country
                        )
                        if lead_data and lead_data.get("business_name"):
                            scraped_count += 1
                            is_new = _save_lead(db, lead_data)
                            if is_new:
                                new_count += 1

                            # Update progress
                            if job:
                                job.leads_scraped = scraped_count
                                job.leads_found = new_count
                                job.progress = min((scraped_count / max_results) * 100, 99)
                                db.commit()

                        await _rand_delay()

                    except Exception as e:
                        print(f"[Scraper] Item error: {e}")
                        continue

                # Scroll feed for more results
                feed = await page.query_selector('[role="feed"]')
                if feed:
                    await feed.evaluate("el => el.scrollBy(0, 800)")
                    await asyncio.sleep(2)

            await browser.close()

        # Mark complete
        if job:
            job.status = "completed"
            job.completed_at = datetime.datetime.utcnow()
            job.leads_found = new_count
            job.leads_scraped = scraped_count
            job.progress = 100
            db.commit()

        print(f"[Scraper] Done. {new_count} new leads from {scraped_count} results.")

    except Exception as e:
        print(f"[Scraper] Fatal error: {e}")
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
