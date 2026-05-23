# ⚡ LeadGen AI — Lead Generation & Outreach Automation

A full-stack AI-powered system that **scrapes Google Maps**, **analyzes businesses with Gemini AI**, **scores leads**, **generates personalized outreach messages**, and **sends automated email sequences** — all through a beautiful SaaS-style CRM dashboard.

---

## 🚀 Quick Start

### 1. Install
```bash
# Double-click install.bat, or run manually:
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env and fill in:
#   GEMINI_API_KEY=your_key
#   GMAIL_USER=you@gmail.com
#   GMAIL_APP_PASSWORD=xxxx_xxxx_xxxx_xxxx
```

> **Gmail App Password**: Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
> Make sure 2FA is enabled first, then generate an App Password for "Mail".

### 3. Run
```bash
start.bat
# Or: cd backend && python -m uvicorn main:app --reload
```

### 4. Open Dashboard
```
http://localhost:8000
```

---

## 🎯 Target Markets (Pre-configured)

| Market | City | Country |
|--------|------|---------|
| Real Estate Agencies | Dubai | UAE |
| Cafes | Montreal | Canada |
| Restaurants | Montreal | Canada |

Click the **Quick Targets** buttons in the Scraper view to launch instantly.

---

## 🏗️ System Architecture

```
[Google Maps] ──► [Playwright Scraper] ──► [SQLite DB]
                                               │
                                    [Website Checker (httpx)]
                                               │
                                    [Gemini AI Analyzer]
                                               │
                                    [Message Generator]
                                               │
                              ┌────────────────┴──────────────┐
                         [Gmail Email]              [WhatsApp (manual)]
                              │
                    [APScheduler Follow-ups]
                              │
                       [CRM Dashboard]
```

---

## 🔄 Workflow

### Step 1 — Scrape
- Go to **Scraper** tab
- Choose a Quick Target or enter custom category + city
- Click **🚀 Start Scraping**
- Watch real-time progress bar

### Step 2 — Analyze
- Go to **Leads** tab
- Click 🤖 on any lead (or bulk select → Analyze)
- System checks website health and runs Gemini AI analysis
- Lead gets a score 0–10

### Step 3 — Generate Messages
- Click ✍️ on an analyzed lead
- Gemini generates:
  - Personalized cold email + subject
  - WhatsApp intro message
  - Follow-up #1 (day 3)
  - Follow-up #2 (day 7)

### Step 4 — Send
- Go to **Outreach** tab
- Review messages for ready leads
- Click **📧 Send** to dispatch
- System auto-schedules follow-ups via APScheduler

### Step 5 — Track
- Mark replies from the lead detail modal
- Track conversion rate on Dashboard
- View full email history per lead

---

## 📊 Dashboard Views

| View | Description |
|------|-------------|
| 📊 Dashboard | Stats: total leads, hot leads, contacted, conversion rate |
| 👥 Leads | Filterable table with all leads, scores, statuses |
| 🕷️ Scraper | Launch jobs, live progress, job history |
| 📧 Outreach | Review & send messages, follow-up queue, email log |
| 📈 Analytics | Score distribution, pipeline breakdown, city charts |

---

## 📧 Outreach Options

| Method | How |
|--------|-----|
| **Cold Email** | Automated via Gmail SMTP |
| **Follow-up #1** | Auto-sent day 3 by APScheduler |
| **Follow-up #2** | Auto-sent day 7 by APScheduler |
| **WhatsApp** | AI-generated message for manual send |

---

## ⚙️ Configuration (.env)

```env
GEMINI_API_KEY=AIza...         # Required for AI analysis
GEMINI_MODEL=gemini-2.0-flash  # Or gemini-1.5-pro for higher quality

GMAIL_USER=you@gmail.com       # Gmail address
GMAIL_APP_PASSWORD=xxxx        # Gmail App Password (not your login password)
SENDER_NAME=Your Name          # Appears as sender name

MAX_EMAILS_PER_DAY=50          # Daily send limit (keep low for domain warmup)
FOLLOWUP_DAY_1=3               # Days before first follow-up
FOLLOWUP_DAY_2=7               # Days before second follow-up
```

---

## 🛡️ Safety Notes

- **Respect daily email limits** — 50/day is safe for a fresh Gmail
- **Warm your domain** before increasing volume
- All messages are **personalized** (not mass spam)
- Always include **unsubscribe option** (included automatically)
- Google Maps scraping uses human-like delays (2–5s between requests)

---

## 📁 Project Structure

```
leadgen-ai/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings from .env
│   ├── database.py          # SQLAlchemy models
│   ├── scrapers/
│   │   ├── google_maps.py   # Playwright scraper
│   │   └── website_checker.py
│   ├── ai/
│   │   └── analyzer.py      # Gemini AI + message gen
│   ├── outreach/
│   │   └── email_sender.py  # Gmail SMTP + APScheduler
│   └── routers/             # FastAPI route handlers
├── frontend/
│   ├── index.html           # SaaS CRM dashboard
│   ├── css/style.css
│   └── js/*.js
├── requirements.txt
├── .env.example
├── install.bat
└── start.bat
```

---

## 🔗 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/scrape/start` | Launch a scrape job |
| GET | `/api/scrape/status/{id}` | Job progress |
| GET | `/api/leads` | List leads (filterable) |
| POST | `/api/leads/{id}/analyze` | Run AI analysis |
| POST | `/api/leads/{id}/generate-messages` | Generate outreach |
| POST | `/api/outreach/send-email` | Send email |
| GET | `/api/dashboard/stats` | Dashboard metrics |
| 📖 | `/docs` | Interactive API docs |

---

*Built with FastAPI · Playwright · Gemini AI · Gmail SMTP · Chart.js*
