
import re
from datetime import datetime
from collections import defaultdict

LOG_DIR = 'logs'
FILES = {
    'tailer': 'dataset_tailer.log',
    'ingestor': 'data_ingestor.log',
    'analysis': 'analysis_worker.log',
    'issue': 'issue_detection.log'
}

def parse_log_line(line):
    # 2026-01-21 17:00:36,353 - ...
    match = re.search(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
    if match:
        return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S,%f')
    return None

def analyze_tailer():
    print("\n--- DATA TRAILER ANALYSIS ---")
    path = f"{LOG_DIR}/{FILES['tailer']}"
    total_items = 0
    start_time = None
    end_time = None
    
    try:
        with open(path, 'r') as f:
            lines = f.readlines()
            # Analyze last 2000 lines approx
            lines = lines[-2000:]
            
            for line in lines:
                ts = parse_log_line(line)
                if not ts: continue
                if not start_time: start_time = ts
                end_time = ts
                
                # "Run ...: Completed tailing. Total items: 60"
                m = re.search(r'Total items: (\d+)', line)
                if m:
                    total_items += int(m.group(1))
                    
            duration = (end_time - start_time).total_seconds() if (end_time and start_time) else 0
            print(f"Time Window: {duration:.2f} seconds")
            print(f"Total Items Fetched: {total_items}")
            if duration > 0:
                print(f"Throughput: {total_items / duration:.2f} items/sec")
                print(f"Throughput: {total_items / (duration/60):.2f} items/min")
    except Exception as e:
        print(f"Error reading tailer log: {e}")

def analyze_ingestor():
    print("\n--- DATA INGESTOR ANALYSIS ---")
    path = f"{LOG_DIR}/{FILES['ingestor']}"
    batches = []
    
    try:
        with open(path, 'r') as f:
            lines = f.readlines()[-2000:]
            for line in lines:
                ts = parse_log_line(line)
                # "Batch inserted 67 records."
                m = re.search(r'Batch inserted (\d+) records', line)
                if m and ts:
                    batches.append({'ts': ts, 'count': int(m.group(1))})
    
        if not batches:
            print("No batch insertions found in recent logs.")
            return

        total_records = sum(b['count'] for b in batches)
        duration = (batches[-1]['ts'] - batches[0]['ts']).total_seconds()
        
        print(f"Time Window: {duration:.2f} seconds")
        print(f"Total Batches: {len(batches)}")
        print(f"Total Records Inserted: {total_records}")
        if len(batches) > 0:
             print(f"Avg Batch Size: {total_records / len(batches):.2f}")
        if duration > 0:
            print(f"Throughput: {total_records / duration:.2f} records/sec")
            print(f"Throughput: {total_records / (duration/60):.2f} records/min")

    except Exception as e:
        print(f"Error reading ingestor log: {e}")

def analyze_analysis():
    print("\n--- ANALYSIS WORKER ---")
    path = f"{LOG_DIR}/{FILES['analysis']}"
    analyzed_count = 0
    start_time = None
    end_time = None
    
    try:
        with open(path, 'r') as f:
            lines = f.readlines()[-2000:]
            for line in lines:
                ts = parse_log_line(line)
                if not ts: continue
                if not start_time: start_time = ts
                end_time = ts
                
                # "✓ Analyzed [804318]"
                if "✓ Analyzed" in line:
                    analyzed_count += 1
            
        duration = (end_time - start_time).total_seconds() if (end_time and start_time) else 0
        print(f"Time Window: {duration:.2f} seconds")
        print(f"Total Records Analyzed: {analyzed_count}")
        if duration > 0:
            print(f"Throughput: {analyzed_count / duration:.2f} records/sec")
            print(f"Throughput: {analyzed_count / (duration/60):.2f} records/min")
            
    except Exception as e:
        print(f"Error reading analysis log: {e}")

def analyze_issue():
    print("\n--- ISSUE ENGINE ---")
    path = f"{LOG_DIR}/{FILES['issue']}"
    cycles = []
    
    try:
        with open(path, 'r') as f:
            lines = f.readlines()[-5000:] # Need more lines for issue engine as it's slow
            
            start_ts = None
            for line in lines:
                ts = parse_log_line(line)
                if not ts: continue
                
                # "Issue detection loop: Starting iteration 18"
                if "Issue detection loop: Starting iteration" in line:
                    start_ts = ts
                
                # "Issue detection loop: Completed iteration 18"
                if "Issue detection loop: Completed iteration" in line and start_ts:
                    duration = (ts - start_ts).total_seconds()
                    cycles.append(duration)
                    start_ts = None
        
        print(f"Total Completed Cycles Found: {len(cycles)}")
        if cycles:
            avg_duration = sum(cycles) / len(cycles)
            print(f"Average Cycle Duration: {avg_duration:.2f} seconds ({avg_duration/60:.2f} minutes)")
            print(f"Max Cycle Duration: {max(cycles):.2f} seconds")
            
    except Exception as e:
        print(f"Error reading issue log: {e}")

if __name__ == "__main__":
    analyze_tailer()
    analyze_ingestor()
    analyze_analysis()
    analyze_issue()
