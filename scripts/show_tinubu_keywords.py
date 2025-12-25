#!/usr/bin/env python3
"""
Script to show keywords for the Tinubu user.
"""

import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import TargetIndividualConfiguration, User

def get_tinubu_user_keywords():
    """Get keywords for the Tinubu user."""
    db = SessionLocal()
    try:
        # First, find users with "tinubu" in their email, username, or name
        users = db.query(User).filter(
            (User.email.ilike('%tinubu%')) |
            (User.username.ilike('%tinubu%')) |
            (User.name.ilike('%tinubu%'))
        ).all()
        
        if not users:
            print("No user found with 'tinubu' in email, username, or name.")
            print("\nSearching for target configurations with 'tinubu' in individual_name...")
            
            # Try searching by individual_name in target configurations
            configs = db.query(TargetIndividualConfiguration).filter(
                TargetIndividualConfiguration.individual_name.ilike('%tinubu%')
            ).all()
            
            if not configs:
                print("No target configuration found with 'tinubu' in individual name.")
                return
            
            print(f"\nFound {len(configs)} target configuration(s) with 'tinubu':\n")
            for config in configs:
                user = db.query(User).filter(User.id == config.user_id).first() if config.user_id else None
                print(f"  Configuration ID: {config.id}")
                print(f"  Individual Name: {config.individual_name}")
                print(f"  User ID: {str(config.user_id) if config.user_id else 'N/A'}")
                print(f"  User Email: {user.email if user else 'N/A'}")
                print(f"  User Name: {user.name if user else 'N/A'}")
                print(f"  Keywords ({len(config.query_variations) if config.query_variations else 0}):")
                if config.query_variations:
                    for i, keyword in enumerate(config.query_variations, 1):
                        print(f"    {i}. {keyword}")
                else:
                    print("    (No keywords set)")
                print()
            return
        
        print(f"Found {len(users)} user(s) with 'tinubu':\n")
        for user in users:
            print(f"  User ID: {str(user.id)}")
            print(f"  Email: {user.email}")
            print(f"  Username: {user.username or 'N/A'}")
            print(f"  Name: {user.name or 'N/A'}")
            
            # Get target configurations for this user
            configs = db.query(TargetIndividualConfiguration).filter(
                TargetIndividualConfiguration.user_id == user.id
            ).order_by(TargetIndividualConfiguration.created_at.desc()).all()
            
            if not configs:
                print("  No target configurations found for this user.\n")
            else:
                print(f"  Found {len(configs)} target configuration(s):\n")
                for config in configs:
                    print(f"    Configuration ID: {config.id}")
                    print(f"    Individual Name: {config.individual_name}")
                    print(f"    Keywords ({len(config.query_variations) if config.query_variations else 0}):")
                    if config.query_variations:
                        for i, keyword in enumerate(config.query_variations, 1):
                            print(f"      {i}. {keyword}")
                    else:
                        print("      (No keywords set)")
                    print()
    finally:
        db.close()

if __name__ == "__main__":
    get_tinubu_user_keywords()

