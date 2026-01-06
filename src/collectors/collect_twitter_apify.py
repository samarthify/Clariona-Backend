import os
import pandas as pd
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv
from apify_client import ApifyClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.config.config_manager import ConfigManager

# Define actor configurations
ACTOR_CONFIGS: List[Dict] = [
    {
        "id": "CJdippxWmn9uRfooo",  # Original actor ID (kaitoeasyapi)
        "input_type_key": "queryType",
        "supports_filters": True,
        "date_param_format": "since_until",  # Uses "since" and "until" parameters
        "name": "Original Actor"
    },
    {
        "id": "nfp1fpt5gUlBwPcor",  # New actor ID (apidojo/twitter-scraper-lite)
        "input_type_key": "sort",
        "supports_filters": True,
        "date_param_format": "start_end",  # Uses "start" and "end" parameters
        "name": "New Actor"
    }
]

def collect_twitter_apify(queries: List[str], output_file=None, max_items=None, query_type="Latest", language="en", **kwargs):
    """
    Collect Twitter/X data using the Apify API for the given queries, trying multiple actors.
    
    Args:
        queries (List[str]): List of query strings to search for.
        output_file: Path to save the results
        max_items: Maximum number of items to fetch per query (default: 100)
        query_type: Type of query to run (default: "Latest")
        language: Language of tweets to search for (default: "en")
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
    
    # Get default max_items from ConfigManager if not provided
    if max_items is None:
        from src.config.config_manager import ConfigManager
        config = ConfigManager()
        max_items = config.get_int("collectors.twitter.default_max_items", 100)
    
    # Get keywords from ConfigManager (enables DB editing)
    # Priority: 1) ConfigManager default, 2) queries parameter, 3) hardcoded defaults
    from src.config.config_manager import ConfigManager
    config = ConfigManager()
    
    # Try to get target name from queries if available (for target-specific keywords)
    target_name = None
    if queries and len(queries) > 0:
        # First element might be target name
        target_name = queries[0].lower().replace(" ", "_") if queries else None
    
    # Priority 1: Target-specific keywords from ConfigManager (if target name available)
    if target_name:
        target_key = f"collectors.keywords.{target_name}.twitter"
        target_keywords = config.get_list(target_key, None)
        if target_keywords:
            print(f"[Twitter Apify] Using target-specific keywords from ConfigManager: {target_keywords}")
            queries = target_keywords
    
    # Priority 2: Default keywords from ConfigManager (enables DB editing)
    if not queries:
        default_keywords = config.get_list("collectors.keywords.default.twitter", None)
        if default_keywords:
            print(f"[Twitter Apify] Using default keywords from ConfigManager: {default_keywords}")
            queries = default_keywords
    
    # Priority 3: Use queries parameter as-is (if provided)
    # Priority 4: Hardcoded fallback (last resort)
    if not queries:
        print("[Twitter Apify] Using hardcoded default keywords - consider configuring in ConfigManager/DB")
        queries = ["qatar", "nigeria", "india", "politics", "news"]
    
    # Ensure output directory exists
    if output_file is None:
        from src.config.path_manager import PathManager
        path_manager = PathManager()
        today = datetime.now().strftime("%Y%m%d")
        output_file = str(path_manager.data_raw / f"twitter_apify_data_{today}.csv")
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Date range for search - Can be overridden for incremental collection
    # Get defaults from ConfigManager
    config = ConfigManager()
    default_date_range_days = config.get_int("collectors.apify.default_date_range_days", 7)
    default_since_date = config.get("collectors.apify.default_since_date", "2021-01-01_00:00:00_UTC")
    
    if 'since_date' not in kwargs and 'until_date' not in kwargs:
        # Default to configured number of days if not specified
        since_date = (datetime.now(timezone.utc) - timedelta(days=default_date_range_days)).strftime("%Y-%m-%d_%H:%M:%S_UTC")
        until_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H:%M:%S_UTC")
    else:
        since_date = kwargs.get('since_date', default_since_date)
        until_date = kwargs.get('until_date', datetime.now(timezone.utc).strftime("%Y-%m-%d_%H:%M:%S_UTC"))
    
    all_data = []
    total_collected_count = 0
    
    # Helper function to process a single query (runs in parallel)
    def process_single_query(query: str, actor_config: Dict, since_date: str, until_date: str, api_token: str) -> Tuple[List[Dict], int]:
        """Process a single query for a given actor configuration. Returns (data_list, item_count)."""
        # Create a client instance for this thread
        thread_client = ApifyClient(api_token)
        
        actor_id = actor_config["id"]
        actor_name = actor_config["name"]
        input_type_key = actor_config["input_type_key"]
        supports_filters = actor_config["supports_filters"]
        
        query_data = []
        items_count = 0
        
        try:
            print(f"[Twitter Apify - {actor_name}] Starting parallel collection for query: {query}")
            
            # Create search terms (base query)
            search_terms = [query]
            
            # Prepare the base Actor input
            run_input = {
                "searchTerms": search_terms,
                "maxItems": max_items,
                input_type_key: query_type, # Use the correct key for this actor
                "lang": language,
            }

            # Add filter parameters only if the actor supports them
            if supports_filters:
                date_param_format = actor_config.get("date_param_format", "since_until")
                
                if date_param_format == "start_end":
                    # For apidojo/twitter-scraper-lite: use "start" and "end" parameters
                    # Convert date format from "YYYY-MM-DD_HH:MM:SS_UTC" to YYYY-MM-DD format
                    # The actor expects String format in YYYY-MM-DD format
                    start_date_formatted = since_date.split("_")[0] if "_" in since_date else since_date.split("T")[0]
                    end_date_formatted = until_date.split("_")[0] if "_" in until_date else until_date.split("T")[0]
                    
                    run_input.update({
                        "start": start_date_formatted,  # Format: YYYY-MM-DD
                        "end": end_date_formatted,      # Format: YYYY-MM-DD
                    })
                    print(f"[Twitter Apify - {actor_name}] Using date parameters: start={start_date_formatted}, end={end_date_formatted}")
                else:
                    # For original actor: use "since" and "until" parameters
                    # Get filter defaults from ConfigManager
                    config = ConfigManager()
                    run_input.update({
                        "since": since_date,
                        "until": until_date,
                        "filter:verified": config.get_bool("collectors.apify.twitter.filter_verified", False),
                        "filter:blue_verified": config.get_bool("collectors.apify.twitter.filter_blue_verified", False),
                        "filter:nativeretweets": config.get_bool("collectors.apify.twitter.filter_nativeretweets", False),
                        "include:nativeretweets": config.get_bool("collectors.apify.twitter.include_nativeretweets", False),
                        "filter:replies": config.get_bool("collectors.apify.twitter.filter_replies", False),
                        "filter:quote": config.get_bool("collectors.apify.twitter.filter_quote", False),
                        "min_retweets": config.get_int("collectors.apify.twitter.min_retweets", 0),
                        "min_faves": config.get_int("collectors.apify.twitter.min_faves", 0),
                        "min_replies": config.get_int("collectors.apify.twitter.min_replies", 0),
                        "filter:media": config.get_bool("collectors.apify.twitter.filter_media", False),
                        "filter:images": config.get_bool("collectors.apify.twitter.filter_images", False),
                        "filter:videos": config.get_bool("collectors.apify.twitter.filter_videos", False),
                    })
                    # Update search terms for actors supporting date filters
                    run_input["searchTerms"] = [f"{query} since:{since_date} until:{until_date}"]
            
            print(f"[Twitter Apify - {actor_name}] Running Apify Actor ({actor_id}) with query: {query}")
            # Run the Actor and wait for it to finish
            run = thread_client.actor(actor_id).call(run_input=run_input)
            
            # Fetch results from the Actor's dataset
            if run is None:
                return query_data, items_count
            dataset_id = run.get("defaultDatasetId")
            if dataset_id is None:
                return query_data, items_count
            print(f"[Twitter Apify - {actor_name}] Actor run completed for query '{query}'. Dataset ID: {dataset_id}")
            
            # Collect items from the dataset
            for item in thread_client.dataset(dataset_id).iterate_items():
                try:
                    # Extract relevant information - updated based on actual API response structure
                    tweet_id = item.get("id", "unknown")
                    
                    # Get user information
                    author = item.get("author", {})
                    user_name = author.get("userName", "unknown")
                    user_display_name = author.get("name", "unknown")
                    user_avatar = author.get("profilePicture", "unknown")
                    user_location = author.get("location", "unknown")
                    
                    # Get tweet content
                    text = item.get("text", item.get("fullText", "unknown")) # Try both text and fullText
                    created_at = item.get("createdAt", "unknown")
                    
                    # Get engagement metrics
                    retweets = item.get("retweetCount", 0)
                    likes = item.get("likeCount", 0)
                    reply_count = item.get("replyCount", 0)
                    quote_count = item.get("quoteCount", 0)
                    view_count = item.get("viewCount", 0)
                    
                    # Get tweet URL
                    url = item.get("url", item.get("twitterUrl", "unknown")) # Try both url and twitterUrl
                    
                    # Get tweet type information (handle variations)
                    is_reply = item.get("isReply", False)
                    # Check for both structures for retweet/quote status
                    is_retweet = item.get("isRetweet", "retweeted_tweet" in item and item.get("retweeted_tweet") is not None)
                    is_quote = item.get("isQuote", "quoted_tweet" in item and item.get("quoted_tweet") is not None)

                    # Determine country (basic heuristic based on location)
                    country = "unknown"
                    if user_location and "qatar" in user_location.lower():
                        country = "qatar"
                    elif user_location and any(country in user_location.lower() for country in ["usa", "united states"]):
                        country = "us"
                    elif user_location and any(country in user_location.lower() for country in ["uk", "united kingdom"]):
                        country = "uk"
                    elif user_location and any(country in user_location.lower() for country in ["nigeria"]):
                        country = "nigeria"
                    elif user_location and any(country in user_location.lower() for country in ["india"]):
                        country = "india"
                    
                    # Append to data collection
                    query_data.append({
                        "source": "X",
                        "platform": "X",
                        "type": "post",
                        "post_id": tweet_id,
                        "date": created_at,
                        "text": text,
                        "retweets": retweets,
                        "likes": likes,
                        "user_location": user_location,
                        "country": country,
                        "comments": reply_count,  # Using reply count as comments
                        "user_display_name": user_display_name,
                        "user_name": user_name,
                        "user_avatar": user_avatar,
                        "reply_count": reply_count,
                        "quote_count": quote_count,
                        "view_count": view_count,
                        "is_reply": is_reply,
                        "is_retweet": is_retweet,
                        "is_quote": is_quote,
                        "url": url,
                        "query": query,
                        "actor_id": actor_id # Add actor ID for tracking
                    })
                    
                    items_count += 1
                    if items_count % 100 == 0:
                        print(f"[Twitter Apify - {actor_name}] Processed {items_count} items for query '{query}'...")
                    
                except Exception as e:
                    print(f"[Twitter Apify - {actor_name}] Error processing item for query '{query}': {e}")
                    continue
            
            print(f"[Twitter Apify - {actor_name}] Completed query '{query}': Collected {items_count} items")
            
        except Exception as e:
            print(f"[Twitter Apify - {actor_name}] Error running Actor ({actor_id}) for query '{query}': {e}")
        
        return query_data, items_count
    
    # Helper function to process all queries for a single actor in parallel
    def process_actor_queries(actor_config: Dict) -> Tuple[List[Dict], int]:
        """Process all queries for a single actor in parallel. Returns (all_data_list, total_count)."""
        actor_id = actor_config["id"]
        actor_name = actor_config["name"]
        
        print(f"\n--- [Twitter Apify - {actor_name}] Starting PARALLEL collection for {len(queries)} queries ---")
        
        actor_data = []
        actor_collected_count = 0
        
        # Process all queries in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            # Submit all query tasks in parallel
            future_to_query = {
                executor.submit(process_single_query, query, actor_config, since_date, until_date, api_token): query 
                for query in queries
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    query_data, items_count = future.result()
                    actor_data.extend(query_data)
                    actor_collected_count += items_count
                    print(f"[Twitter Apify - {actor_name}] Query '{query}' completed: {items_count} items")
                except Exception as e:
                    print(f"[Twitter Apify - {actor_name}] Query '{query}' generated an exception: {e}")

        print(f"--- [Twitter Apify - {actor_name}] Finished PARALLEL collection. Collected {actor_collected_count} items. ---")
        return actor_data, actor_collected_count
    
    # Process all actors in parallel, each with their queries running in parallel
    print(f"\n{'='*80}")
    print(f"[Twitter Apify] Starting FULL PARALLEL collection:")
    print(f"  - Actors: {len(ACTOR_CONFIGS)}")
    print(f"  - Queries per actor: {len(queries)}")
    print(f"  - Total parallel operations: {len(ACTOR_CONFIGS) * len(queries)}")
    print(f"{'='*80}\n")
    
    with ThreadPoolExecutor(max_workers=len(ACTOR_CONFIGS)) as actor_executor:
        # Submit all actor tasks in parallel
        actor_futures = {
            actor_executor.submit(process_actor_queries, actor_config): actor_config 
            for actor_config in ACTOR_CONFIGS
        }
        
        # Process completed actors as they finish
        for actor_future in as_completed(actor_futures):
            actor_config = actor_futures[actor_future]
            actor_name = actor_config["name"]
            try:
                actor_data, actor_count = actor_future.result()
                all_data.extend(actor_data)
                total_collected_count += actor_count
                print(f"[Twitter Apify] Actor '{actor_name}' completed: {actor_count} items")
            except Exception as e:
                print(f"[Twitter Apify] Actor '{actor_name}' generated an exception: {e}")

    # Save the collected data
    if all_data:
        df = pd.DataFrame(all_data)
        df.drop_duplicates(subset=['post_id'], keep='first', inplace=True) # Deduplicate based on tweet ID
        
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            try:
                existing_df = pd.read_csv(output_file)
                df = pd.concat([existing_df, df], ignore_index=True)
            except pd.errors.EmptyDataError:
                print(f"Warning: The file '{output_file}' is empty. Creating a new file.")
        df.to_csv(output_file, index=False)
        print(f"[Twitter Apify] Collected {total_collected_count} total tweets. Saved to '{output_file}'.")
    else:
        print("[Twitter Apify] No tweets collected.")
        df = pd.DataFrame(columns=["source", "platform", "type", "post_id", "date", "text", "retweets", "likes", 
                                  "user_location", "country", "comments", "user_display_name", "user_name", 
                                  "user_avatar", "reply_count", "quote_count", "view_count", "is_reply", 
                                  "is_retweet", "is_quote", "url", "query", "actor_id"]) # Add actor_id to empty df
        df.to_csv(output_file, index=False)
        print(f"[Twitter Apify] Created empty '{output_file}' with headers.")
    
    return total_collected_count  # Return count for tracking

def main(target_and_variations: List[str]):
    """Main function called by run_collectors. Accepts target/variations list."""
    if not target_and_variations:
         print("[Twitter Apify] Error: No target/query variations provided.")
         return

    target_name = target_and_variations[0]
    queries = target_and_variations[1:]
    print(f"[Twitter Apify] Received Target: {target_name}, Queries: {queries}")

    # Construct output file name using target name
    from src.config.path_manager import PathManager
    path_manager = PathManager()
    today = datetime.now().strftime("%Y%m%d")
    safe_target_name = target_name.replace(" ", "_").lower()
    output_path = path_manager.data_raw / f"twitter_apify_{safe_target_name}_{today}.csv"

    # Call the collection function with the queries
    collect_twitter_apify(queries=queries, output_file=str(output_path))

def collect_twitter_apify_with_dates(queries: List[str], output_file: Optional[str] = None, max_items: int = 100, 
                                     query_type: str = "Latest", language: str = "en",
                                     since_date: Optional[str] = None, until_date: Optional[str] = None) -> int:
    """
    Wrapper function that explicitly accepts date parameters for incremental collection.
    
    Args:
        queries: List of search queries
        output_file: Output file path
        max_items: Maximum items to collect
        query_type: Query type (Latest, Top, etc.)
        language: Language filter
        since_date: Start date in format "YYYY-MM-DD_HH:MM:SS_UTC"
        until_date: End date in format "YYYY-MM-DD_HH:MM:SS_UTC"
        
    Returns:
        Number of records collected
    """
    kwargs = {}
    if since_date:
        kwargs['since_date'] = since_date
    if until_date:
        kwargs['until_date'] = until_date
    
    return collect_twitter_apify(
        queries=queries,
        output_file=output_file,
        max_items=max_items,
        query_type=query_type,
        language=language,
        **kwargs
    )


if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Collect Twitter data using Apify')
    parser.add_argument('--queries', type=str, required=False, help='JSON string of query variations')
    parser.add_argument('--since', type=str, help='Start date in format YYYY-MM-DD_HH:MM:SS_UTC (for incremental collection)')
    parser.add_argument('--until', type=str, help='End date in format YYYY-MM-DD_HH:MM:SS_UTC (for incremental collection)')
    
    args = parser.parse_args()
    
    if args.queries:
        try:
            # Parse the JSON string to get the list of queries
            queries_list = json.loads(args.queries)
            print(f"[Twitter Apify] Parsed queries: {queries_list}")
            
            # Use incremental dates if provided
            if args.since or args.until:
                print(f"[Twitter Apify] Using incremental collection: {args.since} to {args.until}")
                collect_twitter_apify_with_dates(
                    queries=queries_list,
                    since_date=args.since,
                    until_date=args.until
                )
            else:
                main(queries_list)
        except json.JSONDecodeError as e:
            print(f"[Twitter Apify] Error parsing queries JSON: {e}")
            main([])
    else:
        print("[Twitter Apify] Running Twitter Apify collector directly (without args)... Use run_collectors.py for proper execution.")
        main([]) 
