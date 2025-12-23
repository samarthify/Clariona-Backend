#!/usr/bin/env python3
"""
Show all TikTok actor parameters being sent
"""

import json
from datetime import datetime, timezone

print("=" * 80)
print("TikTok Actor Parameters - Complete Overview")
print("=" * 80)

# Simulate the actual parameters being sent
query = "test"
clean_query = query.replace("#", "").strip()
max_actor_results = 10

# For paid scraper (supports_filters = True)
print("\n1. PAID SCRAPER (clockworks/tiktok-scraper):")
print("-" * 80)
run_input_paid = {
    "hashtags": [clean_query],  # Array of hashtags (without # symbol)
    "resultsPerPage": max_actor_results,  # Number of videos per hashtag
    "oldestPostDateUnified": "1",  # Hardcoded: today's posts only
}

# Add newestPostDate if until_date provided
until_datetime = datetime(2025, 1, 15, tzinfo=timezone.utc)
run_input_paid["newestPostDate"] = until_datetime.strftime("%Y-%m-%d")

print(json.dumps(run_input_paid, indent=2))

print("\n✅ Parameters for paid scraper:")
print("   - hashtags: array of hashtags")
print("   - resultsPerPage: number of videos")
print("   - oldestPostDateUnified: '1' (hardcoded - today's posts)")
print("   - newestPostDate: date string (if until_date provided)")

# For free scraper (supports_filters = False)
print("\n\n2. FREE SCRAPER (clockworks/free-tiktok-scraper):")
print("-" * 80)
run_input_free = {
    "searchTerms": [query],
    "resultsLimit": max_actor_results,
    "searchType": "hashtag",
    "includeComments": True,
    "includeShares": True,
    "downloadVideos": False
}

print(json.dumps(run_input_free, indent=2))

print("\n✅ Parameters for free scraper:")
print("   - searchTerms: array of search terms")
print("   - resultsLimit: number of results")
print("   - searchType: 'hashtag'")
print("   - includeComments: boolean")
print("   - includeShares: boolean")
print("   - downloadVideos: false")

print("\n" + "=" * 80)
print("Note: Post-collection date filtering applies to both scrapers")
print("=" * 80)



