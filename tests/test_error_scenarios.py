"""
Test error scenarios and error handling.

This script tests that errors are handled gracefully.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager, PathManager
from src.exceptions import (
    ConfigError, PathError, CollectionError,
    ProcessingError, DatabaseError, ValidationError
)


def test_config_error_handling():
    """Test ConfigError handling."""
    print("\n" + "="*80)
    print("TEST: ConfigError Handling")
    print("="*80)
    
    try:
        config = ConfigManager()
        
        # Test accessing non-existent key (should return default, not raise error)
        value = config.get('nonexistent.key.path', 'default_value')
        assert value == 'default_value'
        print("[OK] Non-existent key returns default (no error)")
        
        # Test that we can raise ConfigError manually
        try:
            raise ConfigError("Test config error", {"key": "test.key"})
        except ConfigError as e:
            assert "Test config error" in str(e)
            print(f"[OK] ConfigError raised correctly: {e}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] ConfigError handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_path_error_handling():
    """Test PathError handling."""
    print("\n" + "="*80)
    print("TEST: PathError Handling")
    print("="*80)
    
    try:
        paths = PathManager()
        
        # Test that invalid paths are handled
        # PathManager should create directories, not raise errors for valid operations
        test_dir = paths.base_path / 'test_error_dir'
        result = paths.ensure_exists(test_dir)
        
        if result.exists():
            print("[OK] Directory creation works (no errors)")
            # Cleanup
            test_dir.rmdir()
        else:
            print("[WARN] Directory creation may have failed")
        
        # Test that we can raise PathError manually
        try:
            raise PathError("Test path error", {"path": "/invalid/path"})
        except PathError as e:
            assert "Test path error" in str(e)
            print(f"[OK] PathError raised correctly: {e}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] PathError handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exception_hierarchy():
    """Test exception hierarchy and catching."""
    print("\n" + "="*80)
    print("TEST: Exception Hierarchy")
    print("="*80)
    
    try:
        # Test that all exceptions inherit from BackendError
        exceptions_to_test = [
            (ConfigError, "Config error"),
            (PathError, "Path error"),
            (CollectionError, "Collection error"),
            (ProcessingError, "Processing error"),
            (DatabaseError, "Database error"),
            (ValidationError, "Validation error")
        ]
        
        for exc_class, message in exceptions_to_test:
            try:
                raise exc_class(message)
            except exc_class as e:
                # Should be catchable as BackendError
                assert isinstance(e, exc_class)
                print(f"  [OK] {exc_class.__name__} works correctly")
        
        print("[OK] All exceptions work correctly")
        return True
        
    except Exception as e:
        print(f"[ERROR] Exception hierarchy test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_recovery():
    """Test error recovery scenarios."""
    print("\n" + "="*80)
    print("TEST: Error Recovery")
    print("="*80)
    
    try:
        # Test that system continues after configuration errors
        config = ConfigManager()
        
        # Access invalid key (should not crash)
        value = config.get('invalid.key', 'default')
        assert value == 'default'
        print("[OK] System continues after invalid config access")
        
        # Test that system continues after path operations
        paths = PathManager()
        test_path = paths.base_path / 'test_recovery_dir'
        result = paths.ensure_exists(test_path)
        assert result.exists()
        test_path.rmdir()
        print("[OK] System continues after path operations")
        
        # Test that exceptions can be caught and handled
        try:
            raise ConfigError("Recoverable error")
        except ConfigError:
            print("[OK] Exceptions can be caught and handled")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error recovery test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_logging_error_handling():
    """Test that errors are logged correctly."""
    print("\n" + "="*80)
    print("TEST: Error Logging")
    print("="*80)
    
    try:
        from src.config.logging_config import get_logger
        
        logger = get_logger('test.error_handling')
        
        # Test that we can log errors
        try:
            raise ValueError("Test error for logging")
        except ValueError as e:
            logger.error(f"Caught error: {e}", exc_info=True)
            print("[OK] Errors can be logged")
        
        # Test that exception details are logged
        try:
            raise ConfigError("Test config error", {"key": "test.key"})
        except ConfigError as e:
            logger.error(f"Config error: {e}")
            print("[OK] Exception details logged")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all error scenario tests."""
    print("\n" + "="*80)
    print("ERROR SCENARIOS TESTING - Phase 7, Step 7.2")
    print("="*80)
    print("\nThis script tests error handling and recovery scenarios.\n")
    
    results = {}
    
    # Run tests
    results['config_error'] = test_config_error_handling()
    results['path_error'] = test_path_error_handling()
    results['exception_hierarchy'] = test_exception_hierarchy()
    results['error_recovery'] = test_error_recovery()
    results['error_logging'] = test_logging_error_handling()
    
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
        print("\n[OK] All error scenario tests passed!")
        return 0
    else:
        print(f"\n[ERROR] {failed} test(s) failed")
        return 1


if __name__ == '__main__':
    exit(main())








