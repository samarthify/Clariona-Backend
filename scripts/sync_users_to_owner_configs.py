"""
Sync users (ministers) to owner_configs table.

This script creates OwnerConfig entries for each user based on their role and ministry.
Each minister can have different topics configured.
"""

import sys
from pathlib import Path
import logging
from typing import Dict, List, Optional

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from api.database import SessionLocal
from api.models import User, OwnerConfig, Topic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('SyncUsersToOwnerConfigs')

# Mapping of ministries to relevant topics
# You can customize this based on your needs
MINISTRY_TO_TOPICS = {
    'health': [
        'healthcare_crisis',
        'healthcare_access',
        'medical_equipment',
        'hospital_funding'
    ],
    'education': [
        'education_funding',
        'assu_strikes',
        'teacher_salaries',
        'school_infrastructure'
    ],
    'finance': [
        'budget_allocation',
        'inflation',
        'economic_policy',
        'currency'
    ],
    'energy': [
        'fuel_pricing',
        'power_outages',
        'energy_policy'
    ],
    'defense': [
        'military_operations',
        'security_threats',
        'defense_budget'
    ],
    'agriculture': [
        'agriculture_food_security',
        'farmers',
        'food_prices'
    ],
    'transportation': [
        'infrastructure_projects',
        'transportation',
        'roads'
    ],
    'works': [
        'infrastructure_projects',
        'infrastructure',
        'construction'
    ],
    'water_resources': [
        'water_resources',
        'water_supply',
        'water_management'
    ],
    'environment': [
        'environment_ecological',
        'climate_change',
        'pollution'
    ],
    'foreign_affairs': [
        'foreign_affairs',
        'diplomacy',
        'international_relations'
    ],
    'justice': [
        'corruption_cases',
        'legal_reform',
        'judiciary'
    ],
    'interior': [
        'security_threats',
        'police',
        'internal_security'
    ],
    'labour': [
        'unemployment',
        'labour_issues',
        'employment'
    ],
    'youth': [
        'youth_development',
        'unemployment',
        'education_funding'
    ],
    'women': [
        'women_affairs',
        'gender_equality',
        'women_empowerment'
    ],
    'sports': [
        'sports_development',
        'youth_development'
    ],
    'information': [
        'presidential_announcements',
        'media',
        'communications'
    ],
    'science': [
        'science_technology',
        'innovation',
        'research'
    ],
    'trade': [
        'industry_trade',
        'economic_policy',
        'commerce'
    ],
    'petroleum': [
        'fuel_pricing',
        'petroleum_resources',
        'energy_policy'
    ],
    'solid_minerals': [
        'solid_minerals',
        'mining',
        'natural_resources'
    ],
    'steel': [
        'steel_development',
        'industry_trade',
        'manufacturing'
    ],
    'aviation': [
        'aviation_aerospace',
        'transportation',
        'infrastructure_projects'
    ],
    'marine': [
        'marine_blue_economy',
        'fisheries',
        'coastal_development'
    ],
    'niger_delta': [
        'niger_delta',
        'oil_production',
        'regional_development'
    ],
    'fct': [
        'fct_administration',
        'capital_development',
        'infrastructure_projects'
    ],
    'special_duties': [
        'special_duties',
        'coordination',
        'policy_implementation'
    ],
    'tourism': [
        'tourism',
        'culture',
        'heritage'
    ],
    'art_culture': [
        'art_culture_creative',
        'tourism',
        'heritage'
    ],
    'housing': [
        'housing_urban',
        'infrastructure_projects',
        'urban_development'
    ],
    'humanitarian': [
        'humanitarian_poverty',
        'social_welfare',
        'poverty_alleviation'
    ],
    'police': [
        'police_affairs',
        'security_threats',
        'internal_security'
    ],
    'livestock': [
        'livestock_development',
        'agriculture_food_security',
        'animal_husbandry'
    ],
    'power': [
        'power_outages',
        'energy_policy',
        'electricity'
    ]
}

# Default topics for president (all topics)
PRESIDENT_TOPICS = [
    'fuel_pricing',
    'presidential_announcements',
    'military_operations',
    'education_funding',
    'assu_strikes',
    'healthcare_crisis',
    'security_threats',
    'budget_allocation',
    'infrastructure_projects',
    'corruption_cases',
    'power_outages',
    'unemployment',
    'inflation',
    'foreign_affairs',
    'agriculture_food_security'
]

# Priority topics for president
PRESIDENT_PRIORITY_TOPICS = [
    'fuel_pricing',
    'presidential_announcements',
    'inflation',
    'security_threats',
    'budget_allocation'
]


def get_topics_for_ministry(ministry: Optional[str]) -> List[str]:
    """
    Get relevant topics for a ministry.
    
    Args:
        ministry: Ministry name (e.g., 'health', 'education')
    
    Returns:
        List of topic_keys relevant to this ministry
    """
    if not ministry:
        return []
    
    ministry_lower = ministry.lower().strip()
    
    # Direct match
    if ministry_lower in MINISTRY_TO_TOPICS:
        return MINISTRY_TO_TOPICS[ministry_lower]
    
    # Partial match (e.g., "Ministry of Health" -> "health)
    for key, topics in MINISTRY_TO_TOPICS.items():
        if key in ministry_lower or ministry_lower in key:
            return topics
    
    # Default: return empty (can be customized)
    logger.warning(f"No topic mapping found for ministry: {ministry}")
    return []


def create_owner_key(user: User) -> str:
    """
    Create owner_key from user information.
    
    Format:
    - president: "president"
    - ministers: "minister_{ministry}" (e.g., "minister_health")
    - others: "user_{user_id}"
    """
    if user.role and user.role.lower() == 'president':
        return 'president'
    elif user.ministry:
        # Normalize ministry name for key
        ministry_key = user.ministry.lower().replace(' ', '_').replace('-', '_')
        return f'minister_{ministry_key}'
    else:
        # Fallback to user ID
        return f'user_{str(user.id).replace("-", "_")}'


def sync_user_to_owner_config(user: User, db) -> Optional[OwnerConfig]:
    """
    Create or update OwnerConfig for a user.
    
    Args:
        user: User object
        db: Database session
    
    Returns:
        Created/updated OwnerConfig or None
    """
    owner_key = create_owner_key(user)
    
    # Determine topics based on role
    if user.role and user.role.lower() == 'president':
        topics = PRESIDENT_TOPICS
        priority_topics = PRESIDENT_PRIORITY_TOPICS
        owner_type = 'president'
        owner_name = 'President'
    elif user.ministry:
        topics = get_topics_for_ministry(user.ministry)
        priority_topics = topics[:3] if len(topics) > 3 else topics  # Top 3 as priority
        owner_type = 'minister'
        owner_name = f"Minister of {user.ministry.title()}" if user.ministry else f"User {user.email}"
    else:
        # Regular user - no specific topics
        topics = []
        priority_topics = []
        owner_type = 'user'
        owner_name = user.name or user.email or f"User {user.id}"
    
    # Verify topics exist in database
    valid_topics = []
    if topics:
        existing_topics = db.query(Topic.topic_key).filter(
            Topic.topic_key.in_(topics),
            Topic.is_active == True
        ).all()
        valid_topics = [t[0] for t in existing_topics]
        
        # Warn about missing topics
        missing = set(topics) - set(valid_topics)
        if missing:
            logger.warning(f"Topics not found in database for {owner_key}: {missing}")
    
    # Filter priority topics to only valid ones
    valid_priority = [t for t in priority_topics if t in valid_topics]
    
    # Check if OwnerConfig already exists
    existing_config = db.query(OwnerConfig).filter_by(owner_key=owner_key).first()
    
    if existing_config:
        # Update existing
        existing_config.owner_name = owner_name
        existing_config.owner_type = owner_type
        existing_config.topics = valid_topics
        existing_config.priority_topics = valid_priority
        existing_config.is_active = True
        logger.info(f"Updated OwnerConfig for {owner_key}: {len(valid_topics)} topics")
        return existing_config
    else:
        # Create new
        new_config = OwnerConfig(
            owner_key=owner_key,
            owner_name=owner_name,
            owner_type=owner_type,
            topics=valid_topics,
            priority_topics=valid_priority,
            is_active=True,
            config_data={
                'user_id': str(user.id),
                'user_email': user.email,
                'user_role': user.role,
                'user_ministry': user.ministry
            }
        )
        db.add(new_config)
        logger.info(f"Created OwnerConfig for {owner_key}: {len(valid_topics)} topics")
        return new_config


def sync_all_users():
    """Sync all users to owner_configs table."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        logger.info(f"Found {len(users)} users to sync")
        
        synced = 0
        updated = 0
        skipped = 0
        
        for user in users:
            try:
                # Check if config already exists
                owner_key = create_owner_key(user)
                existing_config = db.query(OwnerConfig).filter_by(owner_key=owner_key).first()
                
                if existing_config:
                    # Update existing
                    config = sync_user_to_owner_config(user, db)
                    if config:
                        updated += 1
                else:
                    # Create new
                    config = sync_user_to_owner_config(user, db)
                    if config:
                        synced += 1
                    else:
                        skipped += 1
                
                # Commit after each user to avoid bulk insert issues
                db.commit()
                
            except Exception as e:
                logger.error(f"Error syncing user {user.email}: {e}")
                db.rollback()
                skipped += 1
        
        logger.info(f"Sync complete: {synced} created, {updated} updated, {skipped} skipped")
        
        # Show summary
        print("\n" + "="*60)
        print("SYNC SUMMARY")
        print("="*60)
        all_configs = db.query(OwnerConfig).all()
        for config in all_configs:
            print(f"\n{config.owner_key}:")
            print(f"  Name: {config.owner_name}")
            print(f"  Type: {config.owner_type}")
            print(f"  Topics: {len(config.topics) if config.topics else 0} topics")
            if config.topics:
                print(f"    {', '.join(config.topics[:5])}{'...' if len(config.topics) > 5 else ''}")
            print(f"  Priority: {len(config.priority_topics) if config.priority_topics else 0} topics")
        
    except Exception as e:
        logger.error(f"Error syncing users: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def sync_single_user(user_email: str):
    """Sync a single user by email."""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=user_email).first()
        if not user:
            logger.error(f"User not found: {user_email}")
            return
        
        config = sync_user_to_owner_config(user, db)
        db.commit()
        
        if config:
            print(f"\nSynced user: {user_email}")
            print(f"  Owner Key: {config.owner_key}")
            print(f"  Owner Name: {config.owner_name}")
            print(f"  Type: {config.owner_type}")
            print(f"  Topics: {config.topics}")
            print(f"  Priority Topics: {config.priority_topics}")
        
    except Exception as e:
        logger.error(f"Error syncing user {user_email}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync users to owner_configs table')
    parser.add_argument('--user', type=str, help='Sync specific user by email')
    parser.add_argument('--all', action='store_true', help='Sync all users')
    
    args = parser.parse_args()
    
    if args.user:
        sync_single_user(args.user)
    elif args.all:
        sync_all_users()
    else:
        print("Usage:")
        print("  python scripts/sync_users_to_owner_configs.py --all          # Sync all users")
        print("  python scripts/sync_users_to_owner_configs.py --user <email> # Sync specific user")

