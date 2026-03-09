# Collector Log Management

## Overview

The collector logs can accumulate quickly (186 files = 5.06 MB in your case). We've implemented an automatic log rotation system to keep only recent logs and clean up old ones.

## Automatic Cleanup

### How It Works

1. **Scheduled Cleanup**: Runs daily at 2:00 AM
2. **Retention Period**: Keeps only the last 5 days of logs (configurable)
3. **On Startup**: Runs cleanup when scheduler starts
4. **Automatic**: No manual intervention needed

### Configuration

Edit `config/.env` to change retention period:

```bash
# Keep logs for 5 days (default)
COLLECTOR_LOG_RETENTION_DAYS=5

# Or change to keep more/fewer days:
COLLECTOR_LOG_RETENTION_DAYS=7   # Keep 1 week
COLLECTOR_LOG_RETENTION_DAYS=3   # Keep 3 days
COLLECTOR_LOG_RETENTION_DAYS=14  # Keep 2 weeks
```

## Manual Cleanup

You can also run cleanup manually using the provided script.

### Preview What Would Be Deleted (Dry Run)

```bash
python3 scripts/cleanup_collector_logs.py --dry-run
```

This shows:
- How many files would be deleted per collector
- File names, ages, and sizes
- Total space that would be freed
- **Does NOT actually delete anything**

### Actually Delete Old Logs

```bash
python3 scripts/cleanup_collector_logs.py
```

### Custom Retention Period

```bash
# Keep only 3 days
python3 scripts/cleanup_collector_logs.py --days 3

# Preview with 7 days retention
python3 scripts/cleanup_collector_logs.py --days 7 --dry-run
```

## Example Output

Based on your current logs (186 files):

```
================================================================================
Collector Log Cleanup
================================================================================
📂 Directory: /home/ubuntu/Clariona-1.5/Clariona-Backend/logs/collectors
📅 Retention: 5 days
✂️  Cutoff date: 2026-02-23 17:15:43
================================================================================

📊 Summary by Collector:
--------------------------------------------------------------------------------
  news_api:
    Total: 47 files
    To delete: 42 files (89%)
    To keep: 5 files

  radio_hybrid:
    Total: 46 files
    To delete: 41 files (89%)
    To keep: 5 files

  rss_nigerian_qatar_indian:
    Total: 47 files
    To delete: 42 files (89%)
    To keep: 5 files

  youtube:
    Total: 46 files
    To delete: 41 files (89%)
    To keep: 5 files

================================================================================
Summary:
  Files to delete: 166
  Files to keep: 20
  Space to free: 5.06 MB
================================================================================
```

## What Gets Deleted?

- ✅ Log files older than retention period (default: 5 days)
- ❌ Recent logs (within retention period) are kept
- 📊 Typically keeps 5-7 log files per collector (one per day)

## What Gets Kept?

For each collector, keeps the most recent logs:
- Last 5 days with default retention
- One log file per day per collector
- Example: `youtube_20260228_060000.log` (from today)

## Cron Job Setup (Optional)

To run cleanup automatically via cron instead of the scheduler:

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2 AM
0 2 * * * cd /home/ubuntu/Clariona-1.5/Clariona-Backend && /usr/bin/python3 scripts/cleanup_collector_logs.py >> logs/cleanup.log 2>&1
```

## Monitoring

### Check Current Log Usage

```bash
# Count log files
ls -1 logs/collectors/*.log | wc -l

# Check total size
du -sh logs/collectors/

# Group by collector
for collector in news_api radio_hybrid rss_nigerian_qatar_indian youtube; do
    count=$(ls -1 logs/collectors/${collector}_*.log 2>/dev/null | wc -l)
    echo "$collector: $count files"
done
```

### View Cleanup History

If running via scheduler, check:
```bash
grep "Log cleanup" logs/scheduler.log
```

Example output:
```
2026-02-28 02:00:00 - services.scheduler - INFO - Starting log cleanup (retention: 5 days, cutoff: 2026-02-23)
2026-02-28 02:00:01 - services.scheduler - INFO - Log cleanup complete: 166 files deleted (5.06 MB), 20 files kept
```

## Troubleshooting

### Cleanup Not Running Automatically

1. Check if scheduler is running:
   ```bash
   ps aux | grep scheduler
   ```

2. Check scheduler logs:
   ```bash
   tail -f logs/scheduler.log
   ```

3. Verify cron trigger is set up (should show at 02:00):
   ```bash
   # In scheduler output, look for:
   # "Scheduled log cleanup at 02:00 (retention: 5 days)"
   ```

### Manual Cleanup Failed

1. Check permissions:
   ```bash
   ls -la logs/collectors/
   ```

2. Run with verbose output:
   ```bash
   python3 scripts/cleanup_collector_logs.py --dry-run
   ```

3. Check for errors in output

### Changed Retention But Still Deleting Wrong Files

- Restart the scheduler for changes to take effect
- Environment variables are loaded on scheduler initialization
- Manual script reads from `.env` on each run

## Best Practices

1. **Start with 5 days**: Good balance between debugging history and disk space
2. **Monitor disk usage**: Increase retention if you need more history
3. **Use dry-run first**: Always test with `--dry-run` before manual cleanup
4. **Keep production logs longer**: Consider 7-14 days for production systems
5. **Archive important logs**: If debugging an issue, copy logs elsewhere before cleanup

## Log Size Guidelines

Typical sizes per collector:
- `news_api`: ~1-2 KB (small, mostly errors due to missing API keys)
- `radio_hybrid`: ~90-240 KB (medium, lots of data)
- `rss_nigerian_qatar_indian`: ~0.7 KB (small, errors)
- `youtube`: ~5-60 KB (varies, depends on results)

Expected total with 5-day retention:
- ~20 log files (4 collectors × 5 days)
- ~1-2 MB total disk usage
- Cleanup saves ~5-10 MB weekly

## Summary

✅ **Automatic cleanup at 2 AM daily**  
✅ **Keeps last 5 days by default**  
✅ **Configurable via `COLLECTOR_LOG_RETENTION_DAYS`**  
✅ **Manual cleanup available**  
✅ **Dry-run mode to preview**  
✅ **Per-collector statistics**
