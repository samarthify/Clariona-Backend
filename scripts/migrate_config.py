"""
Migration script for converting old config files to new unified structure.

This script:
1. Reads existing config files
2. Converts them to new unified structure (if needed)
3. Validates the converted config
4. Optionally writes the converted config to a new file
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager


def migrate_agent_config(old_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate agent_config.json to new unified structure.
    
    Args:
        old_config: Old config dictionary from agent_config.json
    
    Returns:
        New unified config structure
    """
    new_config = {}
    
    # Handle parallel_processing -> processing.parallel
    if 'parallel_processing' in old_config:
        if 'processing' not in new_config:
            new_config['processing'] = {}
        new_config['processing']['parallel'] = old_config['parallel_processing'].copy()
    
    # Copy other top-level keys as-is (they're compatible)
    for key, value in old_config.items():
        if key != 'parallel_processing':
            new_config[key] = value
    
    return new_config


def validate_config(config: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate config structure (basic validation).
    
    Args:
        config: Config dictionary to validate
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Basic structure validation
    if not isinstance(config, dict):
        errors.append("Config must be a dictionary")
        return False, errors
    
    # Validate processing.parallel if it exists
    if 'processing' in config:
        if isinstance(config['processing'], dict) and 'parallel' in config['processing']:
            parallel = config['processing']['parallel']
            if isinstance(parallel, dict):
                # Validate worker counts
                for key in ['max_collector_workers', 'max_sentiment_workers', 'max_location_workers']:
                    if key in parallel:
                        if not isinstance(parallel[key], int) or parallel[key] < 1:
                            errors.append(f"{key} must be a positive integer")
    
    # Validate deduplication if it exists
    if 'deduplication' in config:
        if isinstance(config['deduplication'], dict):
            if 'similarity_threshold' in config['deduplication']:
                threshold = config['deduplication']['similarity_threshold']
                if not isinstance(threshold, (int, float)) or not (0 <= threshold <= 1):
                    errors.append("similarity_threshold must be between 0 and 1")
    
    return len(errors) == 0, errors


def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrate configuration files to new unified structure'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='config/agent_config.json',
        help='Input config file path (default: config/agent_config.json)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output config file path (default: print to stdout)'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate the config, do not migrate'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without writing files'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    project_root = Path(__file__).parent.parent
    input_path = project_root / args.input
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    # Load old config
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            old_config = json.load(f)
    except Exception as e:
        print(f"Error loading config file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Migrate if needed
    if args.validate_only:
        new_config = old_config
        print("Validating config (no migration)...")
    else:
        print(f"Migrating config from {input_path}...")
        new_config = migrate_agent_config(old_config)
    
    # Validate
    is_valid, errors = validate_config(new_config)
    
    if not is_valid:
        print("Validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)
    
    print("OK: Config is valid")
    
    # Test with ConfigManager
    print("Testing with ConfigManager...")
    try:
        # Create a temporary config file for testing
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_file = Path(tmpdir) / 'agent_config.json'
            with open(tmp_config_file, 'w') as f:
                json.dump(new_config, f, indent=2)
            
            config_manager = ConfigManager(config_dir=Path(tmpdir))
            
            # Test some accessors
            if 'processing' in new_config and 'parallel' in new_config.get('processing', {}):
                workers = config_manager.get_int('processing.parallel.max_collector_workers', -1)
                print(f"  OK: Can access processing.parallel.max_collector_workers: {workers}")
        
        print("OK: ConfigManager can load and access migrated config")
    except Exception as e:
        print(f"Error testing with ConfigManager: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Output
    output_json = json.dumps(new_config, indent=2, ensure_ascii=False)
    
    if args.dry_run:
        print("\n--- Migrated config (dry run, not saved) ---")
        print(output_json)
        return
    
    if args.output:
        output_path = project_root / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"OK: Migrated config written to {output_path}")
    else:
        print("\n--- Migrated config ---")
        print(output_json)
        print("\n(Use --output to save to a file)")


if __name__ == '__main__':
    main()
