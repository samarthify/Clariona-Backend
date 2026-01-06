"""
Show all users and their corresponding owner_configs.

This script displays:
- All users in the database
- Their roles and ministries
- Their corresponding owner_configs (if any)
- Topics assigned to each user
"""

import sys
from pathlib import Path
import logging

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from api.database import SessionLocal
from api.models import User, OwnerConfig, Topic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ShowUsersAndOwnerConfigs')


def get_owner_key_from_user(user: User) -> str:
    """Get owner_key from user information."""
    if user.role and user.role.lower() == 'president':
        return 'president'
    elif user.ministry:
        ministry_key = user.ministry.lower().replace(' ', '_').replace('-', '_')
        return f'minister_{ministry_key}'
    else:
        return f'user_{str(user.id).replace("-", "_")}'


def show_all_users_and_configs():
    """Display all users and their owner configs."""
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.email).all()
        configs = db.query(OwnerConfig).all()
        
        # Create mapping of owner_key to config
        config_map = {c.owner_key: c for c in configs}
        
        print("\n" + "="*80)
        print("USERS AND OWNER CONFIGS")
        print("="*80)
        print(f"\nTotal Users: {len(users)}")
        print(f"Total Owner Configs: {len(configs)}")
        print("\n" + "-"*80)
        
        for user in users:
            owner_key = get_owner_key_from_user(user)
            config = config_map.get(owner_key)
            
            print(f"\nUser: {user.email}")
            print(f"  ID: {user.id}")
            print(f"  Name: {user.name or 'N/A'}")
            print(f"  Role: {user.role or 'N/A'}")
            print(f"  Ministry: {user.ministry or 'N/A'}")
            print(f"  Owner Key: {owner_key}")
            
            if config:
                print(f"  [OWNER CONFIG EXISTS]")
                print(f"    Name: {config.owner_name}")
                print(f"    Type: {config.owner_type}")
                print(f"    Active: {config.is_active}")
                print(f"    Topics: {len(config.topics) if config.topics else 0}")
                if config.topics:
                    print(f"      {', '.join(config.topics[:10])}{'...' if len(config.topics) > 10 else ''}")
                print(f"    Priority Topics: {len(config.priority_topics) if config.priority_topics else 0}")
                if config.priority_topics:
                    print(f"      {', '.join(config.priority_topics)}")
            else:
                print(f"  [NO OWNER CONFIG] - Run sync script to create")
        
        print("\n" + "="*80)
        print("OWNER CONFIGS WITHOUT USERS")
        print("="*80)
        
        # Find configs that don't have corresponding users
        user_owner_keys = {get_owner_key_from_user(u) for u in users}
        orphan_configs = [c for c in configs if c.owner_key not in user_owner_keys]
        
        if orphan_configs:
            for config in orphan_configs:
                print(f"\n{config.owner_key}:")
                print(f"  Name: {config.owner_name}")
                print(f"  Type: {config.owner_type}")
                print(f"  Topics: {config.topics}")
        else:
            print("\nNo orphan configs found.")
        
    except Exception as e:
        logger.error(f"Error showing users and configs: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    show_all_users_and_configs()













