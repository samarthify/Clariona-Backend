"""
Instagram API Collector using Apify Actors
Collects data from Instagram posts, hashtags, and profiles using working Apify actors.

IMPORTANT NOTES:
1. Instagram scraping supports multiple input types: usernames, hashtags, locations, or search queries.
2. The actors used are:
   - apify/instagram-scraper: Official Instagram scraper (WORKING)
   - curious_coder/instagram-hashtag-scraper: Specialized hashtag scraper (WORKING)

SUPPORTED INPUT TYPES:
✅ VALID (will work):
   - Usernames: "username" or "@username"
   - Hashtags: "#hashtag" or "hashtag"
   - Locations: "location_name"
   - Search queries: "search term"

USAGE:
1. Set APIFY_API_TOKEN in your .env file in the collectors directory
2. Provide Instagram usernames, hashtags, or search terms in your target configuration
3. The actors expect searchTerms format with resultsLimit parameter

EXAMPLE TARGET CONFIGURATION:
{
    "name": "Qatar",
    "sources": {
        "instagram": {
            "actor": "apify/instagram-scraper",
            "params": {
                "searchTerms": ["#qatar", "#doha", "sheikh tamim"],
                "resultsLimit": 50,
                "searchType": "hashtag"
            }
        }
    }
}

LIMITATIONS:
- Instagram's terms of service and robots.txt may restrict scraping
- Some content may be behind login walls
- Rate limiting may apply
- Only public content is accessible
"""

import os
import pandas as pd
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv
from apify_client import ApifyClient
from concurrent.futures import ThreadPoolExecutor, as_completed

# Define Instagram actor configurations
INSTAGRAM_ACTOR_CONFIGS: List[Dict] = [
    {
        "id": "apify/instagram-scraper",  # Official Instagram Scraper
        "name": "Instagram Scraper",
        "type": "general",
        "supports_filters": True,
        "max_results": 100,
        "search_types": ["hashtag", "user", "location", "search"]
    },
    {
        "id": "apify/instagram-hashtag-scraper",  # Official Instagram Hashtag Scraper
        "name": "Instagram Hashtag Scraper",
        "type": "hashtag",
        "supports_filters": False,
        "max_results": 100,
        "search_types": ["hashtag"]
    }
]

def determine_country_from_location(location: str) -> str:
    """Determines a likely country based on location text."""
    country = "unknown"
    if location:
        location_lower = location.lower()
        if any(country in location_lower for country in ["qatar", "doha", "doha"]):
            country = "qatar"
        elif any(country in location_lower for country in ["nigeria", "lagos", "abuja", "kano"]):
            country = "nigeria"
        elif any(country in location_lower for country in ["india", "mumbai", "delhi", "bangalore"]):
            country = "india"
        elif any(country in location_lower for country in ["usa", "united states", "new york", "california"]):
            country = "us"
        elif any(country in location_lower for country in ["uk", "united kingdom", "london", "england"]):
            country = "uk"
        elif any(country in location_lower for country in ["uae", "dubai", "abu dhabi"]):
            country = "uae"
    return country

def determine_country_from_username(username: str) -> str:
    """Determines a likely country based on username patterns."""
    country = "unknown"
    if username:
        username_lower = username.lower()
        if any(country in username_lower for country in ["qatar", "doha", "qa_"]):
            country = "qatar"
        elif any(country in username_lower for country in ["nigeria", "ng_", "lagos", "abuja"]):
            country = "nigeria"
        elif any(country in username_lower for country in ["india", "in_", "mumbai", "delhi"]):
            country = "india"
    return country

def collect_instagram_apify(queries: List[str], output_file=None, max_results=100, search_type="hashtag", 
                          include_comments=True, include_likes=True, **kwargs):
    """
    Collect Instagram data using multiple Apify Actors for the given queries.
    
    Args:
        queries (List[str]): List of query strings to search for (usernames, hashtags, locations).
        output_file: Path to save the results
        max_results: Maximum number of results to fetch per query (default: 100)
        search_type: Type of search to perform (default: "hashtag")
        include_comments: Whether to scrape comments (default: True)
        include_likes: Whether to scrape likes (default: True)
    """
    # Load environment variables from collectors folder
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    
    # API Key from environment variables
    api_token = os.getenv("APIFY_API_TOKEN")
    if not api_token:
        raise ValueError("APIFY_API_TOKEN must be set in .env file")
    
    # Initialize the ApifyClient
    client = ApifyClient(api_token)
    
    # Ensure output directory exists
    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        output_file = str(Path(__file__).parent.parent.parent / "data" / "raw" / f"instagram_apify_data_{today}.csv")
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    all_data = []
    total_collected_count = 0
    
    # Helper function to extract first word from a query for hashtag use
    def extract_hashtag_from_query(query: str) -> str:
        """Extract first word from query to use as hashtag. Removes # and invalid chars."""
        # Remove # if present
        clean_query = query.replace("#", "").strip()
        # Get first word (split by space and take first element)
        first_word = clean_query.split()[0] if clean_query.split() else clean_query
        # Remove invalid characters that Instagram hashtags don't allow
        invalid_chars = "!?.,:;\\-+=*&%$#@/\\~^|<>()[]{}'\"`"
        hashtag = ''.join(char for char in first_word if char not in invalid_chars)
        return hashtag.strip()
    
    # Helper function to check if a query is a valid hashtag (single word, no spaces)
    def is_valid_hashtag(query: str) -> bool:
        """Check if query is a valid hashtag (single word, no spaces, no special chars)."""
        clean_query = query.replace("#", "").strip()
        # Hashtags must be single word, no spaces, and match Instagram's regex pattern
        # Regex: ^[^!?.,:;\-+=*&%$#@/\~^|<>()[\]{}"'`\s]+$
        if not clean_query or " " in clean_query:
            return False
        # Check for invalid characters
        invalid_chars = "!?.,:;\\-+=*&%$#@/\\~^|<>()[]{}'\"`"
        return not any(char in clean_query for char in invalid_chars)
    
    # Helper function to process a single query (runs in parallel)
    def process_single_query(query: str, actor_config: Dict, api_token: str) -> Tuple[List[Dict], int]:
        """Process a single query for a given actor configuration. Returns (data_list, item_count)."""
        # Create a client instance for this thread
        thread_client = ApifyClient(api_token)
        
        actor_id = actor_config["id"]
        actor_name = actor_config["name"]
        actor_type = actor_config["type"]
        max_actor_results = min(max_results, actor_config["max_results"])
        
        query_data = []
        items_count = 0
        
        try:
            print(f"[Instagram Apify - {actor_name}] Starting parallel collection for query: {query}")
            
            # Prepare actor input based on type
            if actor_type == "general":
                run_input = {
                    "search": query,
                    "searchType": search_type,
                    "searchLimit": 10,
                    "resultsType": "posts",
                    "resultsLimit": max_actor_results
                }
            elif actor_type == "hashtag":
                # For multi-word queries, use only the first word as hashtag
                if " " in query or not is_valid_hashtag(query):
                    hashtag = extract_hashtag_from_query(query)
                    if not hashtag:
                        print(f"[Instagram Apify - {actor_name}] Skipping query '{query}' (no valid hashtag could be extracted)")
                        return query_data, items_count
                    print(f"[Instagram Apify - {actor_name}] Using first word '{hashtag}' from multi-word query '{query}' for hashtag search")
                else:
                    hashtag = query.replace("#", "").strip()
                
                if not hashtag:
                    print(f"[Instagram Apify - {actor_name}] Skipping query '{query}' (empty hashtag)")
                    return query_data, items_count
                
                run_input = {
                    "hashtags": [hashtag],
                    "resultsLimit": max_actor_results
                }
            else:
                return query_data, items_count
            
            # Run the actor
            print(f"[Instagram Apify - {actor_name}] Running Apify Actor ({actor_id}) with query: {query}")
            run = thread_client.actor(actor_id).call(run_input=run_input)
            
            # Fetch results from the Actor's dataset
            dataset_id = run["defaultDatasetId"]
            print(f"[Instagram Apify - {actor_name}] Actor run completed for query '{query}'. Dataset ID: {dataset_id}")
            
            # Collect items from the dataset
            for item in thread_client.dataset(dataset_id).iterate_items():
                try:
                    data = _extract_instagram_data(item, query, actor_id, actor_type)
                    if data:
                        query_data.append(data)
                        items_count += 1
                        if items_count % 100 == 0:
                            print(f"[Instagram Apify - {actor_name}] Processed {items_count} items for query '{query}'...")
                except Exception as e:
                    print(f"[Instagram Apify - {actor_name}] Error processing item for query '{query}': {e}")
                    continue
            
            print(f"[Instagram Apify - {actor_name}] Completed query '{query}': Collected {items_count} items")
            
        except Exception as e:
            print(f"[Instagram Apify - {actor_name}] Error running Actor ({actor_id}) for query '{query}': {e}")
        
        return query_data, items_count
    
    # Helper function to process all queries for a single actor in parallel
    def process_actor_queries(actor_config: Dict) -> Tuple[List[Dict], int]:
        """Process all queries for a single actor in parallel. Returns (all_data_list, total_count)."""
        actor_id = actor_config["id"]
        actor_name = actor_config["name"]
        
        print(f"\n--- [Instagram Apify - {actor_name}] Starting PARALLEL collection for {len(queries)} queries ---")
        
        actor_data = []
        actor_collected_count = 0
        
        # Process all queries in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            # Submit all query tasks in parallel
            future_to_query = {
                executor.submit(process_single_query, query, actor_config, api_token): query 
                for query in queries
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    query_data, items_count = future.result()
                    actor_data.extend(query_data)
                    actor_collected_count += items_count
                    print(f"[Instagram Apify - {actor_name}] Query '{query}' completed: {items_count} items")
                except Exception as e:
                    print(f"[Instagram Apify - {actor_name}] Query '{query}' generated an exception: {e}")

        print(f"--- [Instagram Apify - {actor_name}] Finished PARALLEL collection. Collected {actor_collected_count} items. ---")
        return actor_data, actor_collected_count
    
    # Process all actors in parallel, each with their queries running in parallel
    print(f"\n{'='*80}")
    print(f"[Instagram Apify] Starting FULL PARALLEL collection:")
    print(f"  - Actors: {len(INSTAGRAM_ACTOR_CONFIGS)}")
    print(f"  - Queries per actor: {len(queries)}")
    print(f"  - Total parallel operations: {len(INSTAGRAM_ACTOR_CONFIGS) * len(queries)}")
    print(f"{'='*80}\n")
    
    with ThreadPoolExecutor(max_workers=len(INSTAGRAM_ACTOR_CONFIGS)) as actor_executor:
        # Submit all actor tasks in parallel
        actor_futures = {
            actor_executor.submit(process_actor_queries, actor_config): actor_config 
            for actor_config in INSTAGRAM_ACTOR_CONFIGS
        }
        
        # Process completed actors as they finish
        for actor_future in as_completed(actor_futures):
            actor_config = actor_futures[actor_future]
            actor_name = actor_config["name"]
            try:
                actor_data, actor_count = actor_future.result()
                all_data.extend(actor_data)
                total_collected_count += actor_count
                print(f"[Instagram Apify] Actor '{actor_name}' completed: {actor_count} items")
            except Exception as e:
                print(f"[Instagram Apify] Actor '{actor_name}' generated an exception: {e}")
    
    # --- Save Collected Data --- 
    if all_data:
        print(f"\n[Instagram Apify] Total items collected across all actors: {len(all_data)}")
        df = pd.DataFrame(all_data)
        
        # Deduplicate based on post_id or URL
        dedup_key = 'post_id' if 'post_id' in df.columns else 'url'
        if dedup_key in df.columns:
            initial_count = len(df)
            df.drop_duplicates(subset=[dedup_key], keep='first', inplace=True)
            final_count = len(df)
            print(f"[Instagram Apify] Deduplicated {initial_count - final_count} items based on {dedup_key}. Final count: {final_count}")

        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            try:
                existing_df = pd.read_csv(output_file)
                df = pd.concat([existing_df, df], ignore_index=True)
            except pd.errors.EmptyDataError:
                print(f"[Instagram Apify] Warning: The file '{output_file}' is empty. Creating a new file.")
        
        df.to_csv(output_file, index=False)
        print(f"\n[Instagram Apify] Collected {len(all_data)} total Instagram items. Saved to '{output_file}'.")
    else:
        print("\n[Instagram Apify] No Instagram items collected across all actors.")
        # Create empty DataFrame with expected columns
        df = pd.DataFrame(columns=["source", "platform", "type", "post_id", "date", "text", "title", 
                                  "url", "image_url", "domain", "country", "query", "actor_id", "actor_type",
                                  "username", "user_display_name", "likes", "comments", "location"])
        df.to_csv(output_file, index=False)
        print(f"[Instagram Apify] Created empty '{output_file}' with headers.")

def _extract_instagram_data(item: Dict, query: str, actor_id: str, actor_type: str) -> Dict[str, Any]:
    """Extract data from Instagram scraping results."""
    try:
        # Post ID - apify/instagram-scraper uses 'shortCode', fallback to 'id'
        post_id = item.get("shortCode", item.get("id", item.get("shortcode", item.get("pk", "unknown"))))
        
        # Post text/caption - apify/instagram-scraper uses 'caption'
        post_text = item.get("caption", item.get("text", item.get("description", "")))
        
        # Post URL - apify/instagram-scraper uses 'url'
        post_url = item.get("url", item.get("link", item.get("permalink", "")))
        
        # Post date - apify/instagram-scraper uses 'timestamp'
        post_date = item.get("timestamp", item.get("taken_at_timestamp", item.get("date", item.get("created_time", "unknown"))))
        
        # Post type
        post_type = item.get("type", item.get("media_type", "post"))
        
        # Get user information - different actors return different formats
        # apify/instagram-scraper: returns ownerUsername and ownerFullName
        # apify/instagram-hashtag-scraper: only returns ownerId (no username!)
        
        username = item.get("ownerUsername", None)
        user_display_name = item.get("ownerFullName", None)
        owner_id = item.get("ownerId", None)
        
        # If no username but we have ownerId, use that as identifier
        if not username and owner_id:
            username = f"user_{owner_id}"
            user_display_name = f"Instagram User {owner_id}"
        
        # Fallback: try nested owner object (for other scrapers)
        if not username:
            user_info = item.get("owner", item.get("user", {}))
            if isinstance(user_info, dict):
                username = user_info.get("username", user_info.get("name", None))
                user_display_name = user_info.get("fullName", user_info.get("full_name", user_info.get("displayName", username)))
            elif isinstance(user_info, str):
                username = user_info
                user_display_name = user_info
        
        # Additional fallback for top-level username field
        if not username:
            username = item.get("username", "unknown")
            user_display_name = item.get("fullName", username)
        
        # Set display name to username if still not set
        if not user_display_name:
            user_display_name = username
        
        # Get engagement metrics - apify/instagram-scraper uses 'likesCount' and 'commentsCount'
        likes = item.get("likesCount", item.get("likes", item.get("like_count", 0)))
        comments = item.get("commentsCount", item.get("comments", item.get("comment_count", 0)))
        
        # Get media information - apify/instagram-scraper uses 'displayUrl'
        media_url = item.get("displayUrl", "")
        
        # Fallback to other image formats
        if not media_url:
            images = item.get("images", [])
            if isinstance(images, str):
                media_url = images
            elif isinstance(images, list) and images:
                media_url = images[0].get("url", "") if isinstance(images[0], dict) else str(images[0])
            elif item.get("thumbnail_url"):
                media_url = item.get("thumbnail_url")
        
        # Try videos if no image
        if not media_url:
            videos = item.get("videos", [])
            if videos:
                media_url = videos[0].get("url", "") if isinstance(videos[0], dict) else str(videos[0])
        
        # Get location information - apify/instagram-scraper uses 'locationName' as string
        location_name = item.get("locationName", "")
        
        # Fallback to nested location object
        if not location_name:
            location_info = item.get("location", {})
            if isinstance(location_info, dict):
                location_name = location_info.get("name", location_info.get("locationName", ""))
            elif isinstance(location_info, str):
                location_name = location_info
        
        # Determine country from location, username, or query
        country = "unknown"
        if location_name:
            country = determine_country_from_location(location_name)
        if country == "unknown" and username and username != "unknown":
            country = determine_country_from_username(username)
        # Fallback: determine from query
        if country == "unknown" and query:
            query_lower = query.lower()
            if "qatar" in query_lower or "doha" in query_lower:
                country = "qatar"
            elif "nigeria" in query_lower or "tinubu" in query_lower or "peter obi" in query_lower or "lagos" in query_lower:
                country = "nigeria"
        
        return {
            "source": "Instagram",
            "platform": "Instagram",
            "type": post_type,
            "post_id": post_id,
            "date": post_date,
            "text": post_text,
            "title": f"Post by {user_display_name}",
            "url": post_url,
            "image_url": media_url,
            "domain": "instagram.com",
            "country": country,
            "query": query,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "username": username,
            "user_display_name": user_display_name,
            "likes": likes,
            "comments": comments,
            "location": location_name
        }
    except Exception as e:
        print(f"Error extracting Instagram data: {e}")
        return None

def main(target_and_variations: List[str], user_id: str = None):
    """Main function called by run_collectors. Accepts target/variations list."""
    if not target_and_variations:
        print("[Instagram Apify] Error: No target/query variations provided.")
        return
        
    target_name = target_and_variations[0]
    queries = target_and_variations[1:]
    print(f"[Instagram Apify] Received Target: {target_name}, Queries: {queries}")
    
    # Construct output file name
    today = datetime.now().strftime("%Y%m%d")
    safe_target_name = target_name.replace(" ", "_").lower()
    output_path = Path(__file__).parent.parent.parent / "data" / "raw" / f"instagram_apify_{safe_target_name}_{today}.csv"
    
    # Call the collection function with the queries
    collect_instagram_apify(queries=queries, output_file=str(output_path))

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Collect Instagram data using Apify')
    parser.add_argument('--queries', type=str, required=False, help='JSON string of query variations')
    parser.add_argument('--since', type=str, help='Start date in format YYYY-MM-DD_HH:MM:SS_UTC (for incremental collection)')
    parser.add_argument('--until', type=str, help='End date in format YYYY-MM-DD_HH:MM:SS_UTC (for incremental collection)')
    
    args = parser.parse_args()
    
    if args.queries:
        try:
            # Parse the JSON string to get the list of queries
            queries_list = json.loads(args.queries)
            print(f"[Instagram Apify] Parsed queries: {queries_list}")
            
            # Use incremental dates if provided
            if args.since or args.until:
                print(f"[Instagram Apify] Using incremental collection: {args.since} to {args.until}")
                kwargs = {}
                if args.since:
                    kwargs['since_date'] = args.since
                if args.until:
                    kwargs['until_date'] = args.until
                collect_instagram_apify(queries=queries_list, **kwargs)
            else:
                main(queries_list)
        except json.JSONDecodeError as e:
            print(f"[Instagram Apify] Error parsing queries JSON: {e}")
            main([])
    else:
        print("Running Instagram Apify collector directly (without args)... Use run_collectors.py for proper execution.")
        main([])  # Pass empty list for direct run scenario

