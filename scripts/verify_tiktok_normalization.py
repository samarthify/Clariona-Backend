
import logging
import sys
import os
from datetime import datetime

# Adjust path to include src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.services.data_ingestor import DataIngestor
from unittest.mock import MagicMock

# Setup logging
logging.basicConfig(level=logging.DEBUG)

def test_tiktok_normalization():
    print("Testing TikTok Normalization...")
    
    # Mock data based on user report
    raw_record = {
        "postPage": "https://www.tiktok.com/@kashiimshettima/video/7596718807121480967",
        "title": "President Bola Tinubu congratulates the Super Eagles...",
        "views": 195032,
        "likes": 12190,
        "comments": 87,
        "shares": 117,
        "bookmarks": 769,
        "uploadedAt": "2026-01-18T15:08:54.000Z",
        "channel": {
            "name": "KASHIM SHETTIMA",
            "username": "kashiimshettima",
            "id": "7290581174035514374",
            "url": "https://www.tiktok.com/@kashiimshettima",
            "avatar": "https://example.com/avatar.jpg"
        },
        "video": {
            "url": "https://v45.tiktokcdn-eu.com/..."
        }
    }
    
    # Mock session
    mock_session = MagicMock()
    ingestor = DataIngestor(mock_session)
    
    normalized = ingestor.normalize_record(raw_record)
    
    print("\n--- Normalized Record ---")
    for k, v in normalized.items():
        print(f"{k}: {v}")
        
    # Assertions
    expected_url = "https://www.tiktok.com/@kashiimshettima/video/7596718807121480967"
    assert normalized['url'] == expected_url, f"URL mismatch: got {normalized.get('url')}, expected {expected_url}"
    print(f"\n[PASS] URL correctly mapped to {normalized['url']}")
    
    expected_source_url = expected_url
    assert normalized['source_url'] == expected_source_url, f"source_url mismatch: got {normalized.get('source_url')}"
    print(f"[PASS] source_url correctly mapped to {normalized['source_url']}")

    assert normalized['user_handle'] == "kashiimshettima", f"user_handle mismatch: got {normalized.get('user_handle')}"
    print(f"[PASS] user_handle correctly mapped to {normalized['user_handle']}")
    
    assert normalized['user_name'] == "KASHIM SHETTIMA", f"user_name mismatch: got {normalized.get('user_name')}"
    print(f"[PASS] user_name correctly mapped to {normalized['user_name']}")
    
    assert normalized['user_avatar'] == "https://example.com/avatar.jpg", f"user_avatar mismatch: got {normalized.get('user_avatar')}"
    print(f"[PASS] user_avatar correctly mapped to {normalized['user_avatar']}")
    
    # Check likes + bookmarks
    # Original likes: 12190, Bookmarks: 769. Total should be 12959
    expected_likes = 12190 + 769
    assert normalized['likes'] == expected_likes, f"likes mismatch: got {normalized.get('likes')}, expected {expected_likes}"
    print(f"[PASS] likes correctly calculated (likes + bookmarks) = {normalized['likes']}")

    print("\nAll checks passed!")

if __name__ == "__main__":
    test_tiktok_normalization()
