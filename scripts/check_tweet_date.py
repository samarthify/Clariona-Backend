"""
Script to check the date stored in database for a specific tweet/post_id
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Load environment variables - check multiple locations like database.py does
# First try config/.env
config_env_path = Path(__file__).parent.parent / 'config' / '.env'
if config_env_path.exists():
    load_dotenv(dotenv_path=config_env_path)

# Then try root .env
root_env_path = Path(__file__).parent.parent / '.env'
if root_env_path.exists():
    load_dotenv(dotenv_path=root_env_path)

# Also load from system environment variables (for Railway deployment)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    print("\nChecked locations:")
    print(f"  - config/.env: {config_env_path.exists()}")
    print(f"  - .env (root): {root_env_path.exists()}")
    print("  - System environment variables")
    print("\nPlease ensure DATABASE_URL is set in one of these locations.")
    sys.exit(1)

print(f"Using DATABASE_URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}")

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def check_tweet_date(post_id: str):
    """Query database for a specific tweet/post_id and show date information"""
    db = SessionLocal()
    
    try:
        # Query by post_id
        query = text("""
            SELECT 
                entry_id,
                post_id,
                url,
                date,
                created_at,
                run_timestamp,
                text,
                platform,
                user_name,
                published_date,
                published_at
            FROM sentiment_data
            WHERE post_id = :post_id
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        result = db.execute(query, {"post_id": post_id})
        rows = result.fetchall()
        
        if not rows:
            print(f"No records found for post_id: {post_id}")
            print("\nAlso checking by URL pattern...")
            # Try checking by URL
            url_pattern = f"%/status/{post_id}"
            url_query = text("""
                SELECT 
                    entry_id,
                    post_id,
                    url,
                    date,
                    created_at,
                    run_timestamp,
                    text,
                    platform
                FROM sentiment_data
                WHERE url LIKE :url_pattern
                ORDER BY created_at DESC
                LIMIT 10
            """)
            url_result = db.execute(url_query, {"url_pattern": url_pattern})
            url_rows = url_result.fetchall()
            
            if url_rows:
                print(f"\nFound {len(url_rows)} record(s) matching URL pattern:")
                for row in url_rows:
                    print("\n" + "="*80)
                    print(f"Entry ID: {row[0]}")
                    print(f"Post ID: {row[1]}")
                    print(f"URL: {row[2]}")
                    print(f"Date (tweet created_at): {row[3]}")
                    print(f"DB created_at: {row[4]}")
                    print(f"Run timestamp: {row[5]}")
                    print(f"Platform: {row[6]}")
                    if row[7]:
                        print(f"Text preview: {row[7][:100]}...")
            else:
                print(f"No records found matching URL pattern: {url_pattern}")
        else:
            print(f"\nFound {len(rows)} record(s) for post_id: {post_id}")
            for i, row in enumerate(rows, 1):
                print("\n" + "="*80)
                print(f"Record #{i}:")
                print(f"  Entry ID: {row[0]}")
                print(f"  Post ID: {row[1]}")
                print(f"  URL: {row[2]}")
                print(f"  Date (tweet created_at): {row[3]}")
                print(f"  DB created_at (when record was inserted): {row[4]}")
                print(f"  Run timestamp: {row[5]}")
                if row[6]:
                    print(f"  Text preview: {row[6][:150]}...")
                print(f"  Platform: {row[7]}")
                if row[8]:
                    print(f"  User name: {row[8]}")
                if row[9]:
                    print(f"  Published date: {row[9]}")
                if row[10]:
                    print(f"  Published at: {row[10]}")
                
    except Exception as e:
        print(f"\nError querying database: {e}")
        print("\nPlease ensure:")
        print("  1. Database server is running")
        print("  2. DATABASE_URL is correctly configured in .env file")
        print("  3. Database name matches your configuration")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    # Tweet ID from the URL: https://x.com/officialABAT/status/1928033114128887981
    tweet_id = "1928033114128887981"
    
    if len(sys.argv) > 1:
        tweet_id = sys.argv[1]
    
    print(f"Checking database for tweet/post_id: {tweet_id}")
    print("="*80)
    check_tweet_date(tweet_id)

