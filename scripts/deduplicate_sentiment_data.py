"""
Deduplicate SentimentData script (Nuclear Option).
Removes duplicate records based on URL, keeping the most recent one.
Forcefully deletes dependent child records for duplicates.
"""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).resolve().parent.parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import text
from api.database import SessionLocal
from api.models import SentimentData, IssueMention, MentionTopic, SentimentEmbedding

def deduplicate():
    session = SessionLocal()
    try:
        print("Checking for duplicates...")
        
        # Find URLs with count > 1
        query = text("""
            SELECT url, COUNT(*) 
            FROM sentiment_data 
            WHERE url IS NOT NULL 
            GROUP BY url 
            HAVING COUNT(*) > 1
        """)
        
        duplicates = session.execute(query).fetchall()
        
        if not duplicates:
            print("No duplicates found.")
            return

        print(f"Found {len(duplicates)} URLs with duplicates.")
        
        total_deleted = 0
        
        for url, count in duplicates:
            # Get all entries for this URL, ordered by entry_id DESC (newest first)
            entries = session.query(SentimentData).filter(SentimentData.url == url).order_by(SentimentData.entry_id.desc()).all()
            
            # Survivor is the first one (newest)
            victims = entries[1:]
            
            if not victims:
                continue

            victim_ids = [v.entry_id for v in victims]
            
            # DELETE ALL CHILD RECORDS FOR VICTIMS
            session.query(IssueMention).filter(IssueMention.mention_id.in_(victim_ids)).delete(synchronize_session=False)
            session.query(MentionTopic).filter(MentionTopic.mention_id.in_(victim_ids)).delete(synchronize_session=False)
            session.query(SentimentEmbedding).filter(SentimentEmbedding.entry_id.in_(victim_ids)).delete(synchronize_session=False)
            
            # NOW DELETE VICTIMS
            session.query(SentimentData).filter(SentimentData.entry_id.in_(victim_ids)).delete(synchronize_session=False)
            
            total_deleted += len(victim_ids)
            
            if total_deleted % 100 == 0:
                session.commit()
                print(f"Cleaned up {total_deleted} duplicates...")
        
        session.commit()
        print(f"DONE. Successfully deleted {total_deleted} duplicate records.")
        
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    deduplicate()
