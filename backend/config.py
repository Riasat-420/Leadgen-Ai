import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini AI ──────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Gmail ──────────────────────────────────────────────────
GMAIL_USER: str = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
SENDER_NAME: str = os.getenv("SENDER_NAME", "Your Agency")

# ── Twilio SMS (optional) ──────────────────────────────────
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")

# ── Database ───────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./leadgen.db")

# ── Outreach limits ────────────────────────────────────────
MAX_EMAILS_PER_DAY: int = int(os.getenv("MAX_EMAILS_PER_DAY", "50"))
FOLLOWUP_DAY_1: int = int(os.getenv("FOLLOWUP_DAY_1", "3"))
FOLLOWUP_DAY_2: int = int(os.getenv("FOLLOWUP_DAY_2", "7"))

# ── Scraping ───────────────────────────────────────────────
SCRAPE_DELAY_MIN: float = 2.0
SCRAPE_DELAY_MAX: float = 5.0
DEFAULT_MAX_RESULTS: int = 30

# ── Server ─────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# ── Pre-configured target markets ─────────────────────────
DEFAULT_TARGETS = [
    {"category": "real estate agency", "city": "Dubai", "country": "UAE"},
    {"category": "cafe", "city": "Montreal", "country": "Canada"},
    {"category": "restaurant", "city": "Montreal", "country": "Canada"},
]
