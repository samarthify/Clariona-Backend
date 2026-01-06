"""
Direct test script for full data collection cycle.

This script runs the cycle directly without needing the API server.
It's better for testing as it doesn't require starting the backend.
"""

import sys
import time
import io
from pathlib import Path
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.core import SentimentAnalysisAgent
from src.api.database import SessionLocal
from src.api.models import User, TargetIndividualConfiguration, SentimentData
from src.config.path_manager import PathManager
from src.config.config_manager import ConfigManager


def get_test_user_id() -> str:
    """Get a user_id from database for testing."""
    db = SessionLocal()
    try:
        # Try to get user with target config first
        target_config = db.query(TargetIndividualConfiguration).first()
        if target_config and target_config.user_id:
            user_id = str(target_config.user_id)
            print(f"✅ Found user with target config: {user_id}")
            return user_id
        
        # Fallback to any user
        user = db.query(User).first()
        if user:
            user_id = str(user.id)
            print(f"✅ Found user: {user_id} ({user.email})")
            return user_id
        
        raise Exception("No users found in database")
    finally:
        db.close()


def check_cycle_results(user_id: str, before_count: int) -> dict:
    """Check database for cycle results."""
    db = SessionLocal()
    try:
        # Count total records for this user
        total_count = db.query(SentimentData).filter(
            SentimentData.user_id == user_id
        ).count()
        
        new_records = total_count - before_count
        
        # Count records with sentiment analysis
        with_sentiment = db.query(SentimentData).filter(
            SentimentData.user_id == user_id,
            SentimentData.sentiment_label.isnot(None)
        ).count()
        
        # Count records with topics
        from src.api.models import MentionTopic
        with_topics = db.query(MentionTopic).join(
            SentimentData, MentionTopic.mention_id == SentimentData.entry_id
        ).filter(
            SentimentData.user_id == user_id
        ).count()
        
        return {
            "before_count": before_count,
            "total_count": total_count,
            "new_records": new_records,
            "with_sentiment": with_sentiment,
            "with_topics": with_topics
        }
    except Exception as e:
        print(f"⚠️  Error checking results: {e}")
        return {}
    finally:
        db.close()


def main():
    """Run full cycle test directly."""
    print("=" * 80)
    print("FULL DATA COLLECTION CYCLE TEST (DIRECT)")
    print("=" * 80)
    print("\nThis test runs the cycle directly without the API server.")
    print("It will execute all phases: Collection -> Processing -> Storage\n")
    
    try:
        # Step 1: Get user_id
        print("[Step 1] Getting test user_id...")
        user_id = get_test_user_id()
        print(f"   User ID: {user_id}\n")
        
        # Step 2: Get initial record count
        print("[Step 2] Checking initial database state...")
        db = SessionLocal()
        try:
            initial_count = db.query(SentimentData).filter(
                SentimentData.user_id == user_id
            ).count()
            print(f"   Initial records: {initial_count}\n")
        finally:
            db.close()
        
        # Step 3: Initialize agent
        print("[Step 3] Initializing agent...")
        db_factory = SessionLocal
        agent = SentimentAnalysisAgent(db_factory=db_factory)
        print("✅ Agent initialized\n")
        
        # Step 4: Run cycle
        print("[Step 4] Running full data collection cycle...")
        print("   This includes:")
        print("   - Phase 1: Data Collection (from multiple sources)")
        print("   - Phase 2: Load Raw Data")
        print("   - Phase 3: Deduplication")
        print("   - Phase 4: Sentiment & Topic Analysis")
        print("   - Phase 5: Location Classification")
        print("   - Phase 6: Issue Detection & Aggregation")
        print("\n   ⏳ This may take several minutes...\n")
        
        start_time = time.time()
        
        # Run the cycle
        agent.run_single_cycle_parallel(user_id=user_id)
        
        elapsed_time = time.time() - start_time
        
        print(f"\n✅ Cycle completed in {elapsed_time / 60:.1f} minutes ({elapsed_time:.1f} seconds)\n")
        
        # Step 5: Check results
        print("[Step 5] Checking cycle results...")
        results = check_cycle_results(user_id, initial_count)
        
        print("\n" + "=" * 80)
        print("TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"Execution Time: {elapsed_time / 60:.1f} minutes ({elapsed_time:.1f} seconds)")
        print(f"\nDatabase Changes:")
        print(f"   Initial Records: {results.get('before_count', initial_count)}")
        print(f"   Total Records: {results.get('total_count', 0)}")
        print(f"   New Records Added: {results.get('new_records', 0)}")
        print(f"   Records with Sentiment: {results.get('with_sentiment', 0)}")
        print(f"   Records with Topics: {results.get('with_topics', 0)}")
        
        # Check for raw data files
        config = ConfigManager()
        paths = PathManager(config)
        raw_data_dir = paths.data_raw
        if raw_data_dir.exists():
            csv_files = list(raw_data_dir.glob("*.csv"))
            print(f"\nRaw Data Files:")
            print(f"   CSV files in data/raw/: {len(csv_files)}")
            if csv_files:
                print("   Recent files:")
                for f in sorted(csv_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                    size = f.stat().st_size / 1024  # KB
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    print(f"     - {f.name} ({size:.1f} KB, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
        
        print("=" * 80)
        
        if results.get('new_records', 0) > 0:
            print("\n✅ SUCCESS: Cycle completed and new data was collected!")
            return 0
        else:
            print("\n⚠️  WARNING: Cycle completed but no new records were added.")
            print("   This could mean:")
            print("   - All data was duplicates")
            print("   - Collectors didn't find new data")
            print("   - Collection sources are not configured")
            return 0  # Still success, just no new data
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
