#!/usr/bin/env python3
"""
Example script demonstrating sentiment change detection and notification.
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path
import random
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.notification_service import send_analysis_report, detect_sentiment_change
from src.utils.mail_config import get_email_recipients, is_email_notification_enabled

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    """Demonstrate sentiment change detection and notification using real data."""
    # Check if email is configured
    if not is_email_notification_enabled():
        logger.error(
            "Email notifications are disabled. "
            "Please set EMAIL_NOTIFICATION_ENABLED=true in your .env file."
        )
        return
    
    recipients = get_email_recipients()
    if not recipients:
        logger.error("No email recipients configured. Please set EMAIL_RECIPIENTS in your .env file.")
        # Optional: Prompt for a recipient if none is configured for testing
        # custom_recipient = input("Enter a recipient email address for testing: ")
        # if custom_recipient:
        #     recipients = [custom_recipient]
        # else:
        #     return
        return # Exit if no recipients configured
    
    # Define paths to the actual dashboard data files
    base_path = Path(__file__).parent.parent.parent
    dashboard_dir = base_path / "dashboard" / "public"
    latest_file = dashboard_dir / "processed_data.csv"
    previous_file = dashboard_dir / "processed_data_old.csv"

    # Load the data files
    logger.info(f"Loading latest data from: {latest_file}")
    if not latest_file.exists():
        logger.error(f"Latest data file not found at {latest_file}. Cannot generate report.")
        return
        
    current_data = pd.read_csv(latest_file)

    logger.info(f"Loading previous data from: {previous_file}")
    previous_data = None
    if previous_file.exists():
        previous_data = pd.read_csv(previous_file)
    else:
        logger.warning(f"Previous data file not found at {previous_file}. Cannot detect changes.")

    # Detect sentiment changes using real data
    logger.info("Detecting sentiment changes...")
    sentiment_changed, sentiment_change_data = detect_sentiment_change(current_data, previous_data)
    
    logger.info(f"Sentiment change detected: {sentiment_changed}")
    if sentiment_changed:
        change_value = sentiment_change_data.get("change_value", 0)
        change_direction = sentiment_change_data.get("change_direction", "changed")
        logger.info(f"Sentiment has {change_direction} by {abs(change_value):.2f} points")
    elif previous_data is None:
        logger.info("Cannot report change direction as previous data was missing.")
    else:
         logger.info("No significant sentiment change detected based on comparison.")
        
    # Calculate statistics from the current real data
    logger.info("Calculating statistics from current data...")
    total = len(current_data)
    positive_count = (current_data['sentiment_label'] == 'positive').sum() if 'sentiment_label' in current_data else 0
    negative_count = (current_data['sentiment_label'] == 'negative').sum() if 'sentiment_label' in current_data else 0
    neutral_count = total - positive_count - negative_count
    
    positive_pct = (positive_count / total * 100) if total > 0 else 0
    negative_pct = (negative_count / total * 100) if total > 0 else 0
    neutral_pct = (neutral_count / total * 100) if total > 0 else 0
    
    # Extract topics by sentiment from current real data
    positive_topics = {}
    negative_topics = {}
    # Check if 'keywords' column exists, otherwise skip topic extraction
    if 'keywords' in current_data.columns and 'sentiment_score' in current_data.columns:
        logger.info("Extracting topics...")
        for _, row in current_data.dropna(subset=['keywords']).iterrows(): # Handle potential NaN in keywords
            keywords = str(row['keywords']).split(',') # Ensure keywords is string
            sentiment = row['sentiment_score']
            
            for keyword in keywords:
                keyword = keyword.strip()
                if not keyword:
                    continue
                
                # Use try-except for sentiment comparison robustness
                try: 
                    if float(sentiment) > 0.2:
                        positive_topics[keyword] = positive_topics.get(keyword, 0) + 1
                    elif float(sentiment) < -0.2:
                        negative_topics[keyword] = negative_topics.get(keyword, 0) + 1
                except (ValueError, TypeError):
                     continue # Skip if sentiment score is not a valid number
    else:
         logger.warning("'keywords' or 'sentiment_score' column not found. Skipping topic extraction.")

    # Prepare insights (Placeholder for this example script)
    insights = [
        "This is an automated analysis based on the latest processed data.",
        f"Compared against data from {previous_file.name if previous_data is not None else 'N/A'}."
    ]
    if sentiment_changed:
        insights.insert(1, f"Sentiment has {sentiment_change_data.get('change_direction', 'changed')} significantly.")
        # Add real change data to insights
        for topic_data in sentiment_change_data.get("new_topics", []):
            insights.append(f"New topic detected: '{topic_data.get('topic')}' with {topic_data.get('count')} mentions")
        for topic_data in sentiment_change_data.get("fading_topics", []):
             insights.append(f"Topic declining/faded: '{topic_data.get('topic')}' (from {topic_data.get('previous_count')} to {topic_data.get('current_count')} mentions)")
    else:
         insights.insert(1, "No significant overall sentiment change detected.")

    # Prepare analysis data dictionary using real stats
    analysis_data = {
        "overall_sentiment": current_data['sentiment_score'].mean() if 'sentiment_score' in current_data else 0,
        "positive_mentions": positive_pct,
        "neutral_mentions": neutral_pct,
        "negative_mentions": negative_pct,
        "total_mentions": total,
        "positive_topics": positive_topics,
        "negative_topics": negative_topics,
        "insights": insights
    }
    
    # Add real sentiment change data if detected
    if sentiment_changed:
        analysis_data.update(sentiment_change_data)
    
    # Send report email with real data analysis
    logger.info("Sending analysis report based on real data comparison...")
    success = send_analysis_report(analysis_data, recipients)
    
    if success:
        logger.info(f"Analysis report sent successfully to {', '.join(recipients)}!")
    else:
        logger.error("Failed to send analysis report.")

if __name__ == "__main__":
    main() 
