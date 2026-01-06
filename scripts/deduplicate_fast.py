"""
Fast Deduplication using Raw SQL.
Bypasses ORM overhead for maximum speed.
"""
import sys
import time
from pathlib import Path

# Add src to path
src_path = Path(__file__).resolve().parent.parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import text
from api.database import SessionLocal

def deduplicate_fast():
    session = SessionLocal()
    start_time = time.time()
    try:
        print("Starting fast deduplication (Raw SQL)...")
        
        # 1. Identify victim IDs (keep only the latest entry_id per URL)
        # We store these in a temporary table or CTE for cleaner deletion
        print("Counting duplicates...")
        
        # Raw SQL for cleanup
        # This deletes child records first, then the main records
        
        cleanup_sql = """
            WITH duplicates AS (
                SELECT entry_id,
                       ROW_NUMBER() OVER (PARTITION BY url ORDER BY entry_id DESC) as rn
                FROM sentiment_data
                WHERE url IS NOT NULL
            ),
            victims AS (
                SELECT entry_id FROM duplicates WHERE rn > 1
            )
            -- We can't delete from multiple tables in one go, but we can use the logic 
            -- repeatedly or do it in steps.
            SELECT count(*) FROM victims;
        """
        
        count = session.execute(text(cleanup_sql)).scalar()
        if count == 0:
            print("No duplicates found!")
            return
            
        print(f"Found {count} duplicate records to delete.")
        
        print("Deleting dependent records...")
        
        # We'll use a temporary table to hold victim IDs to avoid recalculating
        session.execute(text("CREATE TEMP TABLE temp_victims AS \
            SELECT entry_id FROM ( \
                SELECT entry_id, ROW_NUMBER() OVER (PARTITION BY url ORDER BY entry_id DESC) as rn \
                FROM sentiment_data \
                WHERE url IS NOT NULL \
            ) t WHERE rn > 1"))
        
        # Create index on temp table to speed up deletions
        session.execute(text("CREATE INDEX idx_temp_victims ON temp_victims(entry_id)"))
        
        # Delete from children
        print("- Cleaning issue_mentions...")
        session.execute(text("DELETE FROM issue_mentions WHERE mention_id IN (SELECT entry_id FROM temp_victims)"))
        
        print("- Cleaning mention_topics...")
        session.execute(text("DELETE FROM mention_topics WHERE mention_id IN (SELECT entry_id FROM temp_victims)"))
        
        print("- Cleaning sentiment_embeddings...")
        session.execute(text("DELETE FROM sentiment_embeddings WHERE entry_id IN (SELECT entry_id FROM temp_victims)"))
        
        # Delete from main table
        print("- Deleting duplicate SentimentData records...")
        session.execute(text("DELETE FROM sentiment_data WHERE entry_id IN (SELECT entry_id FROM temp_victims)"))
        
        # Drop temp table
        session.execute(text("DROP TABLE temp_victims"))
        
        session.commit()
        duration = time.time() - start_time
        print(f"DONE. Deleted {count} records in {duration:.2f} seconds.")
        
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    deduplicate_fast()
