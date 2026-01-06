"""
Common utility functions used across the codebase.

This module provides shared utility functions to avoid code duplication
and ensure consistent behavior across different modules.
"""

from datetime import datetime
from typing import Optional, Any
import re
import logging

logger = logging.getLogger(__name__)

__all__ = ['parse_datetime', 'safe_int', 'safe_float']


def parse_datetime(value: Optional[Any]) -> Optional[datetime]:
    """
    Parse a date string or datetime object to datetime.
    
    This function consolidates date parsing logic from multiple implementations
    to provide a single, robust date parser that handles various formats used
    throughout the codebase.
    
    Supported formats:
    - Twitter format: 'Fri Nov 24 17:49:36 +0000 2023'
    - ISO format with timezone: '2025-03-21T12:19:52.000Z'
    - Standard datetime format: '2025-03-14 16:17:49'
    - 5-digit timezone format: '2025-03-31 10:57:46 +00000'
    - Custom format: '04:19 09 Mar 2025'
    - Custom format with timezone: '12/04/2024, 08:00 AM, +0000 UTC'
    - datetime objects (returned as-is, with timezone removed if present)
    
    Args:
        value: Date string, datetime object, or None/NaN value to parse
        
    Returns:
        datetime object (timezone-naive), or None if value cannot be parsed
        
    Examples:
        >>> parse_datetime('Fri Nov 24 17:49:36 +0000 2023')
        datetime.datetime(2023, 11, 24, 17, 49, 36)
        
        >>> parse_datetime('2025-03-21T12:19:52.000Z')
        datetime.datetime(2025, 3, 21, 12, 19, 52)
        
        >>> parse_datetime(None)
        None
        
        >>> parse_datetime('invalid')
        None
    """
    # Handle None, NaN, and empty values
    if value is None:
        return None
    
    # Handle pandas NaN values
    try:
        import pandas as pd
        if pd.isna(value):
            return None
    except ImportError:
        pass  # pandas not available, skip NaN check
    
    # Handle datetime objects - return as-is but make timezone-naive
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.replace(tzinfo=None)
        return value
    
    # Handle non-string types
    if not isinstance(value, str):
        logger.debug(f"Unexpected type for date parsing: {type(value)}. Value: {value}")
        return None
    
    # Convert to string and strip whitespace
    date_str = str(value).strip()
    
    # Skip invalid or empty date strings
    if not date_str or date_str.lower() in ['none', 'nan', '', 'unknown']:
        return None
    
    try:
        # Try to parse the date string in various formats
        
        # 1. Twitter date format (e.g., Fri Nov 24 17:49:36 +0000 2023)
        twitter_pattern = r'[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[+]\d{4}\s+\d{4}'
        if re.match(twitter_pattern, date_str):
            return datetime.strptime(date_str, '%a %b %d %H:%M:%S +0000 %Y')
        
        # 2. Standard datetime format with 5-digit timezone (e.g., 2025-03-31 10:57:46 +00000)
        if re.match(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+[+]\d{5}', date_str):
            # Remove timezone info since we only need the date
            base_date = date_str.split('+')[0].strip()
            return datetime.strptime(base_date, '%Y-%m-%d %H:%M:%S')
        
        # 3. ISO format with timezone (e.g., 2025-03-21T12:19:52.000Z)
        if 'T' in date_str and ('Z' in date_str or '+' in date_str or '-' in date_str[-6:]):
            # Replace Z with +00:00 for ISO parsing
            iso_str = date_str.replace('Z', '+00:00')
            parsed_dt = datetime.fromisoformat(iso_str)
            # Make timezone-naive if timezone info exists
            if parsed_dt.tzinfo:
                return parsed_dt.replace(tzinfo=None)
            return parsed_dt
        
        # 4. Custom format (e.g., 04:19 09 Mar 2025)
        if re.match(r'\d{2}:\d{2}\s+\d{2}\s+[A-Za-z]{3}\s+\d{4}', date_str):
            return datetime.strptime(date_str, '%H:%M %d %b %Y')
        
        # 5. Custom format with timezone (e.g., 12/04/2024, 08:00 AM, +0000 UTC)
        if re.match(r'\d{2}/\d{2}/\d{4},\s+\d{1,2}:\d{2}\s+(AM|PM),\s+\+0000\s+UTC', date_str):
            # Extract the main part and parse
            date_part = date_str.split(', +')[0]
            # Handle day-first format (DD/MM/YYYY)
            parsed_dt = datetime.strptime(date_part, '%d/%m/%Y, %I:%M %p')
            return parsed_dt
        
        # 6. Standard datetime format (e.g., 2025-03-14 16:17:49)
        if re.match(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', date_str):
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        
        # 7. Try ISO format as fallback (handles formats like 2025-03-21T12:19:52 without timezone)
        try:
            parsed_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if parsed_dt.tzinfo:
                return parsed_dt.replace(tzinfo=None)
            return parsed_dt
        except ValueError:
            pass
        
        # 8. Final fallback: try dateutil.parser if available (for unusual formats)
        try:
            from dateutil import parser
            parsed_dt = parser.parse(date_str)
            if parsed_dt.tzinfo:
                return parsed_dt.replace(tzinfo=None)
            return parsed_dt
        except (ImportError, ValueError, TypeError):
            pass
        
    except (ValueError, AttributeError, TypeError) as e:
        logger.debug(f"Error parsing date string '{date_str}': {e}")
        return None
    
    # If we get here, we couldn't parse the date
    logger.debug(f"Could not parse date string: '{date_str}' - format not recognized")
    return None


def safe_float(value: Any) -> Optional[float]:
    """
    Safely convert a value to float, returning None if conversion fails.
    
    This function handles various input types (None, int, float, str) and safely
    converts them to float, returning None for invalid or empty values.
    
    Args:
        value: Value to convert to float. Can be None, int, float, or string.
        
    Returns:
        float value if conversion succeeds, None otherwise.
        
    Examples:
        >>> safe_float(42)
        42.0
        
        >>> safe_float("3.14")
        3.14
        
        >>> safe_float("none")
        None
        
        >>> safe_float(None)
        None
        
        >>> safe_float("invalid")
        None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ('none', 'null', 'nan', ''):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


def safe_int(value: Any) -> Optional[int]:
    """
    Safely convert a value to int, returning None if conversion fails.
    
    This function handles various input types (None, int, float, str) and safely
    converts them to int, returning None for invalid or empty values.
    String values like "1.0" are handled by converting via float first.
    
    Args:
        value: Value to convert to int. Can be None, int, float, or string.
        
    Returns:
        int value if conversion succeeds, None otherwise.
        
    Examples:
        >>> safe_int(42)
        42
        
        >>> safe_int("42")
        42
        
        >>> safe_int("1.0")
        1
        
        >>> safe_int("none")
        None
        
        >>> safe_int(None)
        None
        
        >>> safe_int("invalid")
        None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ('none', 'null', 'nan', ''):
            return None
        try:
            return int(float(value))  # Convert via float to handle "1.0" strings
        except (ValueError, TypeError):
            return None
    return None

