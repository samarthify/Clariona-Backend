#!/usr/bin/env python3
"""Debug script to test the mapping function."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "src"))

from processing.governance_categories import map_to_closest_category, FEDERAL_MINISTRIES

# Test cases based on the actual results we saw
test_cases = [
    ("homosexuality allegations social stigma", "negative"),
    ("rabid bat Monterey County health risks", "negative"), 
    ("Olubadan Peter Obi tension leaders", "neutral"),
    ("governance criticism achievements understanding interview", "positive"),
    ("library renovation new aircraft educational infrastructure government commissioning", "positive"),
    ("Buhari clarity of power president of Nigeria", "positive"),
    ("governance dialogue corruption political dynamics", "negative"),
    ("lyssavirus bat rabies health crisis medical care", "negative"),
]

print("=== TESTING MAPPING FUNCTION ===")
print(f"Available federal ministries: {len(FEDERAL_MINISTRIES)}")
print()

for text, sentiment in test_cases:
    result = map_to_closest_category(text, sentiment)
    print(f"Text: '{text}'")
    print(f"Sentiment: {sentiment}")
    print(f"Mapped to: {result}")
    print(f"Ministry: {FEDERAL_MINISTRIES.get(result, 'NOT FOUND')}")
    print("-" * 50)

