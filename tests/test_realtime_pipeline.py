"""
Integration tests for the real-time analysis pipeline (Polling).

Verifies:
1. AnalysisWorker correctly polls for unanalyzed records.
2. AnalysisWorker triggers Agent analysis.
"""

import asyncio
import logging
import pytest
import sys
from datetime import datetime
from unittest.mock import MagicMock

from sqlalchemy import text

# Add src to path
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.database import SessionLocal
from src.services.analysis_worker import AnalysisWorker
from src.api.models import SentimentData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
def clean_db():
    # Clean up test data before/after
    session = SessionLocal()
    session.execute(text("DELETE FROM sentiment_data WHERE url LIKE 'test_polling_%'"))
    session.commit()
    session.close()
    yield
    session = SessionLocal()
    session.execute(text("DELETE FROM sentiment_data WHERE url LIKE 'test_polling_%'"))
    session.commit()
    session.close()

@pytest.mark.asyncio
async def test_analysis_worker_polling(clean_db):
    """Verify AnalysisWorker correctly polls and processes a record."""
    
    # Mock the Agent to avoid full LLM calls
    mock_agent = MagicMock()
    mock_agent.sentiment_analyzer.analyze_sentiment.return_value = {
        'sentiment_label': 'polling_positive',
        'sentiment_score': 0.95,
        'justification': 'Test polling justification'
    }
    mock_agent.emotion_analyzer.analyze_emotion.return_value = {
        'emotion_label': 'joy',
        'emotion_score': 0.8,
        'emotion_distribution': {'joy': 0.8, 'anger': 0.1, 'sadness': 0.1}
    }
    mock_agent.location_classifier.classify_location.return_value = None
    mock_agent.issue_detector.detect_issues.return_value = None
    
    # Create worker with mocked agent & fast poll interval
    worker = AnalysisWorker(max_workers=1, poll_interval=0.1)
    worker._agent = mock_agent # Inject mock
    
    # Create a real DB record to analyze
    session = SessionLocal()
    record = SentimentData(
        url="test_polling_url_1",
        text="This is input for the polling worker test.",
        platform="test_polling",
        run_timestamp=datetime.now(),
        created_at=datetime.now()
    )
    session.add(record)
    session.commit()
    entry_id = record.entry_id
    session.close()
    
    # Run worker for a short burst
    worker_task = asyncio.create_task(worker.run_forever())
    
    try:
        # Wait enough time for poll -> fetch -> analyze
        await asyncio.sleep(2)
        
        # Stop worker
        worker.stop()
        await worker_task
        
        # Check DB for updates
        session = SessionLocal()
        updated_record = session.query(SentimentData).filter_by(entry_id=entry_id).first()
        
        assert updated_record is not None
        # Should be updated by worker
        if updated_record.sentiment_label is None:
             pytest.fail("Record was not picked up by polling worker!")
             
        assert updated_record.sentiment_label == 'polling_positive'
        assert updated_record.processing_status == 'completed'
        assert updated_record.processing_completed_at is not None
        
        session.close()
        
    except Exception as e:
        worker.stop()
        if not worker_task.done():
            worker_task.cancel()
        raise e

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
