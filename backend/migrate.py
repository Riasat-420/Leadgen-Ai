"""
Database Migration Script for LeadGen AI
Safely adds missing Phase 2 columns to the SQLite database without losing existing data.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "leadgen.db")

def run_migrations():
    print(f"[Migration] Checking database schema at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("[Migration] Database file does not exist yet. It will be initialized on startup.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── 1. Check & Update 'leads' table ───────────────────────────
    cursor.execute("PRAGMA table_info(leads)")
    leads_columns = [col[1] for col in cursor.fetchall()]

    if "source" not in leads_columns:
        print("[Migration] Adding 'source' column to 'leads' table...")
        try:
            cursor.execute("ALTER TABLE leads ADD COLUMN source TEXT DEFAULT 'google_maps'")
            conn.commit()
            print("[Migration] 'source' column added successfully.")
        except Exception as e:
            print(f"[Migration] Error adding 'source' column: {e}")

    # ── 2. Check & Update 'outreach_logs' table ──────────────────
    cursor.execute("PRAGMA table_info(outreach_logs)")
    outreach_columns = [col[1] for col in cursor.fetchall()]

    tracking_columns = {
        "tracking_id": "TEXT",
        "email_opened": "BOOLEAN DEFAULT 0",
        "email_opened_at": "TIMESTAMP",
        "link_clicked": "BOOLEAN DEFAULT 0",
        "link_clicked_at": "TIMESTAMP",
        "open_count": "INTEGER DEFAULT 0"
    }

    for col_name, col_type in tracking_columns.items():
        if col_name not in outreach_columns:
            print(f"[Migration] Adding '{col_name}' column to 'outreach_logs' table...")
            try:
                cursor.execute(f"ALTER TABLE outreach_logs ADD COLUMN {col_name} {col_type}")
                conn.commit()
                print(f"[Migration] '{col_name}' column added successfully.")
            except Exception as e:
                print(f"[Migration] Error adding '{col_name}' column: {e}")

    # Create indexes if they were added
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_leads_source ON leads (source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_outreach_logs_tracking_id ON outreach_logs (tracking_id)")
        conn.commit()
    except Exception as e:
        print(f"[Migration] Index creation warning: {e}")

    conn.close()
    print("[Migration] Schema checks and migrations completed successfully.")

if __name__ == "__main__":
    run_migrations()
