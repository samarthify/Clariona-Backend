#!/usr/bin/env python3
"""
Standalone script to clean up old collector log files.
Can be run manually or via cron job.

Usage:
    python3 scripts/cleanup_collector_logs.py [--days 5] [--dry-run]
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path


def cleanup_logs(log_dir: Path, retention_days: int, dry_run: bool = False):
    """
    Clean up old log files.
    
    Args:
        log_dir: Path to logs/collectors directory
        retention_days: Number of days to retain logs
        dry_run: If True, only show what would be deleted
    """
    if not log_dir.exists():
        print(f"❌ Log directory does not exist: {log_dir}")
        return 1
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    print("=" * 80)
    print(f"Collector Log Cleanup {'(DRY RUN)' if dry_run else ''}")
    print("=" * 80)
    print(f"📂 Directory: {log_dir}")
    print(f"📅 Retention: {retention_days} days")
    print(f"✂️  Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    # Get all log files
    log_files = sorted(log_dir.glob("*.log"))
    
    if not log_files:
        print("ℹ️  No log files found.")
        return 0
    
    print(f"Found {len(log_files)} total log files\n")
    
    # Categorize by collector type and age
    files_to_delete = []
    files_to_keep = []
    total_size_to_delete = 0
    
    # Group by collector type
    by_collector = {}
    
    for log_file in log_files:
        try:
            # Extract collector name from filename (e.g., "youtube_20260228_060000.log" -> "youtube")
            collector_name = log_file.stem.rsplit('_', 2)[0]
            
            # Get file age
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            age_days = (datetime.now() - file_mtime).days
            file_size = log_file.stat().st_size
            
            if collector_name not in by_collector:
                by_collector[collector_name] = {
                    'to_delete': [],
                    'to_keep': []
                }
            
            if file_mtime < cutoff_date:
                files_to_delete.append((log_file, age_days, file_size))
                by_collector[collector_name]['to_delete'].append((log_file, age_days, file_size))
                total_size_to_delete += file_size
            else:
                files_to_keep.append((log_file, age_days, file_size))
                by_collector[collector_name]['to_keep'].append((log_file, age_days, file_size))
                
        except Exception as e:
            print(f"⚠️  Error processing {log_file.name}: {e}")
    
    # Print summary by collector
    print("📊 Summary by Collector:")
    print("-" * 80)
    for collector_name in sorted(by_collector.keys()):
        info = by_collector[collector_name]
        delete_count = len(info['to_delete'])
        keep_count = len(info['to_keep'])
        total_count = delete_count + keep_count
        
        print(f"  {collector_name}:")
        print(f"    Total: {total_count} files")
        print(f"    To delete: {delete_count} files")
        print(f"    To keep: {keep_count} files")
    
    print()
    
    # Show files to be deleted
    if files_to_delete:
        print(f"🗑️  Files to delete ({len(files_to_delete)}):")
        print("-" * 80)
        for log_file, age_days, file_size in sorted(files_to_delete, key=lambda x: x[1], reverse=True):
            size_kb = file_size / 1024
            print(f"  - {log_file.name:50s} (age: {age_days:3d} days, size: {size_kb:7.1f} KB)")
        print()
    
    # Convert total size to human-readable format
    if total_size_to_delete > 1024 * 1024 * 1024:
        size_str = f"{total_size_to_delete / (1024 * 1024 * 1024):.2f} GB"
    elif total_size_to_delete > 1024 * 1024:
        size_str = f"{total_size_to_delete / (1024 * 1024):.2f} MB"
    elif total_size_to_delete > 1024:
        size_str = f"{total_size_to_delete / 1024:.2f} KB"
    else:
        size_str = f"{total_size_to_delete} bytes"
    
    # Summary
    print("=" * 80)
    print(f"Summary:")
    print(f"  Files to delete: {len(files_to_delete)}")
    print(f"  Files to keep: {len(files_to_keep)}")
    print(f"  Space to free: {size_str}")
    print("=" * 80)
    print()
    
    if not files_to_delete:
        print("✅ No old logs to delete.")
        return 0
    
    # Delete files (if not dry run)
    if not dry_run:
        print("🗑️  Deleting old logs...")
        deleted_count = 0
        error_count = 0
        
        for log_file, _, _ in files_to_delete:
            try:
                log_file.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"❌ Error deleting {log_file.name}: {e}")
                error_count += 1
        
        print(f"\n✅ Cleanup complete!")
        print(f"   Deleted: {deleted_count} files")
        print(f"   Errors: {error_count}")
        print(f"   Freed: {size_str}")
        
        return 0 if error_count == 0 else 1
    else:
        print("ℹ️  DRY RUN - No files were actually deleted.")
        print("   Run without --dry-run to actually delete files.")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Clean up old collector log files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what would be deleted (default: 5 days retention)
  python3 scripts/cleanup_collector_logs.py --dry-run

  # Actually delete logs older than 5 days
  python3 scripts/cleanup_collector_logs.py

  # Delete logs older than 7 days
  python3 scripts/cleanup_collector_logs.py --days 7

  # Preview deletion with 3 days retention
  python3 scripts/cleanup_collector_logs.py --days 3 --dry-run
        """
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=5,
        help='Number of days to retain logs (default: 5)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    parser.add_argument(
        '--log-dir',
        type=Path,
        default=None,
        help='Path to logs/collectors directory (default: auto-detect)'
    )
    
    args = parser.parse_args()
    
    # Determine log directory
    if args.log_dir:
        log_dir = args.log_dir
    else:
        # Auto-detect: assume script is in scripts/ and logs are in logs/collectors/
        base_path = Path(__file__).parent.parent
        log_dir = base_path / 'logs' / 'collectors'
    
    # Run cleanup
    return cleanup_logs(log_dir, args.days, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
