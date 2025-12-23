#!/usr/bin/env python3
"""
Script to improve data quality for a specific user by running Phase 4 (Sentiment Analysis) 
and Phase 5 (Location Classification) on records that are missing these fields.

This script uses the existing methods from the automatic cycles.
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Change to project root directory
os.chdir(project_root)

from src.api.database import SessionLocal
from src.agent.core import SentimentAnalysisAgent
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def improve_user_data(user_id: str, test_batch_size: int = 100):
    """
    Improve data quality for a specific user by running:
    1. Phase 4: Sentiment Analysis (for records missing sentiment_label, issue_label, or issue_keywords)
    2. Phase 5: Location Classification (for all records)
    
    Args:
        user_id: The user ID to process
        test_batch_size: Number of records to process in test mode (default: 100)
    """
    logger.info("=" * 80)
    logger.info(f"STARTING DATA IMPROVEMENT PROCESS")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Test Batch Size: {test_batch_size} records")
    logger.info("=" * 80)
    
    try:
        # Step 1: Initialize the agent
        logger.info("\n[STEP 1] Initializing SentimentAnalysisAgent...")
        agent = SentimentAnalysisAgent(db_factory=SessionLocal)
        logger.info("✓ Agent initialized successfully")
        logger.info(f"  - Max Sentiment Workers: {agent.max_sentiment_workers}")
        logger.info(f"  - Sentiment Batch Size: {agent.sentiment_batch_size}")
        logger.info(f"  - Max Location Workers: {agent.max_location_workers}")
        logger.info(f"  - Location Batch Size: {agent.location_batch_size}")
        
        # Step 2: Analyze current data quality
        logger.info("\n[STEP 2] Analyzing current data quality...")
        from sqlalchemy import or_, func
        import src.api.models as models
        
        with SessionLocal() as db:
            # Get statistics
            total_records = db.query(func.count(models.SentimentData.entry_id)).filter(
                models.SentimentData.user_id == user_id
            ).scalar()
            
            missing_sentiment = db.query(func.count(models.SentimentData.entry_id)).filter(
                models.SentimentData.user_id == user_id,
                or_(
                    models.SentimentData.sentiment_label.is_(None),
                    models.SentimentData.sentiment_label == ''
                )
            ).scalar()
            
            missing_issue = db.query(func.count(models.SentimentData.entry_id)).filter(
                models.SentimentData.user_id == user_id,
                or_(
                    models.SentimentData.issue_label.is_(None),
                    models.SentimentData.issue_label == '',
                    models.SentimentData.issue_label == 'General Issue'
                )
            ).scalar()
            
            missing_keywords = db.query(func.count(models.SentimentData.entry_id)).filter(
                models.SentimentData.user_id == user_id,
                models.SentimentData.issue_keywords.is_(None)
            ).scalar()
            
            records_needing_processing = db.query(func.count(models.SentimentData.entry_id)).filter(
                models.SentimentData.user_id == user_id,
                or_(
                    models.SentimentData.sentiment_label.is_(None),
                    models.SentimentData.sentiment_label == '',
                    models.SentimentData.issue_label.is_(None),
                    models.SentimentData.issue_label == '',
                    models.SentimentData.issue_label == 'General Issue',
                    models.SentimentData.issue_keywords.is_(None)
                )
            ).scalar()
        
        logger.info("✓ Data quality analysis complete:")
        logger.info(f"  - Total Records: {total_records:,}")
        logger.info(f"  - Missing Sentiment Label: {missing_sentiment:,}")
        logger.info(f"  - Missing/General Issue Label: {missing_issue:,}")
        logger.info(f"  - Missing Issue Keywords: {missing_keywords:,}")
        logger.info(f"  - Records Needing Processing: {records_needing_processing:,}")
        
        if records_needing_processing == 0:
            logger.info("\n✓ All records are already complete! No processing needed.")
            return
        
        # Step 3: Phase 4 - Prepare records for sentiment analysis
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 4: SENTIMENT ANALYSIS & CLASSIFICATION")
        logger.info("=" * 80)
        
        logger.info("\n[STEP 3] Identifying records that need sentiment/classification processing...")
        with SessionLocal() as db:
            # Get records that need processing (limited to test batch size)
            records_to_reset = db.query(models.SentimentData).filter(
                models.SentimentData.user_id == user_id,
                or_(
                    models.SentimentData.sentiment_label.is_(None),
                    models.SentimentData.sentiment_label == '',
                    models.SentimentData.issue_label.is_(None),
                    models.SentimentData.issue_label == '',
                    models.SentimentData.issue_label == 'General Issue',
                    models.SentimentData.issue_keywords.is_(None)
                )
            ).limit(test_batch_size).all()
            
            logger.info(f"✓ Found {len(records_to_reset)} records to process (limited to {test_batch_size} for testing)")
            
            # Reset sentiment_label to NULL for records that need processing
            # This ensures they get picked up by the existing method
            logger.info("\n[STEP 4] Preparing records for sentiment analysis...")
            # Track which records we're processing
            record_ids_to_process = []
            reset_reasons = {
                'missing_sentiment': 0,
                'missing_issue': 0,
                'general_issue': 0,
                'missing_keywords': 0
            }
            
            for record in records_to_reset:
                needs_reset = False
                if not record.sentiment_label or record.sentiment_label == '':
                    reset_reasons['missing_sentiment'] += 1
                    needs_reset = True
                if not record.issue_label or record.issue_label == '':
                    reset_reasons['missing_issue'] += 1
                    needs_reset = True
                if record.issue_label == 'General Issue':
                    reset_reasons['general_issue'] += 1
                    needs_reset = True
                if record.issue_keywords is None:
                    reset_reasons['missing_keywords'] += 1
                    needs_reset = True
                
                if needs_reset:
                    # Store the entry_id so we can process only these records
                    record_ids_to_process.append(record.entry_id)
                    # Reset sentiment_label to NULL so the processing method picks it up
                    record.sentiment_label = None
            
            db.commit()
            logger.info(f"✓ Prepared {len(record_ids_to_process)} records for sentiment analysis")
            logger.info(f"  Reset reasons breakdown:")
            logger.info(f"    - Missing sentiment: {reset_reasons['missing_sentiment']}")
            logger.info(f"    - Missing issue label: {reset_reasons['missing_issue']}")
            logger.info(f"    - General Issue label: {reset_reasons['general_issue']}")
            logger.info(f"    - Missing keywords: {reset_reasons['missing_keywords']}")
            logger.info(f"  Record IDs to process: {len(record_ids_to_process)}")
        
        # Step 5: Run Phase 4 sentiment analysis on ONLY the records we identified
        logger.info("\n[STEP 5] Running Phase 4: Sentiment Analysis (processing only identified records)...")
        logger.info(f"  Processing {len(record_ids_to_process)} records in parallel batches...")
        sentiment_start_time = time.time()
        
        # Process only the records we identified, not all NULL records
        # We'll use the data processor directly to process only our specific records
        with SessionLocal() as db:
            # Get the actual records we want to process
            records_to_process = db.query(models.SentimentData).filter(
                models.SentimentData.entry_id.in_(record_ids_to_process)
            ).all()
            
            logger.info(f"  Retrieved {len(records_to_process)} records from database")
            
            # Process in batches using the agent's data processor
            batch_size = agent.sentiment_batch_size
            processed_count = 0
            
            for i in range(0, len(records_to_process), batch_size):
                batch = records_to_process[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(records_to_process) + batch_size - 1) // batch_size
                
                logger.info(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} records)")
                
                # Prepare texts and source types
                texts = []
                source_types = []
                batch_record_ids = []
                
                for record in batch:
                    text_content = record.text or record.content or record.title or record.description
                    if text_content:
                        texts.append(text_content)
                        source_types.append(record.source_type)
                        batch_record_ids.append(record.entry_id)
                
                if not texts:
                    logger.warning(f"  Batch {batch_num} has no text content, skipping")
                    continue
                
                # Use the agent's data processor to get sentiment and classification
                try:
                    results = agent.data_processor.batch_get_sentiment(texts, source_types)
                    
                    # Update records with results
                    with SessionLocal() as update_db:
                        for idx, record_id in enumerate(batch_record_ids):
                            if idx < len(results):
                                result = results[idx]
                                record = update_db.query(models.SentimentData).filter(
                                    models.SentimentData.entry_id == record_id
                                ).first()
                                
                                if record:
                                    # Update sentiment fields
                                    record.sentiment_label = result.get('sentiment_label')
                                    record.sentiment_score = result.get('sentiment_score')
                                    record.sentiment_justification = result.get('sentiment_justification')
                                    
                                    # Update issue/classification fields
                                    record.issue_label = result.get('issue_label')
                                    record.issue_slug = result.get('issue_slug')
                                    record.ministry_hint = result.get('ministry_hint')
                                    record.issue_confidence = result.get('issue_confidence')
                                    record.issue_keywords = result.get('issue_keywords')
                                    
                                    processed_count += 1
                        
                        update_db.commit()
                        logger.info(f"  ✓ Batch {batch_num} completed: {processed_count}/{len(record_ids_to_process)} records updated")
                
                except Exception as e:
                    logger.error(f"  ✗ Error processing batch {batch_num}: {e}", exc_info=True)
                    continue
        
        sentiment_duration = time.time() - sentiment_start_time
        sentiment_success = processed_count > 0
        
        if sentiment_success:
            logger.info(f"✓ Phase 4 completed successfully in {sentiment_duration:.2f} seconds!")
        else:
            logger.warning(f"⚠ Phase 4 completed with some issues (duration: {sentiment_duration:.2f}s)")
        
        # Step 6: Verify Phase 4 results
        logger.info("\n[STEP 6] Verifying Phase 4 results...")
        with SessionLocal() as db:
            # Check how many records were updated
            updated_records = db.query(func.count(models.SentimentData.entry_id)).filter(
                models.SentimentData.user_id == user_id,
                models.SentimentData.sentiment_label.isnot(None),
                models.SentimentData.sentiment_label != '',
                models.SentimentData.issue_label.isnot(None),
                models.SentimentData.issue_label != '',
                models.SentimentData.issue_label != 'General Issue',
                models.SentimentData.issue_keywords.isnot(None)
            ).scalar()
            
            logger.info(f"✓ Records with complete data after Phase 4: {updated_records:,}")
        
        # Step 7: Phase 5 - Location Classification
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 5: LOCATION CLASSIFICATION")
        logger.info("=" * 80)
        
        logger.info("\n[STEP 7] Running Phase 5: Location Classification...")
        logger.info(f"  Processing with batch size: 300 (limited to {test_batch_size} records for testing)")
        location_start_time = time.time()
        
        # For testing, we'll limit the location classification too
        location_result = agent.update_location_classifications(user_id, batch_size=300)
        location_duration = time.time() - location_start_time
        
        if 'error' in location_result:
            logger.error(f"✗ Location classification error: {location_result['error']}")
        else:
            logger.info(f"✓ Phase 5 completed successfully in {location_duration:.2f} seconds!")
            logger.info(f"  Location classification results:")
            logger.info(f"    - Total records processed: {location_result.get('total_records', 0):,}")
            logger.info(f"    - Records updated: {location_result.get('total_updated', 0):,}")
            logger.info(f"    - Records unchanged: {location_result.get('total_unchanged', 0):,}")
            if 'average_confidence' in location_result:
                logger.info(f"    - Average confidence: {location_result['average_confidence']:.3f}")
            if 'high_confidence_count' in location_result:
                logger.info(f"    - High confidence (≥0.7): {location_result['high_confidence_count']:,}")
                logger.info(f"    - Medium confidence (0.4-0.7): {location_result['medium_confidence_count']:,}")
                logger.info(f"    - Low confidence (<0.4): {location_result['low_confidence_count']:,}")
        
        # Step 8: Final summary
        logger.info("\n" + "=" * 80)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✓ Data improvement process completed!")
        logger.info(f"  - Phase 4 Duration: {sentiment_duration:.2f} seconds")
        logger.info(f"  - Phase 5 Duration: {location_duration:.2f} seconds")
        logger.info(f"  - Total Duration: {sentiment_duration + location_duration:.2f} seconds")
        logger.info(f"  - Records processed: {len(records_to_reset)} (test batch)")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("ERROR OCCURRED DURING DATA IMPROVEMENT")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    # User ID from the query
    user_id = "6440da7f-e630-4b2f-884e-a8721cc9a9c0"
    
    # Test batch size - process only 100 records for testing
    test_batch_size = 100
    
    print(f"\n{'='*80}")
    print(f"Data Improvement Script - TEST MODE")
    print(f"User ID: {user_id}")
    print(f"Test Batch Size: {test_batch_size} records")
    print(f"{'='*80}\n")
    
    improve_user_data(user_id, test_batch_size=test_batch_size)

