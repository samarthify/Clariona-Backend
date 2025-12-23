#!/usr/bin/env python3
"""
Script to check users table for general role users
Run with: python scripts/check_users.py
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from src.api.models import User

# Load environment variables
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    print("   Please check your .env file")
    sys.exit(1)

print(f"🔍 Connecting to database...\n")

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
except Exception as e:
    print(f"❌ Error connecting to database: {e}")
    sys.exit(1)

try:
    print("👥 Checking Users Table...\n")

    # Get all users
    all_users = db.query(User).all()
    print(f"📊 Total users in database: {len(all_users)}\n")

    # Group by role
    print("📋 Users by Role:")
    role_counts = {}
    for user in all_users:
        role = user.role or 'NULL'
        if role not in role_counts:
            role_counts[role] = []
        role_counts[role].append(user)

    for role, users in sorted(role_counts.items()):
        print(f"  {role}: {len(users)} user(s)")

    # Check specifically for general users
    print("\n🔍 Checking for 'general' role users:")
    general_users = [u for u in all_users if u.role and u.role.lower() == 'general']
    
    if general_users:
        print(f"  ✅ Found {len(general_users)} general user(s):\n")
        for idx, user in enumerate(general_users, 1):
            print(f"  {idx}. User ID: {user.id}")
            print(f"     Email: {user.email}")
            print(f"     Username: {user.username or 'N/A'}")
            print(f"     Name: {user.name or 'N/A'}")
            print(f"     Role: {user.role}")
            print(f"     Ministry: {user.ministry or 'N/A'}")
            print(f"     Is Admin: {user.is_admin}")
            print(f"     Created: {user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else 'N/A'}")
            print(f"     Last Login: {user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else 'Never'}")
            print()
    else:
        print("  ❌ No users with 'general' role found")
        print("  💡 You can create a general user by setting role='general' in the users table")

    # Show all roles for reference
    print("\n📊 All unique roles in database:")
    unique_roles = set(u.role for u in all_users if u.role)
    for role in sorted(unique_roles):
        count = sum(1 for u in all_users if u.role == role)
        print(f"  '{role}': {count} user(s)")

    # Show sample of all users
    print("\n📋 Sample of all users (first 10):")
    for idx, user in enumerate(all_users[:10], 1):
        print(f"\n  {idx}. Email: {user.email}")
        print(f"     Username: {user.username or 'N/A'}")
        print(f"     Name: {user.name or 'N/A'}")
        print(f"     Role: {user.role or 'NULL'}")
        print(f"     Ministry: {user.ministry or 'N/A'}")
        print(f"     Is Admin: {user.is_admin}")

    db.close()
    print('\n✅ Check complete!')
    
except Exception as e:
    print(f'❌ Error checking users: {e}')
    import traceback
    traceback.print_exc()
    db.close()
    sys.exit(1)













