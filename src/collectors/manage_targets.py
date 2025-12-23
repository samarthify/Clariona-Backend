#!/usr/bin/env python3
"""
Target Configuration Management CLI Tool
Allows users to view, test, and manage target configurations.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src directory to Python path
src_dir = Path(__file__).parent.parent
sys.path.append(str(src_dir))

from collectors.target_config_manager import TargetConfigManager, get_target_config, get_target_by_name
from collectors.configurable_collector import ConfigurableCollector

def list_targets():
    """List all available targets and their configurations"""
    config_manager = TargetConfigManager()
    summary = config_manager.get_target_summary()
    
    print(f"\n📋 Available Targets ({summary['total_targets']}):")
    print("=" * 80)
    
    for target in summary["available_targets"]:
        print(f"\n🎯 {target['name']} ({target['id']})")
        print(f"   Full Name: {target['full_name']}")
        print(f"   Country: {target['country']} ({target['country_code']})")
        print(f"   Enabled Sources: {', '.join(target['enabled_sources'])}")
        print(f"   Keywords: {', '.join(target['keywords'][:5])}{'...' if len(target['keywords']) > 5 else ''}")
    
    print("\n" + "=" * 80)

def show_target(target_id: str):
    """Show detailed configuration for a specific target"""
    target_config = get_target_config(target_id)
    if not target_config:
        print(f"❌ Target '{target_id}' not found")
        return
    
    print(f"\n🎯 Target Configuration: {target_config.name}")
    print("=" * 80)
    print(f"ID: {target_id}")
    print(f"Full Name: {target_config.full_name}")
    print(f"Country: {target_config.country} ({target_config.country_code})")
    print(f"Keywords: {', '.join(target_config.keywords)}")
    
    print(f"\n📡 Sources Configuration:")
    for source_type, source_config in target_config.sources.items():
        status = "✅ Enabled" if source_config.enabled else "❌ Disabled"
        print(f"  {source_type.upper()}: {status}")
        
        if source_config.enabled:
            if source_config.countries:
                print(f"    Countries: {', '.join(source_config.countries)}")
            if source_config.keywords:
                print(f"    Keywords: {', '.join(source_config.keywords)}")
            if source_config.locations:
                print(f"    Locations: {', '.join(source_config.locations)}")
            if source_config.feeds:
                print(f"    RSS Feeds: {len(source_config.feeds)} feeds")
            if source_config.filters:
                print(f"    Filters: {json.dumps(source_config.filters, indent=4)}")
    
    if hasattr(target_config, 'sentiment_rules'):
        print(f"\n😊 Sentiment Rules:")
        for rule_type, keywords in target_config.sentiment_rules.items():
            print(f"  {rule_type.title()}: {', '.join(keywords)}")
    
    print("=" * 80)

def test_target_detection(target_name: str):
    """Test target detection for a given name"""
    print(f"\n🧪 Testing Target Detection for: '{target_name}'")
    print("=" * 80)
    
    # Test different detection methods
    config_manager = TargetConfigManager()
    
    # Method 1: Direct name matching
    target_config = get_target_by_name(target_name)
    if target_config:
        print(f"✅ Direct name match found: {target_config.name}")
        # Find the target ID
        for target_id, config in config_manager.targets.items():
            if config == target_config:
                print(f"   Target ID: {target_id}")
                break
    else:
        print(f"❌ No direct name match found")
    
    # Method 2: Keyword matching
    target_config = config_manager.get_target_by_keywords([target_name])
    if target_config:
        print(f"✅ Keyword match found: {target_config.name}")
        # Find the target ID
        for target_id, config in config_manager.targets.items():
            if config == target_config:
                print(f"   Target ID: {target_id}")
                break
    else:
        print(f"❌ No keyword match found")
    
    # Method 3: Fuzzy matching
    available_targets = config_manager.get_available_targets()
    fuzzy_matches = []
    
    for target_id in available_targets:
        target_config = config_manager.get_target_config(target_id)
        if target_config:
            # Check if any part of the target name matches
            if any(part.lower() in target_name.lower() for part in target_config.name.split()):
                fuzzy_matches.append((target_id, target_config.name))
    
    if fuzzy_matches:
        print(f"✅ Fuzzy matches found:")
        for target_id, name in fuzzy_matches:
            print(f"   {target_id}: {name}")
    else:
        print(f"❌ No fuzzy matches found")
    
    print("=" * 80)

def validate_target(target_id: str):
    """Validate a target configuration and show any issues"""
    config_manager = TargetConfigManager()
    issues = config_manager.validate_target_config(target_id)
    
    print(f"\n🔍 Validating Target: {target_id}")
    print("=" * 80)
    
    if not issues:
        print("✅ Target configuration is valid!")
    else:
        print("❌ Target configuration has issues:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    
    print("=" * 80)

def test_collection(target_name: str, queries: List[str], user_id: str = "test-user"):
    """Test collection for a target (dry run)"""
    print(f"\n🚀 Testing Collection for Target: '{target_name}'")
    print("=" * 80)
    
    # Create test queries
    test_queries = [target_name] + queries
    
    try:
        collector = ConfigurableCollector()
        
        # Run collection with target detection
        result = collector.run_collection_with_target_detection(test_queries, user_id)
        
        if result["success"]:
            print(f"✅ Collection test successful!")
            print(f"   Target ID: {result['target_id']}")
            print(f"   Target Name: {result['target_name']}")
            print(f"   Target Country: {result['target_country']}")
            print(f"   Queries: {result['queries']}")
            print(f"   Results: {result['results']}")
        else:
            print(f"❌ Collection test failed: {result['error']}")
            
    except Exception as e:
        print(f"❌ Error during collection test: {e}")
    
    print("=" * 80)

def reload_config():
    """Reload target configuration from file"""
    config_manager = TargetConfigManager()
    config_manager.reload_config()
    
    print(f"\n🔄 Reloaded target configuration")
    print("=" * 80)
    print(f"Loaded {len(config_manager.targets)} targets")
    
    for target_id in config_manager.targets:
        print(f"  - {target_id}")
    
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Manage and test target configurations")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List targets command
    subparsers.add_parser('list', help='List all available targets')
    
    # Show target command
    show_parser = subparsers.add_parser('show', help='Show detailed configuration for a target')
    show_parser.add_argument('target_id', help='Target ID to show')
    
    # Test detection command
    test_detection_parser = subparsers.add_parser('test-detection', help='Test target detection for a name')
    test_detection_parser.add_argument('target_name', help='Target name to test')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate a target configuration')
    validate_parser.add_argument('target_id', help='Target ID to validate')
    
    # Test collection command
    test_collection_parser = subparsers.add_parser('test-collection', help='Test collection for a target')
    test_collection_parser.add_argument('target_name', help='Target name to test')
    test_collection_parser.add_argument('queries', nargs='+', help='Additional queries to test')
    
    # Reload config command
    subparsers.add_parser('reload', help='Reload target configuration from file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'list':
            list_targets()
        elif args.command == 'show':
            show_target(args.target_id)
        elif args.command == 'test-detection':
            test_target_detection(args.target_name)
        elif args.command == 'validate':
            validate_target(args.target_id)
        elif args.command == 'test-collection':
            test_collection(args.target_name, args.queries)
        elif args.command == 'reload':
            reload_config()
        else:
            print(f"Unknown command: {args.command}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
