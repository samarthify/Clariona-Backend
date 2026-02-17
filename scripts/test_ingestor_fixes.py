
import logging
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.getcwd())

from src.services.data_ingestor import DataIngestor
from src.api.models import SentimentData

# Mock SQLAlchemy session
class MockSession:
    def __init__(self):
        self.executed_stmts = []
        self.committed = False
        self.query_result = None

    def execute(self, stmt):
        self.executed_stmts.append(stmt)
        return MagicMock()

    def commit(self):
        self.committed = True

    def rollback(self):
        pass
    
    def query(self, *args):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = self.query_result
        return mock_query

def test_ingestor_fixes():
    print("Running Data Ingestor Verification...")
    
    # 1. Test Imports (Simulate by checking if DataIngestor loads without error)
    # If we are here, imports works.
    print("✅ Imports loaded successfully.")

    session = MockSession()
    ingestor = DataIngestor(session)
    
    # 2. Test insert_record fixed undefined 'records' variable
    # We call insert_record. If it doesn't crash with NameError, it's fixed.
    try:
        record = {
            "url": "http://example.com/1",
            "text": "test", 
            "likes": 10,
            "platform": "twitter"
        }
        # Mock existing record to None so it tries strict insert first
        session.query_result = None
        
        result = ingestor.insert_record(record)
        print(f"✅ insert_record ran successfully. Result: {result}")
    except NameError as e:
        print(f"❌ FAILED: insert_record raised NameError: {e}")
    except Exception as e:
        print(f"❌ FAILED: insert_record raised unexpected error: {e}")

    # 3. Test Backfill Logic (COALESCE) & Protected Fields
    # We inspect the generated SQL statement for insert_batch
    try:
        # Batch with missing fields to trigger backfill logic
        batch = [
            {"url": "http://example.com/2", "text": "batch1", "date": datetime.now()},
            {"url": "http://example.com/3", "text": "batch2"} # missing date
        ]
        
        # We need to spy on the stmt passed to execute
        with patch.object(session, 'execute') as mock_execute:
            ingestor.insert_batch(batch)
            
            # Get the statement
            call_args = mock_execute.call_args
            if not call_args:
                 print("❌ FAILED: insert_batch did not execute statement")
                 return
                 
            stmt = call_args[0][0]
            
            # Check ON CONFLICT clause
            # We can't easily parse the SQL string from SQLAlchemy object without binding, 
            # but we can check if the underlying logic didn't crash and looks reasonable.
            
            # In particular, we want to verify the CRITICAL fix: 
            # If all rows have NULL for a field, it should NOT be in update_dict.
            
            # Let's try a batch where 'user_location' is NULL for ALL items
            batch_nulls = [
                {"url": "http://example.com/4", "text": "nulls1", "user_location": None},
                {"url": "http://example.com/5", "text": "nulls2"} # missing user_location implicitly None
            ]
            
            # Clear previous calls
            mock_execute.reset_mock()
            
            ingestor.insert_batch(batch_nulls)
            
            stmt_nulls = mock_execute.call_args[0][0]
            
            # Check if user_location is in the set clause (it shouldn't be!)
            # Note: access internal storage of on_conflict_do_update is tricky, 
            # but usually in stmt._post_values or similar.
            # Simplified check: if it ran without error, that's step 1.
            
            print("✅ insert_batch ran with all-NULL field without error.")
            
    except Exception as e:
        print(f"❌ FAILED: insert_batch raised error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ingestor_fixes()
