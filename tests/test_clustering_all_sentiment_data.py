"""
Test script for clustering ALL sentiment_data records (not just those with topics).

This script tests different similarity thresholds on all records in sentiment_data table.
"""

import sys
from pathlib import Path
import time
from datetime import datetime
from typing import Dict, List, Any
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.processing.issue_clustering_service import IssueClusteringService
from src.api.database import SessionLocal
from src.api.models import SentimentData, SentimentEmbedding
from sqlalchemy import func
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_all_sentiment_data_with_embeddings(session, limit: int = None) -> List[Dict[str, Any]]:
    """
    Get all sentiment_data records that have embeddings.
    
    Args:
        session: Database session
        limit: Optional limit on number of records
        
    Returns:
        List of mention dictionaries with embeddings
    """
    # Query sentiment_data with embeddings
    query = session.query(SentimentData, SentimentEmbedding).join(
        SentimentEmbedding, SentimentData.entry_id == SentimentEmbedding.entry_id
    ).filter(
        SentimentEmbedding.embedding.isnot(None)
    )
    
    if limit:
        query = query.limit(limit)
    
    results = query.all()
    
    mentions = []
    for sentiment_data, embedding_record in results:
        mention_dict = {
            'entry_id': sentiment_data.entry_id,
            'text': sentiment_data.text or sentiment_data.content or sentiment_data.title or '',
            'run_timestamp': sentiment_data.run_timestamp or sentiment_data.created_at,
            'sentiment_label': sentiment_data.sentiment_label,
            'sentiment_score': sentiment_data.sentiment_score,
            'emotion_label': sentiment_data.emotion_label,
            'source_type': sentiment_data.source_type,
        }
        
        # Get embedding
        if embedding_record and embedding_record.embedding:
            if isinstance(embedding_record.embedding, str):
                mention_dict['embedding'] = json.loads(embedding_record.embedding)
            else:
                mention_dict['embedding'] = embedding_record.embedding
        
        mentions.append(mention_dict)
    
    logger.info(f"Retrieved {len(mentions)} sentiment_data records with embeddings")
    return mentions


def test_clustering_threshold(
    mentions: List[Dict[str, Any]],
    similarity_threshold: float,
    min_cluster_size: int = 500,
    time_window_hours: int = 168
) -> Dict[str, Any]:
    """
    Test clustering with a specific similarity threshold.
    
    Args:
        mentions: List of mention dictionaries
        similarity_threshold: Similarity threshold to test (0.0-1.0)
        min_cluster_size: Minimum cluster size
        time_window_hours: Time window for clustering
        
    Returns:
        Dictionary with clustering results
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing similarity threshold: {similarity_threshold:.3f}")
    logger.info(f"  Mentions: {len(mentions)}")
    logger.info(f"  Min cluster size: {min_cluster_size}")
    logger.info(f"  Time window: {time_window_hours}h")
    logger.info(f"{'='*60}")
    
    # Create clustering service with specific threshold
    clustering_service = IssueClusteringService(
        similarity_threshold=similarity_threshold,
        min_cluster_size=min_cluster_size,
        time_window_hours=time_window_hours
    )
    
    start_time = time.time()
    
    try:
        # Cluster mentions (topic_key is just for logging, not used for filtering)
        clusters = clustering_service.cluster_mentions(mentions, topic_key="all_data")
        elapsed_time = time.time() - start_time
        
        # Calculate statistics
        total_mentions_in_clusters = sum(len(cluster) for cluster in clusters)
        coverage_percent = (total_mentions_in_clusters / len(mentions) * 100) if mentions else 0
        
        # Get cluster size distribution
        cluster_sizes = [len(c) for c in clusters]
        avg_cluster_size = sum(cluster_sizes) / len(cluster_sizes) if cluster_sizes else 0
        max_cluster_size = max(cluster_sizes) if cluster_sizes else 0
        min_cluster_size_actual = min(cluster_sizes) if cluster_sizes else 0
        
        result = {
            'similarity_threshold': similarity_threshold,
            'total_mentions': len(mentions),
            'clusters_found': len(clusters),
            'mentions_in_clusters': total_mentions_in_clusters,
            'coverage_percent': coverage_percent,
            'avg_cluster_size': avg_cluster_size,
            'max_cluster_size': max_cluster_size,
            'min_cluster_size': min_cluster_size_actual,
            'elapsed_time': elapsed_time,
            'cluster_sizes': sorted(cluster_sizes, reverse=True)[:10]  # Top 10
        }
        
        logger.info(f"\nResults for threshold {similarity_threshold:.3f}:")
        logger.info(f"  Clusters found: {len(clusters)}")
        logger.info(f"  Mentions in clusters: {total_mentions_in_clusters} / {len(mentions)}")
        logger.info(f"  Coverage: {coverage_percent:.1f}%")
        logger.info(f"  Avg cluster size: {avg_cluster_size:.1f}")
        logger.info(f"  Cluster size range: {min_cluster_size_actual} - {max_cluster_size}")
        logger.info(f"  Time: {elapsed_time:.2f}s")
        
        if clusters:
            logger.info(f"\n  Top 5 cluster sizes:")
            for i, size in enumerate(sorted(cluster_sizes, reverse=True)[:5], 1):
                logger.info(f"    {i}. {size} mentions")
        
        return result
        
    except Exception as e:
        logger.error(f"Error testing threshold {similarity_threshold:.3f}: {e}", exc_info=True)
        return {
            'similarity_threshold': similarity_threshold,
            'error': str(e),
            'clusters_found': 0
        }


def compare_thresholds(
    mentions: List[Dict[str, Any]],
    thresholds: List[float],
    min_cluster_size: int = 500,
    time_window_hours: int = 168
) -> List[Dict[str, Any]]:
    """
    Compare multiple similarity thresholds.
    
    Args:
        mentions: List of mention dictionaries
        thresholds: List of similarity thresholds to test
        min_cluster_size: Minimum cluster size
        time_window_hours: Time window for clustering
        
    Returns:
        List of results for each threshold
    """
    logger.info(f"\n{'#'*60}")
    logger.info(f"Comparing similarity thresholds on {len(mentions)} mentions")
    logger.info(f"Thresholds to test: {thresholds}")
    logger.info(f"Min cluster size: {min_cluster_size}, Time window: {time_window_hours}h")
    logger.info(f"{'#'*60}\n")
    
    results = []
    
    for threshold in thresholds:
        result = test_clustering_threshold(
            mentions, 
            threshold, 
            min_cluster_size=min_cluster_size,
            time_window_hours=time_window_hours
        )
        results.append(result)
        
        # Small delay between tests
        time.sleep(0.5)
    
    return results


def print_comparison_summary(results: List[Dict[str, Any]]):
    """Print a summary comparison of all thresholds."""
    logger.info(f"\n{'='*80}")
    logger.info("SIMILARITY THRESHOLD COMPARISON SUMMARY")
    logger.info(f"{'='*80}\n")
    
    logger.info(f"{'Threshold':<12} {'Clusters':<10} {'Coverage %':<12} {'Avg Size':<10} {'Time (s)':<10} {'Status'}")
    logger.info("-" * 80)
    
    for result in results:
        threshold = result.get('similarity_threshold', 0)
        clusters = result.get('clusters_found', 0)
        coverage = result.get('coverage_percent', 0)
        avg_size = result.get('avg_cluster_size', 0)
        elapsed = result.get('elapsed_time', 0)
        error = result.get('error')
        
        status = "ERROR" if error else "OK"
        
        logger.info(f"{threshold:<12.3f} {clusters:<10} {coverage:<12.1f} {avg_size:<10.1f} {elapsed:<10.2f} {status}")
    
    logger.info(f"\n{'='*80}\n")
    
    # Recommendations
    valid_results = [r for r in results if 'error' not in r]
    if valid_results:
        # Find threshold with best balance (good coverage, reasonable number of clusters)
        best_balance = None
        best_score = -1
        
        for result in valid_results:
            coverage = result.get('coverage_percent', 0)
            clusters = result.get('clusters_found', 0)
            # Score: coverage * log(clusters + 1) to balance both
            import math
            score = coverage * math.log(clusters + 1) if clusters > 0 else 0
            
            if score > best_score:
                best_score = score
                best_balance = result
        
        if best_balance:
            logger.info(f"💡 Recommended threshold: {best_balance['similarity_threshold']:.3f}")
            logger.info(f"   - Creates {best_balance['clusters_found']} clusters")
            logger.info(f"   - Covers {best_balance['coverage_percent']:.1f}% of mentions")
            logger.info(f"   - Average cluster size: {best_balance['avg_cluster_size']:.1f}")
            logger.info(f"   - Balance score: {best_score:.2f}\n")


def main():
    """Main function to run clustering on all sentiment_data."""
    logger.info("="*80)
    logger.info("CLUSTERING ALL SENTIMENT_DATA RECORDS")
    logger.info("="*80)
    
    session = SessionLocal()
    
    try:
        # Get all sentiment_data records with embeddings
        logger.info("\nLoading all sentiment_data records with embeddings...")
        mentions = get_all_sentiment_data_with_embeddings(session, limit=None)
        
        if not mentions:
            logger.error("No sentiment_data records with embeddings found.")
            return
        
        logger.info(f"\nFound {len(mentions)} records with embeddings")
        logger.info("Testing different similarity thresholds...\n")
        
        # Test different similarity thresholds
        # Focused range for faster testing
        thresholds = [0.70, 0.75, 0.80]
        
        # Or test a wider range
        # thresholds = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
        
        # Compare thresholds
        results = compare_thresholds(
            mentions=mentions,
            thresholds=thresholds,
            min_cluster_size=500,  # Your configured value
            time_window_hours=168  # Your configured value (1 week)
        )
        
        # Print summary
        print_comparison_summary(results)
        
        logger.info("✅ Clustering threshold tuning complete!")
        logger.info("\nTo use a specific threshold, update your config:")
        logger.info('  "processing.issue.clustering.similarity_threshold": 0.75')
        logger.info("\nOr via environment variable:")
        logger.info("  CONFIG__PROCESSING__ISSUE__CLUSTERING__SIMILARITY_THRESHOLD=0.75")
        
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    finally:
        session.close()


if __name__ == "__main__":
    main()
