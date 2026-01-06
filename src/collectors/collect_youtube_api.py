"""
YouTube API Collector for TV Channels
Collects data from YouTube channels for Qatar and Nigeria TV news channels.
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
from src.api.database import SessionLocal
from src.services.data_ingestor import DataIngestor


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add this after the imports, around line 20
_configured_instance = None

def set_target_config(target_config):
    """Set target-specific configuration for the collector instance"""
    global _configured_instance
    if _configured_instance is None:
        _configured_instance = YouTubeAPICollector()
    _configured_instance.set_target_config(target_config)
    logger.info(f"Set target config for: {target_config.name if target_config else 'None'}")

class YouTubeAPICollector:
    def __init__(self, user_id: Optional[str] = None):
        """
        Initialize YouTubeAPICollector.
        
        Args:
            user_id: Optional user ID to associate with collected data.
        """
        self.user_id = user_id
        self.session = SessionLocal()
        self.ingestor = DataIngestor(self.session, user_id=user_id)

        # Load .env from collectors folder first, then root directory as fallback
        collectors_env_path = Path(__file__).parent / '.env'
        
        # Add src directory to path to allow imports from config
        import sys
        src_path = Path(__file__).resolve().parent.parent
        if str(src_path) not in sys.path:
            sys.path.append(str(src_path))
            
        from src.config.path_manager import PathManager
        self.path_manager = PathManager()
        root_env_path = self.path_manager.base_path / '.env'
        
        logger.info(f"Current file location: {Path(__file__)}")
        logger.info(f"Checking for .env in collectors folder: {collectors_env_path}")
        logger.info(f"Checking for .env in root directory: {root_env_path}")
        
        # Try to load from collectors folder first
        if collectors_env_path.exists():
            load_dotenv(collectors_env_path)
            logger.info(f"✅ Loaded .env from collectors folder: {collectors_env_path}")
        elif root_env_path.exists():
            load_dotenv(root_env_path)
            logger.info(f"✅ Loaded .env from root directory: {root_env_path}")
        else:
            logger.warning(f"❌ No .env file found. Checked:")
            logger.warning(f"  - Collectors folder: {collectors_env_path}")
            logger.warning(f"  - Root directory: {root_env_path}")
        
        self.base_path = self.path_manager.base_path
        
        # YouTube API configuration
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        logger.info(f"Environment check - YOUTUBE_API_KEY: {'✅ Found' if self.youtube_api_key else '❌ Missing'}")
        
        if not self.youtube_api_key:
            # Show all environment variables that contain 'YOUTUBE' for debugging
            youtube_env_vars = {k: v for k, v in os.environ.items() if 'YOUTUBE' in k.upper()}
            if youtube_env_vars:
                logger.info(f"Found YouTube-related env vars: {youtube_env_vars}")
            else:
                logger.warning("No YouTube-related environment variables found")
            raise ValueError("YOUTUBE_API_KEY not found in environment variables")
        
        # Initialize YouTube API client
        self.youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
        
        # Target-specific configuration
        self.target_config = None
        
        # Load TV Channel configurations from config file
        self.tv_channels = self._load_tv_channels_config()
        
        logger.info("YouTube API Collector initialized successfully")

    def _load_tv_channels_config(self) -> Dict[str, Dict[str, str]]:
        """Load TV channels configuration from JSON file"""
        try:
            config_path = self.path_manager.config_dir / 'youtube_tv_channels.json'
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Extract just the channel IDs for backward compatibility
                channels: Dict[str, Dict[str, str]] = {}
                for country, country_channels in config.items():
                    if country in ['qatar', 'nigeria']:
                        channels[country] = {}
                        for channel_name, channel_info in country_channels.items():
                            if isinstance(channel_info, dict) and 'channel_id' in channel_info:
                                channels[country][channel_name] = channel_info['channel_id']
                            elif isinstance(channel_info, str):
                                # Backward compatibility for old format
                                channels[country][channel_name] = channel_info
                
                logger.info(f"Loaded {sum(len(ch) for ch in channels.values())} TV channels from config")
                return channels
            else:
                logger.warning(f"TV channels config file not found at {config_path}")
                return self._get_default_tv_channels()
                
        except Exception as e:
            logger.error(f"Error loading TV channels config: {e}")
            return self._get_default_tv_channels()

    def _get_default_tv_channels(self) -> Dict[str, Dict[str, str]]:
        """Fallback default TV channels configuration"""
        return {
            "qatar": {
                "Al Jazeera Arabic": "UCfiwzLy-8yKzIbsmZTzxDgw",
                "Al Jazeera English": "UCNye-wNBqNL5ZzHSJj3l8Bg",
                "Al Jazeera Mubasher": "UCCv1Pd24oPErw5S7zJWltnQ",
                "Al Jazeera Documentary": "UC0LSnqrwqtMwl2YwfUpO66g",
                "beIN SPORTS": "UCJUCcJUeh0Cz2xyKwkw5Q1w",
                "Qatar TV (QTV)": "UC2EJXBsWR_5BTCy6R4kIO3A",
                "Al Rayyan TV": "UCK8LcweIXy4BGzTqjoj01DA"
            },
            "nigeria": {
                "Channel TV": "UCEXGDNclvmg6RW0vipJYsTQ",
                "AIT Live": "UCsUhTIo0bMTHs9RAroEMoQA",
                "NTA Networks": "UCLLWAXn5F415g2kNAcE_T1g",
                "TVC News": "UCgp4A6I8LCWrhUzn-5SbKvA",
                "Silver Bird TV": "UCNuPuew8lLVB3mMAm9_Qt9w",
                "Plus TV Africa": "UCkY5L8JYwx7BT0cOXYZX_dw",
                "News Central": "UCPLKy4Ypb4mfblbjJI8Aljw",
                "Flip TV": "UCPLKy4Ypb4mfblbjJI8Aljw",
                "Trust TV": "UCTlqstA2Wrt4fimd_VWKr8g",
                "Voice TV": "UC20Wx5hNQQLCh4qS4siNBtw",
                "Arise News": "UCyEJX-kSj0kOOCS7Qlq2G7g",
                "Sokoto TV": "UCPlaceholder_SokotoTV",
                "Katsina TV": "UCPlaceholder_KatsinaTV",
                "Kebbi TV": "UCPlaceholder_KebbiTV",
                "Jigawa TV": "UCPlaceholder_JigawaTV",
                "Zamfara TV": "UCPlaceholder_ZamfaraTV",
                "Plateau TV": "UCPlaceholder_PlateauTV",
                "Benue TV": "UCPlaceholder_BenueTV",
                "Niger TV": "UCPlaceholder_NigerTV",
                "Kwara TV": "UCPlaceholder_KwaraTV"
            }
        }

    def set_target_config(self, target_config):
        """Set target-specific configuration for the collector instance"""
        global _configured_instance
        if _configured_instance is None:
            _configured_instance = YouTubeAPICollector()
        _configured_instance.target_config = target_config
        logger.info(f"Set target config for: {target_config.name if target_config else 'None'}")

    def _get_target_keywords(self) -> List[str]:  # type: ignore[no-any-return]
        """Get keywords to filter videos based on target configuration.
        
        Priority order:
        1. ConfigManager: collectors.keywords.<target_id>.youtube (target-specific, from DB)
        2. ConfigManager: collectors.keywords.default.youtube (default, from DB)
        3. target_config.sources.youtube.keywords (backward compatibility)
        4. target_config.keywords (backward compatibility)
        5. Hardcoded defaults (last resort)
        """
        from config.config_manager import ConfigManager
        config = ConfigManager()
        
        # Priority 1: Target-specific keywords from ConfigManager (enables DB editing)
        if self.target_config and hasattr(self.target_config, 'name'):
            target_name = self.target_config.name.lower().replace(" ", "_")
            target_key = f"collectors.keywords.{target_name}.youtube"
            target_keywords = config.get_list(target_key, None)
            if target_keywords:
                logger.info(f"Using target-specific keywords from ConfigManager: {target_keywords}")
                return target_keywords
        
        # Priority 2: Default keywords from ConfigManager (enables DB editing)
        default_keywords = config.get_list("collectors.keywords.default.youtube", None)
        if default_keywords:
            logger.info(f"Using default keywords from ConfigManager: {default_keywords}")
            return default_keywords
        
        # Priority 3: Legacy - target_config source-specific keywords (backward compatibility)
        if self.target_config and hasattr(self.target_config, 'sources'):
            youtube_config = self.target_config.sources.get('youtube')
            if youtube_config and hasattr(youtube_config, 'keywords') and youtube_config.keywords:
                logger.info(f"Using keywords from target_config.sources.youtube: {youtube_config.keywords}")
                return youtube_config.keywords
        
        # Priority 4: Legacy - top-level target keywords (backward compatibility)
        if self.target_config and hasattr(self.target_config, 'keywords') and self.target_config.keywords:
            logger.info(f"Using keywords from target_config: {self.target_config.keywords}")
            return self.target_config.keywords
        
        # Priority 5: Hardcoded defaults (last resort)
        logger.warning("Using hardcoded default keywords - consider configuring in ConfigManager/DB")
        return ["emir", "amir", "sheikh tamim", "al thani"]

    def _get_target_countries(self) -> List[str]:
        """Get countries to search based on target configuration"""
        if self.target_config and hasattr(self.target_config, 'sources'):
            # First, check for YouTube-specific channels/countries
            youtube_config = self.target_config.sources.get('youtube')
            if youtube_config and hasattr(youtube_config, 'channels') and youtube_config.channels:
                # If YouTube config specifies channels, use those to determine countries
                channels = youtube_config.channels
                countries = []
                if 'nigeria' in channels or 'ng' in channels:
                    countries.append('ng')
                if 'qatar' in channels or 'qa' in channels:
                    countries.append('qa')
                if countries:
                    return countries
            
            # Fallback to news countries, but filter out 'qa' if target is not Qatar-related
            news_config = self.target_config.sources.get('news')
            if news_config and hasattr(news_config, 'countries') and news_config.countries:
                countries = news_config.countries.copy()
                # Filter out Qatar if target country is not Qatar
                if hasattr(self.target_config, 'country_code') and self.target_config.country_code != 'qa':
                    countries = [c for c in countries if c != 'qa']
                return countries
        
        # Fallback: use target's country_code if available
        if self.target_config and hasattr(self.target_config, 'country_code'):
            return [self.target_config.country_code]
        
        # Fallback to default countries for backward compatibility (without qa)
        return ['us', 'gb', 'ae', 'ng', 'in']

    def _should_include_video(self, title: str, description: str) -> bool:
        """Determine if a video should be included based on target configuration"""
        if not self.target_config:
            # Fallback to default keywords from ConfigManager (enables DB editing)
            from config.config_manager import ConfigManager
            config = ConfigManager()
            default_keywords = config.get_list("collectors.keywords.default.youtube", 
                config.get_list("collectors.default_keywords.youtube", ["emir", "amir", "sheikh tamim", "al thani"]))
            content = f"{title} {description}".lower()
            return any(term.lower() in content for term in default_keywords)
        
        # Use target-specific keywords
        target_keywords = self._get_target_keywords()
        content = f"{title} {description}".lower()
        
        # Check if content contains any target keywords
        has_target_keywords = any(keyword.lower() in content for keyword in target_keywords)
        
        # Apply additional filters if configured
        if hasattr(self.target_config, 'sources') and 'news' in self.target_config.sources:
            news_config = self.target_config.sources['news']
            if hasattr(news_config, 'filters') and news_config.filters:
                filters = news_config.filters
                
                # Check must_contain filters
                if 'must_contain' in filters:
                    must_contain = filters['must_contain']
                    if not any(term.lower() in content for term in must_contain):
                        return False
                
                # Check exclude filters
                if 'exclude' in filters:
                    exclude_terms = filters['exclude']
                    if any(term.lower() in content for term in exclude_terms):
                        return False
        
        return has_target_keywords

    def _get_channel_videos(self, channel_id: str, max_results: int = 1000) -> List[Dict[str, Any]]:
        """Get videos from a specific YouTube channel"""
        try:
            # Get channel's uploads playlist
            channels_response = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()
            
            if not channels_response['items']:
                logger.warning(f"No channel found for ID: {channel_id}")
                return []
            
            uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get videos from uploads playlist
            playlist_response = self.youtube.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=uploads_playlist_id,
                maxResults=max_results
            ).execute()
            
            videos = []
            for item in playlist_response['items']:
                try:
                    # Validate that required fields exist
                    if 'contentDetails' not in item or 'videoId' not in item['contentDetails']:
                        logger.warning(f"Missing videoId in playlist item: {item}")
                        continue
                    
                    if 'snippet' not in item:
                        logger.warning(f"Missing snippet in playlist item: {item}")
                        continue
                    
                    video_id = item['contentDetails']['videoId']
                    snippet = item['snippet']
                    
                    # Get additional video details
                    try:
                        video_response = self.youtube.videos().list(
                            part='snippet,statistics,contentDetails',
                            id=video_id
                        ).execute()
                        
                        if video_response['items']:
                            video_info = video_response['items'][0]
                            video_data = {
                                'video_id': video_id,
                                'title': snippet.get('title', 'Unknown Title'),
                                'description': snippet.get('description', ''),
                                'channel_title': snippet.get('channelTitle', 'Unknown Channel'),
                                'channel_id': channel_id,
                                'published_at': snippet.get('publishedAt', ''),
                                'view_count': video_info['statistics'].get('viewCount', 0),
                                'like_count': video_info['statistics'].get('likeCount', 0),
                                'comment_count': video_info['statistics'].get('commentCount', 0),
                                'duration': video_info['contentDetails'].get('duration', ''),
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'thumbnail': self._get_thumbnail_url(snippet.get('thumbnails', {}))
                            }
                            videos.append(video_data)
                    
                    except HttpError as e:
                        logger.warning(f"Error getting video details for {video_id}: {e}")
                        continue
                    
                except KeyError as e:
                    logger.warning(f"Missing required field in playlist item: {e}, item: {item}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error processing playlist item: {e}, item: {item}")
                    continue
                
                # Rate limiting from ConfigManager
                from config.config_manager import ConfigManager
                config = ConfigManager()
                delay = config.get_float("collectors.youtube.delay_between_requests_seconds", 0.1)
                time.sleep(delay)
            
            return videos
            
        except HttpError as e:
            logger.error(f"Error getting videos from channel {channel_id}: {e}")
            return []

    def _search_channel_videos(self, channel_id: str, query: str, max_results: int = 1000) -> List[Dict[str, Any]]:
        """Search for videos within a specific channel using keywords"""
        try:
            # Search for videos in the channel
            search_response = self.youtube.search().list(
                part='snippet',
                channelId=channel_id,
                q=query,
                type='video',
                order='date',
                maxResults=max_results
            ).execute()
            
            videos = []
            for item in search_response['items']:
                try:
                    # Validate that required fields exist
                    if 'id' not in item or 'videoId' not in item['id']:
                        logger.warning(f"Missing videoId in search item: {item}")
                        continue
                    
                    if 'snippet' not in item:
                        logger.warning(f"Missing snippet in search item: {item}")
                        continue
                    
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    
                    # Get additional video details
                    try:
                        video_response = self.youtube.videos().list(
                            part='snippet,statistics,contentDetails',
                            id=video_id
                        ).execute()
                        
                        if video_response['items']:
                            video_info = video_response['items'][0]
                            video_data = {
                                'video_id': video_id,
                                'title': snippet.get('title', 'Unknown Title'),
                                'description': snippet.get('description', ''),
                                'channel_title': snippet.get('channelTitle', 'Unknown Channel'),
                                'channel_id': channel_id,
                                'published_at': snippet.get('publishedAt', ''),
                                'view_count': video_info['statistics'].get('viewCount', 0),
                                'like_count': video_info['statistics'].get('likeCount', 0),
                                'comment_count': video_info['statistics'].get('commentCount', 0),
                                'duration': video_info['contentDetails'].get('duration', ''),
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'thumbnail': self._get_thumbnail_url(snippet.get('thumbnails', {})),
                                'search_query': query
                            }
                            videos.append(video_data)
                    
                    except HttpError as e:
                        logger.warning(f"Error getting video details for {video_id}: {e}")
                        continue
                    
                except KeyError as e:
                    logger.warning(f"Missing required field in search item: {e}, item: {item}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error processing search item: {e}, item: {item}")
                    continue
                
                # Rate limiting from ConfigManager
                from config.config_manager import ConfigManager
                config = ConfigManager()
                delay = config.get_float("collectors.youtube.delay_between_requests_seconds", 0.1)
                time.sleep(delay)
            
            return videos
            
        except HttpError as e:
            logger.error(f"Error searching videos in channel {channel_id}: {e}")
            return []

    def _get_thumbnail_url(self, thumbnails: Dict[str, Any]) -> str:  # type: ignore[no-any-return]
        """Safely get the highest resolution thumbnail URL or a default."""
        if 'high' in thumbnails and thumbnails['high']['url']:
            return thumbnails['high']['url']
        elif 'medium' in thumbnails and thumbnails['medium']['url']:
            return thumbnails['medium']['url']
        elif 'default' in thumbnails and thumbnails['default']['url']:
            return thumbnails['default']['url']
        return "https://via.placeholder.com/120x90" # Default thumbnail

    def collect_data(self, target_and_variations: Optional[List[str]] = None) -> Dict[str, Any]:
        """Main collection method"""
        start_time = time.time()
        logger.info("Starting YouTube API data collection")
        
        if not target_and_variations:
            # Default fallback from ConfigManager (enables DB editing)
            from config.config_manager import ConfigManager
            config = ConfigManager()
            target_and_variations = config.get_list("collectors.keywords.default.youtube_default_fallback", 
                config.get_list("collectors.default_keywords.youtube_default_fallback", ["emir"]))
        
        target_keywords = self._get_target_keywords()
        target_countries = self._get_target_countries()
        
        all_videos = []
        collection_stats = {
            'total_videos': 0,
            'channels_searched': 0,
            'videos_filtered': 0,
            'errors': 0
        }
        
        # Determine which countries to search based on target configuration
        countries_to_search = []
        if 'qa' in target_countries:
            countries_to_search.append('qatar')
        if 'ng' in target_countries:
            countries_to_search.append('nigeria')
        
        # If no specific countries, search both
        if not countries_to_search:
            countries_to_search = ['qatar', 'nigeria']
        
        logger.info(f"Searching channels in countries: {countries_to_search}")
        logger.info(f"Using target keywords: {target_keywords}")
        
        for country in countries_to_search:
            if country not in self.tv_channels:
                logger.warning(f"Country {country} not found in TV channels configuration")
                continue
            
            country_channels = self.tv_channels[country]
            logger.info(f"Searching {len(country_channels)} channels in {country}")
            
            for channel_name, channel_id in country_channels.items():
                try:
                    logger.info(f"Processing channel: {channel_name} ({channel_id})")
                    collection_stats['channels_searched'] += 1
                    
                    # Method 1: Get recent videos from channel
                    recent_videos = self._get_channel_videos(channel_id, max_results=1000)
                    
                    # Method 2: Search for videos using target keywords
                    keyword_videos = []
                    for keyword in target_keywords:
                        keyword_results = self._search_channel_videos(channel_id, keyword, max_results=1000)
                        keyword_videos.extend(keyword_results)
                    
                    # Combine and deduplicate videos
                    all_channel_videos = recent_videos + keyword_videos
                    unique_videos = {}
                    for video in all_channel_videos:
                        if video['video_id'] not in unique_videos:
                            unique_videos[video['video_id']] = video
                    
                    # Filter videos based on target configuration
                    filtered_videos = []
                    for video in unique_videos.values():
                        if self._should_include_video(video['title'], video['description']):
                            # Add metadata
                            video['country'] = country
                            video['source_type'] = 'youtube_tv'
                            video['collected_at'] = datetime.now().isoformat()
                            video['target_keywords_matched'] = [
                                kw for kw in target_keywords 
                                if kw.lower() in f"{video['title']} {video['description']}".lower()
                            ]
                            
                            filtered_videos.append(video)
                            collection_stats['videos_filtered'] += 1
                    
                    all_videos.extend(filtered_videos)
                    collection_stats['total_videos'] += len(filtered_videos)
                    
                    logger.info(f"Found {len(filtered_videos)} relevant videos from {channel_name}")
                    
                    # Stream to DB immediately
                    for video in filtered_videos:
                        self.ingestor.insert_record(video, commit=False)
                    self.ingestor.session.commit()
                    logger.info(f"Ingested {len(filtered_videos)} videos to DB")

                    
                except Exception as e:
                    logger.error(f"Error processing channel {channel_name}: {e}")
                    collection_stats['errors'] += 1
                    continue
                
                # Rate limiting between channels from ConfigManager
                from config.config_manager import ConfigManager
                config = ConfigManager()
                delay = config.get_int("collectors.youtube.delay_between_pages_seconds", 1)
                time.sleep(delay)
        
        # Save collected data (Legacy/Backup - Optional)
        # if all_videos:
        #     self._save_data(all_videos)

        
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f"YouTube collection completed in {duration:.2f}s")
        logger.info(f"Collection stats: {collection_stats}")
        
        return {
            'success': True,
            'total_videos': len(all_videos),
            'stats': collection_stats,
            'duration': duration,
            'videos': all_videos
        }

    def _save_data(self, videos: List[Dict[str, Any]]) -> None:
        """Save collected video data to CSV file"""
        try:
            # Create data directory if it doesn't exist
            data_dir = self.path_manager.data_raw
            data_dir.mkdir(parents=True, exist_ok=True)
            
            # Create DataFrame
            df = pd.DataFrame(videos)
            
            # Add timestamp to filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"youtube_tv_collection_{timestamp}.csv"
            filepath = data_dir / filename
            
            # Save to CSV
            df.to_csv(filepath, index=False)
            logger.info(f"Saved {len(videos)} videos to {filepath}")
            
            # Also save to processed data directory
            processed_dir = self.path_manager.data_processed
            processed_dir.mkdir(parents=True, exist_ok=True)
            processed_filepath = processed_dir / filename
            df.to_csv(processed_filepath, index=False)
            logger.info(f"Saved {len(videos)} videos to processed directory")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")

def main(target_and_variations: Optional[List[str]] = None, user_id: Optional[str] = None):
    """Main function for standalone execution and integration with collector system"""
    try:
        # Check if we have a pre-configured instance from the configurable collector
        global _configured_instance
        if _configured_instance and _configured_instance.target_config:
            collector = _configured_instance
            print(f"[YouTube Collector] Using configured instance for target: {collector.target_config.name}")
        else:
            # Create new instance for standalone execution
            # Create new instance for standalone execution
            collector = YouTubeAPICollector(user_id=user_id)

            print(f"[YouTube Collector] Created new instance for standalone execution")
        
        # If target_and_variations are provided, use them for collection
        if target_and_variations:
            print(f"[YouTube Collector] Received Target: {target_and_variations[0]}, Queries: {target_and_variations[1:]}")
            
            # Construct output file name with target
            from src.config.path_manager import PathManager
            path_manager = PathManager()
            today = datetime.now().strftime("%Y%m%d")
            safe_target_name = target_and_variations[0].replace(" ", "_").lower()
            output_path = path_manager.data_raw / f"youtube_tv_{safe_target_name}_{today}.csv"
            
            # Collect data with target-specific queries
            result = collector.collect_data(target_and_variations[1:])
        else:
            # Default collection without specific target
            result = collector.collect_data()
            output_path = None
        
        if result['success']:
            print(f"✅ YouTube collection completed successfully!")
            print(f"📊 Total videos collected: {result['total_videos']}")
            print(f"⏱️  Duration: {result['duration']:.2f}s")
            print(f"📈 Stats: {result['stats']}")
            
            if output_path:
                print(f"💾 Data saved to: {output_path}")
        else:
            print(f"❌ YouTube collection failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error running YouTube collector: {e}")
        logger.error(f"Error in main: {e}", exc_info=True)

if __name__ == "__main__":
    main()
