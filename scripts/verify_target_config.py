#!/usr/bin/env python3
"""
Simple standalone test to verify target configuration from .env file.
No dependencies required.
"""

import os
import json
from pathlib import Path

def load_env_manually(env_file):
    """Manually parse .env file"""
    config = {}
    if not env_file.exists():
        return config
    
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config

def main():
    print("=" * 80)
    print("Target Configuration Test (Standalone)")
    print("=" * 80)
    
    # Load .env file
    env_path = Path(__file__).parent.parent / 'config' / '.env'
    print(f"\n📂 Loading .env from: {env_path}")
    
    if not env_path.exists():
        print(f"❌ File not found!")
        return 1
    
    print(f"✅ File exists\n")
    
    # Parse it manually
    config = load_env_manually(env_path)
    
    # Test TARGET_INDIVIDUAL
    print("=" * 80)
    print("Testing TARGET_INDIVIDUAL")
    print("=" * 80)
    
    target = config.get('TARGET_INDIVIDUAL', '').strip('"').strip("'")
    if not target:
        print("❌ TARGET_INDIVIDUAL not found or empty")
        return 1
    
    print(f"✅ Found: {target}")
    
    # Test QUERY_VARIATIONS
    print("\n" + "=" * 80)
    print("Testing QUERY_VARIATIONS")
    print("=" * 80)
    
    variations_str = config.get('QUERY_VARIATIONS', '')
    if not variations_str:
        print("❌ QUERY_VARIATIONS not found or empty")
        return 1
    
    try:
        variations = json.loads(variations_str)
        print(f"✅ Found {len(variations)} variations:")
        for i, var in enumerate(variations, 1):
            print(f"   {i}. {var}")
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        print(f"   Raw value: {variations_str}")
        return 1
    
    # Show combined queries list
    print("\n" + "=" * 80)
    print("Combined Queries List")
    print("=" * 80)
    
    all_queries = [target] + variations
    print(f"This is what collectors will use ({len(all_queries)} total queries):\n")
    for i, query in enumerate(all_queries, 1):
        print(f"   {i}. {query}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"✅ Configuration is valid!")
    print(f"📊 Target: {target}")
    print(f"📊 Total Queries: {len(all_queries)}")
    print(f"\n💡 To change target, edit: {env_path}")
    print("   Then restart collectors/scheduler for changes to take effect.")
    
    return 0

if __name__ == "__main__":
    exit(main())
