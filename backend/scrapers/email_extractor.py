"""
Email Extractor
Visits a business website and extracts real contact email addresses.
Checks homepage + /contact, /about, /contact-us sub-pages.
Filters out noreply, wordpress, and other junk addresses.
"""
import re
import httpx
from bs4 import BeautifulSoup
from typing import Optional
from urllib.parse import urljoin, urlparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Regex pattern to find email addresses in raw HTML
EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)

# Common junk/generic emails to skip
JUNK_PATTERNS = re.compile(
    r'noreply|no-reply|donotreply|example\.com|sentry\.io|'
    r'wix\.com|wordpress\.com|squarespace\.com|godaddy\.com|'
    r'schema\.org|w3\.org|placeholder|test@|admin@admin|'
    r'@2x\.|\.png|\.jpg|\.gif|\.svg|\.webp',
    re.IGNORECASE
)

# Contact-related sub-pages to try
CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us", "/reach-us", "/get-in-touch"]


def decode_cloudflare_email(cfemail: str) -> str:
    """Decode a Cloudflare hex-obfuscated email address."""
    try:
        k = int(cfemail[:2], 16)
        return "".join(
            chr(int(cfemail[i:i+2], 16) ^ k)
            for i in range(2, len(cfemail), 2)
        )
    except Exception:
        return ""


def _extract_emails_from_html(html: str) -> list[str]:
    """Extract and clean email addresses from raw HTML."""
    # De-obfuscate common text layouts
    html_clean = (
        html.replace("&#64;", "@")
        .replace("%40", "@")
        .replace("&#46;", ".")
        .replace(" [at] ", "@")
        .replace(" (at) ", "@")
        .replace("[at]", "@")
        .replace("(at)", "@")
        .replace(" [dot] ", ".")
        .replace(" (dot) ", ".")
        .replace("[dot]", ".")
        .replace("(dot)", ".")
    )

    soup = BeautifulSoup(html_clean, "lxml")
    emails = []

    # 1. Parse Cloudflare-obfuscated emails
    for el in soup.find_all(attrs={"data-cfemail": True}):
        decoded = decode_cloudflare_email(el["data-cfemail"])
        if decoded and EMAIL_PATTERN.match(decoded):
            emails.append(decoded.lower().strip())

    for el in soup.select(".__cf_email__"):
        cf = el.get("data-cfemail")
        if cf:
            decoded = decode_cloudflare_email(cf)
            if decoded and EMAIL_PATTERN.match(decoded):
                emails.append(decoded.lower().strip())

    # 2. Parse mailto links (highest quality)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0].strip().lower()
            if email and EMAIL_PATTERN.match(email):
                emails.append(email)

    # 3. Scan full cleaned HTML text for email patterns
    raw_emails = EMAIL_PATTERN.findall(html_clean)
    for e in raw_emails:
        emails.append(e.lower().strip())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for e in emails:
        if e not in seen:
            seen.add(e)
            unique.append(e)

    return unique


def _filter_emails(emails: list[str], domain: str = "") -> list[str]:
    """Remove junk emails and prioritize domain-matching ones."""
    cleaned = []
    for e in emails:
        if JUNK_PATTERNS.search(e):
            continue
        if len(e) > 100:
            continue
        if e.count("@") != 1:
            continue
        cleaned.append(e)

    if not cleaned:
        return []

    # Prefer emails matching the business domain
    if domain:
        domain_part = domain.replace("www.", "").split("/")[0]
        domain_emails = [e for e in cleaned if domain_part in e]
        if domain_emails:
            return domain_emails

    # Prefer common contact-style prefixes
    preferred_prefixes = ["contact", "hello", "info", "enquiries", "enquiry",
                          "sales", "support", "office", "team", "hi"]
    for prefix in preferred_prefixes:
        found = [e for e in cleaned if e.startswith(prefix + "@")]
        if found:
            return found

    return cleaned


def extract_emails_from_website(url: Optional[str], timeout: int = 10) -> Optional[str]:
    """
    Visit a business website and extract the best contact email.
    Returns a single email string or None.
    """
    if not url or not url.startswith("http"):
        return None

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    domain = parsed.netloc

    all_emails: list[str] = []
    pages_to_check = [url] + [urljoin(base_url, path) for path in CONTACT_PATHS]

    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=HEADERS,
        verify=False,
    ) as client:
        for page_url in pages_to_check:
            try:
                resp = client.get(page_url)
                if resp.status_code == 200:
                    found = _extract_emails_from_html(resp.text)
                    all_emails.extend(found)

                    # If we found good emails on this page, stop early
                    filtered = _filter_emails(all_emails, domain)
                    if filtered:
                        return filtered[0]
            except Exception:
                continue

    filtered = _filter_emails(all_emails, domain)
    return filtered[0] if filtered else None
