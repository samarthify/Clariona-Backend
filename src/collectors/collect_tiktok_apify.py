"""
TikTok API Collector using Apify Actors
Collects data from TikTok videos, hashtags, and users using working Apify actors.

IMPORTANT NOTES:
1. TikTok scraping supports hashtag-based searches using working Apify actors.
2. The actors used are:
   - clockworks/tiktok-scraper: Working TikTok scraper
   - clockworks/free-tiktok-scraper: Free TikTok scraper

ACTOR PARAMETERS (clockworks/tiktok-scraper):
Core Parameters:
  - hashtags: Array of hashtags (without # symbol)
  - resultsPerPage: Number of videos per hashtag (default: 1)
  - profiles: Array of TikTok usernames
  - searchQueries: Array of search keywords
  - postURLs: Array of direct TikTok video URLs
Date Filtering:
  - oldestPostDateUnified: Scrape videos published after this date
    Can be date string (YYYY-MM-DD) or number of days (1 = today, 2 = yesterday+today)
  - newestPostDate: Scrape videos published before this date (YYYY-MM-DD format)
Profile Options:
  - profileScrapeSections: ["videos"] or ["reposts"]
  - profileSorting: "latest" (default), "popular", or "oldest"
  - excludePinnedPosts: boolean (default: false)

SUPPORTED INPUT TYPES:
✅ VALID (will work):
   - Hashtags: "#hashtag" or "hashtag" (automatically cleaned)
   - Clean hashtags without # symbol
   - Keywords for search mode

USAGE:
1. Set APIFY_API_TOKEN in your .env file in the collectors directory
2. Provide TikTok hashtags in your target configuration
3. The actor expects: hashtags, resultsPerPage, oldestPostDateUnified, newestPostDate

EXAMPLE TARGET CONFIGURATION:
{
    "name": "Nigeria",
    "sources": {
        "tiktok": {
            "actor": "clockworks/tiktok-scraper",
            "params": {
                "hashtags": ["nigeria", "tinubu", "lagos"],
                "resultsPerPage": 50
            }
        }
    }
}

LIMITATIONS:
- TikTok's terms of service and robots.txt may restrict scraping
- Some content may be behind login walls
- Rate limiting may apply
- Only public content is accessible
- Video files are not downloaded (metadata only)
"""

import os
import pandas as pd
import json
import time
import requests
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from apify_client import ApifyClient

# Define TikTok actor configurations (UPDATED WITH WORKING ACTORS)
TIKTOK_ACTOR_CONFIGS: List[Dict] = [
    {
        "id": "clockworks/tiktok-scraper",  # Working TikTok Scraper
        "name": "Clockworks TikTok Scraper",
        "type": "general",
        "supports_filters": True,
        "max_results": 10000,
        "search_types": ["hashtag", "user", "sound", "trending"],
        "input_format": "hashtags"  # Uses 'hashtags' parameter
    },
    {
        "id": "clockworks/free-tiktok-scraper",  # Free TikTok Scraper
        "name": "Clockworks Free TikTok Scraper", 
        "type": "general",
        "supports_filters": False,
        "max_results": 10000,
        "search_types": ["hashtag", "user"],
        "input_format": "hashtags"  # Uses 'hashtags' parameter
    }
]

def determine_country_from_location(location: str) -> str:
    """Determines a likely country based on location text."""
    country = "unknown"
    if location:
        location_lower = location.lower()
        if any(country in location_lower for country in ["qatar", "doha"]):
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

def collect_tiktok_apify(queries: List[str], output_file=None, max_results=10000, search_type="hashtag", 
                        include_comments=True, include_shares=True, download_subtitles=True, **kwargs):
    """
    Collect TikTok data using multiple Apify Actors for the given queries.
    
    Args:
        queries (List[str]): List of query strings to search for (usernames, hashtags, sounds).
        output_file: Path to save the results
        max_results: Maximum number of results to fetch per query (default: 10000)
        search_type: Type of search to perform (default: "hashtag")
        include_comments: Whether to scrape comments (default: True)
        include_shares: Whether to scrape shares (default: True)
        download_subtitles: Whether to download and parse subtitle/transcript content (default: True)
        since_date: Optional start date in format "YYYY-MM-DD_HH:MM:SS_UTC" or ISO format (for filtering)
        until_date: Optional end date in format "YYYY-MM-DD_HH:MM:SS_UTC" or ISO format (for filtering)
    """
    # Extract date parameters for post-collection filtering
    since_date = kwargs.get('since_date')
    until_date = kwargs.get('until_date')
    
    # Parse dates if provided (support both underscore and ISO formats)
    since_datetime = None
    until_datetime = None
    
    if since_date:
        try:
            # Try underscore format first (YYYY-MM-DD_HH:MM:SS_UTC)
            if '_' in since_date and 'UTC' in since_date:
                since_datetime = datetime.strptime(since_date.replace('_UTC', ''), "%Y-%m-%d_%H:%M:%S")
                since_datetime = since_datetime.replace(tzinfo=timezone.utc)
            # Try ISO format (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM:SS.000Z)
            elif 'T' in since_date:
                since_datetime = datetime.fromisoformat(since_date.replace('Z', '+00:00'))
            else:
                # Try simple date format (YYYY-MM-DD)
                since_datetime = datetime.strptime(since_date, "%Y-%m-%d")
                since_datetime = since_datetime.replace(tzinfo=timezone.utc)
        except Exception as e:
            print(f"[TikTok Apify] Warning: Could not parse since_date '{since_date}': {e}")
    
    if until_date:
        try:
            # Try underscore format first (YYYY-MM-DD_HH:MM:SS_UTC)
            if '_' in until_date and 'UTC' in until_date:
                until_datetime = datetime.strptime(until_date.replace('_UTC', ''), "%Y-%m-%d_%H:%M:%S")
                until_datetime = until_datetime.replace(tzinfo=timezone.utc)
            # Try ISO format (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM:SS.000Z)
            elif 'T' in until_date:
                until_datetime = datetime.fromisoformat(until_date.replace('Z', '+00:00'))
            else:
                # Try simple date format (YYYY-MM-DD)
                until_datetime = datetime.strptime(until_date, "%Y-%m-%d")
                until_datetime = until_datetime.replace(tzinfo=timezone.utc)
        except Exception as e:
            print(f"[TikTok Apify] Warning: Could not parse until_date '{until_date}': {e}")
    
    if since_datetime or until_datetime:
        print(f"[TikTok Apify] Date filtering enabled: {since_datetime} to {until_datetime}")
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
        output_file = str(Path(__file__).parent.parent.parent / "data" / "raw" / f"tiktok_apify_data_{today}.csv")
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    all_data = []
    total_collected_count = 0

    # --- Run Actors --- 
    for actor_config in TIKTOK_ACTOR_CONFIGS:
        actor_id = actor_config["id"]
        actor_name = actor_config["name"]
        actor_type = actor_config["type"]
        supports_filters = actor_config["supports_filters"]
        max_actor_results = min(max_results, actor_config["max_results"])
        
        print(f"\n--- [TikTok Apify - {actor_name}] Starting collection ({actor_id}) ---")
        
        actor_collected_count = 0
        runs_to_process = []

        # --- Prepare and Run Actor --- 
        for query in queries:
            try:
                print(f"[TikTok Apify - {actor_name}] Running for query: {query}")
                
                # Prepare actor input based on actor's expected format
                input_format = actor_config.get("input_format", "hashtags")
                
                if input_format == "hashtags":
                    # clockworks/tiktok-scraper actual parameters:
                    # hashtags (array), resultsPerPage (integer), oldestPostDateUnified, newestPostDate
                    clean_query = query.replace("#", "").strip()
                    
                    run_input = {
                        "hashtags": [clean_query],  # Array of hashtags (without # symbol)
                        "resultsPerPage": max_actor_results  # Number of videos per hashtag
                    }
                    
                    # Add date filters if supported and dates are provided
                    if supports_filters:
                        # Date filtering using oldestPostDateUnified and newestPostDate
                        # oldestPostDateUnified: scrape videos published after this date
                        # newestPostDate: scrape videos published before this date
                        # Format: Must be date string (YYYY-MM-DD) OR number with unit (e.g., "1 day", "2 days", "1 week")
                        # Regex pattern: ^(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(T[0-2]\d:[0-5]\d(:[0-5]\d)?(\.\d+)?Z?)?$|^(\d+)\s*(minute|hour|day|week|month|year)s?$
                        
                        # Use "1 day" format (not just "1") to match the required pattern
                        # This means: scrape videos from the last 1 day (today)
                        run_input["oldestPostDateUnified"] = "1 day"
                        
                        if until_datetime:
                            # newestPostDate: scrape videos published before this date
                            run_input["newestPostDate"] = until_datetime.strftime("%Y-%m-%d")
                        
                        if since_datetime or until_datetime:
                            print(f"[TikTok Apify - {actor_name}] Using date filters: oldestPostDateUnified='1 day' (last 24 hours), newestPostDate={run_input.get('newestPostDate', 'N/A')} - date filtering will be applied post-collection")
                        else:
                            print(f"[TikTok Apify - {actor_name}] Using date filter: oldestPostDateUnified='1 day' (last 24 hours)")
                        
                else:
                    # Legacy format (for any other actors)
                    run_input = {
                        "searchTerms": [query],
                        "resultsLimit": max_actor_results,
                        "searchType": search_type,
                        "includeComments": include_comments,
                        "includeShares": include_shares,
                        "downloadVideos": False
                    }

                # Run the actor with timeout
                timeout_secs = int(os.getenv('APIFY_TIMEOUT_SECONDS', '180'))
                wait_secs = int(os.getenv('APIFY_WAIT_SECONDS', '180'))

                print(f"[TikTok Apify - {actor_name}] Running actor with timeout={timeout_secs}s, wait={wait_secs}s")

                try:
                    run = client.actor(actor_id).call(
                        run_input=run_input,
                        timeout_secs=timeout_secs,
                        wait_secs=wait_secs
                    )
                    runs_to_process.append({"run": run, "query": query, "actor_type": actor_type})
                    print(f"[TikTok Apify - {actor_name}] Run initiated for query '{query}'. Dataset ID: {run['defaultDatasetId']}")
                    time.sleep(3)  # Delay between runs

                except Exception as actor_error:
                    if "timeout" in str(actor_error).lower():
                        print(f"[TikTok Apify - {actor_name}] ⏱️ TIMEOUT after {timeout_secs}s for query '{query}'")
                    raise  # Re-raise to outer exception handler

            except Exception as e:
                print(f"[TikTok Apify - {actor_name}] Error running actor for query '{query}': {e}")
                print(f"[TikTok Apify - {actor_name}] This might be due to:")
                print(f"[TikTok Apify - {actor_name}] - Invalid query format")
                print(f"[TikTok Apify - {actor_name}] - Actor not found or access denied")
                print(f"[TikTok Apify - {actor_name}] - Invalid input parameters")
                continue

        # --- Process Results from Runs --- 
        for run_info in runs_to_process:
            run_data = run_info["run"]
            query = run_info["query"]
            actor_type = run_info["actor_type"]
            dataset_id = run_data["defaultDatasetId"]
            
            print(f"[TikTok Apify - {actor_name}] Fetching results for query '{query}' (Dataset: {dataset_id})")
            
            try:
                items_count_for_run = 0
                items_skipped = 0
                items_in_dataset = 0
                
                for item in client.dataset(dataset_id).iterate_items():
                    items_in_dataset += 1
                    try:
                        # Extract data based on actor type
                        if actor_type in ["general", "hashtag"]:
                            # Debug: Print the first item to see its structure
                            if items_count_for_run == 0:
                                print(f"[TikTok Apify - {actor_name}] DEBUG: First item structure: {json.dumps(item, indent=2, default=str)}")
                            
                            data = _extract_tiktok_data(item, query, actor_id, actor_type, download_subtitles)
                        else:
                            data = None
                            print(f"[TikTok Apify - {actor_name}] Skipping item - actor_type '{actor_type}' not supported")
                        
                        if data:
                            # Apply date filtering if dates are provided
                            should_include = True
                            if since_datetime or until_datetime:
                                # Extract date from data (createTimeISO field)
                                item_date_str = data.get('date', '')
                                if item_date_str and item_date_str != 'unknown':
                                    try:
                                        # Parse the date (could be ISO format or timestamp)
                                        if isinstance(item_date_str, str):
                                            if 'T' in item_date_str:
                                                # ISO format: "2025-08-02T18:45:03.000Z"
                                                item_datetime = datetime.fromisoformat(item_date_str.replace('Z', '+00:00'))
                                            elif item_date_str.isdigit():
                                                # Unix timestamp
                                                item_datetime = datetime.fromtimestamp(int(item_date_str), tz=timezone.utc)
                                            else:
                                                # Try other formats
                                                item_datetime = datetime.fromisoformat(item_date_str.replace('Z', '+00:00'))
                                        else:
                                            # Already a datetime object
                                            item_datetime = item_date_str
                                        
                                        # Apply date filters
                                        if since_datetime and item_datetime < since_datetime:
                                            should_include = False
                                        if until_datetime and item_datetime > until_datetime:
                                            should_include = False
                                    except Exception as e:
                                        # If date parsing fails, include the item (better to have it than miss it)
                                        print(f"[TikTok Apify - {actor_name}] Warning: Could not parse date '{item_date_str}': {e}")
                            
                            if should_include:
                                all_data.append(data)
                                items_count_for_run += 1
                            else:
                                items_skipped += 1
                            
                            if items_count_for_run % 10 == 0:
                                print(f"[TikTok Apify - {actor_name}] Processed {items_count_for_run} items...")
                        else:
                            items_skipped += 1
                            if items_skipped <= 3:  # Only log first few skips
                                print(f"[TikTok Apify - {actor_name}] Warning: Item {items_in_dataset} returned None (skipped)")
                            
                    except Exception as e:
                        items_skipped += 1
                        print(f"[TikTok Apify - {actor_name}] Error processing item {items_in_dataset}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                print(f"[TikTok Apify - {actor_name}] Dataset had {items_in_dataset} total items")
                if since_datetime or until_datetime:
                    print(f"[TikTok Apify - {actor_name}] Date filtering applied: {items_count_for_run} items within date range, {items_skipped} filtered out")
                else:
                    print(f"[TikTok Apify - {actor_name}] Successfully processed: {items_count_for_run}, Skipped/Failed: {items_skipped}")
                
                print(f"[TikTok Apify - {actor_name}] Collected {items_count_for_run} items for query '{query}'")
                actor_collected_count += items_count_for_run
                
            except Exception as e:
                print(f"[TikTok Apify - {actor_name}] Error fetching dataset {dataset_id}: {e}")

        print(f"--- [TikTok Apify - {actor_name}] Finished collection. Collected {actor_collected_count} items. ---")
        total_collected_count += actor_collected_count
        time.sleep(5)  # Delay between actors
    
    # --- Save Collected Data --- 
    if all_data:
        print(f"\n[TikTok Apify] Total items collected across all actors: {len(all_data)}")
        df = pd.DataFrame(all_data)
        
        # Deduplicate based on post_id or URL
        dedup_key = 'post_id' if 'post_id' in df.columns else 'url'
        if dedup_key in df.columns:
            initial_count = len(df)
            df.drop_duplicates(subset=[dedup_key], keep='first', inplace=True)
            final_count = len(df)
            print(f"[TikTok Apify] Deduplicated {initial_count - final_count} items based on {dedup_key}. Final count: {final_count}")

        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            try:
                existing_df = pd.read_csv(output_file)
                df = pd.concat([existing_df, df], ignore_index=True)
            except pd.errors.EmptyDataError:
                print(f"[TikTok Apify] Warning: The file '{output_file}' is empty. Creating a new file.")
        
        df.to_csv(output_file, index=False)
        print(f"\n[TikTok Apify] Collected {len(all_data)} total TikTok items. Saved to '{output_file}'.")
    else:
        print("\n[TikTok Apify] No TikTok items collected across all actors.")
        # Create empty DataFrame with expected columns
        df = pd.DataFrame(columns=["source", "platform", "type", "post_id", "date", "text", 
                                  "url", "image_url", "country", "query", "actor_id",
                                  "username", "user_display_name", "user_verified", "user_followers",
                                  "likes", "comments", "shares", "views", "collects",
                                  "video_duration", "music_name", "music_original", "hashtags",
                                  "subtitle_language", "subtitle_text"])
        df.to_csv(output_file, index=False)
        print(f"[TikTok Apify] Created empty '{output_file}' with headers.")

def _download_subtitle_content(subtitle_url: str) -> str:
    """
    Download and parse subtitle content from TikTok subtitle URL.
    TikTok subtitles are in WebVTT format.
    Returns cleaned text content without timestamps.
    """
    if not subtitle_url:
        return ""
    
    try:
        response = requests.get(subtitle_url, timeout=10)
        response.raise_for_status()
        
        # Parse WebVTT format
        content = response.text
        
        # Remove WEBVTT header
        content = re.sub(r'^WEBVTT.*?\n\n', '', content, flags=re.MULTILINE | re.DOTALL)
        
        # Remove timestamp lines (format: 00:00:00.000 --> 00:00:00.000)
        content = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}.*?\n', '', content)
        
        # Remove cue identifiers (numbers at start of lines)
        content = re.sub(r'^\d+\n', '', content, flags=re.MULTILINE)
        
        # Remove empty lines and extra whitespace
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # Join with spaces and clean up
        text = ' '.join(lines)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    except Exception as e:
        print(f"Error downloading subtitle: {e}")
        return ""

def _extract_tiktok_data(item: Dict, query: str, actor_id: str, actor_type: str, download_subtitles: bool = False) -> Dict[str, Any]:
    """Extract data from TikTok scraping results."""
    try:
        # Post ID
        post_id = item.get("id", item.get("videoId", "unknown"))
        
        # Post text/description
        post_text = item.get("text", item.get("description", item.get("caption", "")))
        
        # Post URL - Apify returns 'webVideoUrl'
        post_url = item.get("webVideoUrl", item.get("url", item.get("link", "")))
        
        # Post date - Apify returns 'createTimeISO' or 'createTime'
        post_date = item.get("createTimeISO", item.get("createTime", item.get("timestamp", item.get("date", "unknown"))))
        
        # Post type
        post_type = "slideshow" if item.get("isSlideshow", False) else "video"
        
        # Get user information - Apify returns 'authorMeta' not 'author'
        user_info = item.get("authorMeta", item.get("author", item.get("user", {})))
        if not isinstance(user_info, dict):
            user_info = {}
        
        username = user_info.get("name", user_info.get("username", "unknown"))
        user_display_name = user_info.get("nickName", user_info.get("displayName", user_info.get("fullName", username)))
        user_id = user_info.get("id", "")
        user_verified = user_info.get("verified", False)
        user_followers = user_info.get("fans", user_info.get("followers", 0))
        user_avatar = user_info.get("avatar", user_info.get("originalAvatarUrl", ""))
        
        # Get engagement metrics - Apify uses different field names
        likes = item.get("diggCount", item.get("likesCount", item.get("likes", item.get("likeCount", 0))))
        comments = item.get("commentCount", item.get("commentsCount", item.get("comments", 0)))
        shares = item.get("shareCount", item.get("sharesCount", item.get("shares", 0)))
        views = item.get("playCount", item.get("viewsCount", item.get("views", item.get("viewCount", 0))))
        collects = item.get("collectCount", item.get("saves", 0))
        
        # Get video metadata - Apify returns 'videoMeta'
        video_meta = item.get("videoMeta", {})
        if not isinstance(video_meta, dict):
            video_meta = {}
        
        video_duration = video_meta.get("duration", 0)
        video_height = video_meta.get("height", 0)
        video_width = video_meta.get("width", 0)
        video_quality = video_meta.get("definition", "")
        
        # Get media information
        image_url = video_meta.get("coverUrl", video_meta.get("originalCoverUrl", item.get("thumbnailUrl", item.get("coverUrl", ""))))
        
        # Get music information - Apify returns 'musicMeta' not 'music'
        music_info = item.get("musicMeta", item.get("music", {}))
        if not isinstance(music_info, dict):
            music_info = {}
        
        music_name = music_info.get("musicName", music_info.get("title", music_info.get("name", "")))
        music_author = music_info.get("musicAuthor", music_info.get("author", music_info.get("artist", "")))
        music_original = music_info.get("musicOriginal", False)
        music_id = music_info.get("musicId", "")
        
        # Get hashtags
        hashtags = item.get("hashtags", [])
        hashtag_names = [h.get("name", "") if isinstance(h, dict) else str(h) for h in hashtags]
        hashtag_string = ", ".join(hashtag_names) if hashtag_names else ""
        
        # Get location information
        location_info = item.get("location", {})
        location_name = ""
        if isinstance(location_info, dict):
            location_name = location_info.get("name", "")
        elif location_info:
            location_name = str(location_info)
        
        # Determine country
        country = "unknown"
        if location_name:
            country = determine_country_from_location(location_name)
        elif username:
            country = determine_country_from_username(username)
        
        # Get subtitles/transcripts - TikTok provides ASR (auto speech recognition) captions
        subtitle_links = video_meta.get("subtitleLinks", [])
        subtitle_text = ""
        subtitle_url = ""
        subtitle_language = ""
        
        # Try to find English ASR (automatic speech recognition) subtitle first
        english_asr = None
        english_mt = None
        any_subtitle = None
        
        for subtitle in subtitle_links:
            if not isinstance(subtitle, dict):
                continue
            
            lang = subtitle.get("language", "")
            source = subtitle.get("source", "")
            
            # Prioritize English ASR (automatic speech recognition)
            if "eng" in lang.lower() and source == "ASR":
                english_asr = subtitle
                break
            # Fallback to English MT (machine translation)
            elif "eng" in lang.lower() and source == "MT":
                english_mt = subtitle
            # Keep track of any subtitle as last resort
            elif not any_subtitle:
                any_subtitle = subtitle
        
        # Use the best available subtitle
        best_subtitle = english_asr or english_mt or any_subtitle
        
        if best_subtitle:
            subtitle_url = best_subtitle.get("downloadLink", best_subtitle.get("tiktokLink", ""))
            subtitle_language = best_subtitle.get("language", "")
            subtitle_source = best_subtitle.get("source", "")
            
            # Download subtitle content if requested
            if download_subtitles and subtitle_url:
                subtitle_text = _download_subtitle_content(subtitle_url)
            else:
                # Store URL for later download if needed
                subtitle_text = ""
        
        return {
            "source": "TikTok",
            "platform": "TikTok",
            "type": post_type,
            "post_id": post_id,
            "date": post_date,
            "text": post_text,
            "url": post_url,
            "image_url": image_url,
            "country": country,
            "query": query,
            "actor_id": actor_id,
            "username": username,
            "user_display_name": user_display_name,
            "user_verified": user_verified,
            "user_followers": user_followers,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "views": views,
            "collects": collects,
            "video_duration": video_duration,
            "music_name": music_name,
            "music_original": music_original,
            "hashtags": hashtag_string,
            "subtitle_language": subtitle_language,
            "subtitle_text": subtitle_text
        }
    except Exception as e:
        print(f"Error extracting TikTok data: {e}")
        import traceback
        traceback.print_exc()
        return None

def main(target_and_variations: List[str], user_id: str = None):
    """Main function called by run_collectors. Accepts target/variations list."""
    if not target_and_variations:
        print("[TikTok Apify] Error: No target/query variations provided.")
        return
        
    target_name = target_and_variations[0]
    queries = target_and_variations[1:]
    print(f"[TikTok Apify] Received Target: {target_name}, Queries: {queries}")
    
    # Construct output file name
    today = datetime.now().strftime("%Y%m%d")
    safe_target_name = target_name.replace(" ", "_").lower()
    output_path = Path(__file__).parent.parent.parent / "data" / "raw" / f"tiktok_apify_{safe_target_name}_{today}.csv"
    
    # Call the collection function with the queries
    collect_tiktok_apify(queries=queries, output_file=str(output_path))

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Collect TikTok data using Apify')
    parser.add_argument('--queries', type=str, required=False, help='JSON string of query variations')
    parser.add_argument('--since', type=str, help='Start date in format YYYY-MM-DD_HH:MM:SS_UTC (for incremental collection)')
    parser.add_argument('--until', type=str, help='End date in format YYYY-MM-DD_HH:MM:SS_UTC (for incremental collection)')
    
    args = parser.parse_args()
    
    if args.queries:
        try:
            # Parse the JSON string to get the list of queries
            queries_list = json.loads(args.queries)
            print(f"[TikTok Apify] Parsed queries: {queries_list}")
            
            # Use incremental dates if provided
            if args.since or args.until:
                print(f"[TikTok Apify] Using incremental collection: {args.since} to {args.until}")
                kwargs = {}
                if args.since:
                    kwargs['since_date'] = args.since
                if args.until:
                    kwargs['until_date'] = args.until
                collect_tiktok_apify(queries=queries_list, **kwargs)
            else:
                main(queries_list)
        except json.JSONDecodeError as e:
            print(f"[TikTok Apify] Error parsing queries JSON: {e}")
            main([])
    else:
        print("Running TikTok Apify collector directly (without args)... Use run_collectors.py for proper execution.")
        main([])  # Pass empty list for direct run scenario

