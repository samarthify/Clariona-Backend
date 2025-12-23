"""
Simple helper for collectors to get target configuration from database.
This replaces the complex query_variations.py file.
"""

import os
from typing import List, Optional, Tuple
from src.api.database import get_db
from src.api.models import TargetIndividualConfiguration


def get_target_config(user_id: str) -> Optional[Tuple[str, List[str]]]:
    """
    Get target configuration for a specific user from database.
    
    Returns:
        Tuple of (target_name, query_variations) or None if not found
    """
    try:
        db = next(get_db())
        target_config = db.query(TargetIndividualConfiguration)\
                         .filter(TargetIndividualConfiguration.user_id == user_id)\
                         .order_by(TargetIndividualConfiguration.created_at.desc())\
                         .first()
        
        if target_config:
            return target_config.individual_name, target_config.query_variations
        return None
        
    except Exception as e:
        print(f"Error getting target config: {e}")
        return None
    finally:
        if 'db' in locals():
            db.close()


def get_target_and_queries(user_id: str) -> List[str]:
    """
    Get target name + query variations as a single list.
    
    Returns:
        List starting with target name, followed by query variations
    """
    config = get_target_config(user_id)
    if config:
        target_name, query_variations = config
        return [target_name] + (query_variations or [])
    return []


