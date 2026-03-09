#!/usr/bin/env python3
"""
Create FMITI (Federal Ministry of Industry, Trade and Investment) minister user.

This user gets owner_key minister_industry_trade_investment (via user.ministry),
which is configured in owner_configs from config/minister_configs/fmiti_minister_config.json.

Usage:
  python scripts/create_fmiti_minister_user.py
  python scripts/create_fmiti_minister_user.py --email fmiti@example.com --username fmiti_minister --password YourSecurePassword
  python scripts/create_fmiti_minister_user.py --email fmiti@example.com --username fmiti_minister  # prompts for password
"""

import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
import os
import uuid
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.api.models import User
import bcrypt

env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    sys.exit(1)


def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=10)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_fmiti_minister_user(
    db,
    email: str,
    username: str,
    password: str,
    name: str = "FMITI Minister",
) -> bool:
    """Create a user with role=minister and ministry=industry_trade_investment (FMITI)."""
    ministry = "industry_trade_investment"
    existing_email = db.query(User).filter(User.email == email).first()
    existing_username = db.query(User).filter(User.username == username).first()
    if existing_email:
        print(f"⚠️  User with email '{email}' already exists (ministry={existing_email.ministry}). Skipping.")
        return False
    if existing_username:
        print(f"⚠️  Username '{username}' already taken. Skipping.")
        return False

    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)

    ministry_key = ministry.lower().replace(" ", "_").replace("-", "_")
    owner_key = f"minister_{ministry_key}"
    user = User(
        id=user_id,
        email=email,
        username=username,
        name=name,
        password_hash=password_hash,
        role='minister',
        ministry=ministry,
        owner_key=owner_key,
        is_admin=False,
        created_at=datetime.now(),
        api_calls_count=0,
        data_entries_count=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    print(f"✅ Created FMITI minister user: {email} (username={username}) → owner_key={owner_key}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Create FMITI minister user")
    parser.add_argument("--email", type=str, default="fmiti@example.com", help="Email for FMITI minister user")
    parser.add_argument("--username", type=str, default="fmiti_minister", help="Username for FMITI minister user")
    parser.add_argument("--password", type=str, help="Password (required)")
    parser.add_argument("--name", type=str, default="FMITI Minister", help="Display name")
    args = parser.parse_args()

    if not args.password:
        import getpass
        args.password = getpass.getpass("Password: ")
        if not args.password:
            print("❌ Password is required")
            sys.exit(1)

    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        sys.exit(1)

    try:
        if create_fmiti_minister_user(db, args.email, args.username, args.password, name=args.name):
            print("\n💡 Next steps:")
            print("  1. Run 'python scripts/populate_topics_from_json.py' to load FMITI topics and owner config")
            print("  2. Run 'python scripts/sync_users_to_owner_configs.py --user " + args.email + "' to sync owner config")
            print("  3. Run 'python src/processing/topic_embedding_generator.py' to generate embeddings for new topics")
        db.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        db.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
