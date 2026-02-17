import os
import re
from datetime import datetime, timedelta

LOG_DIR = '/home/ubuntu/Clariona-1.5/Clariona-Backend/logs'
RESTART_TIME_STR = '2026-01-21 17:31:00'
RESTART_TIME = datetime.strptime(RESTART_TIME_STR, '%Y-%m-%d %H:%M:%S')

def analysis_metrics():
    log_file = os.path.join(LOG_DIR, 'analysis_worker.log')
    timestamps = []
    
    with open(log_file, 'r') as f:
        for line in f:
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
            if match and '✓ Analyzed' in line:
                ts = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S,%f')
                if ts > RESTART_TIME:
                    timestamps.append(ts)
    
    if not timestamps:
        return "No analyzed records found."

    # Sort just in case
    timestamps.sort()
    
    # Calculate rolling throughput (1-second windows)
    max_throughput = 0
    current_window_start = timestamps[0]
    current_window_count = 0
    
    # Bucket into seconds
    buckets = {}
    for ts in timestamps:
        sec = ts.replace(microsecond=0)
        buckets[sec] = buckets.get(sec, 0) + 1
        
    max_throughput = max(buckets.values()) if buckets else 0
    avg_throughput = len(timestamps) / (timestamps[-1] - timestamps[0]).total_seconds() if len(timestamps) > 1 else len(timestamps)
    
    return f"Analysis: Total {len(timestamps)} records. Avg: {avg_throughput:.2f}/sec. Peak: {max_throughput} records/sec."

def issue_metrics():
    log_file = os.path.join(LOG_DIR, 'issue_detection.log')
    if not os.path.exists(log_file):
        return "Issue log not found."
    
    topics_started = []
    cycle_start = None
    
    with open(log_file, 'r') as f:
        for line in f:
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
            if match:
                ts = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S,%f')
                if ts > RESTART_TIME:
                    if 'Issue detection: Starting detection run' in line:
                        cycle_start = ts
                    if 'Detecting issues for topic:' in line:
                        topics_started.append(ts)
    
    if cycle_start:
        duration = "(Running)"
        if topics_started:
             # Check distinct seconds to see parallelism
             secs = set(t.replace(microsecond=0) for t in topics_started)
             return f"Issue Detection: Cycle started {cycle_start}. Topics processed: {len(topics_started)}. Unique Start Seconds: {len(secs)} (Indicates parallelism if << topic count)."
        return f"Issue Detection: Cycle started {cycle_start}. No topics processed yet."
        
    return "Issue Detection: No cycle started yet."

print("refined_metrics")
print(analysis_metrics())
print(issue_metrics())
