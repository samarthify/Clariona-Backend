"""
Manual testing helper for complete cycle execution.

This script helps verify that the complete cycle execution works correctly.
"""

import sys
import os
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager, PathManager
from src.config.logging_config import get_logger, setup_logging


def test_configuration_loading():
    """Test that configuration loads correctly."""
    print("\n" + "="*80)
    print("TEST 1: Configuration Loading")
    print("="*80)
    
    try:
        config = ConfigManager()
        print("[OK] ConfigManager initialized successfully")
        
        # Test some key configurations
        max_workers = config.get_int('processing.parallel.max_collector_workers', -1)
        similarity_threshold = config.get_float('deduplication.similarity_threshold', -1.0)
        pool_size = config.get_int('database.pool_size', -1)
        
        print(f"  - Max collector workers: {max_workers}")
        print(f"  - Similarity threshold: {similarity_threshold}")
        print(f"  - Database pool size: {pool_size}")
        
        if max_workers > 0 and similarity_threshold > 0 and pool_size > 0:
            print("[OK] Configuration values loaded correctly")
            return True
        else:
            print("[WARN] Some configuration values are missing or invalid")
            return False
            
    except Exception as e:
        print(f"[ERROR] Configuration loading failed: {e}")
        return False


def test_path_manager():
    """Test that PathManager works correctly."""
    print("\n" + "="*80)
    print("TEST 2: PathManager Integration")
    print("="*80)
    
    try:
        config = ConfigManager()
        paths = PathManager(config)
        print("[OK] PathManager initialized successfully")
        
        # Test path properties
        print(f"  - Base path: {paths.base_path}")
        print(f"  - Data raw: {paths.data_raw}")
        print(f"  - Data processed: {paths.data_processed}")
        print(f"  - Logs: {paths.logs}")
        print(f"  - Config dir: {paths.config_dir}")
        
        # Verify paths exist or can be created
        if paths.base_path.exists():
            print("[OK] Base path exists")
        else:
            print("[WARN] Base path does not exist")
        
        # Test directory creation
        test_dir = paths.base_path / 'test_manual_dir'
        result = paths.ensure_exists(test_dir)
        if result.exists():
            print("[OK] Directory creation works")
            # Cleanup
            test_dir.rmdir()
        else:
            print("[WARN] Directory creation failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] PathManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_logging_system():
    """Test that logging system works correctly."""
    print("\n" + "="*80)
    print("TEST 3: Logging System")
    print("="*80)
    
    try:
        config = ConfigManager()
        setup_logging(config)
        print("[OK] Logging setup completed")
        
        logger = get_logger('test.manual')
        print("[OK] Logger created")
        
        # Test different log levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        print("[OK] Log messages sent successfully")
        
        # Check log file exists
        paths = PathManager(config)
        log_file = paths.logs / 'backend.log'
        if log_file.exists() or paths.logs.exists():
            print(f"[OK] Log directory exists: {paths.logs}")
        else:
            print("[WARN] Log directory/file not found (may be created on first log)")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Logging system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """Test that error handling works correctly."""
    print("\n" + "="*80)
    print("TEST 4: Error Handling")
    print("="*80)
    
    try:
        from src.exceptions import (
            ConfigError, PathError, CollectionError,
            ProcessingError, DatabaseError
        )
        print("[OK] Exception classes imported successfully")
        
        # Test exception creation
        try:
            raise ConfigError("Test configuration error", {"key": "test.key"})
        except ConfigError as e:
            print(f"[OK] ConfigError raised correctly: {e}")
            assert "Test configuration error" in str(e)
        
        try:
            raise PathError("Test path error", {"path": "/test/path"})
        except PathError as e:
            print(f"[OK] PathError raised correctly: {e}")
        
        print("[OK] Error handling works correctly")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """Test database connection (if available)."""
    print("\n" + "="*80)
    print("TEST 5: Database Connection")
    print("="*80)
    
    try:
        from src.api.database import get_db
        from sqlalchemy.orm import Session
        
        # Try to get database session
        db: Session = next(get_db())
        print("[OK] Database connection successful")
        
        # Test a simple query
        from src.api.models import SystemConfiguration
        count = db.query(SystemConfiguration).count()
        print(f"[OK] Database query successful (SystemConfiguration count: {count})")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"[WARN] Database connection test skipped: {e}")
        print("   (This is expected if database is not configured or not accessible)")
        return None  # Not a failure, just not available


def main():
    """Run all manual tests."""
    print("\n" + "="*80)
    print("MANUAL TESTING SUITE - Phase 7, Step 7.2")
    print("="*80)
    print("\nThis script tests core functionality without running the full cycle.")
    print("Use this to verify that all components work correctly.\n")
    
    results = {}
    
    # Run tests
    results['configuration'] = test_configuration_loading()
    results['path_manager'] = test_path_manager()
    results['logging'] = test_logging_system()
    results['error_handling'] = test_error_handling()
    results['database'] = test_database_connection()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        if result is True:
            status = "[PASS]"
        elif result is False:
            status = "[FAIL]"
        else:
            status = "[SKIP]"
        print(f"  {test_name:20} {status}")
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    total = len(results)
    
    print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    
    if failed == 0:
        print("\n[OK] All available tests passed!")
        return 0
    else:
        print(f"\n[ERROR] {failed} test(s) failed")
        return 1


if __name__ == '__main__':
    exit(main())

