#!/usr/bin/env python3
"""Direct script to update keywords for Target Configuration #1"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import TargetIndividualConfiguration

# Parse the keywords from user input - 10 keywords total
keywords = [
    "Tinubu Presidency",
    "Obi Atiku PDP LP",
    "INEC Elections",
    "Fuel Subsidy NNPC Refineries",
    "Cost of Living Inflation Food Prices",
    "Protests #EndBadGovernance #DaysOfRage",
    "Power Grid Electricity Tariffs",
    "EFCC Corruption",
    "Banditry Kidnapping Insecurity",
    "IPOB Separatism"
]

db = SessionLocal()
try:
    config = db.query(TargetIndividualConfiguration).filter(
        TargetIndividualConfiguration.id == 1
    ).first()
    
    if not config:
        print("❌ Configuration with ID 1 not found.")
        sys.exit(1)
    
    old_keywords = config.query_variations or []
    config.query_variations = keywords
    db.commit()
    
    print("✅ Successfully updated keywords for Target Configuration #1")
    print(f"   Individual: {config.individual_name}")
    print(f"   User: {config.user_id}")
    print(f"\n   Old keywords ({len(old_keywords)}): {old_keywords}")
    print(f"\n   New keywords ({len(keywords)}):")
    for i, kw in enumerate(keywords, 1):
        print(f"      {i}. {kw}")
    
except Exception as e:
    db.rollback()
    print(f"❌ Error updating keywords: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()

