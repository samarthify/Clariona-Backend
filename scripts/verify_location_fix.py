
import sys
import os
import logging
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.getcwd())

from src.services.data_ingestor import DataIngestor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_location_parsing():
    # Mock DB session
    mock_session = MagicMock()
    ingestor = DataIngestor(mock_session)

    # Test Case 1: TikTok with POI
    tiktok_record = {
        'url': 'https://www.tiktok.com/@user/video/123456',
        'platform': 'tiktok',
        'poi': {
            'name': 'Eiffel Tower',
            'address': 'Champ de Mars, 5 Av. Anatole France, 75007 Paris, France'
        },
        'author': {'name': 'TikTok User'}
    }
    
    logger.info("Testing TikTok Parsing...")
    normalized_tiktok = ingestor.normalize_record(tiktok_record)
    if normalized_tiktok.get('user_location') == 'Eiffel Tower':
        logger.info("✅ TikTok location parsed correctly: 'Eiffel Tower'")
    else:
        logger.error(f"❌ TikTok parsing failed. Got: {normalized_tiktok.get('user_location')}")

    # Test Case 2: Twitter with user_info
    twitter_record = {
        'url': 'https://twitter.com/user/status/123456',
        'platform': 'twitter',
        'user_info': {
            'location': 'New York, NY',
            'screen_name': 'twitter_user'
        },
        'user': {} # empty user obj as seen in logs
    }
    
    logger.info("Testing Twitter Parsing...")
    normalized_twitter = ingestor.normalize_record(twitter_record)
    if normalized_twitter.get('user_location') == 'New York, NY':
        logger.info("✅ Twitter location parsed correctly: 'New York, NY'")
    else:
        logger.error(f"❌ Twitter parsing failed. Got: {normalized_twitter.get('user_location')}")
        
    # Test Case 3: Instagram (Negative Test - should still be None if no info)
    instagram_record = {
        'url': 'https://instagram.com/p/12345',
        'platform': 'instagram',
        'ownerUsername': 'insta_user'
        # No location info
    }
    logger.info("Testing Instagram Parsing (Expect None)...")
    normalized_insta = ingestor.normalize_record(instagram_record)
    if normalized_insta.get('user_location') is None:
        logger.info("✅ Instagram correctly has no location")
    else:
        logger.warning(f"⚠️ Instagram unexpectedly found location: {normalized_insta.get('user_location')}")

if __name__ == "__main__":
    test_location_parsing()
