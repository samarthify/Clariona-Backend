
import sys
import os
from pathlib import Path
from sqlalchemy import text
from datetime import datetime, timedelta
from sqlalchemy import func

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.api.database import SessionLocal
from src.api.models import SentimentData
from src.services.data_ingestor import DataIngestor

def check_recent_locations():
    session = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(hours=24)
        print(f"Checking records since {cutoff}...")
        
        recent = session.query(SentimentData).filter(SentimentData.created_at >= cutoff)
        total_recent = recent.count()
        
        null_recent = recent.filter(SentimentData.user_location.is_(None)).count()
        empty_recent = recent.filter(SentimentData.user_location == '').count()
        valid_recent = recent.filter(SentimentData.user_location != None, SentimentData.user_location != '').count()
        
        print(f"Total Recent: {total_recent}")
        print(f"NULL Recent: {null_recent}")
        print(f"Empty Recent: {empty_recent}")
        print(f"Valid Recent: {valid_recent}")
        
        print("\nBreakdown by Platform:")
        platforms = session.query(SentimentData.platform, func.count(SentimentData.entry_id)).filter(SentimentData.created_at >= cutoff).group_by(SentimentData.platform).all()
        for platform, count in platforms:
            missing = session.query(SentimentData).filter(
                SentimentData.created_at >= cutoff,
                SentimentData.platform == platform,
                (SentimentData.user_location.is_(None) | (SentimentData.user_location == ''))
            ).count()
            print(f"  {platform}: {count} total, {missing} missing location ({missing/count*100:.1f}%)")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_recent_locations()
