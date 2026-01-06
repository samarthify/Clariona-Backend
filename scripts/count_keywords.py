#!/usr/bin/env python3
"""Quick script to count keywords"""

keywords = [
    "Tinubu",
    "President Of Nigeria",
    "President Tinubu",
    "President Nigeria",
    "Nigerian President",
    "Bola Ahmed Tinubu",
    "Bola Tinubu",
    "BAT",
    "Peter Obi",
    "Atiku",
    "PDP Nigeria",
    "Labour Party Nigeria",
    "APC Nigeria",
    "INEC",
    "NNPC",
    "Wale Edun",
    "Nigerian Economy",
    "EndSARS / EndBadGovernance",
    "Power: NERC",
    "EFCC",
    "Adebayo Adelabu",
    "Information Minister Mohammed Idris",
    "Banditry Nigeria",
    "IPOB"
]

print(f"Total keywords: {len(keywords)}")
print("\nKeywords list:")
for i, kw in enumerate(keywords, 1):
    print(f"  {i}. {kw}")







