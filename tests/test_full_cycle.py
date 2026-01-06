"""
Test script for full data collection cycle.

This script:
1. Checks if backend API is running
2. Gets a valid user_id from database
3. Triggers a full cycle via API endpoint
4. Monitors progress through logs
5. Reports results
"""

import sys
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import User, TargetIndividualConfiguration
from src.config.path_manager import PathManager
from src.config.config_manager import ConfigManager


def check_backend_running(url: str = "http://localhost:8000") -> bool:
    """Check if backend API is running."""
    try:
        response = requests.get(f"{url}/health", timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Backend not accessible: {e}")
        return False


def get_test_user_id() -> Optional[str]:
    """Get a user_id from database for testing."""
    db = SessionLocal()
    try:
        # Try to get user with target config first
        target_config = db.query(TargetIndividualConfiguration).first()
        if target_config and target_config.user_id:
            user_id = str(target_config.user_id)
            print(f"✅ Found user with target config: {user_id}")
            return user_id
        
        # Fallback to any user
        user = db.query(User).first()
        if user:
            user_id = str(user.id)
            print(f"✅ Found user: {user_id} ({user.email})")
            return user_id
        
        print("❌ No users found in database")
        return None
    except Exception as e:
        print(f"❌ Error getting user_id: {e}")
        return None
    finally:
        db.close()


def trigger_cycle(backend_url: str, user_id: str) -> dict:
    """Trigger a full data collection cycle."""
    url = f"{backend_url}/agent/test-cycle-no-auth"
    params = {"test_user_id": user_id}
    
    try:
        print(f"\n🔄 Triggering cycle for user: {user_id}")
        print(f"   Endpoint: {url}")
        
        response = requests.post(url, params=params, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Cycle triggered successfully!")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message')}")
        
        if 'worker_configuration' in result:
            config = result['worker_configuration']
            print(f"\n📊 Worker Configuration:")
            print(f"   Collector Workers: {config.get('collector_workers')}")
            print(f"   Sentiment Workers: {config.get('sentiment_workers')}")
            print(f"   Location Workers: {config.get('location_workers')}")
            print(f"   Parallel Enabled: {config.get('parallel_enabled')}")
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to trigger cycle: {e}")
        return {"status": "error", "message": str(e)}


def monitor_logs(log_file: Path, max_wait_minutes: int = 30) -> bool:
    """Monitor log file for cycle completion."""
    print(f"\n📋 Monitoring logs: {log_file}")
    print(f"   Max wait time: {max_wait_minutes} minutes")
    
    if not log_file.exists():
        print(f"⚠️  Log file doesn't exist yet: {log_file}")
        print("   It will be created when the cycle starts.")
        return False
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    last_position = log_file.stat().st_size if log_file.exists() else 0
    
    print("\n⏳ Waiting for cycle to complete...")
    print("   (Press Ctrl+C to stop monitoring)")
    
    cycle_started = False
    cycle_completed = False
    
    try:
        while time.time() - start_time < max_wait_seconds:
            time.sleep(10)  # Check every 10 seconds
            
            if not log_file.exists():
                continue
            
            # Read new lines
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_position)
                new_lines = f.readlines()
                last_position = f.tell()
            
            # Check for cycle events
            for line in new_lines:
                if '[CYCLE START]' in line or 'Starting cycle' in line:
                    cycle_started = True
                    print(f"\n✅ Cycle started: {line.strip()}")
                
                if '[CYCLE END]' in line or 'Cycle completed' in line:
                    cycle_completed = True
                    print(f"\n✅ Cycle completed: {line.strip()}")
                    return True
                
                # Show progress updates
                if 'Phase' in line or 'PHASE' in line:
                    print(f"   {line.strip()}")
            
            # Show elapsed time
            elapsed = int(time.time() - start_time)
            if elapsed % 60 == 0:  # Every minute
                print(f"   ⏳ Elapsed: {elapsed // 60} minutes")
        
        if cycle_started and not cycle_completed:
            print(f"\n⚠️  Cycle started but didn't complete within {max_wait_minutes} minutes")
            return False
        elif not cycle_started:
            print(f"\n⚠️  Cycle didn't start within {max_wait_minutes} minutes")
            return False
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoring stopped by user")
        return False
    except Exception as e:
        print(f"\n❌ Error monitoring logs: {e}")
        return False


def check_cycle_results(user_id: str) -> dict:
    """Check database for cycle results."""
    db = SessionLocal()
    try:
        from src.api.models import SentimentData
        
        # Count recent records (last hour)
        one_hour_ago = datetime.now().timestamp() - 3600
        recent_count = db.query(SentimentData).filter(
            SentimentData.user_id == user_id,
            SentimentData.run_timestamp >= datetime.fromtimestamp(one_hour_ago)
        ).count()
        
        total_count = db.query(SentimentData).filter(
            SentimentData.user_id == user_id
        ).count()
        
        return {
            "recent_records": recent_count,
            "total_records": total_count
        }
    except Exception as e:
        print(f"❌ Error checking results: {e}")
        return {}
    finally:
        db.close()


def main():
    """Run full cycle test."""
    print("=" * 80)
    print("FULL DATA COLLECTION CYCLE TEST")
    print("=" * 80)
    
    # Configuration
    backend_url = "http://localhost:8000"
    config = ConfigManager()
    paths = PathManager(config)
    log_file = paths.logs_scheduling
    
    # Step 1: Check backend
    print("\n[Step 1] Checking backend API...")
    if not check_backend_running(backend_url):
        print("\n❌ Backend API is not running!")
        print("   Please start the backend first:")
        print("   uvicorn src.api.service:app --reload --host 0.0.0.0 --port 8000")
        return 1
    
    print("✅ Backend API is running")
    
    # Step 2: Get user_id
    print("\n[Step 2] Getting test user_id...")
    user_id = get_test_user_id()
    if not user_id:
        print("❌ Could not get user_id")
        return 1
    
    # Step 3: Trigger cycle
    print("\n[Step 3] Triggering data collection cycle...")
    result = trigger_cycle(backend_url, user_id)
    
    if result.get('status') != 'success':
        print("❌ Failed to trigger cycle")
        return 1
    
    # Step 4: Monitor progress
    print("\n[Step 4] Monitoring cycle progress...")
    cycle_completed = monitor_logs(log_file, max_wait_minutes=30)
    
    # Step 5: Check results
    print("\n[Step 5] Checking cycle results...")
    results = check_cycle_results(user_id)
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Cycle Status: {'✅ Completed' if cycle_completed else '⚠️  Incomplete or Timeout'}")
    print(f"Recent Records: {results.get('recent_records', 0)}")
    print(f"Total Records for User: {results.get('total_records', 0)}")
    print(f"Log File: {log_file}")
    print("=" * 80)
    
    return 0 if cycle_completed else 1


if __name__ == "__main__":
    sys.exit(main())
