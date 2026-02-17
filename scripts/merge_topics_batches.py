import json
import os
from datetime import datetime
from pathlib import Path

def merge_batches():
    base_dir = Path("config")
    master_path = base_dir / "master_topics.json"
    
    # Load master topics
    with open(master_path, 'r') as f:
        master_data = json.load(f)
    
    initial_count = len(master_data.get("topics", {}))
    print(f"Initial topic count: {initial_count}")
    
    # List of batch files
    batch_files = [
        "education_topics_batch.json",
        "agriculture_topics_batch.json",
        "health_topics_batch.json",
        "transport_topics_batch.json",
        "youth_topics_batch.json",
        "finance_topics_batch.json",
        "interior_topics_batch.json",
        "power_topics_batch.json",
        "communications_topics_batch.json",
        "defence_topics_batch.json"
    ]
    
    merged_count = 0
    for batch_file in batch_files:
        path = base_dir / batch_file
        if not path.exists():
            print(f"Warning: {batch_file} not found")
            continue
            
        with open(path, 'r') as f:
            batch_data = json.load(f)
            
        # Merge into master
        for key, value in batch_data.items():
            master_data["topics"][key] = value
            merged_count += 1
            
        print(f"Merged {len(batch_data)} topics from {batch_file}")

    # Update metadata
    master_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    
    # Save master topics
    with open(master_path, 'w') as f:
        json.dump(master_data, f, indent=4)
        
    final_count = len(master_data["topics"])
    print(f"\nFinal topic count: {final_count}")
    print(f"Total new/updated topics merged: {merged_count}")
    print(f"Master topics updated at {master_path}")

if __name__ == "__main__":
    merge_batches()
