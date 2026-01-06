import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text, func, Column
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add src to path
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))

from src.api.models import SentimentData
from src.api.database import Base

# Load environment variables
try:
    from src.config.path_manager import PathManager
    path_manager = PathManager()
    env_path = path_manager.config_dir / '.env'
except Exception:
    env_path = Path(__file__).parent.parent / 'config' / '.env'

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found. Exiting.")
    sys.exit(1)

print(f"Connecting to database: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

def analyze_columns():
    inspector = inspect(engine)
    columns = inspector.get_columns('sentiment_data')
    
    total_rows = session.query(func.count(SentimentData.entry_id)).scalar()
    print(f"Total rows in sentiment_data: {total_rows}")
    
    if total_rows == 0:
        print("Table is empty.")
        return

    unused_columns = []
    partially_used_columns = []
    used_columns = []

    print("\nAnalyzing columns...")
    print(f"{'Column':<30} | {'Non-Null Count':<15} | {'Null Count':<15} | {'% Filled':<10}")
    print("-" * 80)

    for col in columns:
        col_name = col['name']
        # Dynamically build query for count of non-nulls
        # We use text() for flexibility or getattr on model if available
        # getattr is safer with ORM, but let's use raw SQL for speed on checking non-nulls
        
        query = text(f"SELECT COUNT(*) FROM sentiment_data WHERE \"{col_name}\" IS NOT NULL")
        try:
            non_null_count = session.execute(query).scalar()
        except Exception as e:
            print(f"Error querying {col_name}: {e}")
            continue
            
        null_count = total_rows - non_null_count
        percent_filled = (non_null_count / total_rows) * 100
        
        print(f"{col_name:<30} | {non_null_count:<15} | {null_count:<15} | {percent_filled:.1f}%")
        
        if non_null_count == 0:
            unused_columns.append(col_name)
        elif non_null_count < total_rows:
            partially_used_columns.append(col_name)
        else:
            used_columns.append(col_name)

    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"Total Columns: {len(columns)}")
    print(f"Unused Columns (Always NULL): {len(unused_columns)}")
    print(f"Partially Used Columns: {len(partially_used_columns)}")
    print(f"Fully Used Columns: {len(used_columns)}")
    
    print("\n--- Unused Columns (Candidates for Removal) ---")
    for col in unused_columns:
        print(f"- {col}")

if __name__ == "__main__":
    analyze_columns()
