#!/usr/bin/env python3
"""
Configuration for email notifications.
"""

import os
import sys
from typing import List, Union
from pathlib import Path
from dotenv import load_dotenv

# Determine project root directory and config path
current_file = Path(__file__)
project_root = current_file.parent.parent.parent  # Go up from src/utils to project root
config_path = project_root / "config" / ".env"

# Load environment variables from .env file
load_dotenv(config_path)

# Removed EMAIL_PROVIDER setting as we're using direct SMTP config now
# EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "gmail").lower()

# Email notification settings
DEFAULT_EMAIL_RECIPIENTS = os.getenv("EMAIL_RECIPIENTS", "").split(",")
EMAIL_NOTIFICATION_ENABLED = os.getenv("EMAIL_NOTIFICATION_ENABLED", "false").lower() == "true"
NOTIFY_ON_COLLECTION = os.getenv("NOTIFY_ON_COLLECTION", "false").lower() == "true"
NOTIFY_ON_PROCESSING = os.getenv("NOTIFY_ON_PROCESSING", "false").lower() == "true"
NOTIFY_ON_ANALYSIS = os.getenv("NOTIFY_ON_ANALYSIS", "true").lower() == "true"

def get_email_recipients() -> List[str]:
    """
    Get the list of email recipients from environment variables.
    
    Returns:
        List[str]: List of email addresses
    """
    recipients = DEFAULT_EMAIL_RECIPIENTS
    # Filter out empty strings
    return [email.strip() for email in recipients if email.strip()]

def is_email_notification_enabled() -> bool:
    """
    Check if email notifications are enabled.
    
    Returns:
        bool: True if enabled, False otherwise
    """
    return EMAIL_NOTIFICATION_ENABLED

# Removed get_email_provider function
# def get_email_provider() -> str:
#     """
#     Get the configured email provider.
#     
#     Returns:
#         str: Email provider name (e.g., 'protonmail', 'gmail')
#     """
#     return EMAIL_PROVIDER 