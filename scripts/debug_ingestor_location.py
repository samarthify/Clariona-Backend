
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path (parent of src)
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.services.data_ingestor import DataIngestor
from src.api.models import SentimentData

# Mock session since we won't write to DB
class MockSession:
    def query(self, *args): return self
    def filter(self, *args): return self
    def first(self): return None
    def execute(self, *args): pass
    def commit(self): pass
    def rollback(self): pass

def test_normalization():
    print("Testing DataIngestor normalization...")
    
    # Check if column exists in SQLAlchemy model
    columns = {c.name for c in SentimentData.__table__.columns}
    print(f"'user_location' in SentimentData columns: {'user_location' in columns}")

    ingestor = DataIngestor(MockSession())
    
    # Mock data record simulating collect_twitter_apify output
    raw_record = {
        "source": "X",
        "platform": "X",
        "type": "post",
        "post_id": "12345",
        "date": "2023-10-27T10:00:00",
        "text": "Hello world",
        "user_location": "Lagos, Nigeria",  # Explicitly provided
        "user_name": "Test User",
        "url": "https://twitter.com/test/status/12345"
    }
    
    normalized = ingestor.normalize_record(raw_record)
    
    print(f"Input user_location: {raw_record.get('user_location')}")
    print(f"Output user_location: {normalized.get('user_location')}")
    
    if normalized.get('user_location') == "Lagos, Nigeria":
        print("SUCCESS: user_location preserved.")
    else:
        print("FAILURE: user_location lost or modified.")

    # Test case 2: Location in author object (dict)
    raw_record_nested = {
        "url": "https://twitter.com/test/status/67890",
        "author": {
            "location": "Abuja, Nigeria"
        }
    }
    normalized_nested = ingestor.normalize_record(raw_record_nested)
    print(f"Output user_location (nested dict): {normalized_nested.get('user_location')}")

    # Test case 3: Location in author object (JSON string) - Key fix test
    import json
    raw_record_json = {
        "url": "https://twitter.com/test/status/11223",
        "author": json.dumps({
            "location": "Port Harcourt, Nigeria",
            "name": "JSON User"
        })
    }
    normalized_json = ingestor.normalize_record(raw_record_json)
    print(f"Output user_location (JSON string author): {normalized_json.get('user_location')}")

    # Test case 4: Case insensitive keys
    raw_record_case = {
        "url": "https://twitter.com/test/status/44556",
        "Author": {  # Capitalized key
            "Location": "Kano, Nigeria"  # Capitalized key
        }
    }
    normalized_case = ingestor.normalize_record(raw_record_case)
    print(f"Output user_location (Case Insensitive): {normalized_case.get('user_location')}")

if __name__ == "__main__":
    test_normalization()
