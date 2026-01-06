"""
Export all topics and their keywords to CSV.
"""

import sys
from pathlib import Path
import csv
import json

# Load topics from JSON
config_dir = Path(__file__).parent.parent / 'config'
topics_file = config_dir / 'master_topics.json'

with open(topics_file, 'r', encoding='utf-8') as f:
    topics_data = json.load(f)
    all_topics = topics_data.get('topics', {})

# Prepare CSV data
csv_data = []
for topic_key, topic_info in all_topics.items():
    keywords = topic_info.get('keywords', [])
    keywords_str = ', '.join(keywords) if keywords else ''
    keywords_count = len(keywords)
    
    csv_data.append({
        'topic_key': topic_key,
        'topic_name': topic_info.get('name', topic_key),
        'category': topic_info.get('category', ''),
        'description': topic_info.get('description', ''),
        'keywords_count': keywords_count,
        'keywords': keywords_str,
        'keywords_list': json.dumps(keywords)  # JSON array for easy parsing
    })

# Sort by topic name
csv_data.sort(key=lambda x: x['topic_name'])

# Write to CSV
output_file = Path(__file__).parent.parent / 'topics_and_keywords.csv'

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['topic_key', 'topic_name', 'category', 'description', 'keywords_count', 'keywords', 'keywords_list']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(csv_data)

print(f"\n{'='*90}")
print(f"Topics and Keywords exported to: {output_file}")
print(f"{'='*90}")
print(f"\nTotal topics: {len(csv_data)}")
print(f"Total keywords across all topics: {sum(d['keywords_count'] for d in csv_data)}")
print(f"\nCSV columns:")
print(f"  - topic_key: Unique identifier")
print(f"  - topic_name: Display name")
print(f"  - category: Topic category")
print(f"  - description: Full description")
print(f"  - keywords_count: Number of keywords")
print(f"  - keywords: Comma-separated keywords (human-readable)")
print(f"  - keywords_list: JSON array of keywords (for parsing)")
print(f"\n[SUCCESS] Export completed!")
















