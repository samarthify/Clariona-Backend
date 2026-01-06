#!/usr/bin/env python3
"""
Script to populate topics and owner_configs tables from JSON files.
Uses the development database URL specified in the script.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.api.models import Topic, OwnerConfig

def get_database_url():
    """Get database URL from environment variable."""
    # Load from .env file first
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Try config/.env first
    config_env_path = Path(__file__).parent.parent / 'config' / '.env'
    if config_env_path.exists():
        load_dotenv(dotenv_path=config_env_path)
    
    # Also load from root .env
    root_env_path = Path(__file__).parent.parent / '.env'
    if root_env_path.exists():
        load_dotenv(dotenv_path=root_env_path)
    
    # Load from system environment
    load_dotenv()
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        print("Please set DATABASE_URL in config/.env or .env file")
        sys.exit(1)
    
    return db_url

def load_master_topics(json_path: str):
    """Load topics from master_topics.json."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('topics', {})

def load_owner_config(json_path: str):
    """Load owner config from JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def populate_topics(db_session, topics_data):
    """Populate topics table from JSON data."""
    print(f"Populating {len(topics_data)} topics...")
    
    for topic_key, topic_info in topics_data.items():
        # Check if topic already exists
        existing = db_session.query(Topic).filter(Topic.topic_key == topic_key).first()
        
        if existing:
            print(f"  Topic '{topic_key}' already exists, skipping...")
            continue
        
        topic = Topic(
            topic_key=topic_key,
            topic_name=topic_info.get('name', topic_key),
            description=topic_info.get('description'),
            category=topic_info.get('category'),
            keywords=topic_info.get('keywords', []),
            is_active=True,
            created_at=datetime.now()
        )
        
        db_session.add(topic)
        print(f"  Added topic: {topic_key} - {topic_info.get('name')}")
    
    db_session.commit()
    print(f"Successfully populated {len(topics_data)} topics\n")

def populate_owner_configs(db_session, config_paths):
    """Populate owner_configs table from JSON files."""
    print(f"Populating owner configs...")
    
    for config_path in config_paths:
        if not os.path.exists(config_path):
            print(f"  Config file not found: {config_path}, skipping...")
            continue
        
        config_data = load_owner_config(config_path)
        owner_key = config_data.get('owner')
        
        if not owner_key:
            print(f"  No 'owner' key in {config_path}, skipping...")
            continue
        
        # Check if config already exists
        existing = db_session.query(OwnerConfig).filter(OwnerConfig.owner_key == owner_key).first()
        
        if existing:
            # Update existing config
            existing.owner_name = config_data.get('owner_name', owner_key)
            existing.owner_type = config_data.get('owner_type')
            existing.topics = config_data.get('topics', [])
            existing.priority_topics = config_data.get('priority_topics', [])
            existing.is_active = config_data.get('is_active', True)
            existing.config_data = config_data.get('config_data')
            existing.updated_at = datetime.now()
            print(f"  Updated owner config: {owner_key}")
        else:
            # Create new config
            owner_config = OwnerConfig(
                owner_key=owner_key,
                owner_name=config_data.get('owner_name', owner_key),
                owner_type=config_data.get('owner_type'),
                topics=config_data.get('topics', []),
                priority_topics=config_data.get('priority_topics', []),
                is_active=config_data.get('is_active', True),
                config_data=config_data.get('config_data'),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db_session.add(owner_config)
            print(f"  Added owner config: {owner_key} - {config_data.get('owner_name')}")
    
    db_session.commit()
    print(f"Successfully populated owner configs\n")

def main():
    """Main function to populate database."""
    print("=" * 80)
    print("POPULATING TOPICS AND OWNER CONFIGS FROM JSON FILES")
    print("=" * 80)
    print()
    
    # Get database URL from environment
    database_url = get_database_url()
    
    # Show which database we're using (masked)
    db_display = database_url.split('@')[1] if '@' in database_url else 'hidden'
    print(f"Database: {db_display}")
    print()
    
    # Create database connection
    try:
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        db_session = SessionLocal()
        
        # Test connection
        db_session.execute(text("SELECT 1"))
        print("Database connection successful\n")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)
    
    try:
        # Load and populate topics
        master_topics_path = Path(__file__).parent.parent / 'config' / 'master_topics.json'
        if not master_topics_path.exists():
            print(f"ERROR: master_topics.json not found at: {master_topics_path}")
            sys.exit(1)
        
        topics_data = load_master_topics(str(master_topics_path))
        populate_topics(db_session, topics_data)
        
        # Load and populate owner configs
        config_paths = []
        
        # President config
        president_config_path = Path(__file__).parent.parent / 'config' / 'president_config.json'
        if president_config_path.exists():
            config_paths.append(str(president_config_path))
        
        # Minister configs (if directory exists)
        minister_configs_dir = Path(__file__).parent.parent / 'config' / 'minister_configs'
        if minister_configs_dir.exists():
            for config_file in minister_configs_dir.glob('*.json'):
                config_paths.append(str(config_file))
        
        if config_paths:
            populate_owner_configs(db_session, config_paths)
        else:
            print("No owner config files found, skipping...\n")
        
        print("=" * 80)
        print("POPULATION COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"Error during population: {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()

if __name__ == "__main__":
    main()

