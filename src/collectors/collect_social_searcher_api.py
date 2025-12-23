import requests
import pandas as pd
import os
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import List

def collect_social_searcher_api(queries: List[str], output_file=None, max_pages=5, time_period="last30days"):
    """
    Collect data from Social Searcher using their API instead of scraping.
    
    Args:
        queries: List of queries to search for
        output_file: Path to save the results
        max_pages: Maximum number of pages to fetch per query (default: 5)
        time_period: Time period to search in (default: "last30days")
    """
    load_dotenv()
    
    # API Key - provided by the user
    api_key = os.getenv("SOCIAL_SEARCHER_API_KEY")
    if not api_key:
        raise ValueError("SOCIAL_SEARCHER_API_KEY must be set in .env file")
    
    # Ensure output directory exists
    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        output_file = str(Path(__file__).parent.parent.parent / "data" / "raw" / f"social_searcher_api_data_{today}.csv")
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    all_data = []
    api_url = "https://api.social-searcher.com/v2/search"
    
    # Networks to search in
    networks = ["web"]
    
    # Languages to search in
    languages = ["en", "ar", "in", "ng"]  # English, Arabic, India, Nigeria
    
    # Try each query variation passed as argument
    for query in queries:
        print(f"Searching for query: {query}")
        
        # Try various query formats
        query_formats = [
            query,                  # Regular query
            f'"{query}"',           # Exact phrase matching
        ]
        
        for query_format in query_formats:
            print(f"  Using query format: {query_format}")
            
            # Try each language
            for lang in languages:
                print(f"  Searching in language: {lang}")
                
                # Try each network separately for better results
                for network in networks:
                    print(f"    Searching in network: {network}")
                    
                    # Define parameters for the API request
                    params = {
                        "q": query_format,
                        "limit": 100,        # Maximum allowed limit
                        "network": network,  # Specify network for better results
                        "lang": lang,        # Specify language
                        "period": time_period, # Time period
                        "key": api_key
                    }
                    
                    # For pagination
                    current_page = 0
                    request_id = None
                    has_more_results = True
                    total_posts = 0
                    
                    # Loop through pages
                    while has_more_results and current_page < max_pages:
                        # If we have a request_id (not the first page), update params
                        if request_id is not None:
                            params = {
                                "requestid": request_id,
                                "page": current_page,
                                "limit": 100,
                                "network": network,
                                "lang": lang,
                                "period": time_period,
                                "key": api_key
                            }
                    
                        try:
                            response = requests.get(api_url, params=params)
                            
                            # Debug output
                            safe_url = response.url
                            if api_key:
                                safe_url = safe_url.replace(api_key, 'API_KEY_HIDDEN')
                            print(f"    API URL: {safe_url}")
                            print(f"    Status code: {response.status_code}")
                            
                            if response.status_code == 200:
                                try:
                                    data = response.json()
                                    
                                    # Print response metadata for debugging
                                    if "meta" in data:
                                        print(f"    Response metadata: {data['meta']}")
                                        # Get request_id for pagination
                                        request_id = data["meta"].get("requestid")
                                    
                                    # Process posts data
                                    if "posts" in data and isinstance(data["posts"], list):
                                        posts = data["posts"]
                                        posts_count = len(posts)
                                        total_posts += posts_count
                                        print(f"    Found {posts_count} posts on page {current_page} for query: {query_format} in language: {lang}, network: {network}, period: {time_period}")
                                        
                                        # No more results if we get 0 posts
                                        if posts_count == 0:
                                            has_more_results = False
                                            print(f"    No more results found for this query and network.")
                                            break
                                        
                                        for post in posts:
                                            try:
                                                # Extract relevant information
                                                network_type = post.get("network", "unknown")
                                                
                                                # Determine source type
                                                if network_type == "web":
                                                    source = "News"
                                                    platform = post.get("user", {}).get("name", "unknown")
                                                else:
                                                    source = "Social Media"
                                                    platform = network_type.capitalize()
                                                
                                                # Extract text and URL
                                                text = post.get("text", "unknown")
                                                url = post.get("url", "unknown")
                                                
                                                # Extract date
                                                posted_date = post.get("posted", "unknown")
                                                
                                                # Extract post type
                                                post_type = post.get("type", "unknown")
                                                
                                                # Extract sentiment
                                                sentiment = post.get("sentiment", "unknown")
                                                
                                                # Extract language
                                                language = post.get("lang", "unknown")
                                                
                                                # Determine country (basic heuristic)
                                                country = "us" if ".com" in platform.lower() or "cnn" in platform.lower() else \
                                                        "uk" if ".co.uk" in platform.lower() or "bbc" in platform.lower() else \
                                                        "uae" if ".ae" in platform.lower() or any(src in platform.lower() for src in ["gulfnews", "khaleejtimes", "thenational"]) else \
                                                        "qatar" if ".qa" in platform.lower() or any(src in platform.lower() for src in ["aljazeera", "gulf-times", "qatar-tribune"]) else \
                                                        "unknown"
                                                
                                                # Extract popularity metrics
                                                popularity = post.get("popularity", {})
                                                likes = popularity.get("likes", 0)
                                                comments = popularity.get("comments", 0)
                                                shares = popularity.get("shares", 0)
                                                
                                                # Extract user information
                                                user = post.get("user", {})
                                                user_name = user.get("name", "unknown")
                                                user_url = user.get("url", "unknown")
                                                
                                                # Append to data collection
                                                all_data.append({
                                                    "source": source,
                                                    "platform": platform,
                                                    "type": post_type,
                                                    "post_id": post.get("id", url.split("/")[-1] if url != "unknown" else "unknown"),
                                                    "date": posted_date,
                                                    "text": text,
                                                    "retweets": shares,
                                                    "likes": likes,
                                                    "user_location": user_name,
                                                    "country": country,
                                                    "comments": comments,
                                                    "sentiment": sentiment,
                                                    "language": language,
                                                    "url": url,
                                                    "query": query
                                                })
                                                
                                                # Print brief summary of collected data
                                                # print(f"      Collected: {platform} - {text[:50]}...")
                                                
                                            except Exception as e:
                                                print(f"      Error processing post: {e}")
                                                continue
                                    else:
                                        print(f"    No posts found or unexpected response format for query: {query_format} in language: {lang}, network: {network}")
                                        # Output a sample of the response for debugging
                                        print(f"    Response sample: {str(data)[:500]}...")
                                        has_more_results = False
                                except json.JSONDecodeError:
                                    print(f"    Error decoding JSON response for query: {query_format} in language: {lang}, network: {network}")
                                    print(f"    Response text: {response.text[:500]}...")
                                    has_more_results = False
                            else:
                                print(f"    API request failed with status code {response.status_code}: {response.text[:500]}...")
                                has_more_results = False
                            
                            # Move to the next page
                            current_page += 1
                            
                            # Add small delay between requests to avoid rate limiting
                            time.sleep(2)
                            
                        except Exception as e:
                            print(f"    Error making API request for query '{query_format}' in language: {lang}, network: {network}: {e}")
                            has_more_results = False
                    
                    # Print summary for this query and network
                    print(f"    Total posts collected for '{query_format}' in language: {lang}, network: {network}: {total_posts}")
    
    # Save the collected data
    if all_data:
        df = pd.DataFrame(all_data)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            try:
                existing_df = pd.read_csv(output_file)
                df = pd.concat([existing_df, df], ignore_index=True)
            except pd.errors.EmptyDataError:
                print(f"Warning: The file '{output_file}' is empty. Creating a new file.")
        df.to_csv(output_file, index=False)
        print(f"\nCollected {len(all_data)} total items from Social Searcher API. Saved to '{output_file}'.")
    else:
        print("\nNo items collected.")
        df = pd.DataFrame(columns=["source", "platform", "type", "post_id", "date", "text", "retweets", "likes", "user_location", "country", "comments", "sentiment", "language", "url", "query"])
        df.to_csv(output_file, index=False)
        print(f"Created empty '{output_file}' with headers.")

def main(target_and_variations: List[str]):
    """Main function called by run_collectors. Accepts target/variations list."""
    if not target_and_variations:
        print("[Social Searcher] Error: No target/query variations provided.")
        return
        
    target_name = target_and_variations[0]
    queries = target_and_variations[1:]
    print(f"[Social Searcher] Received Target: {target_name}, Queries: {queries}")
    
    # Call fetch with the passed queries
    posts = collect_social_searcher_api(queries=queries)
    
    if posts:
        df = pd.DataFrame(posts)
        # ... (existing dataframe processing and saving logic) ...
        # Rename/map columns as needed
        df.rename(columns={'text': 'content', 'posted': 'date', 'network': 'platform', 'url': 'post_url', 'query_used': 'query'}, inplace=True)
        # Select/reorder relevant columns
        # df = df[[...relevant columns...]]
        
        today = datetime.now().strftime("%Y%m%d")
        safe_target_name = target_name.replace(" ", "_").lower()
        output_dir = Path(__file__).parent.parent.parent / "data" / "raw"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"social_searcher_{safe_target_name}_{today}.csv"
        
        # ... (append/save logic) ...
        df.to_csv(output_file, index=False, mode='a', header=not output_file.exists())
        print(f"[Social Searcher] Saved/Appended {len(df)} posts to {output_file}")
    else:
        print("[Social Searcher] No posts fetched.")

if __name__ == "__main__":
    print("Running Social Searcher collector directly (without args)... Use run_collectors.py for proper execution.")
    main([]) # Pass empty list 