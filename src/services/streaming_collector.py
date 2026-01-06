
import os
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv
from apify_client import ApifyClientAsync

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'collectors', '.env'))

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")

if not APIFY_TOKEN:
    print("Error: APIFY_API_TOKEN not found in .env")
    exit(1)

async def stream_actor_results(actor_id: str, run_input: dict):
    """
    Starts an actor run and streams its dataset items as they are generated.
    """
    client = ApifyClientAsync(APIFY_TOKEN)
    
    print(f"[{datetime.now()}] Starting actor {actor_id} run...")
    # Start the run asynchronously (wait_secs=0 means don't wait for finish)
    run = await client.actor(actor_id).call(run_input=run_input, wait_secs=0)
    
    if not run:
        print("Failed to start run.")
        return

    run_id = run['id']
    dataset_id = run['defaultDatasetId']
    print(f"[{datetime.now()}] Run started: {run_id}")
    print(f"[{datetime.now()}] Streaming from Dataset: {dataset_id}")

    dataset_client = client.dataset(dataset_id)
    
    # Streaming loop
    # Note: stream_items() streams the *current* items. 
    # For a running actor, we might need to handle the stream closing and reopening 
    # or use a polling approach if stream_items closes when it hits current EOF.
    # The Apify docs say "stream_items" downloads the dataset. 
    # Let's test if it blocks for new items or just finishes.
    # If it finishes, we wrap it in a loop until the run is finished.
    
    processed_ids = set()
    is_running = True
    
    while is_running:
        # Check run status periodically
        run_info = await client.run(run_id).get()
        if run_info['status'] in ['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT']:
            is_running = False
            print(f"[{datetime.now()}] Run status: {run_info['status']}")
        
        # Stream items (this might just get current items)
        # We use an async for loop. 
        # If stream_items returns immediately, we need to track offset or IDs.
        # But stream_items is a download method.
        # Let's try iterating.
        
        try:
           async with dataset_client.stream_items() as stream:
               async for item in stream:
                   # In a real stream, 'item' might be bytes or dict depending on client
                   # The user example showed bytes_chunk processing. 
                   # standard stream_items() usually yields dicts if using the high-level client?
                   # Wait, the user example used log_client.stream().
                   # dataset_client.stream_items() returns an iterator of items if using the sync client helper,
                   # but the AsyncClient returns a stream context.
                   
                   # Let's assume it yields chunks of bytes (NDJSON or JSON array parts).
                   # Handling raw bytes manually is complex.
                   # Alternative: Use list_items with pagination for simplicity and robustness.
                   pass
        except Exception as e:
            pass

        # For this prototype, let's use the robust OFFSET method which simulates streaming
        # and is guaranteed to work with running actors.
        
        # ... (Switching to Offset Polling implementation for the prototype to ensure it works) ...
        # If the user INSISTS on stream_items, we can try it, but offset is safer for "tailing".
        # Let's try to implement a pure asyncio stream using dataset_client.stream_items() if we can confirm behavior.
        # But for now, let's use list_items(offset=...) as it's the standard pattern for "tailing" a dataset.
        
        pass 
        
    print(f"[{datetime.now()}] Stream finished.")

async def stream_with_polling(actor_id: str, run_input: dict):
    """
    Robust streaming using offset polling.
    """
    client = ApifyClientAsync(APIFY_TOKEN)
    print(f"[{datetime.now()}] Starting actor {actor_id}...")
    run = await client.actor(actor_id).call(run_input=run_input, wait_secs=0)
    
    run_id = run['id']
    dataset_id = run['defaultDatasetId']
    dataset_client = client.dataset(dataset_id)
    
    offset = 0
    limit = 100
    is_running = True
    
    print(f"[{datetime.now()}] Tailing dataset {dataset_id}...")
    
    while is_running:
        # Fetch status
        run_details = await client.run(run_id).get()
        status = run_details['status']
        if status in ['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT']:
            is_running = False
        
        # Fetch new items
        result = await dataset_client.list_items(offset=offset, limit=limit)
        items = result.items
        
        if items:
            print(f"[{datetime.now()}] Received {len(items)} new items.")
            for item in items:
                # Process item (e.g., print title/id)
                print(f"  - Item: {item.get('title', 'No Title')[:30]}... ({item.get('url', 'No URL')})")
            
            offset += len(items)
        else:
            if is_running:
                # Wait before next poll if no new items
                await asyncio.sleep(5)
        
        # If run finished, do one final check to ensure we got everything
        if not is_running:
             # Final poll
             result = await dataset_client.list_items(offset=offset, limit=limit)
             if result.items:
                 print(f"[{datetime.now()}] Final catch-up: {len(result.items)} items.")
                 offset += len(result.items)
                 
    print(f"[{datetime.now()}] Run {status}. Total items streamed: {offset}")


if __name__ == "__main__":
    # Switching to Twitter Scraper Lite (nfp1fpt5gUlBwPcor) as News Scraper requires rental
    actor_id = "nfp1fpt5gUlBwPcor" 
    run_input = {
        "searchTerms": ["AI technology"],
        "maxItems": 20,
        "sort": "Latest"
    }
    
    try:
        asyncio.run(stream_with_polling(actor_id, run_input))
    except KeyboardInterrupt:
        print("\nStopped.")
