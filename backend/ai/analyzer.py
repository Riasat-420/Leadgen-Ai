"""
AI Lead Analyzer + Message Generator using Google Gemini API.
Produces structured analysis and personalized outreach messages.
"""
import json
import re
from typing import Optional

from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL, SENDER_NAME

# Lazy client — initialized on first use
_client = None

def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in .env")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _safe_json(text: str) -> Optional[dict]:
    """Extract and parse the first JSON object from model output."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# ── Lead Analysis ──────────────────────────────────────────

ANALYSIS_PROMPT = """
You are an expert digital marketing consultant and business analyst.
Analyze this business and their web/online presence based on the data below.

Business Info:
- Name: {business_name}
- Category: {category}
- Location: {city}, {country}
- Google Rating: {rating}/5 ({review_count} reviews)
- Has Website: {has_website}

Website Health (if applicable):
- Website Loads: {website_loads}
- SSL Certificate: {has_ssl}
- Load Time: {load_time_ms}ms
- Mobile Friendly: {mobile_friendly}
- Has WhatsApp Link: {has_whatsapp}
- Has Contact Form: {has_contact_form}
- Has Google Analytics: {has_google_analytics}
- SEO Score: {seo_score}/100
- Page Title: {page_title}

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
  "issues_found": ["specific problem 1", "specific problem 2", ...],
  "opportunities": ["improvement opportunity 1", "improvement opportunity 2", ...],
  "pitch_angle": "the single most compelling angle to approach this business with — be specific to their situation"
}}

Be concrete and specific. Reference actual data from above. Max 5 issues, max 4 opportunities.
"""

def analyze_lead(lead_data: dict) -> dict:
    """Run Gemini analysis on a lead. Returns analysis dict."""
    prompt = ANALYSIS_PROMPT.format(
        business_name=lead_data.get("business_name", "Unknown"),
        category=lead_data.get("category", "Business"),
        city=lead_data.get("city", ""),
        country=lead_data.get("country", ""),
        rating=lead_data.get("google_rating") or "N/A",
        review_count=lead_data.get("review_count") or 0,
        has_website=lead_data.get("has_website", False),
        website_loads=lead_data.get("website_loads", "N/A"),
        has_ssl=lead_data.get("has_ssl", "N/A"),
        load_time_ms=lead_data.get("load_time_ms") or "N/A",
        mobile_friendly=lead_data.get("mobile_friendly", "N/A"),
        has_whatsapp=lead_data.get("has_whatsapp", "N/A"),
        has_contact_form=lead_data.get("has_contact_form", "N/A"),
        has_google_analytics=lead_data.get("has_google_analytics", "N/A"),
        seo_score=lead_data.get("seo_score") or "N/A",
        page_title=lead_data.get("page_title") or "None",
    )

    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        result = _safe_json(response.text)
        if result:
            return result
    except Exception as e:
        print(f"[AI Analyzer] Gemini error: {e}")

    return {
        "issues_found": ["Unable to complete AI analysis — check Gemini API key"],
        "opportunities": ["Manual review recommended"],
        "pitch_angle": "General digital improvement services",
    }


# ── Message Generator ──────────────────────────────────────

MESSAGE_PROMPT = """
You are an expert B2B copywriter specializing in cold outreach for digital agencies.
Write personalized outreach messages for this business.

Business: {business_name}
Category: {category}
Location: {city}, {country}
Problems Found: {issues}
Best Pitch Angle: {pitch_angle}
Sender Name: {sender_name}

Requirements:
- cold_email: Professional but human, 100-140 words. Mention 1-2 SPECIFIC problems.
  End with a low-friction CTA (free audit, quick question, loom video).
- email_subject: Compelling, specific, not spammy, max 60 chars. Reference their business or problem.
- whatsapp_message: Casual and short (50-70 words). One specific problem. Simple question.
- followup_1: 3-day follow-up email. Reference prior email. Add new value or stat.
- followup_2: 7-day final follow-up. Short, create urgency. Offer something free.

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
  "email_subject": "...",
  "cold_email": "...",
  "whatsapp_message": "...",
  "followup_1": "...",
  "followup_2": "..."
}}
"""

def generate_messages(lead_data: dict, analysis: dict) -> dict:
    """Generate personalized outreach messages using Gemini."""
    issues_str = ", ".join(analysis.get("issues_found", [])[:3]) or "various web issues"
    pitch = analysis.get("pitch_angle", "improving their digital presence")

    prompt = MESSAGE_PROMPT.format(
        business_name=lead_data.get("business_name", "your business"),
        category=lead_data.get("category", "business"),
        city=lead_data.get("city", ""),
        country=lead_data.get("country", ""),
        issues=issues_str,
        pitch_angle=pitch,
        sender_name=SENDER_NAME,
    )

    try:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        result = _safe_json(response.text)
        if result:
            return result
    except Exception as e:
        print(f"[AI MessageGen] Gemini error: {e}")

    # Fallback template
    name = lead_data.get("business_name", "there")
    return {
        "email_subject": f"Quick question about {name}'s website",
        "cold_email": (
            f"Hi,\n\nI came across {name} on Google Maps and noticed a few "
            f"things that might be affecting your online visibility and customer conversions.\n\n"
            f"I specialize in helping local businesses in {lead_data.get('city', 'your area')} "
            f"improve their digital presence — from website performance to SEO and lead generation.\n\n"
            f"Would you be open to a free 10-minute audit call this week?\n\n"
            f"Best,\n{SENDER_NAME}"
        ),
        "whatsapp_message": (
            f"Hi! I found {name} on Google Maps and noticed a couple of things "
            f"on your website that could be costing you customers. "
            f"Mind if I send you a quick video showing what I found? 🙂"
        ),
        "followup_1": (
            f"Hi,\n\nJust following up on my previous email about {name}.\n\n"
            f"I've since looked at a few competitors in {lead_data.get('city', 'your area')} "
            f"and there's a clear gap you could fill.\n\n"
            f"Happy to share what I found — no strings attached.\n\n{SENDER_NAME}"
        ),
        "followup_2": (
            f"Hi,\n\nLast email, I promise!\n\n"
            f"I put together a free audit for {name} — "
            f"it shows exactly 3 things holding your website back. "
            f"I'll send it over with no obligation.\n\n"
            f"Worth 5 minutes?\n\n{SENDER_NAME}"
        ),
    }
