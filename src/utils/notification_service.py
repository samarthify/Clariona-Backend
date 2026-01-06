#!/usr/bin/env python3
"""
Notification service for sentiment analysis results.
"""

import os
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Union, Optional
from pathlib import Path
import numpy as np
import requests
import json

from src.utils.mail_sender import MailSender
# Remove get_email_recipients, is_email_notification_enabled
# from src.utils.mail_config import get_email_recipients, is_email_notification_enabled

# Need Session factory type hint for db_factory argument
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

BASE_PATH = Path(__file__).parent.parent.parent
# Define API endpoint URL (Best practice: move to config or env var)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000") # Default for local dev
COMPARISON_DATA_ENDPOINT = f"{API_BASE_URL}/comparison-data"

# Load sentiment thresholds from ConfigManager
def _get_sentiment_thresholds():
    """Get sentiment thresholds from ConfigManager with fallback defaults."""
    try:
        from config.config_manager import ConfigManager
        config = ConfigManager()
        positive_threshold = config.get_float("processing.sentiment.positive_threshold", 0.2)
        negative_threshold = config.get_float("processing.sentiment.negative_threshold", -0.2)
        return positive_threshold, negative_threshold
    except Exception as e:
        logger.warning(f"Could not load ConfigManager for sentiment thresholds, using defaults: {e}")
        return 0.2, -0.2

# Cache thresholds at module level
POSITIVE_THRESHOLD, NEGATIVE_THRESHOLD = _get_sentiment_thresholds()

def send_analysis_report(recipients: List[str], db_factory: sessionmaker) -> bool:
    """
    Fetches latest and previous data from the API, compares them, generates an 
    analysis report, and sends it via email using the provided recipients and 
    DB session factory.
    
    Args:
        recipients (List[str]): List of email recipients (MUST be provided).
        db_factory (sessionmaker): SQLAlchemy session factory for MailSender.
    
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    if not recipients:
        logger.warning("No email recipients provided to send_analysis_report. Skipping email.")
        return False

    latest_data_df = pd.DataFrame() # Initialize empty DataFrame
    previous_data_df = None # Initialize as None

    try:
        # --- Fetch data from API instead of CSV ---
        logger.info(f"Fetching comparison data from API endpoint: {COMPARISON_DATA_ENDPOINT}")
        response = requests.get(COMPARISON_DATA_ENDPOINT, timeout=60)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        api_data = response.json()
        
        if not api_data.get('latest_data'):
            logger.error("API response missing 'latest_data'. Cannot generate report.")
            return False

        # Convert list of dicts to DataFrame
        latest_data_list = api_data.get('latest_data', [])
        latest_data_df = pd.DataFrame(latest_data_list)
        logger.info(f"Received {len(latest_data_df)} latest records from API.")

        # Convert timestamps if they exist (adjust column names as needed)
        for col in ['published_date', 'date', 'published_at']:
            if col in latest_data_df.columns:
                # Convert to datetime objects, coerce errors to NaT
                latest_data_df[col] = pd.to_datetime(latest_data_df[col], errors='coerce')

        if api_data.get('previous_data'):
            previous_data_list = api_data.get('previous_data', [])
            previous_data_df = pd.DataFrame(previous_data_list)
            logger.info(f"Received {len(previous_data_df)} previous records from API.")
            # Convert timestamps if they exist
            for col in ['published_date', 'date', 'published_at']:
                 if col in previous_data_df.columns:
                     previous_data_df[col] = pd.to_datetime(previous_data_df[col], errors='coerce')
        else:
            logger.info("No 'previous_data' found in API response. Skipping comparison.")
        # --- End API data fetching ---

        sentiment_change_data = {}
        if previous_data_df is not None and not previous_data_df.empty: # Check if df exists and is not empty
            logger.info("Detecting sentiment change...")
            # Pass DataFrames to detect_sentiment_change
            sentiment_change_data = detect_sentiment_change(latest_data_df, previous_data_df) 
            if sentiment_change_data.get("sentiment_changed"):
                change_direction = "Improved" if sentiment_change_data.get("sentiment_change", 0) > 0 else "Declined"
                logger.info(f"Significant sentiment change detected: {change_direction}")
            else:
                logger.info("No significant sentiment change detected.")
        else:
             logger.info("Skipping sentiment change detection due to missing or empty previous data.")
        
        logger.info("Calculating metrics for the report...")
        overall_sentiment_score = 0.0 # Use float
        positive_pct = 0.0
        negative_pct = 0.0
        neutral_pct = 0.0
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        total_mentions = len(latest_data_df)
        positive_topics = {}
        negative_topics = {}
        source_metrics = {}
        
        # Ensure 'sentiment_score' column exists and handle potential NaN/None before mean()
        if total_mentions > 0 and 'sentiment_score' in latest_data_df.columns and latest_data_df['sentiment_score'].notna().any():
            overall_sentiment_score = latest_data_df['sentiment_score'].mean(skipna=True) # Skip NaNs
            
            # Use 'sentiment_label' if available, otherwise calculate based on score
            if 'sentiment_label' in latest_data_df.columns:
                 positive_count = (latest_data_df['sentiment_label'] == 'positive').sum()
                 negative_count = (latest_data_df['sentiment_label'] == 'negative').sum()
                 # Calculate neutral based on total - positive - negative
                 # Ensure counts don't exceed total due to potential 'neutral' labels not counted above
                 neutral_count = max(0, total_mentions - positive_count - negative_count) 
            else:
                 # Calculate counts based on score, ensuring sentiment_score exists and is not null
                 if 'sentiment_score' in latest_data_df.columns:
                     valid_scores = latest_data_df['sentiment_score'].dropna() # Drop NaNs before comparison
                     positive_count = (valid_scores > POSITIVE_THRESHOLD).sum()
                     negative_count = (valid_scores < NEGATIVE_THRESHOLD).sum()
                     neutral_count = len(valid_scores) - positive_count - negative_count
                 else:
                      logger.warning("'sentiment_score' column needed for calculating sentiment counts when 'sentiment_label' is missing.")

            if total_mentions > 0: # Avoid division by zero
                positive_pct = (positive_count / total_mentions * 100)
                negative_pct = (negative_count / total_mentions * 100)
                neutral_pct = (neutral_count / total_mentions * 100)

            # Topic extraction (assuming 'keywords' column exists and contains comma-separated strings)
            keywords_column_exists = 'keywords' in latest_data_df.columns

            # Check if 'sentiment_score' exists before iterating
            if 'sentiment_score' in latest_data_df.columns:
                for _, row in latest_data_df.iterrows():
                    # Handle potential None/NaN in sentiment_score
                    sentiment = row['sentiment_score']
                    if pd.isna(sentiment): 
                        continue # Skip rows with no sentiment score

                    keywords = []
                    if keywords_column_exists:
                        keywords_val = row.get('keywords') # Use .get for safety
                        if isinstance(keywords_val, str):
                            keywords = [kw.strip() for kw in keywords_val.split(',') if kw.strip()]
                    
                    for keyword in keywords:
                        # Normalize keyword case if needed: keyword = keyword.lower()
                        if sentiment > POSITIVE_THRESHOLD:
                            positive_topics[keyword] = positive_topics.get(keyword, 0) + 1
                        elif sentiment < NEGATIVE_THRESHOLD:
                            negative_topics[keyword] = negative_topics.get(keyword, 0) + 1
            else:
                logger.warning("Skipping topic extraction as 'sentiment_score' column is missing.")

            # Source metrics extraction
            if 'source' in latest_data_df.columns and 'sentiment_score' in latest_data_df.columns:
                # Filter out rows where sentiment_score is NaN before grouping
                valid_source_data = latest_data_df.dropna(subset=['sentiment_score'])
                if not valid_source_data.empty:
                     source_groups = valid_source_data.groupby('source')['sentiment_score']
                     source_metrics = source_groups.agg(['mean', 'count']).to_dict('index')
            else:
                 logger.warning("Skipping source metrics calculation due to missing 'source' or 'sentiment_score' columns.")


        analysis_data = {
            "overall_sentiment": overall_sentiment_score,
            "positive_mentions": positive_pct,
            "neutral_mentions": neutral_pct,
            "negative_mentions": negative_pct,
            "positive_count": int(positive_count),
            "neutral_count": int(neutral_count),
            "negative_count": int(negative_count),
            "total_mentions": total_mentions,
            "positive_topics": positive_topics,
            "negative_topics": negative_topics,
            "source_metrics": source_metrics,
            "insights": [] # Initialize insights list
        }
        # Add comparison data if available
        if sentiment_change_data:
            analysis_data.update(sentiment_change_data) # Add keys like 'sentiment_changed', 'previous_overall_sentiment' etc.
            # Generate insights based on changes
            if sentiment_change_data.get("sentiment_changed"):
                 # Add overall change insight
                 change_val = sentiment_change_data.get("sentiment_change", 0)
                 change_dir = "improved" if change_val > 0 else "declined"
                 analysis_data["insights"].append(f"Overall sentiment has {change_dir} significantly (Score change: {change_val:+.3f}).")

                 # Add topic change insights
                 for topic_data in sentiment_change_data.get("new_topics", []):
                     topic = topic_data.get("topic")
                     count = topic_data.get("count")
                     analysis_data["insights"].append(f"New topic detected: '{topic}' ({count} mentions)")
                 for topic_data in sentiment_change_data.get("fading_topics", []):
                     topic = topic_data.get("topic")
                     prev_count = topic_data.get("previous_count")
                     curr_count = topic_data.get("current_count")
                     dec_text = f"reduced from {prev_count} to {curr_count}" if curr_count > 0 else f"disappeared (was {prev_count})"
                     analysis_data["insights"].append(f"Topic declining: '{topic}' {dec_text} mentions")
            else:
                 analysis_data["insights"].append("No significant change in overall sentiment detected.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from API for report: {e}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding API response JSON: {e}")
        return False
    except pd.errors.EmptyDataError: # Should not happen with API, but keep for safety
        logger.error(f"Error preparing report: Received empty data structure.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error preparing analysis data for report: {e}", exc_info=True)
        return False

    # --- Format and Send Email (existing logic) ---
    try:
        report_content = format_analysis_report(analysis_data)
    except Exception as e:
        logger.error(f"Error formatting analysis report: {e}", exc_info=True)
        return False
        
    mail_sender = MailSender() # MailSender now loads config from .env
    
    sentiment_score = analysis_data.get("overall_sentiment", 0)
    overall_sentiment_text = "Positive" if sentiment_score > POSITIVE_THRESHOLD else ("Negative" if sentiment_score < NEGATIVE_THRESHOLD else "Neutral")
    
    subject = f"Sentiment Analysis Report: {overall_sentiment_text} ({datetime.now().strftime('%Y-%m-%d')})"
    if analysis_data.get("sentiment_changed", False):
        change_direction = "Improved" if analysis_data.get("sentiment_change", 0) > 0 else "Declined"
        subject = f"ALERT: Sentiment {change_direction} - {subject}"
    
    logger.info(f"Sending analysis report email to: {', '.join(recipients)}")
    
    success = False
    try:
        # Get a DB session to pass to send_report_email
        with db_factory() as db:
            success = mail_sender.send_report_email(
                db=db, # Pass the database session
                recipients=recipients,
                subject=subject,
                report_content=report_content
            )
    except Exception as e:
        logger.error(f"Error creating DB session or sending report email: {e}", exc_info=True)
        # Ensure success remains False
    
    if success:
        logger.info(f"Analysis report email sent successfully to {', '.join(recipients)}")
    else:
        logger.error(f"Failed to send analysis report email to {', '.join(recipients)}")
        
    return success

def send_collection_notification(collection_data: Dict[str, Any], recipients: List[str], db_factory: sessionmaker) -> bool:
    """
    Send notification that data collection has completed, using DB config.
    
    Args:
        collection_data (Dict[str, Any]): Collection metrics and data.
                                         Expected keys: collection_success_rate (float), 
                                         active_sources (int), total_sources (int), 
                                         total_records (int), duration_seconds (float)
        recipients (List[str]): List of email recipients (MUST be provided).
        db_factory (sessionmaker): SQLAlchemy session factory for MailSender.
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Removed checks using .env config
    
    if not recipients:
        logger.warning("No recipients provided for collection notification.")
        return False
    
    success_rate = collection_data.get("collection_success_rate", 0) * 100
    active_sources = collection_data.get("active_sources", 0)
    total_sources = collection_data.get("total_sources", 0)
    total_records = collection_data.get("total_records", 0)
    duration = collection_data.get("duration_seconds", 0)
    
    subject = f"Data Collection Complete: {success_rate:.1f}% Success Rate"
    # Using plain text for consistency with processing notification
    body = f"""
    Data collection process finished on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    Collection Metrics:
    - Duration: {duration:.2f} seconds
    - Sources Attempted: {total_sources}
    - Successful Sources: {active_sources} ({success_rate:.1f}%)
    - Total Records Collected: {total_records}
    
    The data processing and analysis phase will begin based on its schedule.
    """
    
    mail_sender = MailSender()
    success = False
    try:
        with db_factory() as db:
            success = mail_sender.send_email(
                db=db,
                recipients=recipients,
                subject=subject,
                body=body,
                html=False # Plain text
            )
    except Exception as e:
         logger.error(f"Error creating DB session or sending collection notification: {e}", exc_info=True)

    recipient_str = ", ".join(recipients)
    if success:
        logger.info(f"Collection notification email sent successfully to {recipient_str}.")
    else:
        logger.error(f"Failed to send collection notification email to {recipient_str}.")
    
    return success

def detect_sentiment_change(current_data: pd.DataFrame, previous_data: pd.DataFrame, 
                           threshold: float = 0.1) -> Dict[str, Any]:
    """
    Detect significant changes in sentiment between current and previous data.
    Also identifies new and fading topics based on keywords.
    
    Args:
        current_data (pd.DataFrame): The current processed data (needs 'sentiment_score', optionally 'sentiment_label', 'keywords')
        previous_data (pd.DataFrame): The previous processed data (needs 'sentiment_score', optionally 'sentiment_label', 'keywords')
        threshold (float): The minimum absolute change in overall sentiment score to be considered significant.
    
    Returns:
        Dict[str, Any]: Dictionary with change information including:
            sentiment_changed (bool): True if overall sentiment change exceeds threshold.
            sentiment_change (float): The difference in mean sentiment score (current - previous).
            positive_change (float): Percentage point change in positive mentions.
            negative_change (float): Percentage point change in negative mentions.
            neutral_change (float): Percentage point change in neutral mentions.
            new_topics (List[Dict]): List of {'topic': str, 'count': int} for new topics.
            fading_topics (List[Dict]): List of {'topic': str, 'previous_count': int, 'current_count': int} for fading topics.
    """
    result = {
        "sentiment_changed": False,
        "sentiment_change": 0,
        "positive_change": 0,
        "negative_change": 0,
        "neutral_change": 0,
        "new_topics": [],
        "fading_topics": []
    }
    
    if 'sentiment_score' not in current_data.columns or 'sentiment_score' not in previous_data.columns:
        logger.warning("Cannot detect sentiment change: 'sentiment_score' column missing in one or both dataframes.")
        return result
    if current_data.empty or previous_data.empty:
         logger.warning("Cannot detect sentiment change: One or both dataframes are empty.")
         return result

    current_sentiment = np.mean(current_data['sentiment_score'])
    previous_sentiment = np.mean(previous_data['sentiment_score'])
    
    sentiment_change = current_sentiment - previous_sentiment
    result["sentiment_change"] = sentiment_change
    
    def get_sentiment_percentages(df):
        total = len(df)
        if total == 0:
            return {"positive": 0, "negative": 0, "neutral": 0}
        
        if 'sentiment_label' in df.columns:
            positive = len(df[df['sentiment_label'] == 'positive']) / total * 100
            negative = len(df[df['sentiment_label'] == 'negative']) / total * 100
            neutral = 100 - positive - negative
        elif 'sentiment_score' in df.columns:
            positive = len(df[df['sentiment_score'] > POSITIVE_THRESHOLD]) / total * 100
            negative = len(df[df['sentiment_score'] < NEGATIVE_THRESHOLD]) / total * 100
            neutral = 100 - positive - negative
        else:
            return {"positive": 0, "negative": 0, "neutral": 0}
            
        return {"positive": positive, "negative": negative, "neutral": neutral}
    
    current_percentages = get_sentiment_percentages(current_data)
    previous_percentages = get_sentiment_percentages(previous_data)
    
    result["positive_change"] = current_percentages["positive"] - previous_percentages["positive"]
    result["negative_change"] = current_percentages["negative"] - previous_percentages["negative"]
    result["neutral_change"] = current_percentages["neutral"] - previous_percentages["neutral"]
    
    result["sentiment_changed"] = abs(sentiment_change) >= threshold
    
    if 'keywords' in current_data.columns and 'keywords' in previous_data.columns:
        try:
            def get_keyword_counts(series):
                keyword_counts = {}
                for keywords_str in series.dropna().astype(str):
                     if keywords_str:
                          for keyword in keywords_str.split(','):
                              keyword = keyword.strip()
                              if keyword:
                                  keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
                return keyword_counts

            current_keywords = get_keyword_counts(current_data['keywords'])
            previous_keywords = get_keyword_counts(previous_data['keywords'])
            
            for keyword, count in current_keywords.items():
                if keyword not in previous_keywords and count >= 3: 
                    result["new_topics"].append({"topic": keyword, "count": count})
            
            for keyword, prev_count in previous_keywords.items():
                curr_count = current_keywords.get(keyword, 0)
                if prev_count >= 3 and (curr_count == 0 or curr_count < prev_count * 0.5):
                    result["fading_topics"].append({
                        "topic": keyword, 
                        "previous_count": prev_count,
                        "current_count": curr_count
                    })
            result["new_topics"].sort(key=lambda x: x['count'], reverse=True)
            result["fading_topics"].sort(key=lambda x: x['previous_count'], reverse=True)

        except Exception as topic_err:
            logger.error(f"Error detecting topic changes: {topic_err}", exc_info=True)
            result["new_topics"] = []
            result["fading_topics"] = []
            
    else:
         logger.warning("Cannot detect topic changes: 'keywords' column missing in one or both dataframes.")

    return result 

def send_processing_notification(processing_data: Dict[str, Any], recipients: List[str], db_factory: sessionmaker) -> bool:
    """
    Send a notification about the completion (or failure) of a data processing task.
    
    Args:
        processing_data (Dict[str, Any]): Information about the processing task.
                                         Expected keys: status ('success'/'failure'), 
                                         processed_count (int), raw_file_count (int), 
                                         timestamp (str), error (str, optional)
        recipients (List[str]): List of email recipients (MUST be provided).
        db_factory (sessionmaker): SQLAlchemy session factory for MailSender.
        
    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    if not recipients:
        logger.warning("No recipients provided for processing notification.")
        return False

    status = processing_data.get("status", "unknown")
    timestamp_str = processing_data.get("timestamp", datetime.now().isoformat())
    processed_count = processing_data.get("processed_count", 0)
    raw_count = processing_data.get("raw_file_count", "N/A")
    error_msg = processing_data.get("error", "None")

    subject = f"Data Processing {status.capitalize()}"
    body = f"""
    Data processing task finished at {timestamp_str}.
    
    Status: {status.upper()}
    Raw files processed: {raw_count}
    Records processed: {processed_count}
    """
    if status == 'failure':
        body += f"\nError Details: {error_msg}"
        subject = f"ALERT: Data Processing Failed"

    mail_sender = MailSender()
    success = False
    try:
        with db_factory() as db:
            # Use the basic send_email method
            success = mail_sender.send_email(
                db=db,
                recipients=recipients,
                subject=subject,
                body=body,
                html=False # Plain text for this notification
            )
    except Exception as e:
        logger.error(f"Error creating DB session or sending processing notification: {e}", exc_info=True)

    if success:
        logger.info(f"Processing notification sent successfully to {', '.join(recipients)}")
    else:
        logger.error(f"Failed to send processing notification to {', '.join(recipients)}")
        
    return success

def format_analysis_report(analysis_data: Dict[str, Any]) -> str:
    """
    Format the analysis data into an HTML report.
    
    Args:
        analysis_data (Dict[str, Any]): The analysis data
    
    Returns:
        str: Formatted HTML report content
    """
    sentiment_score = analysis_data.get("overall_sentiment", 0)
    prev_sentiment_score = analysis_data.get("previous_overall_sentiment")
    sentiment_text = "Positive" if sentiment_score > POSITIVE_THRESHOLD else ("Negative" if sentiment_score < NEGATIVE_THRESHOLD else "Neutral")
    sentiment_color = "#28a745" if sentiment_score > POSITIVE_THRESHOLD else ("#dc3545" if sentiment_score < NEGATIVE_THRESHOLD else "#6c757d")
    
    sentiment_percentage = round((sentiment_score + 1) * 50, 1)
    
    total_mentions = analysis_data.get("total_mentions", 0)
    pos_count = analysis_data.get("positive_count", 0)
    neg_count = analysis_data.get("negative_count", 0)
    neu_count = analysis_data.get("neutral_count", 0)
    pos_pct = analysis_data.get("positive_mentions", 0)
    neg_pct = analysis_data.get("negative_mentions", 0)
    neu_pct = analysis_data.get("neutral_mentions", 0)
    
    prev_pos_pct = analysis_data.get("previous_positive_mentions")
    prev_neg_pct = analysis_data.get("previous_negative_mentions")
    prev_neu_pct = analysis_data.get("previous_neutral_mentions")
    
    insights = analysis_data.get("insights", [])
    insights_html = "<ul>"
    if insights:
        for insight in insights[:15]:
            insights_html += f"<li>{insight}</li>"
    else:
        insights_html += "<li>No specific insights generated.</li>"
    insights_html += "</ul>"
    
    positive_topics = analysis_data.get("positive_topics", {})
    negative_topics = analysis_data.get("negative_topics", {})
    
    positive_html = "<p>No prominent positive themes detected.</p>"
    if positive_topics:
        positive_html = '<table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;"><tr><th>Theme</th><th>Mentions</th></tr>'
        for topic, count in sorted(positive_topics.items(), key=lambda x: x[1], reverse=True)[:10]:
            positive_html += f'<tr><td>{topic}</td><td>{count}</td></tr>'
        positive_html += '</table>'

    negative_html = "<p>No prominent negative themes detected.</p>"
    if negative_topics:
        negative_html = '<table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;"><tr><th>Theme</th><th>Mentions</th></tr>'
        for topic, count in sorted(negative_topics.items(), key=lambda x: x[1], reverse=True)[:10]:
            negative_html += f'<tr><td>{topic}</td><td>{count}</td></tr>'
        negative_html += '</table>'

    sentiment_change_html = ""
    if analysis_data.get("sentiment_changed", False):
        change_value = analysis_data.get("sentiment_change", 0)
        change_direction = "improved" if change_value > 0 else "declined"
        change_color = "#28a745" if change_value > 0 else "#dc3545"
        
        pos_change = analysis_data.get("positive_change") 
        neg_change = analysis_data.get("negative_change")
        
        def format_pct_change(current, previous):
            if previous is None or current is None:
                return "N/A"
            change = current - previous
            sign = '+' if change > 0 else ''
            return f"{current:.1f}% (from {previous:.1f}%, Change: {sign}{change:.1f}pp)"
            
        overall_change_display = f"{sentiment_score:.3f} (from {prev_sentiment_score:.3f}, Change: {'+' if change_value > 0 else ''}{change_value:.3f})" if prev_sentiment_score is not None else f"{sentiment_score:.3f} (Previous N/A)"
        pos_change_display = format_pct_change(pos_pct, prev_pos_pct)
        neg_change_display = format_pct_change(neg_pct, prev_neg_pct)
        neu_change_display = format_pct_change(neu_pct, prev_neu_pct)

        sentiment_change_html = f"""
        <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-left: 5px solid {change_color};">
            <h3 style="color: {change_color};">Sentiment Change Detected!</h3>
            <p>The overall sentiment has <strong>{change_direction}</strong> since the last analysis.</p>
            <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                <tr><th>Metric</th><th>Current (vs Previous)</th></tr>
                <tr><td>Overall Score</td><td><strong>{overall_change_display}</strong></td></tr>
                <tr><td>Positive Mentions</td><td><strong>{pos_change_display}</strong></td></tr>
                <tr><td>Negative Mentions</td><td><strong>{neg_change_display}</strong></td></tr>
                <tr><td>Neutral Mentions</td><td><strong>{neu_change_display}</strong></td></tr>
            </table>
        </div>
        """
    
    source_metrics = analysis_data.get("source_metrics", {})
    source_html = "<p>No source-specific data available.</p>"
    if source_metrics:
        source_html = '<table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;"><tr><th>Source</th><th>Avg. Score</th><th>Mentions</th></tr>'
        for source, metrics in sorted(source_metrics.items()):
            source_html += f'<tr><td>{source}</td><td>{metrics.get("mean", 0):.3f}</td><td>{metrics.get("count", 0)}</td></tr>'
        source_html += '</table>'
        
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Sentiment Analysis Report</title>
        <style>
            body {{ font-family: sans-serif; line-height: 1.4; margin: 20px; color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            h2, h3 {{ color: #0056b3; border-bottom: 1px solid #eee; padding-bottom: 5px;}}
        </style>
    </head>
    <body>
        <h2>Sentiment Analysis Report</h2>
        <p>Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h3>Summary</h3>
        <table border="1" cellpadding="5">
            <tr><th>Metric</th><th>Current</th><th>Previous</th><th>Change</th></tr>
            <tr>
                <td>Overall Sentiment Score</td>
                <td>{sentiment_score:.3f} ({sentiment_text})</td>
                <td>{f'{prev_sentiment_score:.3f}' if prev_sentiment_score is not None else 'N/A'}</td>
                <td>{ f'{change_value:+.3f}' if prev_sentiment_score is not None else 'N/A' }</td>
            </tr>
            <tr>
                <td>Total Mentions</td>
                <td>{total_mentions}</td>
                <td>N/A</td>
                <td>N/A</td>
            </tr>
             <tr>
                <td>Positive Mentions</td>
                <td>{pos_count} ({pos_pct:.1f}%)</td>
                <td>{f'{prev_pos_pct:.1f}%' if prev_pos_pct is not None else 'N/A'}</td>
                <td>{ f'{pos_change:+.1f}pp' if prev_pos_pct is not None else 'N/A' }</td>
             </tr>
             <tr>
                <td>Negative Mentions</td>
                <td>{neg_count} ({neg_pct:.1f}%)</td>
                <td>{f'{prev_neg_pct:.1f}%' if prev_neg_pct is not None else 'N/A'}</td>
                <td>{ f'{neg_change:+.1f}pp' if prev_neg_pct is not None else 'N/A' }</td>
             </tr>
             <tr>
                <td>Neutral Mentions</td>
                <td>{neu_count} ({neu_pct:.1f}%)</td>
                <td>{f'{prev_neu_pct:.1f}%' if prev_neu_pct is not None else 'N/A'}</td>
                <td>{ f'{neu_change:+.1f}pp' if prev_neu_pct is not None else 'N/A' }</td>
             </tr>
        </table>
        
        {sentiment_change_html}
        
        <h3>Sentiment Distribution</h3>
        <p>Current Score: <strong>{sentiment_score:.3f}</strong> (<span class="{sentiment_text.lower()}">{sentiment_text}</span>). Range: -1 (Negative) to +1 (Positive)</p>
        <ul>
            <li>Positive: {pos_count} ({pos_pct:.1f}%)</li>
            <li>Negative: {neg_count} ({neg_pct:.1f}%)</li>
            <li>Neutral: {neu_count} ({neu_pct:.1f}%)</li>
        </ul>
        
        <h3>Key Insights & Topic Changes:</h3>
        {insights_html}
        
        <h3>Top 10 Positive Themes:</h3>
        {positive_html}
        
        <h3>Top 10 Negative Themes:</h3>
        {negative_html}

        <h3>Sentiment by Source</h3>
        {source_html}

        <hr style="margin-top: 30px;">
        <p><small>This report was automatically generated by the Sentiment Analysis System.</small></p>
    </body>
    </html>
    """
    
    return html_content 
