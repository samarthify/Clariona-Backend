#!/usr/bin/env python3
"""
Manually trigger all collectors to test them.
This runs all collectors once without waiting for the schedule.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(src_path))

from dotenv import load_dotenv

# Load environment
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / 'config' / '.env')

from api.database import SessionLocal
from services.data_ingestor import DataIngestor
from services.scheduler import LocalScheduler

async def main():
    """Run all collectors manually."""
    print("=" * 80)
    print("Manual Collector Run - Testing All Collectors")
    print("=" * 80)
    print()
    
    # Initialize
    session = SessionLocal()
    ingestor = DataIngestor(session)
    scheduler = LocalScheduler(ingestor)
    
    # Get list of enabled collectors
    collectors = [name for name, config in scheduler.collectors.items() if config['enabled']]
    
    print(f"Found {len(collectors)} enabled collectors:")
    for name in collectors:
        print(f"  - {name}")
    print()
    
    # Run each collector
    results = {}
    for i, collector_name in enumerate(collectors, 1):
        print(f"[{i}/{len(collectors)}] Running {collector_name}...")
        print("-" * 80)
        
        try:
            success = await scheduler.run_collector_now(collector_name)
            results[collector_name] = "✅ Success" if success else "❌ Failed"
            
            if success:
                print(f"✅ {collector_name} completed successfully")
            else:
                print(f"❌ {collector_name} failed")
                
        except Exception as e:
            results[collector_name] = f"❌ Error: {str(e)}"
            print(f"❌ {collector_name} error: {e}")
        
        print()
    
    # Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    for collector_name, result in results.items():
        print(f"{collector_name:30s} : {result}")
    
    print()
    success_count = sum(1 for r in results.values() if "✅" in r)
    print(f"Total: {success_count}/{len(collectors)} collectors succeeded")
    
    # Cleanup
    session.close()
    
    return 0 if success_count == len(collectors) else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
