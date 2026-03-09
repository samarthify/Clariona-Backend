#!/usr/bin/env python3
"""
Sync x_stream_rules from DB to X API. Run on-demand after adding/removing rules.

Usage:
  python scripts/sync_x_stream_rules.py
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
load_dotenv(project_root / "config" / ".env", override=False)

from api.database import SessionLocal
from services.x_stream_rules_manager import XStreamRulesManager


def main():
    db = SessionLocal()
    try:
        mgr = XStreamRulesManager(db)
        result = mgr.sync_rules_to_x_api()
        print(f"Sync result: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
