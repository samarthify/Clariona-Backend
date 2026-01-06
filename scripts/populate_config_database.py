"""
Migration script to populate system_configurations table from existing config files.

This script:
1. Reads configuration from existing JSON files (agent_config.json, etc.)
2. Converts flat structure to nested key-value format
3. Populates system_configurations table with all config values
4. Optionally populates configuration_schemas table from schema file
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import SystemConfiguration, ConfigurationSchema
from src.config.config_manager import ConfigManager


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """
    Flatten a nested dictionary.
    
    Example:
        {'a': {'b': 1, 'c': 2}} -> {'a.b': 1, 'a.c': 2}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def infer_type(value: Any) -> str:
    """Infer configuration value type."""
    if isinstance(value, bool):
        return 'bool'
    elif isinstance(value, int):
        return 'int'
    elif isinstance(value, float):
        return 'float'
    elif isinstance(value, str):
        return 'string'
    elif isinstance(value, list):
        return 'array'
    elif isinstance(value, dict):
        return 'json'
    else:
        return 'string'


def populate_from_config_manager(db):
    """Populate config from ConfigManager defaults and existing files."""
    config_manager = ConfigManager(use_database=False)  # Load from files
    all_config = config_manager.get_all()
    
    configs_to_insert = []
    
    # Flatten the config structure
    flattened = flatten_dict(all_config)
    
    for full_key, value in flattened.items():
        # Parse key (e.g., "processing.parallel.max_collector_workers")
        parts = full_key.split('.')
        if len(parts) < 2:
            continue  # Skip top-level keys that aren't nested
        
        category = parts[0]
        config_key = '.'.join(parts[1:])
        
        # Check if already exists
        existing = db.query(SystemConfiguration).filter(
            SystemConfiguration.category == category,
            SystemConfiguration.config_key == config_key
        ).first()
        
        if existing:
            # Update existing if value changed
            if existing.config_value != value:
                existing.config_value = value
                existing.config_type = infer_type(value)
                existing.updated_at = datetime.utcnow()
                print(f"Updated: {category}.{config_key} = {value}")
        else:
            # Create new
            config = SystemConfiguration(
                category=category,
                config_key=config_key,
                config_value=value,
                config_type=infer_type(value),
                default_value=value  # Use current value as default for now
            )
            configs_to_insert.append(config)
            print(f"Adding: {category}.{config_key} = {value}")
    
    # Bulk insert new configs
    if configs_to_insert:
        db.add_all(configs_to_insert)
        db.commit()
        print(f"\nInserted {len(configs_to_insert)} new configuration values")
    else:
        print("\nNo new configurations to insert (all already exist)")


def populate_schemas_from_json(db, schema_file: Path):
    """Populate configuration_schemas from JSON schema file."""
    if not schema_file.exists():
        print(f"Schema file not found: {schema_file}")
        return
    
    try:
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Extract categories from schema
        properties = schema.get('properties', {})
        
        for category_name, category_schema in properties.items():
            if not isinstance(category_schema, dict):
                continue
            
            # Check if schema already exists
            existing = db.query(ConfigurationSchema).filter(
                ConfigurationSchema.category == category_name
            ).first()
            
            if existing:
                # Update existing
                existing.schema_definition = category_schema
                existing.updated_at = datetime.utcnow()
                print(f"Updated schema for category: {category_name}")
            else:
                # Get default values from ConfigManager
                config_manager = ConfigManager(use_database=False)
                default_values = config_manager.get_dict(category_name, {})
                
                schema_obj = ConfigurationSchema(
                    category=category_name,
                    schema_definition=category_schema,
                    default_values=default_values,
                    description=category_schema.get('description')
                )
                db.add(schema_obj)
                print(f"Added schema for category: {category_name}")
        
        db.commit()
        print("\nSchema population complete")
        
    except Exception as e:
        print(f"Error populating schemas: {e}")
        db.rollback()
        raise


def main():
    """Main migration function."""
    print("=" * 60)
    print("Populating Configuration Database")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Step 1: Populate configurations from ConfigManager
        print("\nStep 1: Populating configurations from existing config files...")
        populate_from_config_manager(db)
        
        # Step 2: Populate schemas (optional)
        schema_file = Path(__file__).parent.parent / "config" / "config.schema.json"
        if schema_file.exists():
            print("\nStep 2: Populating configuration schemas...")
            populate_schemas_from_json(db, schema_file)
        else:
            print("\nStep 2: Skipping schema population (schema file not found)")
        
        print("\n" + "=" * 60)
        print("Migration complete!")
        print("=" * 60)
        
        # Show summary
        total_configs = db.query(SystemConfiguration).count()
        active_configs = db.query(SystemConfiguration).filter(
            SystemConfiguration.is_active == True
        ).count()
        categories = db.query(SystemConfiguration.category).distinct().count()
        
        print(f"\nSummary:")
        print(f"  Total configurations: {total_configs}")
        print(f"  Active configurations: {active_configs}")
        print(f"  Categories: {categories}")
        
    except Exception as e:
        db.rollback()
        print(f"\nError during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()












