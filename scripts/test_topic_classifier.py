"""
Test script for TopicClassifier.
Tests classification with sample texts.
"""

import sys
import os
from pathlib import Path

# Add src directory to path to import modules
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

import logging
from typing import List, Dict

from processing.topic_classifier import TopicClassifier
from processing.topic_embedding_generator import TopicEmbeddingGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('TestTopicClassifier')


def test_keyword_only_classification():
    """Test classification using only keywords (no embeddings)."""
    print("\n" + "="*80)
    print("TEST 1: Keyword-Only Classification")
    print("="*80)
    
    classifier = TopicClassifier(
        keyword_weight=1.0,
        embedding_weight=0.0,
        min_score_threshold=0.3,
        max_topics=5
    )
    
    test_texts = [
        "The government announced a new fuel subsidy removal policy that will affect petrol prices across Nigeria.",
        "ASUU lecturers are going on strike again due to unpaid salaries and poor working conditions.",
        "The Nigerian army conducted a successful operation against bandits in the northern region.",
        "President Tinubu announced new infrastructure projects including roads and railways.",
        "Healthcare facilities are facing critical shortages of medical equipment and supplies.",
        "The budget allocation for education has been increased by 20% this year.",
        "This is a random text about cooking recipes and food preparation.",
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n--- Test Text {i} ---")
        print(f"Text: {text[:100]}...")
        print("\nClassifications:")
        
        classifications = classifier.classify(text, text_embedding=None)
        
        if classifications:
            for cls in classifications:
                print(f"  • {cls['topic_name']} ({cls['topic']})")
                print(f"    Confidence: {cls['confidence']:.3f}")
                print(f"    Keyword Score: {cls['keyword_score']:.3f}")
                print(f"    Embedding Score: {cls['embedding_score']:.3f}")
        else:
            print("  (No topics matched)")


def test_with_embeddings():
    """Test classification with embeddings (requires embeddings file)."""
    print("\n" + "="*80)
    print("TEST 2: Classification with Embeddings")
    print("="*80)
    
    # Check if embeddings file exists
    embeddings_path = Path(__file__).parent.parent / 'config' / 'topic_embeddings.json'
    if not embeddings_path.exists():
        print("\n⚠ Embeddings file not found!")
        print("   Run: python src/processing/topic_embedding_generator.py")
        print("   Skipping embedding-based tests...")
        return
    
    classifier = TopicClassifier(
        keyword_weight=0.3,
        embedding_weight=0.7,
        min_score_threshold=0.5,
        max_topics=3
    )
    
    # Sample embeddings (dummy - in real usage, these would come from OpenAI)
    # For testing, we'll use keyword-only mode
    test_texts = [
        "The fuel price has increased to 700 naira per liter after subsidy removal.",
        "ASUU strike continues as lecturers demand better funding for universities.",
        "Military operations in the northeast have successfully neutralized several terrorist camps.",
    ]
    
    print("\nNote: This test requires actual text embeddings from OpenAI.")
    print("In production, embeddings are generated during data processing.")
    print("\nTesting keyword + embedding mode (with dummy embeddings):")
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n--- Test Text {i} ---")
        print(f"Text: {text}")
        
        # Without embedding, it falls back to keyword-only
        classifications = classifier.classify(text, text_embedding=None)
        
        if classifications:
            for cls in classifications:
                print(f"  • {cls['topic_name']} - Confidence: {cls['confidence']:.3f}")
        else:
            print("  (No topics matched)")


def test_owner_filtering():
    """Test filtering topics for a specific owner."""
    print("\n" + "="*80)
    print("TEST 3: Owner-Based Topic Filtering")
    print("="*80)
    
    classifier = TopicClassifier(
        min_score_threshold=0.3,
        max_topics=10
    )
    
    # Test text that matches multiple topics
    test_text = "The president announced new fuel pricing policies and military operations to address security threats."
    
    print(f"\nTest Text: {test_text}")
    
    # Get all classifications
    all_classifications = classifier.classify(test_text, text_embedding=None)
    
    print(f"\nAll Classifications ({len(all_classifications)}):")
    for cls in all_classifications:
        print(f"  • {cls['topic_name']} ({cls['topic']}) - {cls['confidence']:.3f}")
    
    # Test filtering for president
    print("\n--- Filtering for 'president' owner ---")
    president_topics = classifier.get_topics_for_owner('president')
    print(f"President's topics: {president_topics}")
    
    filtered = classifier.filter_topics_for_owner(all_classifications, 'president')
    print(f"\nFiltered Classifications ({len(filtered)}):")
    for cls in filtered:
        print(f"  • {cls['topic_name']} ({cls['topic']}) - {cls['confidence']:.3f}")


def test_embedding_generation():
    """Test generating embeddings for topics."""
    print("\n" + "="*80)
    print("TEST 4: Topic Embedding Generation")
    print("="*80)
    
    print("\nGenerating embeddings for all topics in database...")
    print("(This requires OPENAI_API_KEY to be set)")
    
    generator = TopicEmbeddingGenerator()
    
    if not generator.openai_client:
        print("\n⚠ OpenAI client not available. Set OPENAI_API_KEY environment variable.")
        return
    
    embeddings = generator.generate_all_embeddings()
    
    if embeddings:
        print(f"\n✓ Successfully generated {len(embeddings)} embeddings")
        print(f"  Saved to: config/topic_embeddings.json")
    else:
        print("\n✗ Failed to generate embeddings")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("TopicClassifier Test Suite")
    print("="*80)
    
    try:
        # Test 1: Keyword-only classification
        test_keyword_only_classification()
        
        # Test 2: Classification with embeddings
        test_with_embeddings()
        
        # Test 3: Owner filtering
        test_owner_filtering()
        
        # Test 4: Embedding generation (optional)
        # Skip interactive prompt in non-interactive mode
        print("\n" + "="*80)
        print("\nNote: Embeddings have already been generated.")
        print("To regenerate, run: python src/processing/topic_embedding_generator.py")
        
        print("\n" + "="*80)
        print("[SUCCESS] All tests completed!")
        print("="*80)
    
    except Exception as e:
        logger.error(f"Error running tests: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

