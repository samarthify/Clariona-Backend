"""
Quick script to check record counts in sentiment_data table.
Checks for actual embeddings vs zero vectors.
"""

import sys
from pathlib import Path
import json
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.api.database import SessionLocal
from src.api.models import SentimentData, SentimentEmbedding
from sqlalchemy import func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_zero_vector(embedding):
    """Check if embedding is a zero vector."""
    if embedding is None:
        return True
    
    # Handle string JSON
    if isinstance(embedding, str):
        try:
            embedding = json.loads(embedding)
        except:
            return True
    
    # Handle list/array
    if isinstance(embedding, list):
        if len(embedding) == 0:
            return True
        # Check if all values are zero (or very close to zero)
        try:
            arr = np.array(embedding, dtype=np.float32)
            return np.allclose(arr, 0.0, atol=1e-6)
        except:
            return True
    
    return False

session = SessionLocal()

try:
    # Total records
    total_count = session.query(func.count(SentimentData.entry_id)).scalar()
    
    # Get all embedding records
    embedding_records = session.query(SentimentEmbedding).all()
    
    actual_embeddings = 0
    zero_vectors = 0
    null_embeddings = 0
    
    print(f"\nChecking {len(embedding_records):,} embedding records...")
    
    for i, emb_record in enumerate(embedding_records):
        if (i + 1) % 5000 == 0:
            print(f"  Processed {i + 1:,} / {len(embedding_records):,}...")
        
        if emb_record.embedding is None:
            null_embeddings += 1
        elif is_zero_vector(emb_record.embedding):
            zero_vectors += 1
        else:
            actual_embeddings += 1
    
    # Records with sentiment analysis
    with_sentiment = session.query(func.count(SentimentData.entry_id)).filter(
        SentimentData.sentiment_label.isnot(None)
    ).scalar()
    
    # Records with actual embeddings AND sentiment
    with_both_query = session.query(SentimentData, SentimentEmbedding).join(
        SentimentEmbedding, SentimentData.entry_id == SentimentEmbedding.entry_id
    ).filter(
        SentimentData.sentiment_label.isnot(None),
        SentimentEmbedding.embedding.isnot(None)
    ).all()
    
    with_both_actual = 0
    for sentiment_data, emb_record in with_both_query:
        if not is_zero_vector(emb_record.embedding):
            with_both_actual += 1
    
    print("\n" + "="*70)
    print("SENTIMENT_DATA TABLE STATISTICS")
    print("="*70)
    print(f"Total records: {total_count:,}")
    print(f"\nEmbedding Statistics:")
    print(f"  Total embedding records: {len(embedding_records):,}")
    print(f"  ✅ Actual embeddings (non-zero): {actual_embeddings:,}")
    print(f"  ❌ Zero vectors: {zero_vectors:,}")
    print(f"  ⚠️  Null embeddings: {null_embeddings:,}")
    print(f"\nSentiment Statistics:")
    print(f"  Records with sentiment: {with_sentiment:,}")
    print(f"  Records with actual embeddings + sentiment: {with_both_actual:,}")
    print("="*70)
    print(f"\n💡 Usable for clustering: {actual_embeddings:,} records")
    print(f"   (With min_cluster_size=500, max ~{actual_embeddings // 500} clusters possible)\n")
    
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
finally:
    session.close()
