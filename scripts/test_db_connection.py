#!/usr/bin/env python3
"""
Simple script to test database connection.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
config_env_path = Path(__file__).parent.parent / 'config' / '.env'
if config_env_path.exists():
    load_dotenv(dotenv_path=config_env_path)

root_env_path = Path(__file__).parent.parent / '.env'
if root_env_path.exists():
    load_dotenv(dotenv_path=root_env_path)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found")
    sys.exit(1)

print("=" * 80)
print("TESTING DATABASE CONNECTION")
print("=" * 80)
print()
print(f"Database URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}")
print()

try:
    print("Creating engine...")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    
    print("Attempting to connect...")
    with engine.connect() as conn:
        print("Connection successful!")
        print()
        
        # Get database info
        result = conn.execute(text("SELECT current_database(), version()"))
        db_name, db_version = result.fetchone()
        
        print(f"Database Name: {db_name}")
        print(f"PostgreSQL Version: {db_version.split(',')[0]}")
        print()
        
        # Check existing tables
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        
        tables = [row[0] for row in result.fetchall()]
        print(f"Existing tables ({len(tables)}):")
        for table in tables:
            print(f"  - {table}")
        print()
        
        # Check if topics table exists
        if 'topics' in tables:
            result = conn.execute(text("SELECT COUNT(*) FROM topics"))
            count = result.fetchone()[0]
            print(f"Topics table exists with {count} topics")
        else:
            print("Topics table does not exist yet")
        
        print()
        print("=" * 80)
        print("CONNECTION TEST SUCCESSFUL")
        print("=" * 80)
        
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    print()
    print("Connection failed. Possible reasons:")
    print("  - Network/firewall blocking the connection")
    print("  - Database server is down")
    print("  - Incorrect credentials")
    print("  - VPN or specific network access required")
    sys.exit(1)
















