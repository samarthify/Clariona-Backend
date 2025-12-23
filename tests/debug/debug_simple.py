#!/usr/bin/env python3
"""Simple debug to test the mapping function with actual AI suggestions."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "src"))

from processing.governance_categories import map_to_closest_category, FEDERAL_MINISTRIES

# Test what happens when we pass the actual AI suggestions that might be coming back
ai_suggestions = [
    "Ministry of Women Affairs and Social Development",
    "Ministry of Health", 
    "Ministry of Interior",
    "Ministry of Information and Culture",
    "Ministry of Education or Ministry of Aviation",
    "Presidency",
    "Ministry of Justice or Anti-Corruption Agencies"
]

print("=== TESTING AI SUGGESTIONS ===")
for suggestion in ai_suggestions:
    result = map_to_closest_category(suggestion, "negative")
    print(f"AI Suggestion: '{suggestion}'")
    print(f"Mapped to: {result}")
    print(f"Ministry: {FEDERAL_MINISTRIES.get(result, 'NOT FOUND')}")
    print("-" * 50)

