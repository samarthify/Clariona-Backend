"""
Check if embeddings exist in the database for sentiment_data records.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.database import SessionLocal
from api.models import SentimentData, SentimentEmbedding

# Set up logging
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger('CheckEmbeddings')


def check_embeddings():
    """Check for embeddings in the database."""
    
    print("\n" + "="*90)
    print("CHECKING EMBEDDINGS IN DATABASE")
    print("="*90)
    
    db = SessionLocal()
    try:
        # Check SentimentEmbedding table
        print("\n[1] Checking SentimentEmbedding table...")
        embedding_count = db.query(SentimentEmbedding).count()
        print(f"    Total embeddings in SentimentEmbedding table: {embedding_count}")
        
        if embedding_count > 0:
            # Get sample embeddings
            sample_embeddings = db.query(SentimentEmbedding).limit(5).all()
            print(f"\n    Sample embeddings:")
            for emb in sample_embeddings:
                embedding_data = emb.embedding
                if isinstance(embedding_data, str):
                    import json
                    try:
                        embedding_list = json.loads(embedding_data)
                        dims = len(embedding_list) if isinstance(embedding_list, list) else 0
                    except:
                        dims = "unknown"
                else:
                    dims = len(embedding_data) if hasattr(embedding_data, '__len__') else "unknown"
                
                print(f"      Entry ID: {emb.entry_id} | "
                      f"Model: {emb.embedding_model} | "
                      f"Dimensions: {dims} | "
                      f"Created: {emb.created_at}")
        
        # Check sentiment_data records with embeddings
        print(f"\n[2] Checking sentiment_data records with embeddings...")
        
        # Join query to find records with embeddings
        records_with_embeddings = db.query(SentimentData).join(
            SentimentEmbedding,
            SentimentData.entry_id == SentimentEmbedding.entry_id
        ).limit(10).all()
        
        print(f"    Records with embeddings: {len(records_with_embeddings)} (showing first 10)")
        
        if records_with_embeddings:
            print(f"\n    Sample records with embeddings:")
            for record in records_with_embeddings:
                text_content = (
                    record.text or 
                    record.content or 
                    record.description or 
                    record.title or 
                    ""
                )[:80]
                
                # Get embedding
                embedding = db.query(SentimentEmbedding).filter(
                    SentimentEmbedding.entry_id == record.entry_id
                ).first()
                
                embedding_data = embedding.embedding if embedding else None
                if isinstance(embedding_data, str):
                    import json
                    try:
                        embedding_list = json.loads(embedding_data)
                        dims = len(embedding_list) if isinstance(embedding_list, list) else 0
                    except:
                        dims = "unknown"
                else:
                    dims = len(embedding_data) if hasattr(embedding_data, '__len__') else "unknown"
                
                print(f"      ID: {record.entry_id} | "
                      f"Text: {text_content}... | "
                      f"Embedding dims: {dims}")
        
        # Check total sentiment_data records
        print(f"\n[3] Checking total sentiment_data records...")
        total_records = db.query(SentimentData).count()
        records_with_text = db.query(SentimentData).filter(
            SentimentData.text.isnot(None),
            SentimentData.text != '',
            text("LENGTH(text) > 50")
        ).count()
        
        print(f"    Total sentiment_data records: {total_records}")
        print(f"    Records with text (>50 chars): {records_with_text}")
        print(f"    Records with embeddings: {embedding_count}")
        print(f"    Coverage: {(embedding_count/records_with_text*100) if records_with_text > 0 else 0:.1f}%")
        
        # Test classification with real embeddings
        if records_with_embeddings:
            print(f"\n[4] Testing classification with real embeddings...")
            from processing.topic_classifier import TopicClassifier
            
            classifier = TopicClassifier(
                keyword_weight=0.3,
                embedding_weight=0.7,
                min_score_threshold=0.3,
                max_topics=5
            )
            
            test_count = 0
            match_count = 0
            
            for record in records_with_embeddings[:5]:
                text_content = (
                    record.text or 
                    record.content or 
                    record.description or 
                    record.title or 
                    ""
                )
                
                if not text_content or len(text_content.strip()) < 20:
                    continue
                
                # Get embedding
                embedding = db.query(SentimentEmbedding).filter(
                    SentimentEmbedding.entry_id == record.entry_id
                ).first()
                
                if not embedding:
                    continue
                
                # Parse embedding
                embedding_data = embedding.embedding
                embedding_list = None
                
                if isinstance(embedding_data, str):
                    import json
                    try:
                        embedding_list = json.loads(embedding_data)
                    except:
                        # Try parsing as list directly
                        try:
                            import ast
                            embedding_list = ast.literal_eval(embedding_data)
                        except:
                            continue
                elif isinstance(embedding_data, list):
                    embedding_list = embedding_data
                elif hasattr(embedding_data, '__iter__'):
                    embedding_list = list(embedding_data)
                else:
                    continue
                
                if not embedding_list or not isinstance(embedding_list, list):
                    continue
                    
                if len(embedding_list) != 1536:
                    logger.warning(f"Embedding has wrong dimensions: {len(embedding_list)}")
                    continue
                
                # Ensure all values are floats
                try:
                    embedding_list = [float(x) for x in embedding_list]
                except:
                    continue
                
                # Classify with embedding
                classifications = classifier.classify(text_content, text_embedding=embedding_list)
                test_count += 1
                
                if classifications:
                    match_count += 1
                    print(f"\n      Record {test_count} (ID: {record.entry_id}):")
                    print(f"        Text: {text_content[:70]}...")
                    print(f"        Topics found ({len(classifications)}):")
                    for cls in classifications:
                        print(f"          • {cls['topic_name']} | "
                              f"Conf: {cls['confidence']:.3f} | "
                              f"KW: {cls['keyword_score']:.3f} | "
                              f"Emb: {cls['embedding_score']:.3f}")
                else:
                    print(f"\n      Record {test_count} (ID: {record.entry_id}): No topics matched")
            
            if test_count > 0:
                print(f"\n    Classification Results:")
                print(f"      Records tested: {test_count}")
                print(f"      Records with topics: {match_count} ({match_count/test_count*100:.1f}%)")
        
        print("\n" + "="*90)
        print("[CHECK COMPLETE]")
        print("="*90)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
    
    finally:
        db.close()


if __name__ == "__main__":
    check_embeddings()

