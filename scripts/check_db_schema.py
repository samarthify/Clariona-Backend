#!/usr/bin/env python3
"""
Script to check the actual database schema for sentiment_data table
Run with: python scripts/check_db_schema.py
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not found in environment variables")
    print("Please check your .env file")
    sys.exit(1)

print("Connecting to database...\n")

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    inspector = inspect(engine)
except Exception as e:
    print(f"Error connecting to database: {e}")
    sys.exit(1)

try:
    print("Checking sentiment_data table schema...\n")
    
    # Get all columns from sentiment_data table
    columns = inspector.get_columns('sentiment_data')
    
    print(f"Found {len(columns)} columns in sentiment_data table:\n")
    
    # Look for date/time related columns
    date_columns = []
    all_columns = []
    
    for col in columns:
        col_name = col['name']
        col_type = str(col['type'])
        nullable = col['nullable']
        all_columns.append((col_name, col_type, nullable))
        
        # Check if it's a date/time column
        if 'date' in col_name.lower() or 'time' in col_name.lower() or 'timestamp' in col_name.lower():
            date_columns.append((col_name, col_type, nullable))
    
    print("All columns:")
    print("-" * 80)
    for col_name, col_type, nullable in sorted(all_columns):
        null_str = "NULL" if nullable else "NOT NULL"
        print(f"  {col_name:40} {col_type:30} {null_str}")
    
    print("\n" + "=" * 80)
    print("Date/Time related columns:")
    print("-" * 80)
    for col_name, col_type, nullable in sorted(date_columns):
        null_str = "NULL" if nullable else "NOT NULL"
        print(f"  {col_name:40} {col_type:30} {null_str}")
    
    # Also check for published* columns specifically
    print("\n" + "=" * 80)
    print("Published-related columns:")
    print("-" * 80)
    published_cols = [col for col in all_columns if 'publish' in col[0].lower()]
    if published_cols:
        for col_name, col_type, nullable in published_cols:
            null_str = "NULL" if nullable else "NOT NULL"
            print(f"  {col_name:40} {col_type:30} {null_str}")
    else:
        print("  No columns found with 'publish' in the name")
    
    db.close()
    print('\nCheck complete!')
    
except Exception as e:
    print(f'Error checking schema: {e}')
    import traceback
    traceback.print_exc()
    db.close()
    sys.exit(1)

