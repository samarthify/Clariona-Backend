#!/usr/bin/env python3
"""
Script to verify connection to the development database.
Shows current database connection and confirms we're using the dev database.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# DEVELOPMENT DATABASE URL - NOT PRODUCTION
DEV_DATABASE_URL = "postgresql://postgres:ZZimVTzeAZGzjfkDPJRgnNeARSBZrqfe@shinkansen.proxy.rlwy.net:50662/railway"

def main():
    print("=" * 80)
    print("DATABASE CONNECTION VERIFICATION")
    print("=" * 80)
    print()
    
    # Check environment variable
    env_db_url = os.getenv("DATABASE_URL")
    if env_db_url:
        env_display = env_db_url.split('@')[1] if '@' in env_db_url else 'hidden'
        print(f"📋 Environment DATABASE_URL: {env_display}")
    else:
        print("📋 Environment DATABASE_URL: Not set")
    print()
    
    # Use dev database
    database_url = DEV_DATABASE_URL
    db_display = database_url.split('@')[1] if '@' in database_url else 'hidden'
    print(f"🔗 Using DEV Database: {db_display}")
    print()
    
    try:
        # Test connection
        engine = create_engine(database_url)
        with engine.connect() as conn:
            # Get database name and version
            result = conn.execute(text("SELECT current_database(), version()"))
            db_name, db_version = result.fetchone()
            
            print("✅ Connection successful!")
            print(f"   Database: {db_name}")
            print(f"   Version: {db_version.split(',')[0]}")
            print()
            
            # Check if topics table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'topics'
                )
            """))
            topics_exists = result.fetchone()[0]
            
            if topics_exists:
                # Count topics
                result = conn.execute(text("SELECT COUNT(*) FROM topics"))
                topic_count = result.fetchone()[0]
                print(f"📊 Topics table exists with {topic_count} topics")
            else:
                print("⚠️  Topics table does not exist yet (run migration first)")
            
            # Check if owner_configs table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'owner_configs'
                )
            """))
            owner_configs_exists = result.fetchone()[0]
            
            if owner_configs_exists:
                # Count owner configs
                result = conn.execute(text("SELECT COUNT(*) FROM owner_configs"))
                config_count = result.fetchone()[0]
                print(f"📊 Owner configs table exists with {config_count} configs")
            else:
                print("⚠️  Owner configs table does not exist yet (run migration first)")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    main()
















