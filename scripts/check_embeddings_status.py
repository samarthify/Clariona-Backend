"""
Check embedding status in database for records with both embedding and sentiment.

This script analyzes embeddings to see:
- How many are zero vectors
- Embedding lengths
- Embedding norms (magnitude)
- Sample embeddings
"""

import sys
from pathlib import Path
import json
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from src.api.database import SessionLocal
from src.api.models import (
    SentimentData, SentimentEmbedding, User
)
from uuid import UUID


def check_embeddings_status(user_id: str = None):
    """Check embedding status for a specific user or all users."""
    db: Session = SessionLocal()
    
    try:
        # Convert user_id to UUID if provided
        user_id_uuid = None
        if user_id:
            user_id_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        
        print("=" * 80)
        print("EMBEDDING STATUS CHECK")
        print("=" * 80)
        print()
        
        # Query for records with both embedding and sentiment
        query = db.query(SentimentData, SentimentEmbedding).join(
            SentimentEmbedding,
            SentimentData.entry_id == SentimentEmbedding.entry_id
        ).filter(
            SentimentData.sentiment_label.isnot(None),
            SentimentEmbedding.embedding.isnot(None)
        )
        
        if user_id_uuid:
            query = query.filter(SentimentData.user_id == user_id_uuid)
            print(f"Checking embeddings for user: {user_id}")
        else:
            print("Checking embeddings for all users")
        
        records = query.limit(1000).all()  # Sample first 1000 records
        
        if not records:
            print("No records found with both embedding and sentiment")
            return
        
        print(f"Analyzing {len(records)} records (sampled from total)...")
        print()
        
        # Analyze embeddings
        zero_vectors = 0
        valid_embeddings = 0
        invalid_lengths = 0
        embedding_lengths = []
        embedding_norms = []
        sample_embeddings = []
        
        for sentiment_data, embedding_record in records:
            try:
                # Parse embedding
                embedding = None
                if isinstance(embedding_record.embedding, str):
                    embedding = json.loads(embedding_record.embedding)
                else:
                    embedding = embedding_record.embedding
                
                if not embedding:
                    continue
                
                # Check length
                embedding_lengths.append(len(embedding))
                if len(embedding) != 1536:
                    invalid_lengths += 1
                    continue
                
                # Check if zero vector
                embedding_array = np.array(embedding, dtype=np.float64)
                norm = np.linalg.norm(embedding_array)
                embedding_norms.append(norm)
                
                if norm == 0 or norm < 1e-10:
                    zero_vectors += 1
                else:
                    valid_embeddings += 1
                    if len(sample_embeddings) < 3:
                        sample_embeddings.append({
                            'entry_id': sentiment_data.entry_id,
                            'norm': norm,
                            'first_10_values': embedding[:10],
                            'min': float(np.min(embedding_array)),
                            'max': float(np.max(embedding_array)),
                            'mean': float(np.mean(embedding_array))
                        })
            
            except Exception as e:
                print(f"Error processing record {sentiment_data.entry_id}: {e}")
                continue
        
        # Print statistics
        print("EMBEDDING STATISTICS:")
        print("-" * 80)
        print(f"Total Records Analyzed: {len(records)}")
        print(f"Valid Embeddings (non-zero): {valid_embeddings} ({valid_embeddings/len(records)*100:.1f}%)")
        print(f"Zero Vectors: {zero_vectors} ({zero_vectors/len(records)*100:.1f}%)")
        print(f"Invalid Lengths (not 1536): {invalid_lengths} ({invalid_lengths/len(records)*100:.1f}%)")
        
        if embedding_lengths:
            print(f"\nEMBEDDING LENGTHS:")
            print(f"  Min Length: {min(embedding_lengths)}")
            print(f"  Max Length: {max(embedding_lengths)}")
            print(f"  Average Length: {sum(embedding_lengths)/len(embedding_lengths):.1f}")
            length_dist = {}
            for length in embedding_lengths:
                length_dist[length] = length_dist.get(length, 0) + 1
            print(f"  Length Distribution: {dict(sorted(length_dist.items())[:10])}")
        
        if embedding_norms:
            print(f"\nEMBEDDING NORMS (Magnitude):")
            print(f"  Min Norm: {min(embedding_norms):.6f}")
            print(f"  Max Norm: {max(embedding_norms):.6f}")
            print(f"  Average Norm: {sum(embedding_norms)/len(embedding_norms):.6f}")
            print(f"  Median Norm: {np.median(embedding_norms):.6f}")
        
        if sample_embeddings:
            print(f"\nSAMPLE VALID EMBEDDINGS:")
            for i, sample in enumerate(sample_embeddings, 1):
                print(f"\n  Sample {i} (entry_id: {sample['entry_id']}):")
                print(f"    Norm: {sample['norm']:.6f}")
                print(f"    First 10 values: {sample['first_10_values']}")
                print(f"    Min: {sample['min']:.6f}, Max: {sample['max']:.6f}, Mean: {sample['mean']:.6f}")
        
        # Check for specific user if provided
        if user_id_uuid:
            # Get total count for this user
            total_count = db.query(SentimentData).join(
                SentimentEmbedding,
                SentimentData.entry_id == SentimentEmbedding.entry_id
            ).filter(
                SentimentData.user_id == user_id_uuid,
                SentimentData.sentiment_label.isnot(None),
                SentimentEmbedding.embedding.isnot(None)
            ).count()
            
            print(f"\nTOTAL RECORDS FOR USER:")
            print(f"  Total with embedding + sentiment: {total_count}")
            print(f"  Estimated zero vectors: ~{int(zero_vectors * total_count / len(records))}")
            print(f"  Estimated valid embeddings: ~{int(valid_embeddings * total_count / len(records))}")
        
        print()
        print("=" * 80)
        
    except Exception as e:
        print(f"ERROR: Error checking embeddings: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Check embedding status in database")
    parser.add_argument("--user-id", type=str, help="Specific user ID to check (optional)")
    
    args = parser.parse_args()
    
    check_embeddings_status(user_id=args.user_id)
