
import sys
import os
from datetime import datetime
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.data_ingestor import DataIngestor
from src.api.models import SentimentData

# Mock session
class MockSession:
    def query(self, *args):
        return self
    def filter(self, *args):
        return self
    def first(self):
        return None
    def execute(self, *args):
        pass
    def commit(self):
        pass

def test_undefined_normalization():
    ingestor = DataIngestor(MockSession())
    
    raw_record = {
        "url": "http://example.com/1",
        "description": "undefined",
        "source": "undefined",
        "title": "Valid Title",
        "likeCount": "undefined",  # Should be handled by safe_int
        "user_location": "undefined",
        "platform": "twitter"
    }
    
    print(f"Raw record: {raw_record}")
    
    normalized = ingestor.normalize_record(raw_record)
    
    print("\nNormalized record:")
    print(f"description: {repr(normalized.get('description'))}")
    print(f"source: {repr(normalized.get('source'))}")
    print(f"user_location: {repr(normalized.get('user_location'))}")
    print(f"likes: {repr(normalized.get('likes'))}")
    
    # Check assertions
    issues = []
    if normalized.get('description') == 'undefined':
        issues.append("FAILURE: 'description' is 'undefined' string")
    elif normalized.get('description') is None:
        print("SUCCESS: 'description' is None")
        
    if normalized.get('source') == 'undefined':
        issues.append("FAILURE: 'source' is 'undefined' string")
    elif normalized.get('source') is None:
        print("SUCCESS: 'source' is None")

    if normalized.get('user_location') == 'undefined':
        issues.append("FAILURE: 'user_location' is 'undefined' string")
    elif normalized.get('user_location') is None:
        print("SUCCESS: 'user_location' is None")
        
    if normalized.get('likes') is None:
         print("SUCCESS: 'likes' is None (safe_int works)")
    else:
         issues.append(f"FAILURE: 'likes' is {normalized.get('likes')}")

    if issues:
        print("\n❌ Verification Failed:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ Verification Passed: No 'undefined' strings found.")

if __name__ == "__main__":
    test_undefined_normalization()
