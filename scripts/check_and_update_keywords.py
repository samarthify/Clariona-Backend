#!/usr/bin/env python3
"""
Script to check and update keywords used for collection in the database.
Keywords are stored in:
1. target_individual_configurations table (query_variations field per user)
2. config/agent_config.json (general keywords)
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import TargetIndividualConfiguration, User

def get_all_target_configs() -> List[Dict[str, Any]]:
    """Get all target configurations from database."""
    db = SessionLocal()
    try:
        configs = db.query(TargetIndividualConfiguration).all()
        results = []
        for config in configs:
            user = db.query(User).filter(User.id == config.user_id).first() if config.user_id else None
            results.append({
                'id': config.id,
                'user_id': str(config.user_id) if config.user_id else None,
                'user_email': user.email if user else None,
                'individual_name': config.individual_name,
                'query_variations': config.query_variations if config.query_variations else [],
                'created_at': str(config.created_at) if config.created_at else None
            })
        return results
    finally:
        db.close()

def get_agent_config_keywords() -> List[str]:
    """Get keywords from agent_config.json."""
    config_path = Path(__file__).parent.parent / "config" / "agent_config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get('keywords', [])
    return []

def display_current_keywords():
    """Display all current keywords."""
    print("=" * 80)
    print("CURRENT KEYWORDS IN DATABASE")
    print("=" * 80)
    
    # Get target configs from database
    target_configs = get_all_target_configs()
    
    if not target_configs:
        print("\n❌ No target configurations found in database.")
    else:
        print(f"\n📊 Found {len(target_configs)} target configuration(s):\n")
        for i, config in enumerate(target_configs, 1):
            print(f"  Configuration #{i}:")
            print(f"    ID: {config['id']}")
            print(f"    User ID: {config['user_id']}")
            print(f"    User Email: {config['user_email'] or 'N/A'}")
            print(f"    Individual Name: {config['individual_name']}")
            print(f"    Query Variations (Keywords): {config['query_variations']}")
            print(f"    Created At: {config['created_at']}")
            print()
    
    # Get general keywords from config file
    print("\n" + "-" * 80)
    print("GENERAL KEYWORDS FROM CONFIG FILE")
    print("-" * 80)
    agent_keywords = get_agent_config_keywords()
    if agent_keywords:
        print(f"\n  Keywords: {agent_keywords}")
    else:
        print("\n  No keywords found in agent_config.json")
    
    print("\n" + "=" * 80)

def update_target_config_keywords(config_id: int, new_keywords: List[str]):
    """Update keywords for a specific target configuration."""
    db = SessionLocal()
    try:
        config = db.query(TargetIndividualConfiguration).filter(
            TargetIndividualConfiguration.id == config_id
        ).first()
        
        if not config:
            print(f"❌ Configuration with ID {config_id} not found.")
            return False
        
        old_keywords = config.query_variations or []
        config.query_variations = new_keywords
        db.commit()
        
        print(f"✅ Successfully updated keywords for configuration #{config_id}")
        print(f"   Individual: {config.individual_name}")
        print(f"   Old keywords: {old_keywords}")
        print(f"   New keywords: {new_keywords}")
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating keywords: {e}")
        return False
    finally:
        db.close()

def update_agent_config_keywords(new_keywords: List[str]):
    """Update general keywords in agent_config.json."""
    config_path = Path(__file__).parent.parent / "config" / "agent_config.json"
    
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        old_keywords = config.get('keywords', [])
        config['keywords'] = new_keywords
        
        # Backup original
        backup_path = config_path.with_suffix('.json.backup')
        if config_path.exists():
            import shutil
            shutil.copy2(config_path, backup_path)
            print(f"📋 Backed up original config to {backup_path}")
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        print(f"✅ Successfully updated general keywords in agent_config.json")
        print(f"   Old keywords: {old_keywords}")
        print(f"   New keywords: {new_keywords}")
        return True
    except Exception as e:
        print(f"❌ Error updating agent_config.json: {e}")
        return False

def interactive_update():
    """Interactive mode to update keywords."""
    display_current_keywords()
    
    print("\n" + "=" * 80)
    print("UPDATE KEYWORDS")
    print("=" * 80)
    print("\nWhat would you like to update?")
    print("1. Update keywords for a target configuration (from database)")
    print("2. Update general keywords in agent_config.json")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        target_configs = get_all_target_configs()
        if not target_configs:
            print("\n❌ No target configurations found.")
            return
        
        print("\nAvailable configurations:")
        for config in target_configs:
            print(f"  {config['id']}. {config['individual_name']} (User: {config['user_email'] or config['user_id']})")
        
        try:
            config_id = int(input("\nEnter configuration ID to update: ").strip())
            print(f"\nCurrent keywords: {next(c['query_variations'] for c in target_configs if c['id'] == config_id)}")
            keywords_input = input("Enter new keywords (comma-separated): ").strip()
            new_keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
            
            if new_keywords:
                update_target_config_keywords(config_id, new_keywords)
            else:
                print("❌ No keywords provided.")
        except ValueError:
            print("❌ Invalid configuration ID.")
        except StopIteration:
            print("❌ Configuration ID not found.")
    
    elif choice == "2":
        current_keywords = get_agent_config_keywords()
        print(f"\nCurrent keywords: {current_keywords}")
        keywords_input = input("Enter new keywords (comma-separated): ").strip()
        new_keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
        
        if new_keywords:
            update_agent_config_keywords(new_keywords)
        else:
            print("❌ No keywords provided.")
    
    elif choice == "3":
        print("Exiting...")
    else:
        print("❌ Invalid choice.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--display" or sys.argv[1] == "-d":
            display_current_keywords()
        elif sys.argv[1] == "--update-target" and len(sys.argv) >= 4:
            config_id = int(sys.argv[2])
            keywords = sys.argv[3].split(',')
            keywords = [k.strip() for k in keywords if k.strip()]
            update_target_config_keywords(config_id, keywords)
        elif sys.argv[1] == "--update-agent" and len(sys.argv) >= 3:
            keywords = sys.argv[2].split(',')
            keywords = [k.strip() for k in keywords if k.strip()]
            update_agent_config_keywords(keywords)
        else:
            print("Usage:")
            print("  python check_and_update_keywords.py                    # Interactive mode")
            print("  python check_and_update_keywords.py --display          # Display current keywords")
            print("  python check_and_update_keywords.py --update-target <id> <keywords>  # Update target config")
            print("  python check_and_update_keywords.py --update-agent <keywords>        # Update agent config")
    else:
        interactive_update()



