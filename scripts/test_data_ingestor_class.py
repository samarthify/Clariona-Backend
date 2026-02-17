
import sys
import os
import logging
from datetime import datetime

# Set path to project root
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('services.data_ingestor')
logger.setLevel(logging.INFO)

from src.services.data_ingestor import DataIngestor
from src.api.database import SessionLocal, engine
from src.api.models import Base

def test_upsert_backfill():
    session = SessionLocal()
    ingestor = DataIngestor(session)
    ingestor._batch_size = 1 # Force immediate write

    # 1. Insert initial record with user_location = None
    url = f"https://twitter.com/test_user/status/{int(datetime.now().timestamp())}"
    print(f"Testing with URL: {url}")

    record1 = {
        'url': url,
        'platform': 'twitter',
        'date': datetime.now(),
        'user_name': 'Test User',
        'user_handle': 'testuser',
        'user_location': None, # Initial insert has None
        'text': 'Initial tweet',
        'likes': 10,
        'retweets': 5,
        'comments': 1
    }

    print("Inserting record 1 (user_location=None)...")
    ingestor.process_record(record1)
    ingestor.flush()
    print("Record 1 inserted.")

    # 2. Upsert same record with NEW user_location
    # This triggers the ON CONFLICT... UPDATE logic where the error happens
    record2 = record1.copy()
    record2['user_location'] = "Lagos, Nigeria" # New value to backfill
    record2['likes'] = 20 # Update metric too

    print("Upserting record 2 (user_location='Lagos, Nigeria')...")
    try:
        ingestor.process_record(record2)
        ingestor.flush()
        print("SUCCESS: Record 2 upserted without error.")
    except Exception as e:
        print(f"FAILURE: Upsert failed with error: {e}")
        import traceback
        traceback.print_exc()

    session.close()

if __name__ == "__main__":
    try:
        test_upsert_backfill()
    except Exception as e:
        print(f"Test crashed: {e}")
