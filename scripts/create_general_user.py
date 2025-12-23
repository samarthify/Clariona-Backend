#!/usr/bin/env python3
"""
Script to create a new user with 'general' role
Run with: python scripts/create_general_user.py
Or with args: python scripts/create_general_user.py --email user@example.com --username testuser --name "Test User" --password mypassword
"""

import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
import os
import uuid
from datetime import datetime

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.api.models import User
import bcrypt

# Load environment variables
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    sys.exit(1)

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    # Encode password to bytes
    password_bytes = password.encode('utf-8')
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=10)
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string
    return hashed.decode('utf-8')

def create_general_user(email: str, username: str = None, name: str = None, password: str = None):
    """Create a new user with general role"""
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        sys.exit(1)

    try:
        # Check if user with email already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"❌ User with email '{email}' already exists!")
            print(f"   User ID: {existing_user.id}")
            print(f"   Current Role: {existing_user.role or 'NULL'}")
            db.close()
            return False

        # Generate user ID
        user_id = str(uuid.uuid4())

        # Hash password if provided
        password_hash = None
        if password:
            password_hash = hash_password(password)

        # Create new user
        new_user = User(
            id=user_id,
            email=email,
            username=username,
            name=name,
            password_hash=password_hash,
            role='general',
            ministry=None,  # General users don't have a ministry
            is_admin=False,
            created_at=datetime.now(),
            api_calls_count=0,
            data_entries_count=0
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        print("✅ General user created successfully!\n")
        print("📋 User Details:")
        print(f"   User ID: {new_user.id}")
        print(f"   Email: {new_user.email}")
        print(f"   Username: {new_user.username or 'N/A'}")
        print(f"   Name: {new_user.name or 'N/A'}")
        print(f"   Role: {new_user.role}")
        print(f"   Ministry: {new_user.ministry or 'N/A'}")
        print(f"   Is Admin: {new_user.is_admin}")
        print(f"   Created: {new_user.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n💡 This user can view alerts but cannot mark them as read or dismiss them.")

        db.close()
        return True

    except Exception as e:
        print(f'❌ Error creating user: {e}')
        import traceback
        traceback.print_exc()
        db.rollback()
        db.close()
        return False

def main():
    parser = argparse.ArgumentParser(description='Create a new user with general role')
    parser.add_argument('--email', type=str, required=True, help='User email address')
    parser.add_argument('--username', type=str, help='Username (optional)')
    parser.add_argument('--name', type=str, help='Full name (optional)')
    parser.add_argument('--password', type=str, help='Password (optional, will prompt if not provided)')
    
    args = parser.parse_args()

    # If password not provided, prompt for it
    password = args.password
    if not password:
        import getpass
        password = getpass.getpass("Enter password (or press Enter to skip): ")
        if password:
            password_confirm = getpass.getpass("Confirm password: ")
            if password != password_confirm:
                print("❌ Passwords do not match!")
                sys.exit(1)

    create_general_user(
        email=args.email,
        username=args.username,
        name=args.name,
        password=password if password else None
    )

if __name__ == '__main__':
    main()

