#!/usr/bin/env python3
"""
Add a rule to x_stream_rules table. Sync to X API happens on next service start
or when XStreamRulesManager.sync_rules_to_x_api() is called.

Usage:
  python scripts/add_x_stream_rule.py "(fuel OR petrol) lang:en -is:retweet" fuel_pricing
  python scripts/add_x_stream_rule.py "#Nigeria president" nigeria_president
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
load_dotenv(project_root / "config" / ".env", override=False)

from api.database import SessionLocal
from api.models import XStreamRule


def main():
    if len(sys.argv) < 2:
        print("Usage: python add_x_stream_rule.py <value> [tag]")
        print("  value: X API filterlang expression (e.g. 'cat has:images')")
        print("  tag: optional label (e.g. fuel_pricing)")
        sys.exit(1)
    value = sys.argv[1]
    tag = sys.argv[2] if len(sys.argv) > 2 else None

    db = SessionLocal()
    try:
        rule = XStreamRule(value=value, tag=tag, is_active=True)
        db.add(rule)
        db.commit()
        print(f"Added rule id={rule.id} value={value[:50]}... tag={tag}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
