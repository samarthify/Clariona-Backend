#!/usr/bin/env python3
"""
Script to update keywords for a specific user by user ID.
"""

import sys
import uuid
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import TargetIndividualConfiguration, User

def update_keywords_for_user(user_id_str: str, new_keywords: list = None):
    """Update keywords for a user by user ID."""
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        print(f"Error: Invalid user ID format: {user_id_str}")
        return False
    
    db = SessionLocal()
    try:
        # Find the user
        user = db.query(User).filter(User.id == user_uuid).first()
        if not user:
            print(f"Error: User with ID {user_id_str} not found.")
            return False
        
        print(f"Found user:")
        print(f"  Email: {user.email}")
        print(f"  Username: {user.username or 'N/A'}")
        print(f"  Name: {user.name or 'N/A'}")
        
        # Find the target configuration for this user
        config = db.query(TargetIndividualConfiguration).filter(
            TargetIndividualConfiguration.user_id == user_uuid
        ).order_by(TargetIndividualConfiguration.created_at.desc()).first()
        
        if not config:
            print(f"\nError: No target configuration found for this user.")
            return False
        
        print(f"\nCurrent Configuration:")
        print(f"  Configuration ID: {config.id}")
        print(f"  Individual Name: {config.individual_name}")
        print(f"  Current Keywords ({len(config.query_variations) if config.query_variations else 0}):")
        if config.query_variations:
            for i, kw in enumerate(config.query_variations, 1):
                print(f"    {i}. {kw}")
        else:
            print("    (No keywords set)")
        
        # If keywords provided, update them
        if new_keywords is not None:
            old_keywords = config.query_variations or []
            config.query_variations = new_keywords
            db.commit()
            
            print(f"\nSuccessfully updated keywords!")
            print(f"\nOld keywords ({len(old_keywords)}):")
            for i, kw in enumerate(old_keywords, 1):
                print(f"  {i}. {kw}")
            
            print(f"\nNew keywords ({len(new_keywords)}):")
            for i, kw in enumerate(new_keywords, 1):
                print(f"  {i}. {kw}")
            return True
        else:
            # Interactive mode - ask for new keywords
            print(f"\nEnter new keywords (one per line, empty line to finish):")
            keywords = []
            while True:
                try:
                    line = input("  Keyword: ").strip()
                    if not line:
                        break
                    keywords.append(line)
                except (EOFError, KeyboardInterrupt):
                    print("\nCancelled.")
                    return False
            
            if not keywords:
                print("No keywords provided. No changes made.")
                return False
            
            old_keywords = config.query_variations or []
            config.query_variations = keywords
            db.commit()
            
            print(f"\nSuccessfully updated keywords!")
            print(f"\nOld keywords ({len(old_keywords)}):")
            for i, kw in enumerate(old_keywords, 1):
                print(f"  {i}. {kw}")
            
            print(f"\nNew keywords ({len(keywords)}):")
            for i, kw in enumerate(keywords, 1):
                print(f"  {i}. {kw}")
            return True
            
    except Exception as e:
        db.rollback()
        print(f"Error updating keywords: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python update_user_keywords.py <user_id> [keyword1,keyword2,...]")
        print("\nExample:")
        print("  python update_user_keywords.py 6440da7f-e630-4b2f-884e-a8721cc9a9c0")
        print("  python update_user_keywords.py 6440da7f-e630-4b2f-884e-a8721cc9a9c0 \"Keyword1,Keyword2,Keyword3\"")
        sys.exit(1)
    
    user_id = sys.argv[1]
    keywords = None
    
    if len(sys.argv) > 2:
        # Keywords provided as comma-separated string
        keywords = [k.strip() for k in sys.argv[2].split(',') if k.strip()]
    
    success = update_keywords_for_user(user_id, keywords)
    sys.exit(0 if success else 1)

