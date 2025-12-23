import requests
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional
import sys
import time
import json
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import random
import feedparser
import xml.etree.ElementTree as ET

# Force UTF-8 encoding for the entire script to prevent charmap codec errors
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HybridRadioCollector:
    def __init__(self):
        # Load .env from collectors folder
        env_path = Path(__file__).parent / '.env'
        load_dotenv(env_path)
        self.base_path = Path(__file__).parent.parent.parent
        
        # Target-specific configuration
        self.target_config = None
        
        # Radio station configuration with grouped URLs
        self.radio_stations = self._load_radio_stations()
        
        # Online sources configuration
        self.online_sources = self._load_online_sources()
        
        # Session for HTTP requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Rate limiting
        self.request_delay = 2  # seconds between requests
        self.last_request_time = 0
        self.max_retries = 3

    def _load_radio_stations(self) -> Dict[str, Dict[str, Any]]:
        """Load radio station configuration with grouped URLs by station"""
        return {
            'Wazobia FM': {
                'name': 'Wazobia FM',
                'region': 'Southwest',
                'location': 'Lagos',
                'urls': {
                    'web': ['https://www.wazobiafm.com/news/'],
                    'rss': ['https://www.wazobiafm.com/news/hottori/feed.xml']
                }
            },
            'Cool FM': {
                'name': 'Cool FM',
                'region': 'Southwest', 
                'location': 'Lagos',
                'urls': {
                    'web': ['https://www.coolfm.ng/news/news/'],
                    'rss': ['https://www.coolfm.ng/news/news/feed.xml']
                }
            },
            'Nigeria Info FM': {
                'name': 'Nigeria Info FM',
                'region': 'Southwest',
                'location': 'Lagos',
                'urls': {
                    'web': ['https://www.nigeriainfo.fm/port-harcourt/news/talkportharcourt/', 
                           'https://www.nigeriainfo.fm/port-harcourt/news/national/',
                           'https://www.nigeriainfo.fm/abuja/news/national/',
                           'https://www.nigeriainfo.fm/lagos/news/national/'],
                    'rss': ['https://www.nigeriainfo.fm/port-harcourt/news/talkportharcourt/feed.xml',
                           'https://www.nigeriainfo.fm/port-harcourt/news/national/feed.xml',
                           'https://www.nigeriainfo.fm/abuja/news/national/feed.xml',
                           'https://www.nigeriainfo.fm/lagos/news/national/feed.xml']
                }
            },
            'Radio Nigeria': {
                'name': 'Radio Nigeria',
                'region': 'North Central',
                'location': 'Abuja',
                'urls': {
                    'web': ['https://www.radionigeriakaduna.gov.ng/category/news/',
                           'https://radionigeria.gov.ng/category/news/',
                           'https://radionigeria.gov.ng/category/news/local/',
                           'https://radionigeria.gov.ng/category/news/politics/'],
                    'rss': []
                }
            },
            'ABS Radio': {
                'name': 'ABS Radio',
                'region': 'Southeast',
                'location': 'Anambra',
                'urls': {
                    'web': ['https://absradiotelevision.com/category/nigeria/'],
                    'rss': []
                }
            },
            'BBC Hausa': {
                'name': 'BBC Hausa',
                'region': 'North West',
                'location': 'Kano',
                'urls': {
                    'web': ['https://www.bbc.com/hausa/bbc_hausa_radio/liveradio'],
                    'rss': []
                }
            },
            'Fresh FM': {
                'name': 'Fresh FM',
                'region': 'Southwest',
                'location': 'Ibadan',
                'urls': {
                    'web': ['https://www.freshfmnigeria.com/category/news/'],
                    'rss': []
                }
            },
            'Rhythm FM': {
                'name': 'Rhythm FM',
                'region': 'Southwest',
                'location': 'Lagos',
                'urls': {
                    'web': ['https://rhythm937.com/category/politics/'],
                    'rss': []
                }
            },
            'Radio Nigeria Ibadan': {
                'name': 'Radio Nigeria Ibadan',
                'region': 'Southwest',
                'location': 'Ibadan',
                'urls': {
                    'web': ['https://radionigeriaibadan.gov.ng/category/tw-news/'],
                    'rss': []
                }
            },
            'Radio Lagos': {
                'name': 'Radio Lagos',
                'region': 'Southwest',
                'location': 'Lagos',
                'urls': {
                    'web': ['https://radiolagos1075.com/'],
                    'rss': []
                }
            },
            'Urban Radio': {
                'name': 'Urban Radio',
                'region': 'Southeast',
                'location': 'Enugu',
                'urls': {
                    'web': ['https://urbanradio945.com/category/politics/'],
                    'rss': []
                }
            },
            'Blaze FM': {
                'name': 'Blaze FM',
                'region': 'Southeast',
                'location': 'Anambra',
                'urls': {
                    'web': ['https://blaze915fm.com/political-news/'],
                    'rss': []
                }
            },
            'ESBS Radio': {
                'name': 'ESBS Radio',
                'region': 'Southeast',
                'location': 'Enugu',
                'urls': {
                    'web': ['https://esbsenugu.com/d?id=Local'],
                    'rss': []
                }
            },
            'Vision FM': {
                'name': 'Vision FM',
                'region': 'North Central',
                'location': 'Abuja',
                'urls': {
                    'web': ['https://visionfm.ng/news'],
                    'rss': []
                }
            },
            'Freedom Radio': {
                'name': 'Freedom Radio',
                'region': 'North West',
                'location': 'Kano',
                'urls': {
                    'web': ['https://freedomradionig.com/category/labarai/'],
                    'rss': []
                }
            },
            'Arewa Radio': {
                'name': 'Arewa Radio',
                'region': 'North West',
                'location': 'Kano',
                'urls': {
                    'web': ['https://www.arewaradio.com/news/labarai-news/'],
                    'rss': ['https://www.arewaradio.com/news/labarai-news/feed.xml']
                }
            },
            'VOA Hausa': {
                'name': 'VOA Hausa',
                'region': 'North West',
                'location': 'Kano',
                'urls': {
                    'web': ['https://www.voahausa.com/najeriya'],
                    'rss': []
                }
            }
        }

    def _load_online_sources(self) -> Dict[str, Dict[str, Any]]:
        """Load online sources configuration from target_configs.json with regional structure"""
        try:
            config_path = self.base_path / "config" / "target_configs.json"
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Look for online sources in any target that has them
            targets = config.get('targets', {})
            for target_name, target_config in targets.items():
                sources = target_config.get('sources', {})
                if 'online_sources' in sources:
                    online_sources_config = sources['online_sources']
                    regions = online_sources_config.get('regions', {})
                    
                    # Flatten all regional sources into a single dictionary
                    all_sources = {}
                    for region_name, region_config in regions.items():
                        region_sources = region_config.get('sources', {})
                        for source_key, source_config in region_sources.items():
                            # Add region info to each source
                            source_config['region'] = region_config.get('name', region_name)
                            source_config['region_key'] = region_name
                            all_sources[source_key] = source_config
                    
                    logger.info(f"Loaded {len(all_sources)} online sources from {len(regions)} regions in {target_name} target")
                    return all_sources
            
            logger.warning("No online_sources found in any target configuration")
            return {}
        except Exception as e:
            logger.error(f"Failed to load online sources configuration: {e}")
            return {}

    def set_target_config(self, target_config):
        """Set target-specific configuration for this collector"""
        self.target_config = target_config
        logger.info(f"Set target config for: {target_config.name if target_config else 'None'}")

    def _rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
        self.last_request_time = time.time()

    def _get_target_keywords(self) -> List[str]:
        """Get keywords to filter content based on target configuration"""
        if self.target_config and hasattr(self.target_config, 'keywords'):
            return self.target_config.keywords
        # Fallback to default keywords
        return ["nigeria", "government", "politics", "economy", "news"]

    def _should_include_content(self, content: str) -> bool:
        """Determine if content should be included based on target configuration"""
        if not self.target_config:
            return True
        
        target_keywords = self._get_target_keywords()
        content_lower = content.lower()
        
        # Check if content contains any target keywords
        has_target_keywords = any(keyword.lower() in content_lower for keyword in target_keywords)
        
        # Apply content quality filtering - reject obvious non-news content
        skip_content_keywords = [
            'masturbate', 'sex', 'drunk', 'alcohol', 'piss', 'bed', 'belle', 
            'husband', 'wife', 'girlfriend', 'sister', 'divorce', 'marriage', 'dating', 
            'love', 'romance', 'kiss', 'kissing', 'wakeup', 'show', 'backyard', 'marketrunz', 
            'kulele', 'nightjolly', 'hottori', 'stories', 'exclusive-interviews', 'editorial',
            'burna', 'tiwa', 'savage', 'bayanni', 'davido', 'ayra', 'starr', '2baba',
            'billboard', 'mobo', 'awards', 'album', 'song', 'concert', 'artist',
            'super eagles', 'football', 'basketball', 'boxing', 'athlete', 'player',
            'team', 'match', 'game', 'sport', 'fitness', 'health', 'medical',
            'hiv', 'zobo', 'blood', 'kidnap', 'pikin', 'shop', 'sell'
        ]
        
        has_skip_content = any(skip in content_lower for skip in skip_content_keywords)
        if has_skip_content:
            return False
        
        # Apply additional filters if configured
        if hasattr(self.target_config, 'sources'):
            # Check both radio and online sources filters
            for source_type in ['radio', 'online_sources']:
                if source_type in self.target_config.sources:
                    source_config = self.target_config.sources[source_type]
                    if hasattr(source_config, 'filters') and source_config.filters:
                        filters = source_config.filters
                        
                        # Check exclude filters
                        if 'exclude' in filters:
                            exclude_terms = [term.lower() for term in filters['exclude']]
                            if any(term in content_lower for term in exclude_terms):
                                return False
        
        return has_target_keywords

    def _find_pagination_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find pagination links on the page"""
        pagination_links = []
        
        # Common pagination selectors
        pagination_selectors = [
            'a[href*="page="]',  # ?page=2, ?page=3
            'a[href*="/page/"]',  # /page/2/, /page/3/
            'a[href*="p="]',  # ?p=2, ?p=3
            '.pagination a',  # .pagination class
            '.pager a',  # .pager class
            '.page-numbers a',  # WordPress pagination
            '.pagination-links a',  # Custom pagination
            'a[rel="next"]',  # Next page link
            'a[title*="Next"]',  # Next page by title
            'a[title*="next"]',  # Next page by title (lowercase)
            'a:contains("Next")',  # Next page by text
            'a:contains("2")',  # Page 2
            'a:contains("3")',  # Page 3
            'a:contains("4")',  # Page 4
            'a:contains("5")',  # Page 5
        ]
        
        for selector in pagination_selectors:
            try:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    if href:
                        # Convert relative URLs to absolute
                        full_url = urljoin(base_url, href)
                        if full_url not in pagination_links and full_url != base_url:
                            pagination_links.append(full_url)
            except Exception as e:
                logger.debug(f"Pagination selector {selector} failed: {e}")
                continue
        
        # Also look for numbered pagination (1, 2, 3, 4, 5)
        numbered_links = soup.find_all('a', href=True)
        for link in numbered_links:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            
            # Check if it's a numbered page link
            if text.isdigit() and 2 <= int(text) <= 10:  # Pages 2-10
                full_url = urljoin(base_url, href)
                if full_url not in pagination_links and full_url != base_url:
                    pagination_links.append(full_url)
        
        return pagination_links[:5]  # Limit to 5 pages

    def _find_section_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find section-specific links like 'More from Fact Check', 'More from Hot Tori', etc."""
        section_links = []
        
        # Look for "More from..." links
        more_links = soup.find_all('a', href=True, string=lambda text: text and 'More from' in text)
        logger.info(f"Found {len(more_links)} 'More from' links")
        
        for link in more_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            if href:
                # Convert relative URLs to absolute
                full_url = urljoin(base_url, href)
                if full_url not in section_links and full_url != base_url:
                    section_links.append(full_url)
                    logger.info(f"Found section link: {text} -> {full_url}")
        
        # Also look for specific Wazobia FM section links
        if 'wazobiafm.com' in base_url:
            wazobia_sections = [
                '/news/fact-check/',
                '/news/hottori/',
                '/news/footballrepublik/'
            ]
            
            for section in wazobia_sections:
                full_url = urljoin(base_url, section)
                if full_url not in section_links:
                    section_links.append(full_url)
                    logger.info(f"Added Wazobia FM section: {full_url}")
        
        return section_links


    def _extract_articles_from_soup(self, soup: BeautifulSoup, station_name: str, url: str) -> List[Dict[str, Any]]:
        """Extract articles from a BeautifulSoup object"""
        articles = []
        
        # Look for Wazobia FM specific structure first
        if 'wazobiafm.com' in url:
            # Wazobia FM has specific structure with .gm-sec-title links
            wazobia_articles = soup.find_all('a', class_='gm-sec-title')
            logger.info(f"Found {len(wazobia_articles)} Wazobia FM articles")
            
            for article_link in wazobia_articles:
                try:
                    title = article_link.get_text(strip=True)
                    href = article_link.get('href', '')
                    
                    # Get description from parent element
                    parent = article_link.find_parent('li')
                    description = ""
                    if parent:
                        desc_elem = parent.find('p', class_='gm-sec-description')
                        if desc_elem:
                            description = desc_elem.get_text(strip=True)
                    
                    if title and len(title) > 10:
                        article_data = {
                            'title': title,
                            'text': description or title,
                            'url': urljoin(url, href) if href else '',
                            'source': station_name,
                            'source_url': url,
                            'source_type': 'radio',
                            'platform': 'radio_website',
                            'language': 'English',
                            'country': 'Nigeria',
                            'region': self.radio_stations[station_name]['region'],
                            'location': self.radio_stations[station_name]['location'],
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'published_date': datetime.now().strftime('%Y-%m-%d'),
                            'query': 'radio_collection',
                            'file_source': 'radio_hybrid',
                            'description': description[:200] + '...' if len(description) > 200 else description,
                            'content': description or title,
                            'id': f"radio_web_{hash(title + description)}_{int(time.time())}",
                            'favorite': False,
                            'tone': 'neutral',
                            'source_name': station_name,
                            'parent_url': url,
                            'parent_id': f"web_{station_name.replace(' ', '_').lower()}",
                            'children': [],
                            'direct_reach': 0,
                            'cumulative_reach': 0,
                            'domain_reach': 0,
                            'tags': ['radio', 'web', self.radio_stations[station_name]['region'].lower()]
                        }
                        
                        if self._should_include_content(article_data.get('text', '')):
                            articles.append(article_data)
                            
                except Exception as e:
                    logger.warning(f"Error processing Wazobia FM article: {e}")
                    continue
            
            if articles:
                return articles
        
        # Fallback to general article extraction
        # Look for common news/article patterns with comprehensive selectors
        article_selectors = [
            'article', '.article', '.news-item', '.post', '.story',
            '.content', '.news-content', '.blog-post', '.entry',
            '.news', '.headline', '.title', 'h1', 'h2', 'h3',
            '.item', '.card', '.tile', '.block', '.section'
        ]
        
        found_articles = []
        for selector in article_selectors:
            try:
                elements = soup.select(selector)
                found_articles.extend(elements)
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        # If no specific article elements found, look for links that might be articles
        if not found_articles:
            logger.info(f"No article elements found, searching all links for {url}")
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # More lenient filtering - accept if it looks like news content
                news_keywords = [
                    'news', 'politics', 'government', 'policy', 'economy', 'business', 
                    'national', 'public', 'official', 'announcement', 'statement', 'press', 
                    'briefing', 'minister', 'president', 'governor', 'senate', 'house', 
                    'assembly', 'election', 'vote', 'campaign', 'budget', 'revenue', 'tax', 
                    'infrastructure', 'development', 'security', 'military', 'police', 'court', 
                    'judge', 'law', 'bill', 'act', 'regulation', 'commission', 'agency', 
                    'department', 'ministry', 'tinubu', 'shettima', 'apc', 'pdp', 'labour',
                    'protest', 'workers', 'minimum wage', 'cost of living', 'lagos', 'abuja', 'nigeria',
                    'update', 'latest', 'breaking', 'report', 'story', 'article', 'post'
                ]
                
                # Only skip obvious non-news content
                skip_keywords = [
                    'masturbate', 'sex', 'drunk', 'alcohol', 'piss', 'bed', 'belle', 
                    'husband', 'wife', 'girlfriend', 'sister', 'divorce', 'marriage', 'dating', 
                    'love', 'romance', 'kiss', 'kissing', 'wakeup', 'show', 'backyard', 'marketrunz', 
                    'kulele', 'nightjolly', 'hottori', 'stories', 'exclusive-interviews', 'editorial',
                    'burna', 'tiwa', 'savage', 'bayanni', 'davido', 'ayra', 'starr', '2baba',
                    'billboard', 'mobo', 'awards', 'album', 'song', 'concert', 'artist',
                    'super eagles', 'football', 'basketball', 'boxing', 'athlete', 'player',
                    'team', 'match', 'game', 'sport', 'fitness', 'health', 'medical',
                    'hiv', 'zobo', 'blood', 'kidnap', 'pikin', 'shop', 'sell'
                ]
                
                # Check if it has news keywords OR looks like a news URL
                has_news_keywords = any(keyword in href.lower() or keyword in text.lower() for keyword in news_keywords)
                has_skip_keywords = any(skip in href.lower() or skip in text.lower() for skip in skip_keywords)
                looks_like_news_url = any(term in href.lower() for term in ['news', 'article', 'story', 'post', 'update', 'latest'])
                
                # Accept if it has news keywords OR looks like news URL, and doesn't have skip keywords
                if (len(text) > 15 and (has_news_keywords or looks_like_news_url) and not has_skip_keywords):
                    found_articles.append(link)
        
        # Also look for headings that might be news titles
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            text = heading.get_text(strip=True)
            if len(text) > 15:
                # More lenient news keyword checking
                news_keywords = ['news', 'politics', 'government', 'policy', 'economy', 'business', 
                               'national', 'public', 'official', 'announcement', 'statement', 'press', 
                               'briefing', 'minister', 'president', 'governor', 'senate', 'house', 
                               'assembly', 'election', 'vote', 'campaign', 'budget', 'revenue', 'tax', 
                               'infrastructure', 'development', 'security', 'military', 'police', 'court', 
                               'judge', 'law', 'bill', 'act', 'regulation', 'commission', 'agency', 
                               'department', 'ministry', 'tinubu', 'shettima', 'apc', 'pdp', 'labour',
                               'protest', 'workers', 'minimum wage', 'cost of living', 'lagos', 'abuja', 'nigeria',
                               'update', 'latest', 'breaking', 'report', 'story', 'article', 'post']
                
                # Only skip obvious non-news content
                skip_keywords = ['masturbate', 'sex', 'drunk', 'alcohol', 'piss', 'bed', 'belle', 
                               'husband', 'wife', 'girlfriend', 'sister', 'divorce', 'marriage', 'dating', 
                               'love', 'romance', 'kiss', 'kissing', 'wakeup', 'show', 'backyard', 'marketrunz', 
                               'kulele', 'nightjolly', 'hottori', 'stories', 'exclusive-interviews', 'editorial',
                               'burna', 'tiwa', 'savage', 'bayanni', 'davido', 'ayra', 'starr', '2baba',
                               'billboard', 'mobo', 'awards', 'album', 'song', 'concert', 'artist',
                               'super eagles', 'football', 'basketball', 'boxing', 'athlete', 'player',
                               'team', 'match', 'game', 'sport', 'fitness', 'health', 'medical',
                               'hiv', 'zobo', 'blood', 'kidnap', 'pikin', 'shop', 'sell']
                
                has_news_keywords = any(keyword in text.lower() for keyword in news_keywords)
                has_skip_keywords = any(skip in text.lower() for skip in skip_keywords)
                
                # Accept if it has news keywords and doesn't have skip keywords
                if has_news_keywords and not has_skip_keywords:
                    found_articles.append(heading)
        
        # Process found articles
        for element in found_articles[:25]:  # Limit to 25 articles per page
            try:
                article_data = self._extract_article_data(element, station_name, url)
                if article_data and self._should_include_content(article_data.get('text', '')):
                    articles.append(article_data)
            except Exception as e:
                logger.warning(f"Error processing article from {url}: {e}")
                continue
        
        return articles

    def _scrape_web_page(self, url: str, station_name: str) -> List[Dict[str, Any]]:
        """Scrape content from a regular web page with pagination support"""
        articles = []
        
        try:
            self._rate_limit()
            logger.info(f"Scraping web page: {url}")
            
            # Try multiple user agents to avoid blocking
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            ]
            
            # Try with different user agents if first attempt fails
            for i, user_agent in enumerate(user_agents):
                try:
                    self.session.headers.update({'User-Agent': user_agent})
                    response = self.session.get(url, timeout=15, allow_redirects=True)
                    response.raise_for_status()
                    break
                except Exception as e:
                    if i == len(user_agents) - 1:  # Last attempt
                        raise e
                    logger.warning(f"Attempt {i+1} failed for {url}: {e}")
                    time.sleep(2)  # Wait before retry
            
            # Parse with different parsers if needed
            try:
                soup = BeautifulSoup(response.content, 'html.parser')
            except Exception:
                try:
                    soup = BeautifulSoup(response.content, 'lxml')
                except Exception:
                    soup = BeautifulSoup(response.content, 'html.parser')
            
            # First, scrape the main page
            page_articles = self._extract_articles_from_soup(soup, station_name, url)
            articles.extend(page_articles)
            logger.info(f"Found {len(page_articles)} articles on main page: {url}")
            
            # Look for section-specific "More from..." links (especially for Wazobia FM)
            section_links = self._find_section_links(soup, url)
            logger.info(f"Found {len(section_links)} section links for {url}")
            
            # Scrape each section
            for i, section_url in enumerate(section_links):
                try:
                    self._rate_limit()
                    logger.info(f"Scraping section {i+1}: {section_url}")
                    
                    section_response = self.session.get(section_url, timeout=15, allow_redirects=True)
                    section_response.raise_for_status()
                    
                    section_soup = BeautifulSoup(section_response.content, 'html.parser')
                    section_articles = self._extract_articles_from_soup(section_soup, station_name, section_url)
                    articles.extend(section_articles)
                    logger.info(f"Found {len(section_articles)} articles in section: {section_url}")
                    
                except Exception as e:
                    logger.warning(f"Failed to scrape section {section_url}: {e}")
                    continue
            
            # Look for pagination links and scrape additional pages
            pagination_links = self._find_pagination_links(soup, url)
            logger.info(f"Found {len(pagination_links)} pagination links for {url}")
            
            # Scrape up to 3 additional pages to avoid overwhelming the site
            for i, page_url in enumerate(pagination_links[:3]):
                try:
                    self._rate_limit()
                    logger.info(f"Scraping pagination page {i+2}: {page_url}")
                    
                    page_response = self.session.get(page_url, timeout=15, allow_redirects=True)
                    page_response.raise_for_status()
                    
                    page_soup = BeautifulSoup(page_response.content, 'html.parser')
                    page_articles = self._extract_articles_from_soup(page_soup, station_name, page_url)
                    articles.extend(page_articles)
                    logger.info(f"Found {len(page_articles)} articles on page {i+2}: {page_url}")
                    
                except Exception as e:
                    logger.warning(f"Failed to scrape pagination page {page_url}: {e}")
                    continue
            
            logger.info(f"Found {len(articles)} relevant articles from web page: {url}")
            
            # Log if few articles found (but don't try Selenium)
            if len(articles) < 5:
                logger.info(f"Found {len(articles)} articles with regular scraping for {url}")
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout scraping {url}")
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error scraping {url}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error scraping {url}: {e}")
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
        
        return articles

    def _scrape_rss_feed(self, url: str, station_name: str) -> List[Dict[str, Any]]:
        """Scrape content from an RSS feed"""
        articles = []
        
        try:
            self._rate_limit()
            logger.info(f"Scraping RSS feed: {url}")
            
            # Parse RSS feed
            feed = feedparser.parse(url)
            
            if feed.bozo:
                logger.warning(f"RSS feed may have issues: {url}")
            
            for entry in feed.entries[:20]:  # Limit to 20 entries per feed
                try:
                    # Extract basic information
                    title = getattr(entry, 'title', '')
                    link = getattr(entry, 'link', '')
                    description = getattr(entry, 'description', '')
                    published = getattr(entry, 'published', '')
                    
                    # Try to get content
                    content = description
                    if hasattr(entry, 'content'):
                        if isinstance(entry.content, list) and len(entry.content) > 0:
                            content = entry.content[0].value
                        else:
                            content = str(entry.content)
                    
                    # Combine title and content for filtering
                    full_text = f"{title} {content}".lower()
                    
                    # STRICT filtering for news and political content only
                    news_keywords = [
                        'news', 'politics', 'government', 'policy', 'economy', 'business', 
                        'national', 'public', 'official', 'announcement', 'statement', 'press', 
                        'briefing', 'minister', 'president', 'governor', 'senate', 'house', 
                        'assembly', 'election', 'vote', 'campaign', 'budget', 'revenue', 'tax', 
                        'infrastructure', 'development', 'security', 'military', 'police', 'court', 
                        'judge', 'law', 'bill', 'act', 'regulation', 'commission', 'agency', 
                        'department', 'ministry', 'tinubu', 'shettima', 'apc', 'pdp', 'labour',
                        'protest', 'workers', 'minimum wage', 'cost of living', 'lagos', 'abuja', 'nigeria'
                    ]
                    
                    skip_keywords = [
                        'entertainment', 'music', 'sports', 'showbiz', 'lifestyle', 'relationship', 
                        'caller', 'confession', 'personal', 'advice', 'gossip', 'celebrity', 'movie', 
                        'song', 'album', 'concert', 'match', 'game', 'player', 'team', 'football', 
                        'basketball', 'boxing', 'athlete', 'advertisement', 'ad', 'sponsor', 'promotion', 
                        'commercial', 'masturbate', 'sex', 'drunk', 'alcohol', 'piss', 'bed', 'belle', 
                        'husband', 'wife', 'girlfriend', 'sister', 'divorce', 'marriage', 'dating', 
                        'love', 'romance', 'kiss', 'kissing', 'wakeup', 'show', 'backyard', 'marketrunz', 
                        'kulele', 'nightjolly', 'hottori', 'stories', 'exclusive-interviews', 'editorial'
                    ]
                    
                    # Must have news keywords AND not have skip keywords
                    has_news_keywords = any(keyword in full_text for keyword in news_keywords)
                    has_skip_keywords = any(skip in full_text for skip in skip_keywords)
                    
                    if has_news_keywords and not has_skip_keywords and len(title) > 10:
                        # Parse published date
                        published_date = datetime.now().strftime('%Y-%m-%d')
                        if published:
                            try:
                                # Try to parse various date formats
                                import dateutil.parser
                                parsed_date = dateutil.parser.parse(published)
                                published_date = parsed_date.strftime('%Y-%m-%d')
                            except:
                                pass
                        
                        article_data = {
                            'title': title,
                            'text': content,
                            'url': link,
                            'source': station_name,
                            'source_url': url,
                            'source_type': 'radio',
                            'platform': 'rss_feed',
                            'language': 'English',
                            'country': 'Nigeria',
                            'region': self.radio_stations[station_name]['region'],
                            'location': self.radio_stations[station_name]['location'],
                            'date': published_date,
                            'published_date': published_date,
                            'query': 'radio_collection',
                            'file_source': 'radio_hybrid',
                            'description': content[:200] + '...' if len(content) > 200 else content,
                            'content': content,
                            'id': f"radio_rss_{hash(title + content)}_{int(time.time())}",
                            'favorite': False,
                            'tone': 'neutral',
                            'source_name': station_name,
                            'parent_url': url,
                            'parent_id': f"rss_{station_name.replace(' ', '_').lower()}",
                            'children': [],
                            'direct_reach': 0,
                            'cumulative_reach': 0,
                            'domain_reach': 0,
                            'tags': ['radio', 'rss', self.radio_stations[station_name]['region'].lower()]
                        }
                        
                        if self._should_include_content(article_data.get('text', '')):
                            articles.append(article_data)
                
                except Exception as e:
                    logger.warning(f"Error processing RSS entry from {url}: {e}")
                    continue
            
            logger.info(f"Found {len(articles)} relevant articles from RSS feed: {url}")
            
        except Exception as e:
            logger.error(f"Error scraping RSS feed {url}: {e}")
        
        return articles

    def _extract_article_data(self, element, station_name: str, base_url: str) -> Optional[Dict[str, Any]]:
        """Extract article data from a DOM element"""
        try:
            # Extract title
            title = ""
            title_element = element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if title_element:
                title = title_element.get_text(strip=True)
            elif element.name == 'a':
                title = element.get_text(strip=True)
            
            # Extract content/text
            text = ""
            if element.name in ['article', 'div', 'section']:
                # Remove script and style elements
                for script in element(["script", "style"]):
                    script.decompose()
                text = element.get_text(separator=' ', strip=True)
            elif element.name == 'a':
                text = element.get_text(strip=True)
            
            # More lenient content filtering - only reject obvious non-news content
            skip_content_keywords = [
                'masturbate', 'sex', 'drunk', 'alcohol', 'piss', 'bed', 'belle', 
                'husband', 'wife', 'girlfriend', 'sister', 'divorce', 'marriage', 'dating', 
                'love', 'romance', 'kiss', 'kissing', 'wakeup', 'show', 'backyard', 'marketrunz', 
                'kulele', 'nightjolly', 'hottori', 'stories', 'exclusive-interviews', 'editorial',
                'burna', 'tiwa', 'savage', 'bayanni', 'davido', 'ayra', 'starr', '2baba',
                'billboard', 'mobo', 'awards', 'album', 'song', 'concert', 'artist',
                'super eagles', 'football', 'basketball', 'boxing', 'athlete', 'player',
                'team', 'match', 'game', 'sport', 'fitness', 'health', 'medical',
                'hiv', 'zobo', 'blood', 'kidnap', 'pikin', 'shop', 'sell'
            ]
            
            # Check for news/political keywords - more lenient
            news_content_keywords = [
                'government', 'president', 'minister', 'governor', 'senate', 'house',
                'assembly', 'election', 'vote', 'campaign', 'budget', 'revenue',
                'tax', 'infrastructure', 'development', 'security', 'military',
                'police', 'court', 'judge', 'law', 'bill', 'act', 'regulation',
                'commission', 'agency', 'department', 'ministry', 'policy',
                'economy', 'business', 'national', 'public', 'official',
                'announcement', 'statement', 'press', 'briefing', 'tinubu',
                'shettima', 'apc', 'pdp', 'labour', 'protest', 'workers',
                'minimum wage', 'cost of living', 'lagos', 'abuja', 'nigeria',
                'news', 'update', 'latest', 'breaking', 'report', 'story', 'article', 'post'
            ]
            
            has_news_content = any(keyword in text.lower() for keyword in news_content_keywords)
            has_skip_content = any(skip in text.lower() for skip in skip_content_keywords)
            
            # Only reject if it has skip content, don't require news content for basic acceptance
            if has_skip_content:
                return None
            
            # Extract URL
            url = ""
            if element.name == 'a' and element.get('href'):
                url = urljoin(base_url, element.get('href'))
            else:
                # Look for link within the element
                link_element = element.find('a', href=True)
                if link_element:
                    url = urljoin(base_url, link_element.get('href'))
            
            # Extract date (look for common date patterns)
            date = datetime.now().strftime('%Y-%m-%d')
            date_text = element.get_text()
            date_patterns = [
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
                r'(\w+ \d{1,2}, \d{4})',
                r'(\d{1,2} \w+ \d{4})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, date_text)
                if match:
                    try:
                        parsed_date = datetime.strptime(match.group(1), '%m/%d/%Y')
                        date = parsed_date.strftime('%Y-%m-%d')
                        break
                    except:
                        try:
                            parsed_date = datetime.strptime(match.group(1), '%Y-%m-%d')
                            date = parsed_date.strftime('%Y-%m-%d')
                            break
                        except:
                            continue
            
            # Only return if we have meaningful content - more lenient requirements
            if title and len(title) > 8 and len(text) > 30:
                # Determine if this is a radio station or online source
                if station_name in self.radio_stations:
                    # Radio station
                    station_config = self.radio_stations[station_name]
                    return {
                        'title': title,
                        'text': text,
                        'url': url,
                        'source': station_config.get('name', station_name),
                        'source_url': base_url,
                        'source_type': 'radio',
                        'platform': 'radio_website',
                        'language': 'English',
                        'country': 'Nigeria',
                        'region': station_config.get('region', 'Unknown'),
                        'location': station_config.get('location', 'Unknown'),
                        'date': date,
                        'published_date': date,
                        'query': 'radio_collection',
                        'file_source': 'radio_hybrid',
                        'description': text[:200] + '...' if len(text) > 200 else text,
                        'content': text,
                        'id': f"radio_web_{hash(title + text)}_{int(time.time())}",
                        'favorite': False,
                        'tone': 'neutral',
                        'source_name': station_config.get('name', station_name),
                        'parent_url': base_url,
                        'parent_id': f"web_{station_name.replace(' ', '_').lower()}",
                        'children': [],
                        'direct_reach': 0,
                        'cumulative_reach': 0,
                        'domain_reach': 0,
                        'tags': ['radio', 'web', station_config.get('region', 'Unknown').lower()]
                    }
                elif station_name in self.online_sources:
                    # Online source
                    source_config = self.online_sources[station_name]
                    return {
                        'title': title,
                        'text': text,
                        'url': url,
                        'source': source_config.get('name', station_name),
                        'source_url': base_url,
                        'source_type': 'online_source',
                        'platform': 'website',
                        'language': 'English',
                        'country': 'Nigeria',
                        'region': source_config.get('region', 'Online'),
                        'location': 'Online',
                        'date': date,
                        'published_date': date,
                        'query': 'online_collection',
                        'file_source': 'online_sources',
                        'description': text[:200] + '...' if len(text) > 200 else text,
                        'content': text,
                        'id': f"online_{hash(title + text)}_{int(time.time())}",
                        'favorite': False,
                        'tone': 'neutral',
                        'source_name': source_config.get('name', station_name),
                        'parent_url': base_url,
                        'parent_id': f"online_{station_name.replace(' ', '_').lower()}",
                        'children': [],
                        'direct_reach': 0,
                        'cumulative_reach': 0,
                        'domain_reach': 0,
                        'tags': ['online', 'news', source_config.get('type', 'website')]
                    }
                else:
                    # Fallback for unknown sources
                    return {
                        'title': title,
                        'text': text,
                        'url': url,
                        'source': station_name,
                        'source_url': base_url,
                        'source_type': 'unknown',
                        'platform': 'website',
                        'language': 'English',
                        'country': 'Nigeria',
                        'region': 'Unknown',
                        'location': 'Unknown',
                        'date': date,
                        'published_date': date,
                        'query': 'unknown_collection',
                        'file_source': 'unknown',
                        'description': text[:200] + '...' if len(text) > 200 else text,
                        'content': text,
                        'id': f"unknown_{hash(title + text)}_{int(time.time())}",
                        'favorite': False,
                        'tone': 'neutral',
                        'source_name': station_name,
                        'parent_url': base_url,
                        'parent_id': f"unknown_{station_name.replace(' ', '_').lower()}",
                        'children': [],
                        'direct_reach': 0,
                        'cumulative_reach': 0,
                        'domain_reach': 0,
                        'tags': ['unknown']
                    }
        
        except Exception as e:
            logger.warning(f"Error extracting article data: {e}")
        
        return None

    def collect_from_station(self, station_name: str, station_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect content from a single radio station using both web and RSS scraping"""
        all_articles = []
        
        logger.info(f"Collecting from {station_name}")
        
        # Scrape web pages
        web_urls = station_config.get('urls', {}).get('web', [])
        for url in web_urls:
            try:
                articles = self._scrape_web_page(url, station_name)
                all_articles.extend(articles)
                logger.info(f"Collected {len(articles)} articles from web page: {url}")
            except Exception as e:
                logger.error(f"Failed to scrape web page {url}: {e}")
        
        # Scrape RSS feeds
        rss_urls = station_config.get('urls', {}).get('rss', [])
        for url in rss_urls:
            try:
                articles = self._scrape_rss_feed(url, station_name)
                all_articles.extend(articles)
                logger.info(f"Collected {len(articles)} articles from RSS feed: {url}")
            except Exception as e:
                logger.error(f"Failed to scrape RSS feed {url}: {e}")
        
        logger.info(f"Total collected {len(all_articles)} articles from {station_name}")
        return all_articles

    def _scrape_online_source(self, source_name: str, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape content from a single online source"""
        all_articles = []
        
        logger.info(f"Collecting from online source: {source_name}")
        
        urls = source_config.get('urls', [])
        source_type = source_config.get('type', 'news_website')
        
        for url in urls:
            try:
                articles = self._scrape_web_page(url, source_name)
                all_articles.extend(articles)
                logger.info(f"Collected {len(articles)} articles from {source_name}: {url}")
            except Exception as e:
                logger.error(f"Failed to scrape {source_name} URL {url}: {e}")
        
        logger.info(f"Total collected {len(all_articles)} articles from {source_name}")
        return all_articles

    def collect_from_online_sources(self) -> List[Dict[str, Any]]:
        """Collect content from all configured online sources"""
        logger.info("Starting online sources collection...")
        
        all_articles = []
        successful_sources = 0
        total_sources = len(self.online_sources)
        
        for source_name, source_config in self.online_sources.items():
            try:
                articles = self._scrape_online_source(source_name, source_config)
                all_articles.extend(articles)
                successful_sources += 1
                logger.info(f"Collected {len(articles)} articles from {source_name}")
            except Exception as e:
                logger.error(f"Failed to collect from {source_name}: {e}")
        
        logger.info(f"Online sources collection complete: {len(all_articles)} articles from {successful_sources}/{total_sources} sources")
        return all_articles

    def collect_all(self, queries: List[str] = None, output_file: str = None) -> Dict[str, Any]:
        """Collect content from all configured radio stations and online sources"""
        logger.info("Starting hybrid radio station and online sources collection...")
        
        all_articles = []
        
        # First, collect from radio stations
        logger.info("=== COLLECTING FROM RADIO STATIONS ===")
        radio_articles = []
        successful_stations = 0
        total_stations = len(self.radio_stations)
        
        for station_name, station_config in self.radio_stations.items():
            try:
                articles = self.collect_from_station(station_name, station_config)
                radio_articles.extend(articles)
                successful_stations += 1
                logger.info(f"Collected {len(articles)} articles from {station_name}")
            except Exception as e:
                logger.error(f"Failed to collect from {station_name}: {e}")
        
        all_articles.extend(radio_articles)
        logger.info(f"Radio collection complete: {len(radio_articles)} articles from {successful_stations}/{total_stations} stations")
        
        # Then, collect from online sources
        logger.info("=== COLLECTING FROM ONLINE SOURCES ===")
        online_articles = self.collect_from_online_sources()
        all_articles.extend(online_articles)
        
        # Save to CSV if output file specified
        if output_file and all_articles:
            df = pd.DataFrame(all_articles)
            df.to_csv(output_file, index=False, encoding='utf-8')
            logger.info(f"Saved {len(all_articles)} articles to {output_file}")
        
        results = {
            'total_articles': len(all_articles),
            'radio_articles': len(radio_articles),
            'online_articles': len(online_articles),
            'successful_stations': successful_stations,
            'total_stations': total_stations,
            'successful_online_sources': len([s for s in self.online_sources.keys()]),
            'total_online_sources': len(self.online_sources),
            'articles': all_articles
        }
        
        logger.info(f"Hybrid collection complete: {len(all_articles)} total articles ({len(radio_articles)} radio + {len(online_articles)} online)")
        return results

def main(target_and_variations: List[str], user_id: str = None):
    """Main function to run hybrid radio station and online sources collection"""
    logger.info(f"Starting hybrid radio station and online sources collection for: {target_and_variations}")
    
    try:
        collector = HybridRadioCollector()
        
        # Set up output file
        output_dir = Path(__file__).parent.parent.parent / "data" / "raw"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"radio_online_hybrid_{timestamp}.csv"
        
        # Collect data
        results = collector.collect_all(queries=target_and_variations, output_file=str(output_file))
        
        logger.info(f"Hybrid collection completed successfully. Collected {results['total_articles']} articles ({results.get('radio_articles', 0)} radio + {results.get('online_articles', 0)} online).")
        return results
        
    except Exception as e:
        logger.error(f"Error in hybrid collection: {e}", exc_info=True)
        return {'total_articles': 0, 'error': str(e)}

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Collect radio data from hybrid sources')
    parser.add_argument('--queries', type=str, required=False, help='JSON string of query variations')
    parser.add_argument('--since', type=str, help='Start date (for incremental collection)')
    parser.add_argument('--until', type=str, help='End date (for incremental collection)')
    
    args = parser.parse_args()
    
    if args.queries:
        try:
            queries_list = json.loads(args.queries)
            logger.info(f"[Radio Hybrid] Parsed queries: {queries_list}")
            
            # Note: This collector doesn't yet support incremental date ranges
            # TODO: Implement date range filtering
            if args.since or args.until:
                logger.warning(f"⚠️  [Radio Hybrid] Date range parameters not yet implemented: {args.since} to {args.until}")
            
            # Get user_id from environment
            user_id = os.getenv('COLLECTOR_USER_ID')
            main(queries_list, user_id=user_id)
        except json.JSONDecodeError as e:
            logger.error(f"[Radio Hybrid] Error parsing queries JSON: {e}")
            import sys
            sys.exit(1)
    else:
        logger.info("Running Radio Hybrid collector directly (without args)... Use run_collectors.py for proper execution.")
        test_queries = ["Test Target", "nigeria", "politics"]
        main(test_queries)
