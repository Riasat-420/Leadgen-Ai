"""
Settings Router — Exposes endpoints to retrieve, update, and test SMTP/IMAP settings.
"""
import smtplib
import ssl
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_setting, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    smtp_host: str
    smtp_port: str
    smtp_user: str
    smtp_password: str
    smtp_sender_name: str
    smtp_encryption: str  # ssl | starttls | none
    imap_host: str
    imap_port: str


@router.get("")
def get_settings():
    return {
        "smtp_host": get_setting("smtp_host", ""),
        "smtp_port": get_setting("smtp_port", "587"),
        "smtp_user": get_setting("smtp_user", ""),
        "smtp_password": "●●●●●●●●" if get_setting("smtp_password", "") else "",
        "smtp_sender_name": get_setting("smtp_sender_name", ""),
        "smtp_encryption": get_setting("smtp_encryption", "starttls"),
        "imap_host": get_setting("imap_host", ""),
        "imap_port": get_setting("imap_port", "993"),
    }


@router.post("")
def update_settings(update: SettingsUpdate):
    set_setting("smtp_host", update.smtp_host.strip())
    set_setting("smtp_port", update.smtp_port.strip())
    set_setting("smtp_user", update.smtp_user.strip())
    
    password = update.smtp_password.strip()
    if password and password != "●●●●●●●●":
        set_setting("smtp_password", password)
        
    set_setting("smtp_sender_name", update.smtp_sender_name.strip())
    set_setting("smtp_encryption", update.smtp_encryption.strip())
    set_setting("imap_host", update.imap_host.strip())
    set_setting("imap_port", update.imap_port.strip())
    
    return {"message": "Settings updated successfully"}


@router.post("/test")
def test_smtp_connection(update: SettingsUpdate):
    password = update.smtp_password.strip()
    if password == "●●●●●●●●":
        password = get_setting("smtp_password", "")
    
    user = update.smtp_user.strip()
    host = update.smtp_host.strip()
    encryption = update.smtp_encryption.strip()
    
    try:
        port = int(update.smtp_port.strip())
        if encryption == "ssl":
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=10, context=ctx) as server:
                server.login(user, password)
        elif encryption == "starttls":
            ctx = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(user, password)
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                if user and password:
                    server.login(user, password)
                    
        return {"success": True, "message": "SMTP connection & authentication successful!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SMTP connection failed: {str(e)}")
