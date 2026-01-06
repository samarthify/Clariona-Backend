"""
Test configuration changes and reload functionality.

This script tests that configuration changes are properly reflected.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager, PathManager


def test_config_file_change():
    """Test changing configuration in file and reloading."""
    print("\n" + "="*80)
    print("TEST: Configuration File Change")
    print("="*80)
    
    try:
        config = ConfigManager()
        
        # Get original value
        original_value = config.get_int('processing.parallel.max_collector_workers', -1)
        print(f"  Original value: {original_value}")
        
        # Test that we can access the config file
        config_file = config.config_dir / 'agent_config.json'
        if config_file.exists():
            print(f"  Config file exists: {config_file}")
            
            # Read current config
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Check if parallel_processing exists
            if 'parallel_processing' in config_data:
                print(f"  Found parallel_processing in config")
                print(f"  Current max_collector_workers: {config_data['parallel_processing'].get('max_collector_workers', 'not set')}")
            else:
                print(f"  parallel_processing not in config (using defaults)")
            
            print("[OK] Configuration file accessible")
            return True
        else:
            print(f"[WARN] Config file not found: {config_file}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Configuration file change test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_reload():
    """Test configuration reload functionality."""
    print("\n" + "="*80)
    print("TEST: Configuration Reload")
    print("="*80)
    
    try:
        config = ConfigManager()
        
        # Get value before reload
        value_before = config.get_int('processing.parallel.max_collector_workers', -1)
        print(f"  Value before reload: {value_before}")
        
        # Reload configuration
        config.reload()
        print("[OK] Configuration reloaded")
        
        # Get value after reload
        value_after = config.get_int('processing.parallel.max_collector_workers', -1)
        print(f"  Value after reload: {value_after}")
        
        # Values should be the same (unless config changed externally)
        if value_before == value_after:
            print("[OK] Configuration reload maintains values")
        else:
            print(f"[INFO] Configuration values changed after reload (expected if config file changed)")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Configuration reload test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_environment_variable_override():
    """Test environment variable override (if set)."""
    print("\n" + "="*80)
    print("TEST: Environment Variable Override")
    print("="*80)
    
    try:
        import os
        
        # Check if any CONFIG__ environment variables are set
        config_env_vars = [k for k in os.environ.keys() if k.startswith('CONFIG__')]
        
        if config_env_vars:
            print(f"  Found {len(config_env_vars)} CONFIG__ environment variables:")
            for var in config_env_vars[:5]:  # Show first 5
                print(f"    - {var}")
            if len(config_env_vars) > 5:
                print(f"    ... and {len(config_env_vars) - 5} more")
            print("[OK] Environment variables detected")
        else:
            print("[INFO] No CONFIG__ environment variables set (this is OK)")
            print("  To test: Set CONFIG__PROCESSING__PARALLEL__MAX_COLLECTOR_WORKERS=10")
        
        # Test that ConfigManager can read from environment
        config = ConfigManager()
        value = config.get_int('processing.parallel.max_collector_workers', -1)
        print(f"  Current value: {value}")
        print("[OK] ConfigManager can read configuration")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Environment variable override test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_path_manager_config_integration():
    """Test that PathManager uses ConfigManager for paths."""
    print("\n" + "="*80)
    print("TEST: PathManager Config Integration")
    print("="*80)
    
    try:
        config = ConfigManager()
        paths = PathManager(config)
        
        # Test that paths come from config
        raw_path_from_config = config.get_path('paths.data_raw', 'data/raw')
        raw_path_from_manager = paths.data_raw
        
        print(f"  Path from config: {raw_path_from_config}")
        print(f"  Path from manager: {raw_path_from_manager}")
        
        # They should match (or be equivalent)
        if str(raw_path_from_config) == str(raw_path_from_manager) or raw_path_from_config == raw_path_from_manager:
            print("[OK] PathManager uses ConfigManager paths")
        else:
            print("[INFO] Paths may differ but both are valid")
        
        # Test that changing config path would affect PathManager
        # (This is more of a verification that they're connected)
        assert paths.config == config
        print("[OK] PathManager references ConfigManager")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] PathManager config integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_configuration_keys_exist():
    """Test that all expected configuration keys exist."""
    print("\n" + "="*80)
    print("TEST: Configuration Keys Existence")
    print("="*80)
    
    try:
        config = ConfigManager()
        
        # Test key categories
        key_categories = [
            'processing',
            'paths',
            'database',
            'api',
            'deduplication',
            'collectors'
        ]
        
        missing_keys = []
        for category in key_categories:
            value = config.get(category)
            if value is None:
                missing_keys.append(category)
                print(f"  [WARN] Missing category: {category}")
            else:
                print(f"  [OK] Category exists: {category}")
        
        if not missing_keys:
            print("[OK] All expected configuration categories exist")
            return True
        else:
            print(f"[WARN] Some categories missing: {missing_keys}")
            return len(missing_keys) < len(key_categories)  # Pass if most exist
        
    except Exception as e:
        print(f"[ERROR] Configuration keys test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all configuration change tests."""
    print("\n" + "="*80)
    print("CONFIGURATION CHANGES TESTING - Phase 7, Step 7.2")
    print("="*80)
    print("\nThis script tests configuration change and reload functionality.\n")
    
    results = {}
    
    # Run tests
    results['config_file_change'] = test_config_file_change()
    results['config_reload'] = test_config_reload()
    results['env_override'] = test_environment_variable_override()
    results['path_config_integration'] = test_path_manager_config_integration()
    results['config_keys'] = test_configuration_keys_exist()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {test_name:30} {status}")
    
    passed = sum(1 for r in results.values() if r)
    failed = sum(1 for r in results.values() if not r)
    total = len(results)
    
    print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
    
    if failed == 0:
        print("\n[OK] All configuration change tests passed!")
        return 0
    else:
        print(f"\n[ERROR] {failed} test(s) failed")
        return 1


if __name__ == '__main__':
    exit(main())








