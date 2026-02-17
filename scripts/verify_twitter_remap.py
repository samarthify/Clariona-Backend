
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

def test_twitter_remapping():
    # Mock DB session
    mock_session = MagicMock()
    ingestor = DataIngestor(mock_session)

    # Test Case: New Twitter Actor Format (based on user input)
    twitter_record = {
        'tweet_id': '2013927070661853690',
        'text': '@SKefason Why are you not calling out El-rufai...',
        'user_info': {
            'screen_name': 'aminu_idrisa',
            'name': 'Wonderful_kano',
            'verified': False,
            'location': 'Kano, Nigeria' # Added for completeness based on previous task
        },
        'created_at': '2026-01-21 10:50:05 UTC',
        'retweets': 0,
        'favorites': 5, # Mapped to likes
        'replies': 2,   # Mapped to comments
        'quotes': 1,    # Added to comments
        'views': 100,   # Mapped to direct_reach
        'lang': 'en',
        'url': 'https://twitter.com/aminu_idrisa/status/2013927070661853690',
        'platform': 'twitter'
    }
    
    logger.info("Testing Twitter Field Remapping...")
    normalized = ingestor.normalize_record(twitter_record)
    
    # Verify User Fields
    if normalized.get('user_handle') == 'aminu_idrisa':
        logger.info("✅ user_handle correctly mapped from user_info.screen_name")
    else:
        logger.error(f"❌ user_handle failed. Got: {normalized.get('user_handle')}")

    if normalized.get('user_name') == 'Wonderful_kano':
        logger.info("✅ user_name correctly mapped from user_info.name")
    else:
        logger.error(f"❌ user_name failed. Got: {normalized.get('user_name')}")

    if normalized.get('user_location') == 'Kano, Nigeria':
        logger.info("✅ user_location correctly mapped from user_info.location")
    else:
        logger.error(f"❌ user_location failed. Got: {normalized.get('user_location')}")

    # Verify ID
    if normalized.get('original_id') == '2013927070661853690':
        logger.info("✅ original_id correctly mapped from tweet_id")
    else:
        logger.error(f"❌ original_id failed. Got: {normalized.get('original_id')}")

    # Verify Metrics
    if normalized.get('likes') == 5:
        logger.info("✅ likes correctly mapped from favorites")
    else:
        logger.error(f"❌ likes failed. Got: {normalized.get('likes')}")

    expected_comments = 2 + 1 # replies + quotes
    if normalized.get('comments') == expected_comments:
        logger.info(f"✅ comments correctly calculated (replies + quotes) = {expected_comments}")
    else:
        logger.error(f"❌ comments failed. Got: {normalized.get('comments')} (Expected {expected_comments})")

    if normalized.get('direct_reach') == 100:
        logger.info("✅ direct_reach correctly mapped from views")
    else:
        logger.error(f"❌ direct_reach failed. Got: {normalized.get('direct_reach')}")

if __name__ == "__main__":
    test_twitter_remapping()
