"""
Script to identify and fix timestamp issues in the database.

This script finds records where:
1. date/published_at/published_date are set to recent times (within last 24 hours)
2. But the content suggests they should be older
3. Extracts dates from content when possible
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import re

# Set path to project root (same pattern as other scripts)
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Now we can import from src
from src.api.database import SessionLocal
from src.api.models import SentimentData
from src.utils.common import parse_datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

def extract_date_from_content(text: str) -> datetime:
    """
    Try to extract date from content text.
    Looks for patterns like:
    - "John 12/01/2026"
    - "12/01/2026"
    - "January 12, 2026"
    - "12 Jan 2026"
    """
    if not text:
        return None
    
    # Pattern 1: "John 12/01/2026" or "Name DD/MM/YYYY"
    pattern1 = r'(\w+)\s+(\d{1,2})/(\d{1,2})/(\d{4})'
    match = re.search(pattern1, text)
    if match:
        day, month, year = int(match.group(2)), int(match.group(3)), int(match.group(4))
        try:
            return datetime(year, month, day)
        except ValueError:
            pass
    
    # Pattern 2: "DD/MM/YYYY" or "MM/DD/YYYY" (try both)
    pattern2 = r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b'
    matches = re.findall(pattern2, text)
    for match in matches:
        day, month, year = int(match[0]), int(match[1]), int(match[2])
        # Try DD/MM/YYYY first (more common in international)
        try:
            dt = datetime(year, month, day)
            if dt < datetime.now():  # Only accept past dates
                return dt
        except ValueError:
            pass
        # Try MM/DD/YYYY
        try:
            dt = datetime(year, day, month)
            if dt < datetime.now():
                return dt
        except ValueError:
            pass
    
    # Pattern 3: "January 12, 2026" or "12 January 2026"
    month_names = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    pattern3 = r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})\b'
    match = re.search(pattern3, text, re.IGNORECASE)
    if match:
        month_name = match.group(0).split()[0].lower()
        day = int(match.group(1))
        year = int(match.group(2))
        month = month_names.get(month_name)
        if month:
            try:
                dt = datetime(year, month, day)
                if dt < datetime.now():
                    return dt
            except ValueError:
                pass
    
    return None

def check_and_fix_records():
    """Check database for problematic timestamp entries and fix them."""
    db: Session = SessionLocal()
    
    try:
        # Find records from last 24 hours that might be incorrectly timestamped
        # Focus on website platform records
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        print("=" * 80)
        print("Checking for problematic timestamp entries...")
        print("=" * 80)
        
        # Query records with recent timestamps
        problematic_records = db.query(SentimentData).filter(
            and_(
                SentimentData.platform == 'website',
                or_(
                    SentimentData.date >= cutoff_time,
                    SentimentData.published_at >= cutoff_time,
                    SentimentData.published_date >= cutoff_time
                )
            )
        ).limit(100).all()
        
        print(f"Found {len(problematic_records)} potentially problematic records")
        print()
        
        fixed_count = 0
        skipped_count = 0
        
        for record in problematic_records:
            # Try to extract date from content
            content = record.text or record.title or record.description or ''
            
            # Extract date from content
            extracted_date = extract_date_from_content(content)
            
            if extracted_date:
                # Check if extracted date is significantly different from current date
                if extracted_date < cutoff_time:
                    print(f"Record {record.entry_id}:")
                    print(f"  URL: {record.url[:80] if record.url else 'None'}")
                    print(f"  Current date: {record.date}")
                    print(f"  Current published_at: {record.published_at}")
                    print(f"  Current published_date: {record.published_date}")
                    print(f"  Extracted date from content: {extracted_date}")
                    print(f"  Content snippet: {content[:100]}...")
                    
                    # Update the record
                    record.date = extracted_date
                    record.published_at = extracted_date
                    record.published_date = extracted_date
                    
                    fixed_count += 1
                    print(f"  ✓ FIXED: Updated to {extracted_date}")
                    print()
            else:
                skipped_count += 1
                if skipped_count <= 5:  # Show first 5 skipped
                    print(f"Record {record.entry_id}: Could not extract date from content")
                    print(f"  Content: {content[:100]}...")
                    print()
        
        if fixed_count > 0:
            db.commit()
            print("=" * 80)
            print(f"✓ Successfully fixed {fixed_count} records")
            print(f"  Skipped {skipped_count} records (could not extract date)")
            print("=" * 80)
        else:
            print("=" * 80)
            print("No records needed fixing")
            print("=" * 80)
        
        # Also check for records with NULL dates that should have dates
        print()
        print("Checking for records with NULL dates that might need dates...")
        null_date_records = db.query(SentimentData).filter(
            and_(
                SentimentData.platform == 'website',
                SentimentData.date.is_(None),
                SentimentData.published_at.is_(None),
                SentimentData.published_date.is_(None)
            )
        ).limit(50).all()
        
        print(f"Found {len(null_date_records)} records with NULL dates")
        
        null_fixed_count = 0
        for record in null_date_records:
            content = record.text or record.title or record.description or ''
            extracted_date = extract_date_from_content(content)
            
            if extracted_date and extracted_date < datetime.now():
                record.date = extracted_date
                record.published_at = extracted_date
                record.published_date = extracted_date
                null_fixed_count += 1
                print(f"  Fixed record {record.entry_id}: {extracted_date}")
        
        if null_fixed_count > 0:
            db.commit()
            print(f"✓ Fixed {null_fixed_count} NULL date records")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    check_and_fix_records()
