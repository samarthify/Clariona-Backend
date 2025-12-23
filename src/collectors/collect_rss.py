import feedparser
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict, Any
# Remove the old import that doesn't exist
# from query_variations import query_variations
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

# Suppress SSL warnings for cleaner output
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RSSFeedCollector:
    def __init__(self, custom_queries=None):
        self.base_path = Path(__file__).parent.parent.parent
        
        # Use provided queries or fall back to predefined query variations as keywords for filtering
        self.custom_queries = custom_queries or []
        
        # Timeout settings
        self.feed_timeout = 15  # Increased timeout for slower servers
        self.max_retries = 3    # Increased retries
        
        # SSL Context for certificate verification issues
        self.ssl_context = ssl._create_unverified_context()
        
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
        
        # Updated RSS feeds with corrected URLs and alternative endpoints
        self.rss_feeds = [
            # Qatar News
            "https://www.gulf-times.com/rss/feed",
            "https://www.thepeninsulaqatar.com/rss/feed",
            "https://dohanews.co/feed",
            "https://www.qna.org.qa/en/rss",
            "https://www.lusailnews.net/rss",
            "https://alarab.qa/rss",
            "https://al-watan.com/feed",
            
            # Major Middle East News
            "https://www.aljazeera.com/xml/rss/all.xml",
            "https://english.alarabiya.net/feed/rss",
            "https://arab.news/rss",
            "https://gulfnews.com/rss/latest",
            "https://www.khaleejtimes.com/rss-feed",
            "https://www.thenationalnews.com/world/rss",
            "https://english.aawsat.com/feed",
            "https://www.middleeastmonitor.com/feed",
            "https://english.alaraby.co.uk/rss.xml",
            
            # UK News
            "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
            "https://www.theguardian.com/world/middleeast/rss",
            "https://www.independent.co.uk/news/world/middle-east/rss",
            "https://www.telegraph.co.uk/rss.xml",
            "https://www.dailymail.co.uk/news/worldnews/index.rss",
            
            # US News
            "http://rss.cnn.com/rss/edition_meast.rss",
            "http://rss.cnn.com/rss/cnn_topstories.rss",
            "https://feeds.npr.org/1001/rss.xml",
            "https://www.latimes.com/world/middleeast/rss2.0.xml",
            "https://www.washingtontimes.com/rss/headlines/news/world",
            
            # Business and Politics
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://www.ft.com/world/mideast/rss",
            "https://www.economist.com/middle-east-and-africa/rss.xml",
            "https://www.cnbc.com/id/100727362/device/rss/rss.html",
            "https://www.marketwatch.com/rss/topstories",
            
            # Think Tanks and Policy
            "https://www.atlanticcouncil.org/feed",
            "https://www.csis.org/feed/reports",
            
            # Energy News
            "https://www.rigzone.com/news/rss",
            "https://oilprice.com/rss/main",
            
            # Additional International News
            "https://www.reuters.com/rssfeed/world/",
            "https://feeds.skynews.com/feeds/rss/world.xml",
            "https://www.dw.com/en/top-stories/rss-topstories/s-9097",
            "https://www.france24.com/en/middle-east/rss",
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "https://www.voanews.com/api/zt$ityeq_wql",
            "https://www3.nhk.or.jp/nhkworld/en/news/rss/",
            "https://www.straitstimes.com/rss/world/feed.xml",
            
            # Technology News
            "https://feeds.feedburner.com/TechCrunch",
            "https://www.wired.com/feed/rss",
            "https://www.theverge.com/rss/index.xml",
            "https://rss.slashdot.org/Slashdot/slashdotMain",
            "https://www.cnet.com/rss/news/",
            "https://arstechnica.com/feed/",
            
            # Entertainment and Culture
            "https://variety.com/feed/",
            "https://www.rollingstone.com/feed/",
            "https://www.hollywoodreporter.com/feed/",
            "https://www.vogue.com/rss",
            "https://www.timeout.com/london/rss",
            
            # Sports
            "https://www.espn.com/espn/rss/news",
            "https://www.skysports.com/rss/0",
            "https://www.fifa.com/rss-feeds/news",
            "https://www.goal.com/feeds/en/news",
            "https://www.cbssports.com/rss/headlines/",
            
            # Science and Environment
            "https://rss.sciam.com/ScientificAmerican-Global",
            "https://www.newscientist.com/feed/home/?cmpid=RSS",
            "https://www.nature.com/nature.rss",
            "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
            "https://www.sciencedaily.com/rss/all.xml",
            
            # Social Media and Blogs
            "https://medium.com/feed/tag/world-news",
            "https://medium.com/feed/tag/middle-east",
            "https://rss.app/feeds/SGYMbetbJ8RyDPtL.xml",  # Twitter trending topics
            "https://www.reddit.com/r/worldnews/.rss",
            "https://www.reddit.com/r/geopolitics/.rss",

            # India News
            "https://www.thehindu.com/news/national/rss.xml",
            "https://www.thehindu.com/news/international/rss.xml",
            "https://www.thehindu.com/news/business/rss.xml",
            "https://www.thehindu.com/news/sports/rss.xml",
            "https://www.thehindu.com/news/entertainment/rss.xml",
            
            # Nigeria News
            "https://www.vanguardngr.com/rss/all.xml",
            "https://www.thisdaylive.com/rss/all.xml",
            "https://www.premiumtimesng.com/rss/all.xml",
            "https://www.dailytrust.com/rss/all.xml",
            "https://www.nairametrics.com/rss/all.xml",
            
        ]

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
            return query.lower() in text
            
        return False

    def _clean_xml(self, xml_content: str) -> str:
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
        """Fetch feed content using requests with better error handling and SSL verification"""
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
                    # First try with SSL verification enabled
                    try:
                        response = requests.get(
                            url,
                            headers=self.headers,
                            timeout=self.feed_timeout,
                            verify=True  # Try with SSL verification first
                        )
                    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                        # If SSL verification fails, try without it
                        logger.debug(f"SSL verification failed for {url}, trying without verification")
                        response = requests.get(
                            url,
                            headers=self.headers,
                            timeout=self.feed_timeout,
                            verify=False  # Fallback to unverified
                        )
                    
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '').lower()
                        if any(t in content_type for t in ['xml', 'rss', 'atom']):
                            return response.text
                        
                        # If content type is HTML, try to find RSS link
                        if 'html' in content_type:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            rss_link = soup.find('link', type='application/rss+xml')
                            if rss_link and rss_link.get('href'):
                                return self._fetch_feed_with_requests(rss_link['href'])
                                
                except requests.RequestException:
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
                    
                    article = {
                        'title': self._clean_text(title),
                        'description': self._clean_text(description),
                        'content': self._clean_text(content),
                        'url': entry.get('link', ''),
                        'published_date': entry.get('published', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'source': feed.feed.get('title', feed_url),
                        'source_url': feed_url,
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

    def collect_from_feeds(self, query: str) -> List[Dict[Any, Any]]:
        """Collect news from all RSS feeds for a given query"""
        all_articles = []
        
        for feed_url in self.rss_feeds:
            if feed_url in self.failed_sources:
                continue
                
            try:
                logger.info(f"Collecting from {feed_url}")
                articles = self._parse_feed(feed_url, query)
                all_articles.extend(articles)
                
                # Be nice to the servers
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error collecting from {feed_url}: {str(e)}")
                continue
        
        # Log summary of failed sources
        if self.failed_sources:
            logger.warning(f"Failed sources in this run: {len(self.failed_sources)}")
            for failed_url in self.failed_sources:
                logger.warning(f"Failed source: {failed_url}")
        
        return all_articles

    def collect_all(self, queries: List[str] = None, output_file: str = None, target_name: str = None) -> None:
        """
        Collect news for all queries and save to CSV
        
        Args:
            queries: Optional list of additional search queries
            output_file: Optional output file path. If not provided, will use default path.
            target_name: Name of the target individual for file naming
        """
        all_articles = []
        
        # Use custom queries as the base if available, otherwise use empty list
        search_queries = self.custom_queries.copy() if self.custom_queries else []
        
        # Add any additional queries if provided
        if queries:
            search_queries.extend(queries)
        
        # If no queries are available, use a default set of relevant keywords
        if not search_queries:
            # Default keywords for Middle East and international news
            search_queries = [
                "middle east", "qatar", "nigeria", "gulf", "arab", "islamic", 
                "oil", "energy", "politics", "diplomacy", "trade", "business"
            ]
        
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
            
            # Sort by published date
            df['published_date'] = pd.to_datetime(df['published_date'])
            df = df.sort_values('published_date', ascending=False)
            
            # Save to CSV
            if output_file is None:
                # Use target name in filename if provided
                filename_prefix = f"rss_news_{target_name.replace(' ', '_').lower()}" if target_name else "rss_news"
                output_file = self.base_path / 'data' / 'raw' / f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            df.to_csv(output_file, index=False)
            logger.info(f"Saved {len(df)} articles to {output_file}")
        else:
            logger.warning("No articles found for any query")

def main(target_and_variations: List[str] = None, user_id: str = None):
    """
    Main function called by run_collectors. Accepts target/variations list.
    
    Args:
        target_and_variations: List containing target name as first element and query variations as remaining elements
        user_id: Optional user ID for database queries
    """
    if not target_and_variations or len(target_and_variations) == 0:
        print("[RSS Collector] Error: No target/query variations provided.")
        return
    
    target_name = target_and_variations[0]
    queries = target_and_variations[1:]
    print(f"[RSS Collector] Received Target: {target_name}, Queries: {queries}")
    
    # Construct output file name
    today = datetime.now().strftime("%Y%m%d")
    safe_target_name = target_name.replace(" ", "_").lower()
    output_path = Path(__file__).parent.parent.parent / "data" / "raw" / f"rss_{safe_target_name}_{today}.csv"
    
    # Initialize collector with the provided queries
    collector = RSSFeedCollector(custom_queries=queries)
    
    # Collect data using the provided queries
    collector.collect_all(queries=queries, output_file=output_path, target_name=target_name)

if __name__ == "__main__":
    print("Running RSS collector directly (without args)... Use run_collectors.py for proper execution.")
    main([]) # Pass empty list for direct run scenario 