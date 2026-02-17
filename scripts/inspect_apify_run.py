
import os
import sys
from pathlib import Path
from apify_client import ApifyClient
from dotenv import load_dotenv

# Add src to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Load environment variables
load_dotenv(project_root / 'config' / '.env')
load_dotenv(project_root / '.env')

def inspect_run(run_id):
    api_token = os.getenv('APIFY_API_TOKEN')
    if not api_token:
        print("Error: APIFY_API_TOKEN not found.")
        return

    client = ApifyClient(api_token)
    
    print(f"Inspecting run: {run_id}")
    run = client.run(run_id).get()
    if not run:
        print("Run not found or inaccessible.")
        return
        
    dataset_id = run.get('defaultDatasetId')
    print(f"Dataset ID: {dataset_id}")
    
    dataset_client = client.dataset(dataset_id)
    items = dataset_client.list_items(limit=20).items
    
    print(f"Fetched {len(items)} items.")
    for i, item in enumerate(items):
        print(f"\n--- Item {i+1} ---")
        
        # Check top-level location fields
        print(f"user_location (top-level): {item.get('user_location')}")
        print(f"location (top-level): {item.get('location')}")
        
        # Check Author object
        author = item.get('author')
        if author:
            print(f"Author.location: {author.get('location')}")
            print(f"Author.name: {author.get('name')}")
            print(f"Author.userName: {author.get('userName')}")
        else:
            print("Author object: None")
            
        # Check User object
        user = item.get('user')
        if user:
            print(f"User.location: {user.get('location')}")
        else:
            print("User object: None")
            
        # Check Place object
        place = item.get('place')
        if place:
            print(f"Place: {place}")
        else:
            print("Place: None")

if __name__ == "__main__":
    # Recent run ID from logs
    run_id = "11Zf4dH5KtMUneq4j" 
    if len(sys.argv) > 1:
        run_id = sys.argv[1]
    
    inspect_run(run_id)
