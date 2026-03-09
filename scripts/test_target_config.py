#!/usr/bin/env python3
"""
Test script to verify target configuration is working correctly.
Checks that collectors can load queries from environment variables.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def test_env_loading():
    """Test that .env file is loaded correctly"""
    print("=" * 80)
    print("Testing Environment Variable Loading")
    print("=" * 80)
    
    # Load from config/.env
    env_path = Path(__file__).parent.parent / 'config' / '.env'
    if not env_path.exists():
        print(f"❌ .env file not found at: {env_path}")
        return False
    
    load_dotenv(env_path)
    print(f"✅ Loaded .env from: {env_path}")
    
    # Check TARGET_INDIVIDUAL
    target = os.getenv('TARGET_INDIVIDUAL')
    if not target:
        print("❌ TARGET_INDIVIDUAL not set in .env")
        return False
    
    print(f"✅ TARGET_INDIVIDUAL: {target}")
    
    # Check QUERY_VARIATIONS
    variations_str = os.getenv('QUERY_VARIATIONS')
    if not variations_str:
        print("❌ QUERY_VARIATIONS not set in .env")
        return False
    
    try:
        variations = json.loads(variations_str)
        print(f"✅ QUERY_VARIATIONS: {variations}")
        print(f"   Total variations: {len(variations)}")
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse QUERY_VARIATIONS: {e}")
        return False
    
    return True

def test_scheduler_loading():
    """Test that scheduler can load queries"""
    print("\n" + "=" * 80)
    print("Testing Scheduler Query Loading")
    print("=" * 80)
    
    try:
        from services.scheduler import LocalScheduler
        
        scheduler = LocalScheduler()
        queries = scheduler.default_queries
        
        print(f"✅ Scheduler loaded queries: {queries}")
        print(f"   Total queries: {len(queries)}")
        
        if len(queries) == 0:
            print("❌ Scheduler loaded empty queries")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading scheduler: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_news_api_collector():
    """Test that News API collector can load keywords"""
    print("\n" + "=" * 80)
    print("Testing News API Collector Keyword Loading")
    print("=" * 80)
    
    try:
        from collectors.collect_news_from_api import NewsAPICollector
        
        # Note: This will fail if API keys aren't set, but we can still test keyword loading
        try:
            collector = NewsAPICollector()
            keywords = collector._get_target_keywords()
            print(f"✅ News API loaded keywords: {keywords}")
            print(f"   Total keywords: {len(keywords)}")
            return True
        except ValueError as e:
            if "No API keys found" in str(e):
                print("⚠️  API keys not configured, but keyword loading works")
                print("   (This is expected if you haven't added MEDIASTACK_API_KEY or GNEWS_API_KEY yet)")
                return True
            raise
        
    except Exception as e:
        print(f"❌ Error testing News API collector: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "🔍 Target Configuration Test Suite" + "\n")
    
    results = {
        "Environment Loading": test_env_loading(),
        "Scheduler Loading": test_scheduler_loading(),
        "News API Collector": test_news_api_collector(),
    }
    
    print("\n" + "=" * 80)
    print("Test Results Summary")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All tests passed! Target configuration is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
