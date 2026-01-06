"""
Streaming Collection Service - Main Entry Point

This module provides the unified entry point for the streaming collection service,
which runs:
1. DatasetTailerService: Tails Apify runs in real-time.
2. LocalScheduler: Schedules daily runs of local collectors.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).resolve().parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from dotenv import load_dotenv
load_dotenv(src_path / 'collectors' / '.env')

from sqlalchemy.orm import Session
from api.database import SessionLocal

from services.data_ingestor import DataIngestor
from services.dataset_tailer import DatasetTailerService
from services.scheduler import LocalScheduler
from services.analysis_worker import AnalysisWorker

from src.config.logging_config import setup_logging, get_logger

# Configure logging using centralized configuration
setup_logging()
logger = get_logger(__name__)


class StreamingCollectionService:
    """
    Main service that orchestrates all streaming collection components.
    """
    
    def __init__(self, user_id: str = None):
        """
        Initialize the streaming collection service.
        
        Args:
            user_id: Optional user ID to associate with collected data.
        """
        self.user_id = user_id
        self.db_session: Session = None
        self.ingestor: DataIngestor = None
        self.tailer: DatasetTailerService = None
        self.scheduler: LocalScheduler = None
        self.analysis_worker: AnalysisWorker = None
        self._running = False
    
    async def start(self):
        """Start all streaming components."""
        logger.info("Starting Streaming Collection Service...")
        
        # Initialize database session
        self.db_session = SessionLocal()
        
        # Initialize DataIngestor
        self.ingestor = DataIngestor(self.db_session, user_id=self.user_id)
        logger.info("DataIngestor initialized.")
        
        # Initialize and start DatasetTailer
        self.tailer = DatasetTailerService(self.ingestor, poll_interval=5.0)
        asyncio.create_task(self.tailer.run_forever())
        logger.info("DatasetTailerService started.")
        
        # Initialize and start LocalScheduler
        self.scheduler = LocalScheduler(self.ingestor)
        await self.scheduler.start()
        logger.info("LocalScheduler started.")
        
        # Initialize and start AnalysisWorker (real-time analysis)
        self.analysis_worker = AnalysisWorker(max_workers=10)
        asyncio.create_task(self.analysis_worker.run_forever())
        logger.info("AnalysisWorker started (real-time analysis enabled).")
        
        self._running = True
        logger.info("Streaming Collection Service is now running.")
        
        # Keep running until stopped
        try:
            while self._running:
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass
    
    async def stop(self):
        """Stop all streaming components."""
        logger.info("Stopping Streaming Collection Service...")
        self._running = False
        
        if self.tailer:
            await self.tailer.stop()
        
        if self.scheduler:
            await self.scheduler.stop()
        
        if self.analysis_worker:
            self.analysis_worker.stop()
        
        if self.db_session:
            self.db_session.close()
        
        logger.info("Streaming Collection Service stopped.")
    
    def get_status(self) -> dict:
        """Get status of all components."""
        return {
            'running': self._running,
            'tailer': {
                'watching_runs': len(self.tailer.watching_runs) if self.tailer else 0,
                'processed_runs': len(self.tailer.processed_run_ids) if self.tailer else 0,
            },
            'scheduler': self.scheduler.get_next_run_times() if self.scheduler else {},
        }


async def main():
    """Main entry point for the streaming service."""
    user_id = os.getenv('STREAMING_USER_ID')
    
    service = StreamingCollectionService(user_id=user_id)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
