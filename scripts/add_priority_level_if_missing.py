#!/usr/bin/env python3
"""
Add x_stream_rules.priority_level if missing (fix for partial migration).
Run once: python scripts/add_priority_level_if_missing.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
load_dotenv(project_root / "config" / ".env", override=False)

from sqlalchemy import create_engine, text
from api.database import engine

def main():
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'x_stream_rules' AND column_name = 'priority_level'
        """))
        if r.fetchone():
            print("Column priority_level already exists. Nothing to do.")
            return
        conn.execute(text("ALTER TABLE x_stream_rules ADD COLUMN priority_level SMALLINT NULL"))
        conn.commit()
        print("Added column x_stream_rules.priority_level.")
    print("Done. Restart the streaming service so Rising/Stabilization jobs work.")

if __name__ == "__main__":
    main()
