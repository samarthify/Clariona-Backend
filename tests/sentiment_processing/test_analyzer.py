#!/usr/bin/env python3
"""
Test script to verify the enhanced Presidential Sentiment Analyzer works correctly.
"""

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.append(str(Path(__file__).parent / "src"))

from processing.presidential_sentiment_analyzer import PresidentialSentimentAnalyzer

def test_analyzer():
    """Test the enhanced analyzer with sample texts."""
    
    # Initialize analyzer
    analyzer = PresidentialSentimentAnalyzer()
    
    # Test cases
    test_cases = [
        {
            'text': 'The President announced new fuel subsidy reforms that will help reduce government spending and improve economic stability.',
            'expected_ministry': 'energy',
            'description': 'Fuel subsidy policy announcement'
        },
        {
            'text': 'Security forces successfully rescued kidnapped victims in Kaduna state, showing improved security measures.',
            'expected_ministry': 'defense',
            'description': 'Security success story'
        },
        {
            'text': 'The government launched a new youth employment program to address unemployment among young people.',
            'expected_ministry': 'labor',
            'description': 'Youth employment initiative'
        },
        {
            'text': 'Healthcare workers protested against poor working conditions and lack of medical supplies.',
            'expected_ministry': 'health',
            'description': 'Healthcare worker protest'
        },
        {
            'text': 'Celebrity wedding trends on social media with beautiful decorations and fashion.',
            'expected_ministry': 'general',
            'description': 'Non-political content'
        }
    ]
    
    print("Testing Enhanced Presidential Sentiment Analyzer")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['description']}")
        print(f"Text: {test_case['text'][:100]}...")
        
        try:
            # Analyze the text
            result = analyzer.analyze(test_case['text'])
            
            # Display results
            print(f"✅ Sentiment: {result['sentiment_label']} (score: {result['sentiment_score']:.2f})")
            print(f"✅ Issue Label: {result['issue_label']}")
            print(f"✅ Issue Slug: {result['issue_slug']}")
            print(f"✅ Issue Confidence: {result['issue_confidence']:.2f}")
            print(f"✅ Ministry Hint: {result['ministry_hint']}")
            print(f"✅ Keywords: {result['issue_keywords'][:5]}")  # Show first 5 keywords
            print(f"✅ Embedding Length: {len(result['embedding'])}")
            print(f"✅ Embedding Sample: {result['embedding'][:3]}...")  # Show first 3 values
            
            # Check ministry prediction
            if result['ministry_hint'] == test_case['expected_ministry']:
                print(f"✅ Ministry prediction CORRECT: {result['ministry_hint']}")
            else:
                print(f"⚠️  Ministry prediction: {result['ministry_hint']} (expected: {test_case['expected_ministry']})")
            
            # Check embedding validity
            if len(result['embedding']) == 1536:
                print("✅ Embedding dimension correct (1536)")
            else:
                print(f"❌ Embedding dimension incorrect: {len(result['embedding'])}")
            
        except Exception as e:
            print(f"❌ Error analyzing text: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed!")

if __name__ == "__main__":
    test_analyzer()
