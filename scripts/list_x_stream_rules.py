#!/usr/bin/env python3
"""
List active X stream rules from DB and optionally from X API.

Usage:
  python scripts/list_x_stream_rules.py           # DB only
  python scripts/list_x_stream_rules.py --api    # DB + X API
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
load_dotenv(project_root / "config" / ".env", override=False)

from api.database import SessionLocal
from api.models import XStreamRule
from services.x_stream_rules_manager import XStreamRulesManager


def main():
    ap = argparse.ArgumentParser(description="List active X stream rules")
    ap.add_argument("--api", action="store_true", help="Also fetch and show rules from X API")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        # DB: active rules
        active = db.query(XStreamRule).filter(XStreamRule.is_active == True).order_by(XStreamRule.id).all()
        inactive = db.query(XStreamRule).filter(XStreamRule.is_active == False).order_by(XStreamRule.id).all()

        print("=== X stream rules (DB) ===")
        print(f"Active:   {len(active)}")
        for r in active:
            tag = f" tag={r.tag}" if r.tag else ""
            xid = f" x_rule_id={r.x_rule_id}" if r.x_rule_id else ""
            pri = f" priority={r.priority_level}" if r.priority_level is not None else ""
            val = r.value if len(r.value) <= 80 else r.value[:77] + "..."
            print(f"  id={r.id}{tag}{xid}{pri}")
            print(f"    value: {val}")
        if inactive:
            print(f"\nInactive: {len(inactive)}")
            for r in inactive:
                print(f"  id={r.id} tag={r.tag or '-'} value={r.value[:50]}...")

        if args.api:
            mgr = XStreamRulesManager(db)
            x_rules = mgr.get_x_rules()
            print("\n=== X API (live) ===")
            print(f"Rules on API: {len(x_rules)}")
            for r in x_rules:
                vid = r.get("id")
                tag = r.get("tag") or "-"
                val = r.get("value", "")
                if len(val) > 60:
                    val = val[:57] + "..."
                print(f"  id={vid} tag={tag} value={val}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
