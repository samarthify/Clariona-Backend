#!/usr/bin/env python3
"""
Example script demonstrating how to use the notification system.
"""

import os
import sys
import logging
from pathlib import Path
import json

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.notification_service import send_analysis_report
from src.utils.mail_config import get_email_recipients, is_email_notification_enabled

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    """Example usage of notification system."""
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
        custom_recipient = input("Enter a recipient email address for testing: ")
        if custom_recipient:
            recipients = [custom_recipient]
        else:
            return
    
    # Create sample analysis data
    analysis_data = {
        "overall_sentiment": 0.65,
        "positive_mentions": 65.0,
        "neutral_mentions": 25.0,
        "negative_mentions": 10.0,
        "total_mentions": 200,
        "positive_topics": {
            "charity work": 38,
            "economic policies": 27,
            "international relations": 19,
            "public speaking": 12,
            "community engagement": 8
        },
        "negative_topics": {
            "controversial statements": 7,
            "policy criticism": 5,
            "past actions": 3,
            "social media presence": 2,
            "public appearance": 1
        },
        "insights": [
            "Sentiment has improved by 15% compared to last week, primarily due to charity initiatives",
            "Economic policy mentions increased significantly following the recent press conference",
            "International relations topics are showing a positive trend in media coverage",
            "The controversial statements from last month are receiving less attention",
            "Social media engagement has increased by 22% with predominantly positive sentiment"
        ]
    }
    
    # Send the report
    logger.info("Sending sample analysis report...")
    success = send_analysis_report(analysis_data, recipients)
    
    if success:
        logger.info(f"Sample report sent successfully to {', '.join(recipients)}!")
    else:
        logger.error("Failed to send sample report.")

if __name__ == "__main__":
    main() 