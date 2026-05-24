"""
LeadGen AI — FastAPI Application Entry Point
"""
import sys
import os

# Ensure backend/ is in path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from database import create_tables
from migrate import run_migrations
from outreach.email_sender import start_scheduler, stop_scheduler
from routers import leads, scraper, outreach, dashboard
from routers import tracking

app = FastAPI(
    title="LeadGen AI",
    description="AI-powered lead generation and outreach automation",
    version="1.0.0",
)

# ── CORS ───────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────
app.include_router(leads.router)
app.include_router(scraper.router)
app.include_router(outreach.router)
app.include_router(dashboard.router)
app.include_router(tracking.router)

# ── Static Frontend ────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# ── Lifecycle ──────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    run_migrations()
    create_tables()
    start_scheduler()
    print("[LeadGen AI] Server running at http://localhost:8000")
    print("[LeadGen AI] Dashboard: http://localhost:8000")
    print("[LeadGen AI] API Docs:  http://localhost:8000/docs")


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()


# ── Health check ───────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "LeadGen AI"}


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
