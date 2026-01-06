"""
Analyze which topic keywords were used in the classifications.
"""

import sys
from pathlib import Path
import csv
import json

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from processing.topic_classifier import TopicClassifier

# Load topics
config_dir = Path(__file__).parent.parent / 'config'
topics_file = config_dir / 'master_topics.json'

with open(topics_file, 'r', encoding='utf-8') as f:
    topics_data = json.load(f)
    all_topics = topics_data.get('topics', {})

# Load CSV results
csv_file = Path(__file__).parent.parent / 'topic_classification_results_100.csv'

print("\n" + "="*90)
print("KEYWORD ANALYSIS - Which Keywords Were Used for Classifications")
print("="*90)

# Track which topics were matched
matched_topics = set()
topic_keyword_matches = {}  # topic -> list of (text, matched_keywords)

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if int(row['topics_found']) > 0:
            topics_json = json.loads(row['topics_json'])
            text_lower = row['text'].lower()
            
            for topic_data in topics_json:
                topic_key = topic_data['topic']
                matched_topics.add(topic_key)
                
                # Get keywords for this topic
                topic_info = all_topics.get(topic_key, {})
                keywords = topic_info.get('keywords', [])
                
                # Find which keywords matched in this text
                matched_keywords = []
                for keyword in keywords:
                    if keyword.lower() in text_lower:
                        matched_keywords.append(keyword)
                
                if topic_key not in topic_keyword_matches:
                    topic_keyword_matches[topic_key] = []
                
                topic_keyword_matches[topic_key].append({
                    'text': row['text'][:100],
                    'matched_keywords': matched_keywords,
                    'keyword_score': topic_data['keyword_score'],
                    'embedding_score': topic_data['embedding_score'],
                    'confidence': topic_data['confidence']
                })

# Show analysis for each matched topic
print(f"\nTopics that were matched: {len(matched_topics)}")
print(f"\n{'='*90}\n")

for topic_key in sorted(matched_topics):
    topic_info = all_topics.get(topic_key, {})
    topic_name = topic_info.get('name', topic_key)
    all_keywords = topic_info.get('keywords', [])
    matches = topic_keyword_matches[topic_key]
    
    print(f"TOPIC: {topic_name} ({topic_key})")
    print(f"  Total Keywords: {len(all_keywords)}")
    print(f"  Times Matched: {len(matches)}")
    print(f"  Keywords: {', '.join(all_keywords[:10])}{'...' if len(all_keywords) > 10 else ''}")
    
    # Show which keywords were actually used
    all_matched_keywords = set()
    for match in matches:
        all_matched_keywords.update(match['matched_keywords'])
    
    print(f"  Keywords That Matched: {', '.join(sorted(all_matched_keywords)) if all_matched_keywords else 'None (embedding-only matches)'}")
    
    # Show examples
    print(f"  Examples ({min(3, len(matches))}):")
    for i, match in enumerate(matches[:3], 1):
        print(f"    {i}. Text: {match['text'][:60]}...")
        print(f"       Matched Keywords: {', '.join(match['matched_keywords']) if match['matched_keywords'] else 'None'}")
        print(f"       Scores: KW={match['keyword_score']:.3f}, Emb={match['embedding_score']:.3f}, Conf={match['confidence']:.3f}")
    
    print()

print("="*90)
print("\n[Summary]")
print(f"  Total topics matched: {len(matched_topics)}")
print(f"  Topics with keyword matches: {sum(1 for k, v in topic_keyword_matches.items() if any(m['matched_keywords'] for m in v))}")
print(f"  Topics with embedding-only matches: {sum(1 for k, v in topic_keyword_matches.items() if not any(m['matched_keywords'] for m in v))}")
















