import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processing.topic_classifier import TopicClassifier

def test_topics():
    print("Initializing TopicClassifier...")
    classifier = TopicClassifier()
    print(f"Loaded {len(classifier.master_topics)} topics.")
    
    if "food_prices_market_dynamics" in classifier.master_topics:
        print("Topic 'food_prices_market_dynamics' loaded successfully.")
        print(f"Keywords: {classifier.master_topics['food_prices_market_dynamics'].get('keywords')}")
    else:
        print("CRITICAL: Topic 'food_prices_market_dynamics' NOT FOUND in classifier.")

    
    test_cases = [
        {
            "text": "The price of rice has gone up drastically in the market.",
            "expected": "food_prices_market_dynamics"
        },
        {
            "text": "ASUU has declared another indefinite strike over salary arrears.",
            "expected": "asuu_strikes" # Or education_institutions_agencies depending on weights
        },
        {
            "text": "Bandits kidnapped travelers on the Abuja-Kaduna expressway.",
            "expected_keywords": ["transport_crisis_signals", "counter_insurgency_northwest"]
        },
        {
            "text": "The national grid collapsed again, leaving the whole country in darkness.",
            "expected": "electricity_gen_trans_dist"
        },
        {
            "text": "NIN-SIM linkage deadline has been extended by the NCC.",
            "expected": "digital_id_platforms"
        },
         {
            "text": "Super Eagles qualify for the AFCON finals.",
            "expected": "football_high_sensitivity"
        }
    ]
    
    print(f"\nRunning {len(test_cases)} test cases...")
    
    for i, case in enumerate(test_cases):
        text = case["text"]
        print(f"\nTest {i+1}: {text}")
        
        results = classifier.classify(text)
        
        if not results:
            print("  -> No topics found.")
            continue
            
        top_topic = results[0]
        print(f"  -> Top Topic: {top_topic['topic']} (Conf: {top_topic['confidence']:.2f})")
        
        # Validation
        if "expected" in case:
            if top_topic['topic'] == case["expected"]:
                print("  -> [PASS] Matched expected topic.")
            else:
                print(f"  -> [FAIL] Expected {case['expected']}, got {top_topic['topic']}")
        elif "expected_keywords" in case:
             found = any(r['topic'] in case["expected_keywords"] for r in results)
             if found:
                 print(f"  -> [PASS] Found one of expected keywords.")
             else:
                 print(f"  -> [FAIL] Did not find any of {case['expected_keywords']}")

if __name__ == "__main__":
    test_topics()
