#!/usr/bin/env python3
"""
Script to process existing sentiment_data records with the enhanced Presidential Sentiment Analyzer.
This will add issue mapping fields and embeddings to existing records that don't have them.

Usage:
    python process_existing_data.py [--limit N] [--batch-size N] [--dry-run]
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
from tqdm import tqdm

# Add the src directory to the path
sys.path.append(str(Path(__file__).parent / "src"))

from processing.governance_analyzer import GovernanceAnalyzer
from api.models import SentimentData, SentimentEmbedding, Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('process_existing_data.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ProcessExistingData')

class ExistingDataProcessor:
    def __init__(self, database_url: str):
        """Initialize the processor with database connection."""
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        self.analyzer = GovernanceAnalyzer()
        
        logger.info("ExistingDataProcessor initialized")

    def get_unprocessed_records(self, limit: int = None) -> pd.DataFrame:
        """Get records that need issue mapping processing."""
        query = """
        SELECT entry_id, text, content, title, description, source_type, platform
        FROM sentiment_data 
        WHERE (issue_label IS NULL OR issue_label = '') 
           OR (issue_slug IS NULL OR issue_slug = '')
           OR (issue_keywords IS NULL)
           OR (ministry_hint IS NULL OR ministry_hint = '')
        ORDER BY created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        try:
            df = pd.read_sql(query, self.engine)
            logger.info(f"Found {len(df)} records needing issue mapping processing")
            return df
        except Exception as e:
            logger.error(f"Error fetching unprocessed records: {e}")
            return pd.DataFrame()

    def process_record(self, record: pd.Series) -> dict:
        """Process a single record with the enhanced analyzer."""
        # Get text content from various fields
        text_content = (
            record.get('text') or 
            record.get('content') or 
            record.get('title') or 
            record.get('description')
        )
        
        if not text_content or str(text_content).strip() == "":
            return {
                'entry_id': record['entry_id'],
                'issue_label': 'Unlabeled Content',
                'issue_slug': 'unlabeled-content',
                'issue_confidence': 0.0,
                'issue_keywords': [],
                'ministry_hint': None,
                'embedding': [0.0] * 1536,
                'category_type': 'non_governance',
                'page_type': 'issues',
                'sentiment': 'neutral',
                'governance_relevance': 0.0,
                'error': 'No text content'
            }
        
        try:
            # Analyze with enhanced analyzer
            analysis_result = self.analyzer.analyze(
                str(text_content), 
                record.get('source_type')
            )
            
            return {
                'entry_id': record['entry_id'],
                'issue_label': analysis_result.get('category_label', 'General Issue'),
                'issue_slug': analysis_result.get('governance_category', 'general-issue'),
                'issue_confidence': analysis_result.get('confidence', 0.0),
                'issue_keywords': analysis_result.get('keywords', []),
                'ministry_hint': analysis_result.get('ministry_hint', 'general'),
                'embedding': analysis_result.get('embedding', [0.0] * 1536),
                'category_type': analysis_result.get('category_type', 'non_governance'),
                'page_type': analysis_result.get('page_type', 'issues'),
                'sentiment': analysis_result.get('sentiment', 'neutral'),
                'governance_relevance': analysis_result.get('governance_relevance', 0.0),
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Error processing record {record['entry_id']}: {e}")
            return {
                'entry_id': record['entry_id'],
                'issue_label': 'Processing Error',
                'issue_slug': 'processing-error',
                'issue_confidence': 0.0,
                'issue_keywords': [],
                'ministry_hint': None,
                'embedding': [0.0] * 1536,
                'category_type': 'non_governance',
                'page_type': 'issues',
                'sentiment': 'neutral',
                'governance_relevance': 0.0,
                'error': str(e)
            }

    def update_database(self, results: list, dry_run: bool = False) -> dict:
        """Update database with processed results."""
        stats = {
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
        
        if dry_run:
            logger.info(f"DRY RUN: Would update {len(results)} records")
            return stats
        
        session = self.Session()
        
        try:
            for result in tqdm(results, desc="Updating database"):
                try:
                    # Update sentiment_data table
                    update_query = text("""
                        UPDATE sentiment_data 
                        SET 
                            issue_label = :issue_label,
                            issue_slug = :issue_slug,
                            issue_confidence = :issue_confidence,
                            issue_keywords = :issue_keywords,
                            ministry_hint = :ministry_hint
                        WHERE entry_id = :entry_id
                    """)
                    
                    session.execute(update_query, {
                        'entry_id': result['entry_id'],
                        'issue_label': result['issue_label'],
                        'issue_slug': result['issue_slug'],
                        'issue_confidence': result['issue_confidence'],
                        'issue_keywords': json.dumps(result['issue_keywords']),
                        'ministry_hint': result['ministry_hint']
                    })
                    
                    # Insert/update embedding
                    embedding_data = result['embedding']
                    if embedding_data and len(embedding_data) == 1536:
                        # Check if embedding exists
                        existing_embedding = session.query(SentimentEmbedding).filter(
                            SentimentEmbedding.entry_id == result['entry_id']
                        ).first()
                        
                        if existing_embedding:
                            # Update existing
                            existing_embedding.embedding = json.dumps(embedding_data)
                            existing_embedding.embedding_model = 'text-embedding-3-small'
                        else:
                            # Create new
                            embedding_record = SentimentEmbedding(
                                entry_id=result['entry_id'],
                                embedding=json.dumps(embedding_data),
                                embedding_model='text-embedding-3-small'
                            )
                            session.add(embedding_record)
                    
                    stats['updated'] += 1
                    
                except Exception as e:
                    logger.error(f"Error updating record {result['entry_id']}: {e}")
                    stats['errors'] += 1
                    continue
            
            # Commit all changes
            session.commit()
            logger.info(f"Successfully updated {stats['updated']} records")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Database update failed: {e}")
            stats['errors'] = len(results)
        finally:
            session.close()
        
        return stats

    def process_batch(self, records_df: pd.DataFrame, batch_size: int = 50) -> list:
        """Process records in batches."""
        all_results = []
        
        for i in tqdm(range(0, len(records_df), batch_size), desc="Processing batches"):
            batch = records_df.iloc[i:i + batch_size]
            batch_results = []
            
            for _, record in batch.iterrows():
                result = self.process_record(record)
                batch_results.append(result)
            
            all_results.extend(batch_results)
            
            # Log progress
            logger.info(f"Processed batch {i//batch_size + 1}: {len(batch_results)} records")
        
        return all_results

    def run(self, limit: int = None, batch_size: int = 50, dry_run: bool = False, test_mode: bool = False):
        """Main processing function."""
        logger.info("Starting existing data processing...")
        
        # In test mode, limit to one batch
        if test_mode:
            limit = batch_size
            logger.info(f"TEST MODE: Processing only {limit} records for testing")
        
        # Get records to process
        records_df = self.get_unprocessed_records(limit)
        
        if records_df.empty:
            logger.info("No records found that need processing")
            return
        
        logger.info(f"Processing {len(records_df)} records...")
        
        # Process records
        results = self.process_batch(records_df, batch_size)
        
        # Show detailed results for testing
        if test_mode and results:
            logger.info("=== DETAILED TEST RESULTS ===")
            for i, result in enumerate(results[:10]):  # Show first 10 results
                logger.info(f"\nRecord {i+1} (Entry ID: {result['entry_id']}):")
                logger.info(f"  Issue Label: {result['issue_label']}")
                logger.info(f"  Issue Slug: {result['issue_slug']}")
                logger.info(f"  Category Type: {result.get('category_type', 'N/A')}")
                logger.info(f"  Page Type: {result.get('page_type', 'N/A')}")
                logger.info(f"  Sentiment: {result.get('sentiment', 'N/A')}")
                logger.info(f"  Issue Confidence: {result['issue_confidence']}")
                logger.info(f"  Governance Relevance: {result.get('governance_relevance', 'N/A')}")
                logger.info(f"  Issue Keywords: {result['issue_keywords']}")
                logger.info(f"  Ministry Hint: {result['ministry_hint']}")
                if result.get('error'):
                    logger.info(f"  Error: {result['error']}")
        
        # Update database
        stats = self.update_database(results, dry_run)
        
        # Print summary
        logger.info("Processing complete!")
        logger.info(f"Records processed: {len(results)}")
        logger.info(f"Records updated: {stats['updated']}")
        logger.info(f"Errors: {stats['errors']}")
        
        # Show sample results
        if results:
            logger.info("Sample processed results:")
            for i, result in enumerate(results[:3]):
                logger.info(f"  {i+1}. Entry {result['entry_id']}: {result['issue_label']} ({result['ministry_hint']})")

def check_environment_variables():
    """Check for required environment variables and provide helpful messages."""
    missing_vars = []
    warnings = []
    
    # Required variables (none currently required due to defaults)
    required_vars = {}
    
    # Optional but recommended variables
    optional_vars = {
        'DATABASE_URL': 'Database connection string (defaults to sqlite:///./sentiment_analysis_local.db)',
        'OPENAI_API_KEY': 'OpenAI API key for presidential analysis and embeddings',
        'CONFIG_DIR': 'Configuration directory path',
        'LOG_LEVEL': 'Logging level (DEBUG, INFO, WARNING, ERROR)'
    }
    
    # Check required variables
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var}: {description}")
    
    # Check optional variables and warn if missing
    for var, description in optional_vars.items():
        if not os.getenv(var):
            warnings.append(f"{var}: {description}")
    
    # Report results
    if missing_vars:
        logger.error("Missing required environment variables:")
        for var in missing_vars:
            logger.error(f"  - {var}")
        logger.error("\nPlease set these environment variables before running the script.")
        logger.error("\nExample:")
        logger.error("  export DATABASE_URL='sqlite:///./sentiment_analysis_local.db'")
        logger.error("  export OPENAI_API_KEY='your-api-key-here'")
        return False
    
    if warnings:
        logger.warning("Optional environment variables not set (functionality may be limited):")
        for var in warnings:
            logger.warning(f"  - {var}")
        logger.warning("\nConsider setting these for full functionality:")
        logger.warning("  export OPENAI_API_KEY='your-api-key-here'  # For AI analysis")
        logger.warning("  export DATABASE_URL='your-database-url'     # Override default")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Process existing sentiment data with issue mapping')
    parser.add_argument('--limit', type=int, help='Limit number of records to process')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for processing')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')
    parser.add_argument('--database-url', help='Database URL (overrides DATABASE_URL env var)')
    parser.add_argument('--skip-env-check', action='store_true', help='Skip environment variable checks')
    parser.add_argument('--test-mode', action='store_true', help='Process only one batch for testing and show detailed results')
    
    args = parser.parse_args()
    
    # Check environment variables unless skipped
    if not args.skip_env_check:
        if not check_environment_variables():
            sys.exit(1)
    
    # Get database URL
    database_url = args.database_url or os.getenv('DATABASE_URL')
    if not database_url:
        # Set default database URL for local development
        database_url = "sqlite:///./sentiment_analysis_local.db"
        logger.warning(f"DATABASE_URL not set, using default: {database_url}")
        # Set it as environment variable for the session
        os.environ['DATABASE_URL'] = database_url
    
    # Log current configuration
    logger.info("Starting process_existing_data.py with configuration:")
    logger.info(f"  Database URL: {database_url}")
    logger.info(f"  Limit: {args.limit or 'No limit'}")
    logger.info(f"  Batch size: {args.batch_size}")
    logger.info(f"  Dry run: {args.dry_run}")
    logger.info(f"  OpenAI API Key: {'Set' if os.getenv('OPENAI_API_KEY') else 'Not set (limited functionality)'}")
    
    # Initialize processor
    processor = ExistingDataProcessor(database_url)
    
    # Run processing
    processor.run(
        limit=args.limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        test_mode=args.test_mode
    )

if __name__ == "__main__":
    main()
