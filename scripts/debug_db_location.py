
import sys
import os
from pathlib import Path
from sqlalchemy import text

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.api.database import SessionLocal
from src.api.models import SentimentData
from src.services.data_ingestor import DataIngestor

def debug_db():
    session = SessionLocal()
    try:
        print("--- Database Statistics ---")
        total = session.query(SentimentData).count()
        null_loc = session.query(SentimentData).filter(SentimentData.user_location.is_(None)).count()
        empty_loc = session.query(SentimentData).filter(SentimentData.user_location == '').count()
        valid_loc = session.query(SentimentData).filter(SentimentData.user_location != None, SentimentData.user_location != '').count()
        
        print(f"Total Records: {total}")
        print(f"NULL user_location: {null_loc}")
        print(f"Empty user_location: {empty_loc}")
        print(f"Valid user_location: {valid_loc}")
        
        # Test Insertion
        print("\n--- Testing Live Insertion ---")
        ingestor = DataIngestor(session)
        
        test_url = "apify://debug/location_test_" + os.urandom(4).hex()
        raw_record = {
            "url": test_url,
            "text": "Debug test for location",
            "author": {
                "location": "Debug City, Testland",
                "name": "Debug User"
            },
            "platform": "debug"
        }
        
        print(f"Inserting test record: {test_url}")
        result = ingestor.insert_record(raw_record, commit=True, log_stored=True)
        print(f"Insertion result: {result}")
        
        # Verify
        stored = session.query(SentimentData).filter(SentimentData.url == test_url).first()
        if stored:
            print(f"Stored user_location: '{stored.user_location}'")
            if stored.user_location == "Debug City, Testland":
                print("SUCCESS: user_location persisted correctly.")
            else:
                print("FAILURE: user_location is missing or incorrect.")
        else:
            print("FAILURE: Record not found.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    debug_db()
