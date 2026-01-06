"""
Comprehensive end-to-end test of the Topic Classification System.
Tests the complete implementation using the database.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

import logging
import json
import time
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import List, Dict

from api.database import SessionLocal
from api.models import SentimentData, SentimentEmbedding, Topic, OwnerConfig, MentionTopic
from processing.topic_classifier import TopicClassifier

# Set up logging
logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger('FullSystemTest')


def parse_embedding(embedding_data):
    """Parse embedding from database format."""
    if embedding_data is None:
        return None
    
    if isinstance(embedding_data, list):
        if len(embedding_data) == 1536:
            try:
                return [float(x) for x in embedding_data]
            except:
                return None
        return None
    
    if isinstance(embedding_data, str):
        try:
            parsed = json.loads(embedding_data)
            if isinstance(parsed, list) and len(parsed) == 1536:
                return [float(x) for x in parsed]
        except:
            pass
    
    return None


def test_database_setup():
    """Test 1: Verify database setup."""
    print("\n" + "="*90)
    print("TEST 1: DATABASE SETUP VERIFICATION")
    print("="*90)
    
    db = SessionLocal()
    try:
        # Check topics table
        topic_count = db.query(Topic).filter(Topic.is_active == True).count()
        print(f"\n[Topics Table]")
        print(f"  Active topics: {topic_count}")
        
        if topic_count > 0:
            sample_topics = db.query(Topic).filter(Topic.is_active == True).limit(5).all()
            print(f"  Sample topics:")
            for topic in sample_topics:
                keywords_count = len(topic.keywords) if topic.keywords else 0
                print(f"    - {topic.topic_name} ({topic.topic_key}): {keywords_count} keywords")
        
        # Check owner_configs table
        owner_count = db.query(OwnerConfig).filter(OwnerConfig.is_active == True).count()
        print(f"\n[Owner Configs Table]")
        print(f"  Active owner configs: {owner_count}")
        
        if owner_count > 0:
            owners = db.query(OwnerConfig).filter(OwnerConfig.is_active == True).all()
            for owner in owners:
                topics_count = len(owner.topics) if owner.topics else 0
                print(f"    - {owner.owner_name} ({owner.owner_key}): {topics_count} topics")
        
        # Check sentiment_embeddings table
        embedding_count = db.query(SentimentEmbedding).count()
        print(f"\n[Sentiment Embeddings Table]")
        print(f"  Total embeddings: {embedding_count}")
        
        # Check sentiment_data table
        total_records = db.query(SentimentData).count()
        records_with_text = db.query(SentimentData).filter(
            SentimentData.text.isnot(None),
            SentimentData.text != '',
            text("LENGTH(text) > 50")
        ).count()
        
        print(f"\n[Sentiment Data Table]")
        print(f"  Total records: {total_records}")
        print(f"  Records with text: {records_with_text}")
        print(f"  Embedding coverage: {(embedding_count/records_with_text*100) if records_with_text > 0 else 0:.1f}%")
        
        # Check mention_topics table
        mention_topic_count = db.query(MentionTopic).count()
        print(f"\n[Mention Topics Table]")
        print(f"  Existing classifications: {mention_topic_count}")
        
        print(f"\n[STATUS] Database setup verified")
        return True
        
    except Exception as e:
        logger.error(f"Database setup check failed: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
        return False
    finally:
        db.close()


def test_topic_classifier_initialization():
    """Test 2: TopicClassifier initialization."""
    print("\n" + "="*90)
    print("TEST 2: TOPIC CLASSIFIER INITIALIZATION")
    print("="*90)
    
    try:
        start = time.time()
        classifier = TopicClassifier(
            keyword_weight=0.3,
            embedding_weight=0.7,
            min_score_threshold=0.3,
            max_topics=5
        )
        init_time = time.time() - start
        
        print(f"\n[Initialization]")
        print(f"  Time: {init_time:.3f}s")
        print(f"  Topics loaded from DB: {len(classifier.master_topics)}")
        print(f"  Topic embeddings loaded: {len(classifier.topic_embeddings)}")
        
        # Verify topics
        print(f"\n[Topics Verification]")
        for topic_key, topic_data in list(classifier.master_topics.items())[:5]:
            keywords_count = len(topic_data.get('keywords', []))
            has_embedding = topic_key in classifier.topic_embeddings
            print(f"  {topic_data['name']:30} | Keywords: {keywords_count:3} | Embedding: {'Yes' if has_embedding else 'No'}")
        
        print(f"\n[STATUS] TopicClassifier initialized successfully")
        return classifier
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
        return None


def test_classification_with_embeddings(classifier: TopicClassifier):
    """Test 3: Classification with real embeddings."""
    print("\n" + "="*90)
    print("TEST 3: CLASSIFICATION WITH REAL EMBEDDINGS")
    print("="*90)
    
    db = SessionLocal()
    try:
        # Get records with embeddings
        records = db.query(SentimentData).join(
            SentimentEmbedding,
            SentimentData.entry_id == SentimentEmbedding.entry_id
        ).filter(
            SentimentData.text.isnot(None),
            SentimentData.text != '',
            text("LENGTH(text) > 50")
        ).limit(30).all()
        
        print(f"\n[Test Data]")
        print(f"  Records with embeddings: {len(records)}")
        
        results = []
        total_time = 0
        matches = 0
        topic_distribution = {}
        
        print(f"\n[Classification Results]")
        print("-" * 90)
        
        for i, record in enumerate(records, 1):
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
            embedding_record = db.query(SentimentEmbedding).filter(
                SentimentEmbedding.entry_id == record.entry_id
            ).first()
            
            if not embedding_record:
                continue
            
            embedding_list = parse_embedding(embedding_record.embedding)
            if not embedding_list:
                continue
            
            # Classify
            start_time = time.time()
            classifications = classifier.classify(text_content, text_embedding=embedding_list)
            elapsed = (time.time() - start_time) * 1000
            total_time += elapsed
            
            if classifications:
                matches += 1
                for cls in classifications:
                    topic = cls["topic"]
                    topic_distribution[topic] = topic_distribution.get(topic, 0) + 1
            
            # Store result
            results.append({
                "entry_id": record.entry_id,
                "text_length": len(text_content),
                "classifications": classifications,
                "time": elapsed,
                "has_embedding": True
            })
            
            # Show first 10 results
            if i <= 10:
                text_preview = text_content[:60].encode('ascii', 'ignore').decode('ascii')
                print(f"\n  Record {i} (ID: {record.entry_id}):")
                print(f"    Text: {text_preview}...")
                print(f"    Time: {elapsed:.2f}ms")
                
                if classifications:
                    print(f"    Topics ({len(classifications)}):")
                    for cls in classifications:
                        print(f"      - {cls['topic_name']:30} | "
                              f"Conf: {cls['confidence']:.3f} | "
                              f"KW: {cls['keyword_score']:.3f} | "
                              f"Emb: {cls['embedding_score']:.3f}")
                else:
                    print(f"    Topics: None")
        
        # Summary
        print("\n" + "-" * 90)
        print(f"[Summary]")
        print(f"  Records tested: {len(results)}")
        print(f"  Records with topics: {matches} ({matches/len(results)*100:.1f}%)")
        print(f"  Average time: {total_time/len(results):.2f}ms")
        print(f"  Throughput: {len(results)/(total_time/1000):.1f} records/second")
        
        if topic_distribution:
            print(f"\n  Topic Distribution:")
            sorted_topics = sorted(topic_distribution.items(), key=lambda x: x[1], reverse=True)
            for topic, count in sorted_topics:
                topic_name = classifier.master_topics.get(topic, {}).get("name", topic)
                percentage = (count / matches) * 100
                print(f"    {topic_name:30} : {count:3} ({percentage:5.1f}%)")
        
        print(f"\n[STATUS] Classification test completed")
        return results
        
    except Exception as e:
        logger.error(f"Classification test failed: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
        return []
    finally:
        db.close()


def test_owner_filtering(classifier: TopicClassifier):
    """Test 4: Owner-based filtering."""
    print("\n" + "="*90)
    print("TEST 4: OWNER-BASED FILTERING")
    print("="*90)
    
    db = SessionLocal()
    try:
        # Get owner configs
        owners = db.query(OwnerConfig).filter(OwnerConfig.is_active == True).all()
        
        print(f"\n[Owner Configurations]")
        for owner in owners:
            topics_count = len(owner.topics) if owner.topics else 0
            print(f"  {owner.owner_name} ({owner.owner_key}): {topics_count} topics")
        
        # Test filtering
        test_text = "The president announced new fuel pricing policies and military operations to address security threats."
        
        print(f"\n[Test Text]")
        print(f"  {test_text}")
        
        # Get all classifications
        all_classifications = classifier.classify(test_text, text_embedding=None)
        
        print(f"\n[All Classifications]")
        print(f"  Found {len(all_classifications)} topics:")
        for cls in all_classifications:
            print(f"    - {cls['topic_name']} ({cls['topic']}) - {cls['confidence']:.3f}")
        
        # Filter for each owner
        for owner in owners:
            owner_topics = classifier.get_topics_for_owner(owner.owner_key)
            filtered = classifier.filter_topics_for_owner(all_classifications, owner.owner_key)
            
            print(f"\n[{owner.owner_name}]")
            print(f"  Configured topics: {len(owner_topics)}")
            print(f"  Filtered results: {len(filtered)}")
            if filtered:
                for cls in filtered:
                    print(f"    - {cls['topic_name']} - {cls['confidence']:.3f}")
        
        print(f"\n[STATUS] Owner filtering test completed")
        return True
        
    except Exception as e:
        logger.error(f"Owner filtering test failed: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
        return False
    finally:
        db.close()


def test_database_storage(classifier: TopicClassifier):
    """Test 5: Test storing classifications in database."""
    print("\n" + "="*90)
    print("TEST 5: DATABASE STORAGE (DRY RUN)")
    print("="*90)
    
    db = SessionLocal()
    try:
        # Get a sample record
        record = db.query(SentimentData).filter(
            SentimentData.text.isnot(None),
            SentimentData.text != '',
            text("LENGTH(text) > 50")
        ).first()
        
        if not record:
            print("\n[ERROR] No records found for testing")
            return False
        
        # Get embedding if available
        embedding_record = db.query(SentimentEmbedding).filter(
            SentimentEmbedding.entry_id == record.entry_id
        ).first()
        
        embedding_list = None
        if embedding_record:
            embedding_list = parse_embedding(embedding_record.embedding)
        
        text_content = record.text or record.content or record.description or ""
        
        # Classify
        classifications = classifier.classify(text_content, text_embedding=embedding_list)
        
        print(f"\n[Sample Record]")
        print(f"  Entry ID: {record.entry_id}")
        print(f"  Text: {text_content[:80]}...")
        print(f"  Has embedding: {embedding_list is not None}")
        print(f"  Classifications: {len(classifications)}")
        
        if classifications:
            print(f"\n  Topics to store:")
            for cls in classifications:
                print(f"    - {cls['topic_name']} ({cls['topic']})")
                print(f"      Confidence: {cls['confidence']:.3f}")
                print(f"      Keyword Score: {cls['keyword_score']:.3f}")
                print(f"      Embedding Score: {cls['embedding_score']:.3f}")
            
            # Check if already exists
            existing = db.query(MentionTopic).filter(
                MentionTopic.mention_id == record.entry_id
            ).all()
            
            print(f"\n  Existing classifications in DB: {len(existing)}")
            
            # Show what would be stored (dry run)
            print(f"\n  [DRY RUN] Would store {len(classifications)} topic classifications:")
            for cls in classifications:
                print(f"    INSERT INTO mention_topics:")
                print(f"      mention_id: {record.entry_id}")
                print(f"      topic_key: {cls['topic']}")
                print(f"      topic_confidence: {cls['confidence']:.3f}")
                print(f"      keyword_score: {cls['keyword_score']:.3f}")
                print(f"      embedding_score: {cls['embedding_score']:.3f}")
        
        print(f"\n[STATUS] Database storage test completed (dry run)")
        return True
        
    except Exception as e:
        logger.error(f"Database storage test failed: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
        return False
    finally:
        db.close()


def test_performance_benchmark(classifier: TopicClassifier):
    """Test 6: Performance benchmark."""
    print("\n" + "="*90)
    print("TEST 6: PERFORMANCE BENCHMARK")
    print("="*90)
    
    db = SessionLocal()
    try:
        # Get records with embeddings
        records = db.query(SentimentData).join(
            SentimentEmbedding,
            SentimentData.entry_id == SentimentEmbedding.entry_id
        ).filter(
            SentimentData.text.isnot(None),
            SentimentData.text != '',
            text("LENGTH(text) > 50")
        ).limit(100).all()
        
        print(f"\n[Benchmark]")
        print(f"  Testing with {len(records)} records")
        
        # Test keyword-only
        kw_classifier = TopicClassifier(
            keyword_weight=1.0,
            embedding_weight=0.0,
            min_score_threshold=0.3,
            max_topics=5
        )
        
        kw_times = []
        kw_matches = 0
        
        for record in records[:50]:
            text_content = record.text or record.content or ""
            if not text_content:
                continue
            
            start = time.time()
            results = kw_classifier.classify(text_content, text_embedding=None)
            kw_times.append((time.time() - start) * 1000)
            if results:
                kw_matches += 1
        
        # Test with embeddings
        emb_times = []
        emb_matches = 0
        
        for record in records[:50]:
            text_content = record.text or record.content or ""
            if not text_content:
                continue
            
            embedding_record = db.query(SentimentEmbedding).filter(
                SentimentEmbedding.entry_id == record.entry_id
            ).first()
            
            embedding_list = None
            if embedding_record:
                embedding_list = parse_embedding(embedding_record.embedding)
            
            if not embedding_list:
                continue
            
            start = time.time()
            results = classifier.classify(text_content, text_embedding=embedding_list)
            emb_times.append((time.time() - start) * 1000)
            if results:
                emb_matches += 1
        
        print(f"\n[Results]")
        if kw_times:
            print(f"  Keyword-Only Mode:")
            print(f"    Average time: {sum(kw_times)/len(kw_times):.2f}ms")
            print(f"    Throughput: {len(kw_times)/(sum(kw_times)/1000):.1f} records/second")
            print(f"    Match rate: {kw_matches/len(kw_times)*100:.1f}%")
        
        if emb_times:
            print(f"\n  Hybrid Mode (Keyword + Embedding):")
            print(f"    Average time: {sum(emb_times)/len(emb_times):.2f}ms")
            print(f"    Throughput: {len(emb_times)/(sum(emb_times)/1000):.1f} records/second")
            print(f"    Match rate: {emb_matches/len(emb_times)*100:.1f}%")
        
        print(f"\n[STATUS] Performance benchmark completed")
        return True
        
    except Exception as e:
        logger.error(f"Performance benchmark failed: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
        return False
    finally:
        db.close()


def main():
    """Run all tests."""
    print("\n" + "="*90)
    print("COMPREHENSIVE TOPIC CLASSIFICATION SYSTEM TEST")
    print("="*90)
    print("\nTesting complete implementation using database...")
    
    results = {
        "database_setup": False,
        "classifier_init": False,
        "classification": False,
        "owner_filtering": False,
        "database_storage": False,
        "performance": False
    }
    
    try:
        # Test 1: Database setup
        results["database_setup"] = test_database_setup()
        
        if not results["database_setup"]:
            print("\n[ERROR] Database setup failed. Cannot continue.")
            return
        
        # Test 2: Classifier initialization
        classifier = test_topic_classifier_initialization()
        results["classifier_init"] = classifier is not None
        
        if not classifier:
            print("\n[ERROR] Classifier initialization failed. Cannot continue.")
            return
        
        # Test 3: Classification with embeddings
        classification_results = test_classification_with_embeddings(classifier)
        results["classification"] = len(classification_results) > 0
        
        # Test 4: Owner filtering
        results["owner_filtering"] = test_owner_filtering(classifier)
        
        # Test 5: Database storage
        results["database_storage"] = test_database_storage(classifier)
        
        # Test 6: Performance
        results["performance"] = test_performance_benchmark(classifier)
        
        # Final summary
        print("\n" + "="*90)
        print("FINAL TEST SUMMARY")
        print("="*90)
        
        print(f"\n[Test Results]")
        for test_name, passed in results.items():
            status = "[PASS]" if passed else "[FAIL]"
            print(f"  {status} {test_name.replace('_', ' ').title()}")
        
        passed_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        print(f"\n[Overall]")
        print(f"  Tests Passed: {passed_count}/{total_count}")
        print(f"  Success Rate: {(passed_count/total_count)*100:.1f}%")
        
        if passed_count == total_count:
            print(f"\n[SUCCESS] All tests passed! System is ready for production.")
        else:
            print(f"\n[WARNING] Some tests failed. Review errors above.")
        
        print("="*90)
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        print(f"\n[FATAL ERROR] {e}")


if __name__ == "__main__":
    main()
















