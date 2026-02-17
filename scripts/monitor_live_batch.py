import os
import re
from datetime import datetime
import time

LOG_DIR = '/home/ubuntu/Clariona-1.5/Clariona-Backend/logs'
# Monitor specifically after user's performance test run (approx 18:19 UTC)
START_TIME_STR = '2026-01-21 19:30:00'
START_TIME = datetime.strptime(START_TIME_STR, '%Y-%m-%d %H:%M:%S')

def monitor_batch_progress():
    ingestor_log = os.path.join(LOG_DIR, 'data_ingestor.log')
    analysis_log = os.path.join(LOG_DIR, 'analysis_worker.log')
    
    ingested_count = 0
    analyzed_count = 0
    
    ingest_timestamps = []
    analysis_timestamps = []
    
    # 1. Count Ingestion
    if os.path.exists(ingestor_log):
        with open(ingestor_log, 'r') as f:
            for line in f:
                # Look for "✓ STORED" or "Batch inserted"
                # "Batch inserted N records." is better for counting volume
                match_ts = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
                if match_ts:
                    ts = datetime.strptime(match_ts.group(1), '%Y-%m-%d %H:%M:%S,%f')
                    if ts > START_TIME:
                        # Check for batch insert
                        batch_match = re.search(r'Batch inserted (\d+) records', line)
                        if batch_match:
                            count = int(batch_match.group(1))
                            ingested_count += count
                            ingest_timestamps.append(ts)
    
    # 2. Count Analysis
    if os.path.exists(analysis_log):
        with open(analysis_log, 'r') as f:
            for line in f:
                match_ts = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
                if match_ts:
                    ts = datetime.strptime(match_ts.group(1), '%Y-%m-%d %H:%M:%S,%f')
                    if ts > START_TIME:
                        if '✓ Analyzed' in line or 'No text content' in line:
                            analyzed_count += 1
                            analysis_timestamps.append(ts)
                            
    # Metrics
    metrics = []
    metrics.append(f"Live Batch Monitoring (Since {START_TIME_STR})")
    metrics.append("-" * 40)
    
    # Ingestion Metrics
    if ingest_timestamps:
        duration = (ingest_timestamps[-1] - ingest_timestamps[0]).total_seconds()
        rate = ingested_count / duration if duration > 0 else ingested_count
        metrics.append(f"Ingestion: {ingested_count} records. Rate: {rate:.2f} rec/sec (Duration: {duration:.2f}s)")
    else:
        metrics.append(f"Ingestion: 0 records found yet.")
        
    # Analysis Metrics
    if analysis_timestamps:
        duration = (analysis_timestamps[-1] - analysis_timestamps[0]).total_seconds()
        rate = analyzed_count / duration if duration > 0 else analyzed_count
        metrics.append(f"Analysis:  {analyzed_count} records. Rate: {rate:.2f} rec/sec (Duration: {duration:.2f}s)")
        
        # Check current lag
        lag = ingested_count - analyzed_count
        metrics.append(f"Pipeline Lag: {lag} records (Ingested - Analyzed)")
    else:
        metrics.append(f"Analysis:  0 records found yet.")
        
    return "\n".join(metrics)

if __name__ == "__main__":
    print(monitor_batch_progress())
