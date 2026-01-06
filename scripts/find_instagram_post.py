#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to search for an Instagram post by username, handle, or content text.
"""

import sys
import io
from pathlib import Path
from sqlalchemy import or_, func

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import SentimentData

def search_instagram_post(search_term=None, username=None, user_handle=None, content_text=None):
    """Search for Instagram posts by various criteria."""
    db = SessionLocal()
    try:
        # Build search conditions
        conditions = [SentimentData.platform == 'Instagram']
        
        if username:
            conditions.append(SentimentData.user_name.ilike(f'%{username}%'))
        
        if user_handle:
            conditions.append(SentimentData.user_handle.ilike(f'%{user_handle}%'))
        
        if content_text:
            conditions.append(or_(
                SentimentData.text.ilike(f'%{content_text}%'),
                SentimentData.content.ilike(f'%{content_text}%'),
                SentimentData.title.ilike(f'%{content_text}%'),
                SentimentData.description.ilike(f'%{content_text}%')
            ))
        
        if search_term:
            # General search across multiple fields
            conditions.append(or_(
                SentimentData.user_name.ilike(f'%{search_term}%'),
                SentimentData.user_handle.ilike(f'%{search_term}%'),
                SentimentData.text.ilike(f'%{search_term}%'),
                SentimentData.content.ilike(f'%{search_term}%'),
                SentimentData.title.ilike(f'%{search_term}%'),
                SentimentData.description.ilike(f'%{search_term}%')
            ))
        
        # Query the database
        records = db.query(SentimentData).filter(
            *conditions
        ).order_by(SentimentData.created_at.desc()).limit(50).all()
        
        if not records:
            print(f"No Instagram records found matching the search criteria.")
            return
        
        print(f"Found {len(records)} Instagram record(s):\n")
        print("=" * 100)
        
        for i, record in enumerate(records, 1):
            print(f"\nRecord #{i}:")
            print(f"  Entry ID: {record.entry_id}")
            print(f"  Post ID: {record.post_id}")
            print(f"  Platform: {record.platform}")
            print(f"  User Name: {record.user_name or 'N/A'}")
            print(f"  User Handle: {record.user_handle or 'N/A'}")
            print(f"  URL: {record.url or 'N/A'}")
            print(f"  Published Date: {record.published_date or 'N/A'}")
            print(f"  Published At: {record.published_at or 'N/A'}")
            print(f"  Date: {record.date or 'N/A'}")
            print(f"  Created At: {record.created_at or 'N/A'}")
            print(f"  Run Timestamp: {record.run_timestamp or 'N/A'}")
            
            print(f"\n  Content:")
            if record.title:
                print(f"    Title: {record.title[:200]}")
            if record.text:
                print(f"    Text: {record.text[:500]}")
            if record.content:
                print(f"    Content: {record.content[:500]}")
            if record.description:
                print(f"    Description: {record.description[:500]}")
            
            print(f"\n  Metadata:")
            print(f"    Sentiment Label: {record.sentiment_label or 'N/A'}")
            print(f"    Sentiment Score: {record.sentiment_score or 'N/A'}")
            print(f"    Location Label: {record.location_label or 'N/A'}")
            print(f"    Issue Label: {record.issue_label or 'N/A'}")
            print(f"    Country: {record.country or 'N/A'}")
            print(f"    Language: {record.language or 'N/A'}")
            
            print(f"\n  Engagement:")
            print(f"    Likes: {record.likes or 'N/A'}")
            print(f"    Comments: {record.comments or 'N/A'}")
            print(f"    Retweets: {record.retweets or 'N/A'}")
            print(f"    Direct Reach: {record.direct_reach or 'N/A'}")
            
            print("\n" + "-" * 100)
            
    except Exception as e:
        print(f"Error searching for Instagram post: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python find_instagram_post.py <search_term>")
        print("  python find_instagram_post.py --username <username>")
        print("  python find_instagram_post.py --handle <user_handle>")
        print("  python find_instagram_post.py --content <text>")
        print("\nExample:")
        print("  python find_instagram_post.py jess_shine_on")
        print("  python find_instagram_post.py --username jess")
        print("  python find_instagram_post.py --content 'buy me this'")
        sys.exit(1)
    
    search_term = None
    username = None
    user_handle = None
    content_text = None
    
    if sys.argv[1] == "--username" and len(sys.argv) > 2:
        username = sys.argv[2]
    elif sys.argv[1] == "--handle" and len(sys.argv) > 2:
        user_handle = sys.argv[2]
    elif sys.argv[1] == "--content" and len(sys.argv) > 2:
        content_text = sys.argv[2]
    else:
        search_term = sys.argv[1]
    
    search_instagram_post(search_term=search_term, username=username, user_handle=user_handle, content_text=content_text)

