"""
Website Health Checker
Analyzes a business website for SEO issues, mobile-friendliness,
load speed, SSL, and key missing elements.
"""
import re
import time
from typing import Optional

import httpx
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def check_website(url: Optional[str]) -> dict:
    """
    Synchronous website health check.
    Returns a dict of metrics.
    """
    result = {
        "website_loads": False,
        "has_ssl": False,
        "load_time_ms": None,
        "mobile_friendly": False,
        "has_whatsapp": False,
        "has_contact_form": False,
        "has_google_analytics": False,
        "seo_score": 0,
        "page_title": None,
        "meta_description": None,
        "has_h1": False,
        "has_booking": False,
    }

    if not url or not url.startswith("http"):
        return result

    result["has_ssl"] = url.startswith("https://")

    try:
        start = time.time()
        with httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            response = client.get(url)
        load_time_ms = int((time.time() - start) * 1000)
        result["load_time_ms"] = load_time_ms
        result["website_loads"] = response.status_code == 200

        if response.status_code != 200:
            return result

        html = response.text
        soup = BeautifulSoup(html, "lxml")

        # Title
        title_tag = soup.find("title")
        result["page_title"] = title_tag.get_text(strip=True) if title_tag else None

        # Meta description
        meta = soup.find("meta", attrs={"name": re.compile("description", re.I)})
        result["meta_description"] = meta.get("content", "").strip() if meta else None

        # H1
        result["has_h1"] = soup.find("h1") is not None

        # Viewport / mobile
        vp = soup.find("meta", attrs={"name": re.compile("viewport", re.I)})
        result["mobile_friendly"] = vp is not None

        # WhatsApp
        result["has_whatsapp"] = bool(
            soup.find("a", href=re.compile(r"wa\.me|whatsapp\.com", re.I))
            or re.search(r"whatsapp", html, re.I)
        )

        # Contact form (has multiple input/textarea fields)
        forms = soup.find_all("form")
        for form in forms:
            inputs = form.find_all(["input", "textarea"])
            if len(inputs) >= 2:
                result["has_contact_form"] = True
                break

        # Booking system
        booking_keywords = [
            "book", "appointment", "calendly", "booking", "schedule",
            "reserv", "opentable", "resy",
        ]
        has_booking = any(kw in html.lower() for kw in booking_keywords)
        result["has_booking"] = has_booking

        # Google Analytics / GTM
        result["has_google_analytics"] = bool(
            re.search(r"gtag\(|GA_MEASUREMENT|analytics\.js|GTM-", html)
        )

        # SEO Score (0-100)
        seo = 0
        if result["page_title"] and len(result["page_title"]) > 10:
            seo += 20
        if result["meta_description"] and len(result["meta_description"]) > 20:
            seo += 20
        if result["has_h1"]:
            seo += 20
        if result["has_ssl"]:
            seo += 20
        if result["mobile_friendly"]:
            seo += 20
        result["seo_score"] = seo

    except httpx.TimeoutException:
        result["load_time_ms"] = 15000
        result["website_loads"] = False
    except Exception as e:
        print(f"[WebsiteChecker] Error checking {url}: {e}")

    return result


def score_platform_lead(lead_data: dict) -> tuple[float, str]:
    """
    Compute a lead score (0–10) specifically for platform postings (Upwork, Freelancer, Fiverr, LinkedIn).
    Returns (score, reason_string).
    """
    score = 3.0  # Base score for platform lead since they have active intent
    reasons = ["Active project posting / professional search"]
    
    source = lead_data.get("source", "upwork")
    notes = lead_data.get("notes") or ""
    notes_lower = notes.lower()
    
    # 1. Check for email
    if lead_data.get("email"):
        score += 3.0
        reasons.append("Direct contact email available")
    else:
        reasons.append("Platform application required")
        
    # 2. Check budget (if applicable)
    budget = ""
    # Extract budget from notes
    for line in notes.split("\n"):
        if "budget:" in line.lower() or "price:" in line.lower() or "starting price:" in line.lower():
            budget = line
            break
            
    if budget:
        # Try to parse numeric amount
        nums = [int(s) for s in re.findall(r'\d+', budget.replace(",", ""))]
        if nums:
            max_num = max(nums)
            if max_num >= 5000:
                score += 3.0
                reasons.append(f"Enterprise budget ({budget.strip()})")
            elif max_num >= 1500:
                score += 2.0
                reasons.append(f"High-value project ({budget.strip()})")
            elif max_num >= 500:
                score += 1.0
                reasons.append(f"Mid-range project ({budget.strip()})")
            else:
                score += 0.5
                reasons.append(f"Small-scale project ({budget.strip()})")
        else:
            score += 1.0
            reasons.append(f"Budget indicated: {budget.replace('Budget:', '').strip()}")
            
    # 3. Check for high-value intent keywords
    intent_keywords = {
        "long-term": 1.5,
        "long term": 1.5,
        "ongoing": 1.0,
        "immediate": 1.0,
        "urgent": 1.0,
        "redesign": 0.5,
        "rebuild": 0.5,
        "expert": 0.5,
        "agency": 0.5,
    }
    
    matched_kws = []
    for kw, val in intent_keywords.items():
        if kw in notes_lower:
            score += val
            matched_kws.append(kw)
            
    if matched_kws:
        reasons.append(f"Intent signals: {', '.join(matched_kws[:3])}")
        
    # 4. Check for description richness
    desc_len = len(notes)
    if desc_len > 300:
        score += 1.0
        reasons.append("Highly detailed requirements")
    elif desc_len > 150:
        score += 0.5
        reasons.append("Moderate details")
        
    score = min(round(score, 1), 10.0)
    return score, " | ".join(reasons)


def score_lead(lead_data: dict, website_data: dict) -> tuple[float, str]:
    """
    Compute a lead score (0–10) based on business + website data.
    Returns (score, reason_string).
    """
    source = lead_data.get("source", "google_maps")
    if source in ["upwork", "freelancer", "fiverr", "linkedin"]:
        return score_platform_lead(lead_data)

    score = 0.0
    reasons = []

    has_website = lead_data.get("has_website", False)

    if not has_website:
        score += 3.0
        reasons.append("No website found")
    else:
        if not website_data.get("website_loads"):
            score += 2.5
            reasons.append("Website is broken / unreachable")
        else:
            # Load time
            lt = website_data.get("load_time_ms") or 0
            if lt > 5000:
                score += 2.0
                reasons.append(f"Very slow load ({lt}ms)")
            elif lt > 3000:
                score += 1.0
                reasons.append(f"Slow load ({lt}ms)")

            # SSL
            if not website_data.get("has_ssl"):
                score += 1.5
                reasons.append("No HTTPS / SSL")

            # Mobile
            if not website_data.get("mobile_friendly"):
                score += 1.0
                reasons.append("Not mobile-friendly")

            # SEO
            seo = website_data.get("seo_score", 100)
            if seo < 40:
                score += 1.5
                reasons.append(f"Poor SEO score ({seo}/100)")
            elif seo < 60:
                score += 0.5
                reasons.append(f"Weak SEO score ({seo}/100)")

            # Missing features
            if not website_data.get("has_whatsapp"):
                score += 0.5
                reasons.append("No WhatsApp contact")
            if not website_data.get("has_contact_form"):
                score += 0.5
                reasons.append("No contact form")
            if not website_data.get("has_google_analytics"):
                score += 0.5
                reasons.append("No analytics tracking")

    # Rating-based score
    rating = lead_data.get("google_rating") or 5.0
    reviews = lead_data.get("review_count") or 0
    if rating < 3.5:
        score += 1.0
        reasons.append(f"Low Google rating ({rating}★)")
    if reviews < 10:
        score += 0.5
        reasons.append("Very few reviews")

    score = min(round(score, 1), 10.0)
    return score, " | ".join(reasons) if reasons else "Healthy presence"
