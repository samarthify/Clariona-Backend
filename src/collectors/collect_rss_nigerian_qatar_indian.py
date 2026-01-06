import feedparser
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional
import time
from urllib.parse import quote
import re
import socket
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import threading
import ssl
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import html
import chardet
import warnings
from urllib3.exceptions import InsecureRequestWarning
import json

# Import our new modules
from .rss_feed_health_monitor import RSSFeedHealthMonitor
from .rss_feed_validator import RSSFeedValidator
from .rss_ssl_handler import RSSSSLHandler
from src.api.database import SessionLocal
from src.services.data_ingestor import DataIngestor


# Suppress SSL warnings for cleaner output
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NigerianQatarIndianRSSCollector:
    def __init__(self, custom_queries=None, user_id: Optional[str] = None):
        self.user_id = user_id
        self.session_db = SessionLocal()
        self.ingestor = DataIngestor(self.session_db, user_id=user_id)

        from src.config.path_manager import PathManager
        from src.config.config_manager import ConfigManager
        self.path_manager = PathManager()
        self.base_path = self.path_manager.base_path
        self.config = ConfigManager()
        
        # Use provided queries or fall back to predefined query variations as keywords for filtering
        self.custom_queries = custom_queries or []
        
        # Timeout settings from ConfigManager
        self.feed_timeout = self.config.get_int("collectors.rss.feed_timeout_seconds", 30)
        self.max_retries = self.config.get_int("collectors.rss.max_retries", 3)
        
        # Initialize new components
        self.health_monitor = RSSFeedHealthMonitor()
        self.feed_validator = RSSFeedValidator()
        self.ssl_handler = RSSSSLHandler()
        
        # Headers for requests to avoid blocking
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, application/atom+xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
        
        # Track failed sources
        self.failed_sources = set()
        self.source_failures = {}  # Track number of failures per source
        
        # Load reliable feeds from configuration
        self.reliable_feeds = self._load_reliable_feeds()
        
        # RSS feeds for Nigerian, Qatar, and Indian news sources
        self.rss_feeds = [
            # --- Nigerian Newspapers ---
            "https://tribuneonlineng.com/feed/",
            "https://www.vanguardngr.com/feed/",
            "https://www.thisdaylive.com/index.php/feed/",
            "https://businessday.ng/feed/",
            "https://thenationonlineng.net/feed/",
            "https://herald.ng/feed/",  # Herald Nigeria
            "https://dailypost.ng/feed/",
            "https://dailypost.ng/news/feed/",  # News section
            "https://guardian.ng/news/rss",  # Main news page feed
            "https://rss.punchng.com/v1/category/latest_news",
            "https://premiumtimesng.com/feed/",
            "https://www.premiumtimesng.com/tag/feed",
            "https://informationng.com/feed/",
            "https://ripplesnigeria.com/feed/",
            "https://dailynigerian.com/feed/",
            "https://thenews-chronicle.com/feed/",
            "https://pointblanknews.com/pbn/feed/",
            "https://hallmarknews.com/feed/",
            "https://pmnewsnigeria.com/feed/",
            "https://saharareporters.com/rss",
            "https://lindaikejisblog.com/feed/",
            "https://bellanaija.com/feed/",
            
            # --- Additional Nigerian Regional Newspapers ---
            "https://sunnewsonline.com/feed/",
            "https://dailytrust.com/feed/",
            "https://leadership.ng/feed/",
            "https://blueprint.ng/feed/",
            "https://abujainquirer.com/feed/",
            "https://newnigeriannewspaper.com/feed/",
            "https://aminiya.com/feed/",
            "https://leadership.ng/hausa/feed/",
            "https://triumphnewspapers.com/feed/",
            "https://authorityngr.com/feed/",
            "https://orientdailyng.com/feed/",
            "https://thetidenewsonline.com/feed/",
            "https://nationalnetworkng.com/feed/",
            "https://nigerianobservernews.com/feed/",
            "https://thepioneerng.com/feed/",
            "https://thescopeng.com/feed/",
            "https://thelistenerng.com/feed/",

            # --- Qatar & Arabic Region ---
            "https://qna.org.qa/en/RSS-Feeds",  # Qatar News Agency
            "https://alwatannews.net/rss",  # Al-Watan Qatar (Arabic)
            "https://aljazeera.com/xml/rss/all.xml",  # Al Jazeera
            "https://dohanews.co/feed/",
            "https://www.gulf-times.com/Rss/Index",  # Gulf Times RSS index

            # --- Indian Newspapers ---
            "https://indianexpress.com/feed/",
            "https://www.nationalheraldindia.com/stories.rss",
            "https://health.economictimes.indiatimes.com/rss/topstories",
            "https://www.thehindu.com/feeder/default.rss",
            "https://feeds.hindustantimes.com/",
            "https://www.tribuneindia.com/rss/news/nation.xml",

            # --- UK / International Newspapers ---
            "https://www.telegraph.co.uk/rss.xml",
            "https://www.mirror.co.uk/?service=rss",
            "https://hulldailymail.co.uk/news/?service=rss",
            "https://feeds.feedburner.com/daily-express-sport-news",
            
            # --- Major Global News Outlets with Nigeria Coverage ---
            "https://feeds.bbci.co.uk/news/world/africa/rss.xml",  # BBC Africa
            "https://feeds.bbci.co.uk/news/world/rss.xml",         # BBC World
            "https://rss.cnn.com/rss/edition_africa.rss",         # CNN Africa
            "https://rss.cnn.com/rss/edition_world.rss",          # CNN World
            "https://www.voanews.com/api/epiqq",                  # Voice of America (VOA)
            "https://rss.dw.com/xml/rss-de-all",                  # Deutsche Welle (DW)
            "https://feeds.reuters.com/Reuters/worldNews",        # Reuters World News
            "https://feeds.afp.com/rss/afpenglishnews",           # AFP English News
            "https://www.theguardian.com/world/rss",              # The Guardian UK World
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",  # New York Times World
            "https://feeds.bloomberg.com/markets/news.rss",       # Bloomberg Markets
            "https://feeds.bloomberg.com/politics/news.rss",      # Bloomberg Politics
            "https://feeds.bloomberg.com/technology/news.rss"     # Bloomberg Technology
        ]

    def _load_reliable_feeds(self) -> List[str]:
        """Load reliable feeds from configuration file."""
        try:
            config_file = Path(__file__).parent / "reliable_rss_feeds.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Extract all feeds from configuration
                feeds = []
                for category, subcategories in config.get('rss_feeds', {}).items():
                    if isinstance(subcategories, dict):
                        for subcategory, feed_list in subcategories.items():
                            if isinstance(feed_list, list):
                                feeds.extend(feed_list)
                    elif isinstance(subcategories, list):
                        feeds.extend(subcategories)
                
                logger.info(f"Loaded {len(feeds)} reliable feeds from configuration")
                return feeds
        except Exception as e:
            logger.warning(f"Failed to load reliable feeds configuration: {e}")
        
        # Fallback to original feeds if config loading fails
        return []

    def _get_healthy_feeds(self, force_validation: bool = False) -> List[str]:
        """Get list of healthy feeds using health monitoring with caching."""
        try:
            # Check if we have cached healthy feeds and they're recent
            cache_file = self.path_manager.data_raw.parent / "healthy_feeds_cache.json"
            cache_valid = False
            cached_feeds = []
            
            if not force_validation and cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    # Check if cache is less than 24 hours old
                    cache_time = datetime.fromisoformat(cache_data.get('timestamp', '1970-01-01'))
                    if datetime.now() - cache_time < timedelta(hours=24):
                        cached_feeds = cache_data.get('healthy_feeds', [])
                        cache_valid = True
                        logger.info(f"Using cached healthy feeds ({len(cached_feeds)} feeds, cached {cache_time.strftime('%Y-%m-%d %H:%M')})")
                except Exception as e:
                    logger.warning(f"Failed to load feed cache: {e}")
            
            if not cache_valid:
                logger.info("Running fresh feed validation...")
                # Use validator to get healthy feeds
                healthy_feeds = self.feed_validator.get_healthy_feeds(self.rss_feeds)
                
                # If we have reliable feeds configured, use them as backup
                if self.reliable_feeds:
                    # Add reliable feeds that aren't already in the list
                    for feed in self.reliable_feeds:
                        if feed not in healthy_feeds:
                            healthy_feeds.append(feed)
                
                # Cache the results
                try:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_data = {
                        'healthy_feeds': healthy_feeds,
                        'timestamp': datetime.now().isoformat(),
                        'total_feeds_tested': len(self.rss_feeds)
                    }
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, indent=2, ensure_ascii=False)
                    logger.info(f"Cached {len(healthy_feeds)} healthy feeds")
                except Exception as e:
                    logger.warning(f"Failed to cache healthy feeds: {e}")
                
                logger.info(f"Found {len(healthy_feeds)} healthy feeds out of {len(self.rss_feeds)} total")
                return healthy_feeds
            else:
                return cached_feeds
            
        except Exception as e:
            logger.error(f"Failed to get healthy feeds: {e}")
            # Fallback to original feeds
            return self.rss_feeds

    def _clean_text(self, text: str) -> str:
        """Clean the text by removing extra whitespace and HTML tags"""
        if not text:
            return ""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = ' '.join(text.split())
        return text

    def _is_relevant_article(self, title: str, description: str, query: str) -> bool:
        """
        Check if the article is relevant based on title and description
        """
        text = (title + " " + description).lower()
        
        # Check if any of the custom queries are present
        for keyword in self.custom_queries:
            if keyword.lower() in text:
                return True
                
        # Also check the original query if it's not in the custom queries
        if query.lower() not in [var.lower() for var in self.custom_queries]:
            if query.lower() in text:
                return True
            
        # If no custom queries, accept all articles from these specific sources
        if not self.custom_queries:
            return True
            
        return False

    def _clean_xml(self, xml_content: str) -> Optional[str]:
        """Clean problematic XML content"""
        if not xml_content:
            return None
            
        try:
            # Detect encoding if not UTF-8
            detected = chardet.detect(xml_content.encode())
            if detected['encoding'] and detected['encoding'].lower() != 'utf-8':
                xml_content = xml_content.encode(detected['encoding']).decode('utf-8', errors='ignore')
            
            # Remove invalid XML characters
            xml_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', xml_content)
            
            # Fix common HTML entities
            xml_content = html.unescape(xml_content)
            
            # Fix unclosed CDATA sections
            xml_content = re.sub(r'<!\[CDATA\[([^\]]*)(?!\]\])>', r'<![CDATA[\1]]>', xml_content)
            
            # Fix malformed tags
            soup = BeautifulSoup(xml_content, 'xml')
            xml_content = str(soup)
            
            return xml_content
        except Exception as e:
            logger.warning(f"Error cleaning XML: {str(e)}")
            return None

    def _fetch_feed_with_requests(self, feed_url: str) -> str:
        """Fetch feed content using improved SSL handler and multiple approaches"""
        try:
            # Try different variations of the URL if initial one fails
            urls_to_try = [
                feed_url,
                feed_url.rstrip('/') + '/feed',
                feed_url.rstrip('/') + '/rss',
                feed_url.replace('feed', 'rss')
            ]
            
            for url in urls_to_try:
                try:
                    # Use SSL handler for automatic SSL strategy selection
                    response = self.ssl_handler.fetch_with_auto_ssl(url, self.feed_timeout)
                    
                    if response and response.status_code == 200:
                        content_type = response.headers.get('content-type', '').lower()
                        if any(t in content_type for t in ['xml', 'rss', 'atom']):
                            return response.text
                        
                        # If content type is HTML, try to find RSS link
                        if 'html' in content_type:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            rss_link = soup.find('link', type='application/rss+xml')
                            if rss_link and rss_link.get('href'):
                                return self._fetch_feed_with_requests(rss_link['href'])
                                
                except Exception as e:
                    logger.debug(f"Failed to fetch {url}: {str(e)}")
                    continue
                    
            return None
        except Exception as e:
            logger.warning(f"Request failed for {feed_url}: {str(e)}")
            return None

    def _parse_feed_with_timeout(self, feed_url: str) -> Any:
        """Parse feed with timeout handling and multiple parsing attempts"""
        # Set socket timeout for the request
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.feed_timeout)
        
        try:
            # First try: Direct feedparser approach with SSL context
            try:
                feed = feedparser.parse(feed_url, handlers=[], request_headers=self.headers)
            except (socket.timeout, ssl.SSLError, URLError, OSError) as e:
                logger.debug(f"Direct feedparser failed for {feed_url}: {str(e)}")
                feed = None
            
            # If failed or empty, try with requests
            if not feed or feed.get('bozo', 0) == 1 or not feed.get('entries', []):
                xml_content = self._fetch_feed_with_requests(feed_url)
                if xml_content:
                    # Clean the XML content
                    cleaned_content = self._clean_xml(xml_content)
                    if cleaned_content:
                        # Try parsing the cleaned content
                        try:
                            feed = feedparser.parse(cleaned_content)
                        except Exception as e:
                            logger.debug(f"Failed to parse cleaned XML for {feed_url}: {str(e)}")
                            feed = None
            
            return feed
        except Exception as e:
            logger.debug(f"Error in _parse_feed_with_timeout for {feed_url}: {str(e)}")
            return None
        finally:
            # Restore original timeout
            socket.setdefaulttimeout(original_timeout)

    def _should_retry_source(self, feed_url: str, error: Exception) -> bool:
        """Determine if we should retry a failed source"""
        # Initialize failure count if not exists
        if feed_url not in self.source_failures:
            self.source_failures[feed_url] = 0
            
        self.source_failures[feed_url] += 1
        
        # Don't retry if we've hit the maximum retries
        if self.source_failures[feed_url] > self.max_retries:
            return False
            
        # Don't retry for certain types of errors
        if isinstance(error, (HTTPError, URLError)):
            if isinstance(error, HTTPError) and error.code in [403, 404, 410]:  # Permanent errors
                return False
                
        return True

    def _parse_feed(self, feed_url: str, query: str) -> List[Dict[Any, Any]]:
        """Parse a single RSS feed and return relevant articles"""
        if feed_url in self.failed_sources:
            logger.debug(f"Skipping previously failed source: {feed_url}")
            return []
            
        try:
            # Try to parse the feed with timeout and better error handling
            feed = self._parse_feed_with_timeout(feed_url)
            
            # Additional validation for feed structure
            if not feed or not hasattr(feed, 'entries'):
                raise ValueError("Invalid feed structure")
            
            # Check if feed parsing was successful
            if hasattr(feed, 'status') and feed.status >= 400:
                raise HTTPError(feed_url, feed.status, f"HTTP Error: {feed.status}", {}, None)
                
            if feed.get('bozo', 0) == 1 and hasattr(feed, 'bozo_exception'):
                # Only raise if it's a serious error
                if not isinstance(feed.bozo_exception, (feedparser.CharacterEncodingOverride)):
                    raise feed.bozo_exception
            
            articles = []
            entries = feed.get('entries', [])
            
            if not entries and hasattr(feed, 'feed') and not feed.feed:
                raise ValueError("Empty or invalid feed")
            
            for entry in entries:
                title = entry.get('title', '')
                description = entry.get('description', '')
                
                if self._is_relevant_article(title, description, query):
                    # Get the full content if available
                    content = entry.get('content', [{}])[0].get('value', '') if 'content' in entry else ''
                    if not content:
                        content = entry.get('summary', description)
                    
                    # Determine source region based on URL
                    source_region = self._determine_source_region(feed_url)
                    
                    article = {
                        'title': self._clean_text(title),
                        'description': self._clean_text(description),
                        'content': self._clean_text(content),
                        'url': entry.get('link', ''),
                        'published_date': entry.get('published', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'source': feed.feed.get('title', feed_url),
                        'source_url': feed_url,
                        'source_region': source_region,
                        'query': query,
                        'language': entry.get('language', 'en')
                    }
                    articles.append(article)
            
            # Reset failure count on success
            self.source_failures.pop(feed_url, None)
            return articles
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            logger.warning(f"Error parsing feed {feed_url}: {error_type} - {error_msg}")
            
            if not self._should_retry_source(feed_url, e):
                logger.error(f"Marking source as failed after multiple attempts: {feed_url}")
                self.failed_sources.add(feed_url)
                
            return []

    def _determine_source_region(self, feed_url: str) -> str:
        """Determine the source region based on the feed URL"""
        feed_url_lower = feed_url.lower()
        
        if any(domain in feed_url_lower for domain in ['nigeria', 'ng', 'tribuneonlineng', 'vanguardngr', 'thisdaylive', 'businessday.ng', 'thenationonlineng', 'herald.ng', 'dailypost.ng', 'guardian.ng', 'punchng', 'premiumtimesng', 'informationng', 'ripplesnigeria', 'dailynigerian', 'thenews-chronicle', 'pointblanknews', 'hallmarknews', 'pmnewsnigeria', 'saharareporters', 'lindaikejisblog', 'bellanaija']):
            return 'Nigeria'
        elif any(domain in feed_url_lower for domain in ['qatar', 'qa', 'qna.org.qa', 'alwatannews', 'aljazeera', 'dohanews', 'gulf-times']):
            return 'Qatar'
        elif any(domain in feed_url_lower for domain in ['india', 'indianexpress', 'nationalheraldindia', 'economictimes.indiatimes', 'thehindu', 'hindustantimes', 'tribuneindia']):
            return 'India'
        elif any(domain in feed_url_lower for domain in ['uk', 'telegraph.co.uk', 'mirror.co.uk', 'hulldailymail.co.uk', 'feedburner.com']):
            return 'UK'
        else:
            return 'International'

    def _ingest_batch(self, articles: List[Dict[str, Any]]) -> None:
        """Helper to ingest a batch of articles into the database"""
        if not articles:
            return
        try:
            for article in articles:
                self.ingestor.insert_record(article, commit=False)
            self.ingestor.session.commit()
            logger.info(f"Streamed {len(articles)} articles to DB")
        except Exception as e:
            logger.error(f"Error streaming batch to DB: {e}")


    def collect_from_feeds(self, query: str) -> List[Dict[Any, Any]]:
        """Collect news from healthy RSS feeds for a given query"""
        all_articles = []
        
        # Get healthy feeds using health monitoring
        healthy_feeds = self._get_healthy_feeds()
        
        logger.info(f"Collecting from {len(healthy_feeds)} healthy feeds for query: {query}")
        
        # Add overall timeout for the entire collection process from ConfigManager
        overall_timeout = self.config.get_int("collectors.rss.overall_timeout_seconds", 600)
        start_time = time.time()
        
        for i, feed_url in enumerate(healthy_feeds):
            # Check if we've exceeded the overall timeout
            if time.time() - start_time > overall_timeout:
                logger.warning(f"Overall collection timeout ({overall_timeout}s) reached. Processed {i}/{len(healthy_feeds)} feeds.")
                break
                
            if feed_url in self.failed_sources:
                continue
                
            try:
                logger.info(f"Collecting from {feed_url}")
                
                # Add individual feed timeout with threading
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._parse_feed, feed_url, query)
                    try:
                        buffer_seconds = self.config.get_int("collectors.rss.feed_buffer_seconds", 5)
                        articles = future.result(timeout=self.feed_timeout + buffer_seconds)
                        all_articles.extend(articles)
                        self._ingest_batch(articles)

                        
                        # Record successful collection in health monitor
                        self.health_monitor.validate_feed(feed_url)
                        
                    except FutureTimeoutError:
                        logger.warning(f"Timeout collecting from {feed_url}, skipping...")
                        self.failed_sources.add(feed_url)
                        continue
                
                # Be nice to the servers - delay from ConfigManager
                delay = self.config.get_int("collectors.rss.delay_between_feeds_seconds", 1)
                time.sleep(delay)
            except Exception as e:
                logger.error(f"Error collecting from {feed_url}: {str(e)}")
                # Record failure in health monitor
                self.health_monitor.validate_feed(feed_url)
                continue
        
        # Log summary of failed sources
        if self.failed_sources:
            logger.warning(f"Failed sources in this run: {len(self.failed_sources)}")
            for failed_url in self.failed_sources:
                logger.warning(f"Failed source: {failed_url}")
        
        # Generate health report
        try:
            health_report = self.health_monitor.get_feed_health_report(healthy_feeds)
            logger.info(f"Health report: {health_report['total_feeds']} feeds checked")
            for status, count in health_report['health_distribution'].items():
                if count > 0:
                    logger.info(f"  {status}: {count} feeds")
        except Exception as e:
            logger.warning(f"Failed to generate health report: {e}")
        
        return all_articles

    def validate_feeds_before_collection(self) -> Dict:
        """Validate all feeds before starting collection."""
        logger.info("Running feed validation before collection...")
        
        try:
            # Get validation report
            validation_report = self.feed_validator.generate_validation_report(self.rss_feeds)
            
            # Save validation report
            report_file = self.feed_validator.save_validation_report(validation_report)
            logger.info(f"Validation report saved to: {report_file}")
            
            # Log summary
            summary = validation_report['summary']
            logger.info(f"Validation Summary:")
            logger.info(f"  Total feeds: {summary['total_feeds']}")
            logger.info(f"  Valid feeds: {summary['valid_feeds']}")
            logger.info(f"  Invalid feeds: {summary['invalid_feeds']}")
            logger.info(f"  Average response time: {summary['avg_response_time']:.2f}s")
            logger.info(f"  Total entries: {summary['total_entries']}")
            
            # Log recommendations
            if validation_report['recommendations']:
                logger.info("Recommendations:")
                for rec in validation_report['recommendations']:
                    logger.info(f"  - {rec}")
            
            return validation_report
            
        except Exception as e:
            logger.error(f"Feed validation failed: {e}")
            return {}

    def collect_all(self, queries: List[str] = None, output_file: str = None, target_name: str = None, validate_first: bool = False) -> None:
        """
        Collect news for all queries and save to CSV
        
        Args:
            queries: Optional list of additional search queries
            output_file: Optional output file path. If not provided, will use default path.
            target_name: Name of the target individual for file naming
            validate_first: Whether to force fresh validation (default: False, uses cache)
        """
        # Run feed validation first if requested (usually not needed due to caching)
        if validate_first:
            self.validate_feeds_before_collection()
        
        all_articles = []
        
        # Use custom queries as the base if available, otherwise use empty list
        search_queries = self.custom_queries.copy() if self.custom_queries else []
        
        # Add any additional queries if provided
        if queries:
            search_queries.extend(queries)
        
        # If no queries are available, use keywords from ConfigManager (enables DB editing)
        if not search_queries:
            from src.config.config_manager import ConfigManager
            config = ConfigManager()
            
            # Priority 1: Default keywords from ConfigManager (enables DB editing)
            default_keywords = config.get_list("collectors.keywords.default.rss_nigerian_qatar_indian", None)
            if default_keywords:
                logger.info(f"Using default keywords from ConfigManager: {default_keywords}")
                search_queries = default_keywords
            else:
                # Priority 2: Legacy key (backward compatibility)
                search_queries = config.get_list("collectors.default_keywords.rss_nigerian_qatar_indian", [
                    "nigeria", "qatar", "india", "africa", "middle east", "gulf", 
                    "arab", "nigerian", "qatari", "indian", "politics", "business", 
                    "economy", "oil", "gas", "energy", "trade", "diplomacy"
                ])
                logger.warning("Using legacy default_keywords - consider migrating to collectors.keywords.default.rss_nigerian_qatar_indian")
        
        # Remove duplicates while preserving order
        search_queries = list(dict.fromkeys(search_queries))
        
        for query in search_queries:
            logger.info(f"Collecting RSS feed news for query: {query}")
            articles = self.collect_from_feeds(query)
            all_articles.extend(articles)
        
        if all_articles:
            df = pd.DataFrame(all_articles)
            
            # Remove duplicates based on URL and title
            df = df.drop_duplicates(subset=['url', 'title'])
            
            # Sort by published date (handle mixed date formats from different RSS feeds)
            df['published_date'] = pd.to_datetime(df['published_date'], format='mixed', errors='coerce')
            df = df.sort_values('published_date', ascending=False)
            
            # Save to CSV
            if output_file is None:
                # Use target name in filename if provided
                filename_prefix = f"nigerian_qatar_indian_rss_{target_name.replace(' ', '_').lower()}" if target_name else "nigerian_qatar_indian_rss"
                output_file = self.path_manager.data_raw / f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            df.to_csv(output_file, index=False)
            logger.info(f"Saved {len(df)} articles to {output_file}")
            
            # Print summary by region
            if 'source_region' in df.columns:
                region_summary = df['source_region'].value_counts()
                logger.info("Articles collected by region:")
                for region, count in region_summary.items():
                    logger.info(f"  {region}: {count} articles")
        else:
            logger.warning("No articles found for any query")

def main(target_and_variations: Optional[List[str]] = None, user_id: Optional[str] = None):
    """
    Main function called by run_collectors. Accepts target/variations list.
    
    Args:
        target_and_variations: List containing target name as first element and query variations as remaining elements
        user_id: Optional user ID for database queries
    """
    if not target_and_variations or len(target_and_variations) == 0:
        print("[Nigerian Qatar Indian RSS Collector] Error: No target/query variations provided.")
        return
    
    target_name = target_and_variations[0]
    queries = target_and_variations[1:]
    print(f"[Nigerian Qatar Indian RSS Collector] Received Target: {target_name}, Queries: {queries}")
    
    # Construct output file name
    from src.config.path_manager import PathManager
    path_manager = PathManager()
    today = datetime.now().strftime("%Y%m%d")
    safe_target_name = target_name.replace(" ", "_").lower()
    output_path = path_manager.data_raw / f"nigerian_qatar_indian_rss_{safe_target_name}_{today}.csv"
    
    # Initialize collector with the provided queries
    collector = NigerianQatarIndianRSSCollector(custom_queries=queries, user_id=user_id)

    
    # Collect data using the provided queries
    collector.collect_all(queries=queries, output_file=output_path, target_name=target_name)

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Collect RSS data from Nigerian, Qatar, and Indian sources')
    parser.add_argument('--queries', type=str, required=False, help='JSON string of query variations')
    parser.add_argument('--since', type=str, required=False, help='Start date (ignored for RSS - RSS feeds dont support date filtering)')
    parser.add_argument('--until', type=str, required=False, help='End date (ignored for RSS - RSS feeds dont support date filtering)')
    
    args = parser.parse_args()
    
    if args.queries:
        try:
            # Parse the JSON string to get the list of queries
            queries_list = json.loads(args.queries)
            print(f"[Nigerian Qatar Indian RSS Collector] Parsed queries: {queries_list}")
            
            # Get user_id from environment if running via CLI
            user_id = os.getenv('COLLECTOR_USER_ID')
            main(queries_list, user_id=user_id)

        except json.JSONDecodeError as e:
            print(f"[Nigerian Qatar Indian RSS Collector] Error parsing queries JSON: {e}")
            main([])
    else:
        print("Running Nigerian Qatar Indian RSS collector directly (without args)... Use run_collectors.py for proper execution.")
        main([]) # Pass empty list for direct run scenario
