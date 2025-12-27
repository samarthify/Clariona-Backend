#!/usr/bin/env python3
"""Count the new keywords list"""

keywords = [
    "Tinubu BAT",
    "President Of Nigeria",
    "Bola Ahmed Tinubu",
    "Peter Obi Atiku",
    "PDP Nigeria",
    "Labour Party Nigeria APC Nigeria",
    "INEC NNPC",
    "Nigerian Economy Wale Edun",
    "EndSARS EndBadGovernance",
    "NERC EFCC",
    "Adebayo Adelabu",
    "Information Minister Mohammed Idris",
    "Banditry Nigeria IPOB"
]

print(f"Total keywords: {len(keywords)}")
print("\nKeywords list:")
for i, kw in enumerate(keywords, 1):
    print(f"  {i}. {kw}")







