#!/usr/bin/env python3
"""
Create users for Economy and Insecurity dashboards.

These users get owner_key minister_economy_dashboard and minister_insecurity_dashboard
(via user.ministry), which are already configured in owner_configs from
config/minister_configs/economy_dashboard_config.json and insecurity_dashboard_config.json.

Usage:
  python scripts/create_dashboard_users.py
  python scripts/create_dashboard_users.py --email-economy economy@example.com --email-insecurity insecurity@example.com
  python scripts/create_dashboard_users.py --economy-only --email economy@example.com --password secret
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


def create_dashboard_user(
    db,
    email: str,
    ministry: str,
    name: str = None,
    username: str = None,
    password: str = None,
) -> bool:
    """Create a user with role=minister and the given ministry (economy_dashboard or insecurity_dashboard)."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"⚠️  User '{email}' already exists (ministry={existing.ministry}). Skipping.")
        return False

    user_id = str(uuid.uuid4())
    password_hash = hash_password(password) if password else None

    user = User(
        id=user_id,
        email=email,
        username=username or email.split('@')[0],
        name=name,
        password_hash=password_hash,
        role='minister',
        ministry=ministry,
        is_admin=False,
        created_at=datetime.now(),
        api_calls_count=0,
        data_entries_count=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    owner_key = f"minister_{ministry}"
    print(f"✅ Created user: {email} → owner_key={owner_key}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Create Economy and Insecurity dashboard users")
    parser.add_argument("--email-economy", type=str, default="economy-dashboard@example.com", help="Email for Economy dashboard user")
    parser.add_argument("--email-insecurity", type=str, default="insecurity-dashboard@example.com", help="Email for Insecurity dashboard user")
    parser.add_argument("--economy-only", action="store_true", help="Create only Economy dashboard user")
    parser.add_argument("--insecurity-only", action="store_true", help="Create only Insecurity dashboard user")
    parser.add_argument("--email", type=str, help="Single email (used with --economy-only or --insecurity-only)")
    parser.add_argument("--name", type=str, help="Display name (for single-user create)")
    parser.add_argument("--password", type=str, help="Password (optional)")
    args = parser.parse_args()

    if not args.password and (args.economy_only or args.insecurity_only):
        import getpass
        args.password = getpass.getpass("Password (or Enter to leave unset): ")

    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        sys.exit(1)

    try:
        created = 0
        if args.economy_only:
            email = args.email or args.email_economy
            if create_dashboard_user(db, email, "economy_dashboard", name=args.name, password=args.password):
                created += 1
        elif args.insecurity_only:
            email = args.email or args.email_insecurity
            if create_dashboard_user(db, email, "insecurity_dashboard", name=args.name, password=args.password):
                created += 1
        else:
            if create_dashboard_user(db, args.email_economy, "economy_dashboard", password=args.password):
                created += 1
            if not args.insecurity_only and create_dashboard_user(db, args.email_insecurity, "insecurity_dashboard", password=args.password):
                created += 1

        if created:
            print("\n💡 Run 'python scripts/sync_users_to_owner_configs.py' to ensure owner_configs match (optional; configs already exist from JSON).")
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
