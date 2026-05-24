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

PLATFORM_ANALYSIS_PROMPT = """
You are an expert agency business development manager and technical consultant.
You are preparing a pitch for a freelance/job posting lead from {source}.

Lead Information:
- Platform/Source: {source}
- Title/Business: {business_name}
- Category/Target: {category}
- Location: {city}, {country}
- Details & Context (Budget, Skills, Bids, Posting Description):
{notes}

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
  "issues_found": ["specific requirement, pain point, or technical challenge identified in the posting 1", "specific requirement or pain point 2", ...],
  "opportunities": ["how we can exceed their expectations or deliver massive value 1", "another value-add or solution option 2", ...],
  "pitch_angle": "the single most compelling pitch angle — direct, highly specific to their project description, budget, and stated technology needs"
}}

Be concrete and extremely specific. Ground your points directly in their posting details. Max 5 issues, max 4 opportunities.
"""

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
    source = lead_data.get("source", "google_maps")
    
    if source in ["upwork", "freelancer", "fiverr", "linkedin"]:
        prompt = PLATFORM_ANALYSIS_PROMPT.format(
            source=source.title(),
            business_name=lead_data.get("business_name", "Unknown Posting"),
            category=lead_data.get("category", "Project"),
            city=lead_data.get("city", "Remote"),
            country=lead_data.get("country", "Global"),
            notes=lead_data.get("notes", "No description provided.")
        )
    else:
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
        client = _get_client()
        response = client.models.generate_content(
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

PLATFORM_MESSAGE_PROMPT = """
You are an expert agency proposal writer and copywriter specializing in winning high-value freelance clients and business leads on platforms like Upwork, Freelancer, Fiverr, and LinkedIn.
Write a personalized proposal pitch and outreach sequence for this posting.

Project Posting Details:
- Platform/Source: {source}
- Title/Business Name: {business_name}
- Category: {category}
- Location: {city}, {country}
- Key Stated Requirements/Pain Points: {issues}
- Core Strategy/Pitch Angle: {pitch_angle}
- Project Details & Budget (from notes):
{notes}
- Sender Name: {sender_name}

Requirements:
- cold_email: This will be the main Proposal/Direct Pitch (100-140 words). Speak directly to their project description, budget, and stated requirements. Be professional, custom, and authoritative. Do NOT mention Google Maps. Do mention that you saw their posting on {source} and have exactly what they need.
  End with a direct low-friction CTA (scheduling a brief chat, sharing previous case study, or a free initial loom wireframe/strategy).
- email_subject: A highly relevant, eye-catching subject line (max 60 chars) referencing their project title or platform posting (e.g., "Re: Upwork - Custom WordPress Rebuild Proposal").
- whatsapp_message: A brief, professional message (50-70 words) for direct follow-up. Very personalized to their project.
- followup_1: A 3-day follow-up message highlighting a similar project you solved or a helpful advice tip for their exact problem.
- followup_2: A 7-day final follow-up checking if they've already hired someone, offering a final free strategic tip or consultation.

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
  "email_subject": "...",
  "cold_email": "...",
  "whatsapp_message": "...",
  "followup_1": "...",
  "followup_2": "..."
}}
"""

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
    source = lead_data.get("source", "google_maps")

    if source in ["upwork", "freelancer", "fiverr", "linkedin"]:
        prompt = PLATFORM_MESSAGE_PROMPT.format(
            source=source.title(),
            business_name=lead_data.get("business_name", "your business"),
            category=lead_data.get("category", "business"),
            city=lead_data.get("city", "Remote"),
            country=lead_data.get("country", "Global"),
            issues=issues_str,
            pitch_angle=pitch,
            notes=lead_data.get("notes", ""),
            sender_name=SENDER_NAME,
        )
    else:
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
    if source in ["upwork", "freelancer", "fiverr", "linkedin"]:
        platform_name = source.title()
        clean_title = re.sub(r"^\[.*?\]\s*", "", name)
        return {
            "email_subject": f"Proposal: {clean_title} — expert agency services",
            "cold_email": (
                f"Hi,\n\nI saw your posting on {platform_name} regarding '{clean_title}' and wanted to reach out directly.\n\n"
                f"Our agency specializes in exactly what you are looking for — particularly in {lead_data.get('category', 'web design and SEO')}.\n\n"
                f"I've reviewed the requirements you outlined in your posting and would love to help you build this successfully. "
                f"Would you be open to a quick 5-minute chat or a free Loom wireframe walkthrough this week?\n\n"
                f"Best regards,\n{SENDER_NAME}"
            ),
            "whatsapp_message": (
                f"Hi! I saw your project '{clean_title}' on {platform_name}. "
                f"I'd love to share a quick advice video or previous case study. "
                f"Let me know if we can connect! 🙂"
            ),
            "followup_1": (
                f"Hi,\n\nFollowing up on my proposal for your {platform_name} posting: '{clean_title}'.\n\n"
                f"I wanted to share a link to a project we recently finished that had almost identical requirements. "
                f"Let me know if you'd like to take a look.\n\nBest,\n{SENDER_NAME}"
            ),
            "followup_2": (
                f"Hi,\n\nI hope your search for the right {platform_name} partner is going great.\n\n"
                f"If you are still looking, I'd love to offer a free 15-minute consultation to map out your project details, absolutely free of charge. "
                f"Is it worth a quick chat before you make your final choice?\n\nBest,\n{SENDER_NAME}"
            ),
        }

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
