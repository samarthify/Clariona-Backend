import sys
import os
import datetime
# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from api.database import SessionLocal, engine, Base
from api.models import SentimentData
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func, text, cast, String

# Create table if not exists
Base.metadata.create_all(bind=engine)

def test_upsert_with_cast():
    session = SessionLocal()
    try:
        # 1. Insert initial record
        url = f"http://test.com/{datetime.datetime.now().timestamp()}"
        initial_record = {
            "url": url,
            "title": "Initial",
            "published_date": datetime.datetime.now(),
            "user_location": None, # Initially None
            "run_timestamp": datetime.datetime.now()
        }
        
        stmt = pg_insert(SentimentData).values(**initial_record)
        stmt = stmt.on_conflict_do_nothing(index_elements=['url'])
        session.execute(stmt)
        session.commit()
        
        print("Initial record inserted.")
        
        # 2. Try upsert with the problematic logic
        new_record = {
            "url": url,
            "title": "Updated", # Should update
            "user_location": "New Location", # Should backfill
            "run_timestamp": datetime.datetime.now()
        }
        
        stmt = pg_insert(SentimentData).values(**new_record)
        
        # Mimic the logic in data_ingestor.py
        update_dict = {}
        
        # simplified backfill logic using text() to avoid bindparam error
        from sqlalchemy import text
        field = 'user_location'
        update_dict[field] = func.coalesce(
            getattr(SentimentData, field), 
            text(f'excluded.{field}')
        )
        
        stmt = stmt.on_conflict_do_update(
            index_elements=['url'],
            set_=update_dict
        )
        
        print("Executing problematic upsert...")
        session.execute(stmt)
        session.commit()
        print("Upsert successful!")
        
        # Verify result
        obj = session.query(SentimentData).filter_by(url=url).first()
        print(f"Result User Location: {obj.user_location}")
        
    except Exception as e:
        print(f"Upsert failed: {e}")
        # import traceback
        # traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_upsert_with_cast()
