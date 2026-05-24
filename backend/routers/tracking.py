"""
Email Tracking Router
Serves the 1x1 tracking pixel and handles click-through redirects.
Logs open/click events to the OutreachLog table.
"""
import base64
import datetime
from urllib.parse import unquote

from fastapi import APIRouter, Response
from fastapi.responses import RedirectResponse

from database import SessionLocal, OutreachLog

router = APIRouter(prefix="/api/track", tags=["tracking"])

# 1x1 transparent GIF (35 bytes)
TRACKING_PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


@router.get("/open/{tracking_id}")
def track_open(tracking_id: str):
    """
    Called when an email client loads the tracking pixel.
    Logs the open event and returns a transparent 1x1 GIF.
    """
    db = SessionLocal()
    try:
        log = db.query(OutreachLog).filter(
            OutreachLog.tracking_id == tracking_id
        ).first()

        if log:
            log.email_opened = True
            log.open_count = (log.open_count or 0) + 1
            if not log.email_opened_at:
                log.email_opened_at = datetime.datetime.utcnow()
            db.commit()
            print(f"[Tracking] Email opened — tracking_id={tracking_id}, opens={log.open_count}")

    except Exception as e:
        print(f"[Tracking] Open tracking error: {e}")
    finally:
        db.close()

    return Response(
        content=TRACKING_PIXEL,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/click/{tracking_id}")
def track_click(tracking_id: str, url: str = ""):
    """
    Called when a tracked link in an email is clicked.
    Logs the click event then redirects to the original URL.
    """
    db = SessionLocal()
    try:
        log = db.query(OutreachLog).filter(
            OutreachLog.tracking_id == tracking_id
        ).first()

        if log:
            log.link_clicked = True
            if not log.link_clicked_at:
                log.link_clicked_at = datetime.datetime.utcnow()
            db.commit()
            print(f"[Tracking] Link clicked — tracking_id={tracking_id}")

    except Exception as e:
        print(f"[Tracking] Click tracking error: {e}")
    finally:
        db.close()

    # Redirect to destination
    destination = unquote(url) if url else "https://google.com"
    return RedirectResponse(url=destination, status_code=302)
