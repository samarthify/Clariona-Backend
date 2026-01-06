
import os
import sys
import time
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, desc

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.database import SessionLocal
from src.api import models

# Config
API_URL = "http://localhost:8000"
LOG_FILE = project_root / "logs" / "automatic_scheduling.log"
OUTPUT_DIR = project_root / "test_results"

def get_test_user_id(db: Session):
    # Try to get first user with target config
    target_config = db.query(models.TargetIndividualConfiguration).first()
    if target_config and target_config.user_id:
        return str(target_config.user_id)
    
    # Fallback to any user
    user = db.query(models.User).first()
    if user:
        return str(user.id)
    return None

def trigger_cycle(user_id, skip_collection=False):
    # Check health first
    try:
        health = requests.get(f"{API_URL}/health")
        print(f"Health check: {health.status_code} - {health.text}")
    except Exception as e:
        print(f"Health check failed: {e}")

    print(f"Triggering test cycle for user: {user_id}")
    try:
        url = f"{API_URL}/agent/test-cycle-no-auth?test_user_id={user_id}"
        if skip_collection:
            url += "&skip_collection_only=true"
        # Retry logic
        for attempt in range(3):
            try:
                print(f"Attempt {attempt+1}...")
                response = requests.post(url, timeout=10) # Short timeout for trigger
                response.raise_for_status()
                print("Cycle triggered successfully.")
                return response.json()
            except requests.exceptions.ConnectionError as ce:
                print(f"Connection error: {ce}. Retrying in 2s...")
                time.sleep(2)
            except Exception as e:
                print(f"Error triggering: {e}")
                raise
        raise Exception("Failed to trigger cycle after retries")
    except Exception as e:
        print(f"Final error triggering cycle: {e}")
        sys.exit(1)

def wait_for_completion(log_file_obj, user_id):
    print("Waiting for cycle completion (monitoring new log frames)...")
    
    # We assume log_file_obj is already opened and seeked to the position before trigger
    # But wait, we passed start_time before. Now passing file obj? 
    # Let's adjust main() to open file first.
    
    max_retries = 200 # 200 * 5s = 1000s (~16 mins) - cycle can be slow
    
    for i in range(max_retries):
        line = log_file_obj.readline()
        while line:
            if f"User: {user_id}" in line and ("[CYCLE SUMMARY]" in line or "[CYCLE END]" in line):
                 print(f"Cycle completion detected: {line.strip()}")
                 return True
            line = log_file_obj.readline()
            
        time.sleep(5)
        if i % 10 == 0:
            print(f"  ... still waiting ({i*5}s)")
            
    print("Timeout waiting for cycle completion.")
    return False

def export_results(db: Session, user_id: str, start_time: datetime):
    print("Exporting results...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")
    
    # 1. Fetch Mentions (SentimentData)
    print("Fetching Mentions...")
    # Fetch mentions updated/created after start_time, or just all recent for this user to be sure
    # Since 'test cycle' might update existing records, filtering by 'updated_at' would be ideal if available,
    # otherwise we take all for user to show the "Results" requested.
    # The user asked: "review the results it is generating for every metric for a mention" - implies viewing the current state.
    
    mentions = db.query(models.SentimentData).filter(
        models.SentimentData.user_id == user_id
    ).order_by(desc(models.SentimentData.entry_id)).limit(100).all() # Limit to 100 recent for brevity/speed? Or all? User said "test cycle", so likely just the ones involved.
    
    mention_data = []
    for m in mentions:
        # Get Topics
        topic_links = db.query(models.MentionTopic).filter(models.MentionTopic.mention_id == m.entry_id).all()
        topics_str = "; ".join([f"{t.topic_key}({t.topic_confidence:.2f})" for t in topic_links])
        
        # Get Issues
        issue_links = db.query(models.IssueMention).filter(models.IssueMention.mention_id == m.entry_id).all()
        issues_str = ""
        if issue_links:
            issue_ids = [link.issue_id for link in issue_links]
            issues = db.query(models.TopicIssue).filter(models.TopicIssue.id.in_(issue_ids)).all()
            issues_str = "; ".join([f"{i.issue_slug}" for i in issues])

        mention_data.append({
            "Entry ID": m.entry_id,
            "Text": (m.text or "")[:100], # Truncate for CSV readability
            "Sentiment": m.sentiment_label,
            "Sentiment Score": m.sentiment_score,
            "Emotion": m.emotion_label,
            "Influence Weight": m.influence_weight,
            "Confidence Weight": m.confidence_weight,
            "Location": m.location_label or m.country,
            "Location Confidence": m.location_confidence,
            "Topics": topics_str,
            "Issues": issues_str,
            "Created At": m.created_at
        })
    
    df_mentions = pd.DataFrame(mention_data)
    mentions_file = OUTPUT_DIR / f"mentions_results_{timestamp_str}.csv"
    df_mentions.to_csv(mentions_file, index=False)
    print(f"Mentions exported to {mentions_file}")

    # 2. Fetch Aggregations
    print("Fetching Aggregations...")
    aggs = db.query(models.SentimentAggregation).order_by(desc(models.SentimentAggregation.calculated_at)).limit(50).all()
    
    agg_data = []
    for a in aggs:
        agg_data.append({
            "Type": a.aggregation_type,
            "Key": a.aggregation_key,
            "Window": a.time_window,
            "Mention Count": a.mention_count,
            "Sentiment Score": a.weighted_sentiment_score,
            "Sentiment Index": a.sentiment_index,
            "Calculated At": a.calculated_at
        })
        
    df_aggs = pd.DataFrame(agg_data)
    aggs_file = OUTPUT_DIR / f"aggregations_results_{timestamp_str}.csv"
    df_aggs.to_csv(aggs_file, index=False)
    print(f"Aggregations exported to {aggs_file}")
    
    # 3. Fetch Issues (Detailed)
    print("Fetching Issues...")
    issues = db.query(models.TopicIssue).filter(
        models.TopicIssue.is_active == True
    ).all()
    
    issue_data = []
    for i in issues:
        issue_data.append({
            "Slug": i.issue_slug,
            "Label": i.issue_label,
            "Topic": i.topic_key,
            "State": i.state,
            "Mentions": i.mention_count,
            "Priority": i.priority_score,
            "Start Time": i.start_time,
            "Last Activity": i.last_activity
        })
    
    df_issues = pd.DataFrame(issue_data)
    issues_file = OUTPUT_DIR / f"issues_results_{timestamp_str}.csv"
    df_issues.to_csv(issues_file, index=False)
    print(f"Issues exported to {issues_file}")

    return [mentions_file, aggs_file, issues_file]


import argparse

def check_cycle_status(user_id):
    """
    Checks if a cycle is currently running or completed recently.
    Returns: 'completed', 'running', 'unknown'
    """
    if not LOG_FILE.exists():
        return 'unknown'
        
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-2000:] # Check last 2000 lines
            
        last_start_idx = -1
        last_end_idx = -1
        
        for i, line in enumerate(lines):
            if f"User: {user_id}" in line:
                if "[PHASE 1: COLLECTION START]" in line:
                    last_start_idx = i
                elif "[CYCLE SUMMARY]" in line or "[CYCLE END]" in line:
                    last_end_idx = i
                    
        if last_start_idx == -1:
            return 'unknown'
            
        if last_end_idx > last_start_idx:
            print(f"Found completed cycle at log line ~{len(lines)-last_end_idx} ago.")
            return 'completed'
        else:
            print(f"Found running cycle started at log line ~{len(lines)-last_start_idx} ago.")
            return 'running'
            
    except Exception as e:
        print(f"Error checking status: {e}")
        return 'unknown'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--monitor-only', action='store_true', help='Skip triggering and only monitor/export')
    parser.add_argument('--skip-collection', action='store_true', help='Skip collection phase when triggering')
    args = parser.parse_args()

    db = SessionLocal()
    log_file_handle = None
    try:
        user_id = get_test_user_id(db)
        if not user_id:
            print("No suitable user found for testing.")
            return

        print("--- Starting Test Core Cycle metrics ---")
        
        start_time = datetime.now()
        
        if args.monitor_only:
            print("Monitor-only mode enabled.")
            status = check_cycle_status(user_id)
            if status == 'completed':
                print("Cycle appears to be already completed. Exporting results immediately.")
                export_results(db, user_id, start_time - timedelta(hours=1)) # approximate start time
                return
            elif status == 'unknown':
                print("Could not detect recent cycle start. Waiting for any new cycle...")
            # If running, we proceed to wait
        else:
            trigger_cycle(user_id, skip_collection=args.skip_collection)
        
        # Open log file for monitoring
        if LOG_FILE.exists():
            log_file_handle = open(LOG_FILE, 'r', encoding='utf-8')
            log_file_handle.seek(0, 2) # Seek to end
        else:
            print(f"Log file not found at {LOG_FILE}. Creating empty...")
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOG_FILE.touch()
            log_file_handle = open(LOG_FILE, 'r', encoding='utf-8')
            log_file_handle.seek(0, 2)

        # Pass the file handle to wait function
        completed = wait_for_completion(log_file_handle, user_id)
        
        if completed:
            print("Cycle completed successfully (according to logs).")
        else:
            print("Warning: Cycle may not have completed or log polling timed out. Exporting available data anyway.")
        
        # Export
        # If we monitored, start_time is now. We should export data from the cycle.
        # Ideally we'd parse the start time from logs, but for now using current time - 1h 
        # as a safe fallback window or just recent records.
        # The export function filters by user_id and limit=100, which is robust enough.
        export_results(db, user_id, start_time)
        print("\n--- Test and Export Data Generation Complete ---")
        print(f"Files generated in: {OUTPUT_DIR}")
        # List files
        for f in OUTPUT_DIR.glob(f"*{start_time.strftime('%Y%m%d')}*.csv"):
            print(f"- {f.name}")
            
    finally:
        if log_file_handle:
            log_file_handle.close()
        db.close()

if __name__ == "__main__":
    main()
