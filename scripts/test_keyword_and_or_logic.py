"""
Test script for AND/OR keyword logic in TopicClassifier.

This script tests the new keyword_groups functionality with various scenarios.
"""

import sys
from pathlib import Path
import logging

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from processing.topic_classifier import TopicClassifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TestKeywordAndOr')

def test_or_group():
    """Test OR group matching."""
    print("\n" + "="*60)
    print("TEST 1: OR Group Matching")
    print("="*60)
    
    classifier = TopicClassifier()
    
    # Test OR group: matches if any keyword is present
    keyword_groups = {
        "groups": [
            {"type": "or", "keywords": ["fuel", "petrol", "diesel"]}
        ],
        "require_all_groups": False
    }
    
    test_cases = [
        ("The fuel price increased", True, "Should match 'fuel'"),
        ("Petrol is expensive", True, "Should match 'petrol'"),
        ("Diesel costs are rising", True, "Should match 'diesel'"),
        ("The price of gasoline", False, "Should NOT match (gasoline not in group)"),
        ("Electric vehicles are popular", False, "Should NOT match"),
    ]
    
    for text, should_match, description in test_cases:
        score = classifier._match_keyword_groups(text.lower(), keyword_groups)
        matched = score > 0
        status = "[PASS]" if matched == should_match else "[FAIL]"
        print(f"{status} | Score: {score:.3f} | {description}")
        print(f"         Text: '{text}'")
        if matched != should_match:
            print(f"         Expected: {should_match}, Got: {matched}")

def test_and_group():
    """Test AND group matching."""
    print("\n" + "="*60)
    print("TEST 2: AND Group Matching")
    print("="*60)
    
    classifier = TopicClassifier()
    
    # Test AND group: all keywords must match
    keyword_groups = {
        "groups": [
            {"type": "and", "keywords": ["fuel", "price", "increase"]}
        ],
        "require_all_groups": False
    }
    
    test_cases = [
        ("The fuel price increased", True, "Should match all: fuel AND price AND increase"),
        ("Fuel price went up", True, "Should match (price/increase implied)"),
        ("The fuel is expensive", False, "Should NOT match (missing 'price' and 'increase')"),
        ("Price increased", False, "Should NOT match (missing 'fuel')"),
        ("Fuel subsidy removal", False, "Should NOT match (missing 'price' and 'increase')"),
    ]
    
    for text, should_match, description in test_cases:
        score = classifier._match_keyword_groups(text.lower(), keyword_groups)
        matched = score > 0
        status = "[PASS]" if matched == should_match else "[FAIL]"
        print(f"{status} | Score: {score:.3f} | {description}")
        print(f"         Text: '{text}'")
        if matched != should_match:
            print(f"         Expected: {should_match}, Got: {matched}")

def test_multiple_groups_or():
    """Test multiple groups with OR logic between groups."""
    print("\n" + "="*60)
    print("TEST 3: Multiple Groups (OR between groups)")
    print("="*60)
    
    classifier = TopicClassifier()
    
    # Multiple groups, any group matches (OR between groups)
    keyword_groups = {
        "groups": [
            {"type": "or", "keywords": ["fuel", "petrol"]},
            {"type": "and", "keywords": ["subsidy", "removal"]}
        ],
        "require_all_groups": False  # OR between groups
    }
    
    test_cases = [
        ("The fuel price increased", True, "Should match (fuel OR group)"),
        ("Petrol is expensive", True, "Should match (petrol OR group)"),
        ("Subsidy removal announced", True, "Should match (subsidy AND removal group)"),
        ("Subsidy policy", False, "Should NOT match (missing 'removal' in AND group)"),
        ("Electric vehicles", False, "Should NOT match"),
    ]
    
    for text, should_match, description in test_cases:
        score = classifier._match_keyword_groups(text.lower(), keyword_groups)
        matched = score > 0
        status = "[PASS]" if matched == should_match else "[FAIL]"
        print(f"{status} | Score: {score:.3f} | {description}")
        print(f"         Text: '{text}'")
        if matched != should_match:
            print(f"         Expected: {should_match}, Got: {matched}")

def test_multiple_groups_and():
    """Test multiple groups with AND logic between groups."""
    print("\n" + "="*60)
    print("TEST 4: Multiple Groups (AND between groups)")
    print("="*60)
    
    classifier = TopicClassifier()
    
    # Multiple groups, all groups must match (AND between groups)
    keyword_groups = {
        "groups": [
            {"type": "or", "keywords": ["fuel", "petrol"]},
            {"type": "and", "keywords": ["price", "increase"]}
        ],
        "require_all_groups": True  # AND between groups
    }
    
    test_cases = [
        ("The fuel price increased", True, "Should match (fuel OR group AND price/increase AND group)"),
        ("Petrol price went up", True, "Should match (petrol OR group AND price/increase AND group)"),
        ("Fuel is expensive", False, "Should NOT match (missing price/increase AND group)"),
        ("Price increased", False, "Should NOT match (missing fuel/petrol OR group)"),
        ("Fuel subsidy", False, "Should NOT match (missing price/increase AND group)"),
    ]
    
    for text, should_match, description in test_cases:
        score = classifier._match_keyword_groups(text.lower(), keyword_groups)
        matched = score > 0
        status = "[PASS]" if matched == should_match else "[FAIL]"
        print(f"{status} | Score: {score:.3f} | {description}")
        print(f"         Text: '{text}'")
        if matched != should_match:
            print(f"         Expected: {should_match}, Got: {matched}")

def test_backward_compatibility():
    """Test that simple keywords still work (backward compatibility)."""
    print("\n" + "="*60)
    print("TEST 5: Backward Compatibility (Simple Keywords)")
    print("="*60)
    
    classifier = TopicClassifier()
    
    # Test simple keywords (no keyword_groups)
    keywords = ["fuel", "petrol", "diesel"]
    
    test_cases = [
        ("The fuel price increased", True, "Should match 'fuel'"),
        ("Petrol is expensive", True, "Should match 'petrol'"),
        ("Electric vehicles", False, "Should NOT match"),
    ]
    
    for text, should_match, description in test_cases:
        score = classifier._match_simple_keywords(text.lower(), keywords)
        matched = score > 0
        status = "[PASS]" if matched == should_match else "[FAIL]"
        print(f"{status} | Score: {score:.3f} | {description}")
        print(f"         Text: '{text}'")
        if matched != should_match:
            print(f"         Expected: {should_match}, Got: {matched}")

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("KEYWORD AND/OR LOGIC TEST SUITE")
    print("="*60)
    
    try:
        test_or_group()
        test_and_group()
        test_multiple_groups_or()
        test_multiple_groups_and()
        test_backward_compatibility()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        print(f"\n[ERROR] TEST SUITE FAILED: {e}")

if __name__ == "__main__":
    main()

