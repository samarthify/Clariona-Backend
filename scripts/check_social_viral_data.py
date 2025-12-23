#!/usr/bin/env python3
"""
Script to analyze social viral data in the database
Run with: python scripts/check_social_viral_data.py
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, func, or_, and_
from sqlalchemy.orm import sessionmaker
from src.api.models import SentimentData

# Load environment variables
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    print("   Please check your .env file")
    sys.exit(1)

print(f"🔍 Connecting to database...")
print(f"   URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}\n")

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
except Exception as e:
    print(f"❌ Error connecting to database: {e}")
    sys.exit(1)

try:
    print("🔍 Analyzing Social Viral Data in Database...\n")

    # First, check what platform values actually exist
    print("📱 Checking platform values in database...")
    platform_counts = db.query(
        SentimentData.platform,
        func.count(SentimentData.entry_id).label('count')
    ).group_by(SentimentData.platform).all()
    
    print(f"   Found {len(platform_counts)} unique platform values:\n")
    for platform, count in sorted(platform_counts, key=lambda x: x[1], reverse=True)[:20]:
        print(f"   '{platform}': {count:,} entries")
    print()

    # Get sample of negative sentiment posts from social platforms
    # Try different platform name variations
    social_platforms_lower = ['x', 'twitter', 'facebook', 'instagram', 'tiktok', 'linkedin', 'reddit']
    
    # Query with case-insensitive matching
    sample_query = db.query(SentimentData).filter(
        or_(
            SentimentData.sentiment_label.in_(['negative', 'Negative']),
            SentimentData.sentiment_label.ilike('negative%')
        ),
        SentimentData.sentiment_score < -0.7
    )
    
    # Try to match platforms (case-insensitive)
    platform_filter = or_(*[
        func.lower(SentimentData.platform).like(f'%{p}%') 
        for p in social_platforms_lower
    ])
    sample_query = sample_query.filter(platform_filter)
    
    total_count = sample_query.count()
    print(f"📊 Found {total_count:,} negative sentiment posts from social platforms\n")
    
    if total_count == 0:
        print("⚠️  No posts found with current filters. Checking all negative sentiment posts...\n")
        # Check all negative sentiment posts regardless of platform
        all_negative = db.query(SentimentData).filter(
            or_(
                SentimentData.sentiment_label.in_(['negative', 'Negative']),
                SentimentData.sentiment_label.ilike('negative%')
            ),
            SentimentData.sentiment_score < -0.7
        ).limit(100).all()
        
        print(f"   Found {len(all_negative)} negative sentiment posts (any platform):\n")
        platform_dist = {}
        for post in all_negative:
            platform = post.platform or 'NULL'
            platform_dist[platform] = platform_dist.get(platform, 0) + 1
        
        for platform, count in sorted(platform_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"   '{platform}': {count} posts")
        print()
        
        # Use all negative posts for analysis
        sample_posts = all_negative[:100]
    else:
        sample_posts = sample_query.order_by(SentimentData.created_at.desc()).limit(100).all()

    if not sample_posts:
        print("❌ No posts found to analyze")
        db.close()
        sys.exit(0)

    # Group by platform
    by_platform = {}
    for post in sample_posts:
        platform = (post.platform or 'unknown').lower()
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(post)

    print('📱 Distribution by Platform:')
    for platform, posts in sorted(by_platform.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {platform}: {len(posts)} posts")
    print()

    # Analyze engagement metrics
    print('📈 Engagement Statistics:')
    
    likes_values = [p.likes for p in sample_posts if p.likes is not None and p.likes > 0]
    retweets_values = [p.retweets for p in sample_posts if p.retweets is not None and p.retweets > 0]
    comments_values = [p.comments for p in sample_posts if p.comments is not None and p.comments > 0]
    cumulative_reach_values = [p.cumulative_reach for p in sample_posts if p.cumulative_reach is not None and p.cumulative_reach > 0]
    direct_reach_values = [p.direct_reach for p in sample_posts if p.direct_reach is not None and p.direct_reach > 0]

    def print_stats(name, values):
        if values:
            print(f"  {name}:")
            print(f"    Min: {min(values):,}")
            print(f"    Max: {max(values):,}")
            print(f"    Avg: {int(sum(values) / len(values)):,}")
            print(f"    Posts with value: {len(values)}/{len(sample_posts)}")
        else:
            print(f"  {name}: No data available")

    print_stats("likes", likes_values)
    print_stats("retweets", retweets_values)
    print_stats("comments", comments_values)
    print_stats("cumulativeReach", cumulative_reach_values)
    print_stats("directReach", direct_reach_values)
    print()

    # Show sample entries
    print('📋 Sample Entries (Top 10 by engagement):')
    
    def get_engagement(post):
        return (post.likes or 0) + (post.retweets or 0) + (post.comments or 0)
    
    sorted_posts = sorted(sample_posts, key=get_engagement, reverse=True)
    
    for idx, post in enumerate(sorted_posts[:10], 1):
        engagement = get_engagement(post)
        print(f"\n  {idx}. Entry ID: {post.entry_id}")
        print(f"     Platform: {post.platform or 'N/A'}")
        sentiment_str = f"{post.sentiment_score:.3f}" if post.sentiment_score is not None else 'N/A'
        print(f"     Sentiment Score: {sentiment_str}")
        print(f"     Engagement: {engagement:,} (Likes: {post.likes or 0}, RTs: {post.retweets or 0}, Comments: {post.comments or 0})")
        print(f"     Reach: Cumulative={post.cumulative_reach or 0:,}, Direct={post.direct_reach or 0:,}")
        print(f"     Issue: {post.issue_label or post.issue_slug or 'N/A'}")
        print(f"     Location: {post.user_location or 'N/A'}")
        print(f"     Date: {post.created_at.strftime('%Y-%m-%d') if post.created_at else 'N/A'}")

    # Check platform value variations
    print('\n🔤 Platform Value Variations in Sample:')
    platform_variations = set()
    for post in sample_posts:
        if post.platform:
            platform_variations.add(post.platform.lower())
    print(f"  Found platform values: {', '.join(sorted(platform_variations))}")

    # Check what would qualify as "social_viral" with current thresholds
    print('\n🎯 Current Social Viral Thresholds:')
    print('  Engagement > 50 OR Reach > 5000')
    
    viral_count = sum(1 for post in sample_posts 
                     if get_engagement(post) > 50 or (post.cumulative_reach or 0) > 5000)
    
    print(f"  Posts that would qualify: {viral_count}/{len(sample_posts)} ({viral_count*100//len(sample_posts) if sample_posts else 0}%)")

    # Suggest thresholds based on data
    engagement_values = sorted([get_engagement(p) for p in sample_posts if get_engagement(p) > 0], reverse=True)
    
    if engagement_values:
        p50_idx = len(engagement_values) // 2
        p75_idx = len(engagement_values) // 4
        p90_idx = len(engagement_values) // 10
        
        p50 = engagement_values[p50_idx] if p50_idx < len(engagement_values) else 0
        p75 = engagement_values[p75_idx] if p75_idx < len(engagement_values) else 0
        p90 = engagement_values[p90_idx] if p90_idx < len(engagement_values) else 0
        
        print('\n💡 Suggested Thresholds (based on percentiles):')
        print(f"  50th percentile: {p50:,} (median)")
        print(f"  75th percentile: {p75:,} (top 25%)")
        print(f"  90th percentile: {p90:,} (top 10%)")

    db.close()
    print('\n✅ Analysis complete!')
    
except Exception as e:
    print(f'❌ Error analyzing data: {e}')
    import traceback
    traceback.print_exc()
    db.close()
    sys.exit(1)

