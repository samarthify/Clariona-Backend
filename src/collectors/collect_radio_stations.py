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

class RadioStationCollector:
    def __init__(self):
        # Load .env from collectors folder
        env_path = Path(__file__).parent / '.env'
        load_dotenv(env_path)
        self.base_path = Path(__file__).parent.parent.parent
        
        # Target-specific configuration
        self.target_config = None
        
        # Radio station configuration
        self.radio_stations = self._load_radio_stations()
        
        # Session for HTTP requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Rate limiting
        self.request_delay = 2  # seconds between requests
        self.last_request_time = 0
        self.max_retries = 3

    def _load_radio_stations(self) -> Dict[str, List[Dict]]:
        """Load radio station configuration from the comprehensive media sources"""
        # Use comprehensive radio station configuration
        return {
            'Southwest': [
                {'name': 'Wazobia FM', 'website_url': 'https://wazobiafm.com', 'location': 'Lagos', 'region': 'Southwest'},
                {'name': 'Cool FM', 'website_url': 'https://coolfm.ng', 'location': 'Lagos', 'region': 'Southwest'},
                {'name': 'Raypower FM', 'website_url': 'https://raypower.fm', 'location': 'Lagos', 'region': 'Southwest'},
                {'name': 'Nigeria Info', 'website_url': 'https://nigeriainfo.fm', 'location': 'Lagos', 'region': 'Southwest'},
                {'name': 'Fresh FM', 'website_url': 'https://freshfm.com.ng', 'location': 'Ibadan', 'region': 'Southwest'},
                {'name': 'Brila FM', 'website_url': 'https://brila.net', 'location': 'Lagos', 'region': 'Southwest'},
                {'name': 'Rhythm FM', 'website_url': 'https://rhythmfm.com.ng', 'location': 'Lagos', 'region': 'Southwest'},
                {'name': 'FRCN Ibadan', 'website_url': 'https://frcn.gov.ng', 'location': 'Ibadan', 'region': 'Southwest'},
                {'name': 'Radio Lagos', 'website_url': 'https://radiolagos.com.ng', 'location': 'Lagos', 'region': 'Southwest'},
            ],
            'Southeast': [
                {'name': 'Dream FM', 'website_url': 'https://dreamfm.com.ng', 'location': 'Enugu', 'region': 'Southeast'},
                {'name': 'Urban Radio', 'website_url': 'https://urbanradio.com.ng', 'location': 'Enugu', 'region': 'Southeast'},
                {'name': 'Flo FM', 'website_url': 'https://flofm.com.ng', 'location': 'Abia', 'region': 'Southeast'},
                {'name': 'Blaze FM', 'website_url': 'https://blazefm.com.ng', 'location': 'Anambra', 'region': 'Southeast'},
                {'name': 'ABS Radio', 'website_url': 'https://absradiotv.com', 'location': 'Anambra', 'region': 'Southeast'},
                {'name': 'ESBS Radio', 'website_url': 'https://esbs.com.ng', 'location': 'Enugu', 'region': 'Southeast'},
                {'name': 'Orient FM', 'website_url': 'https://orientfm.com.ng', 'location': 'Imo', 'region': 'Southeast'},
            ],
            'North Central': [
                {'name': 'Radio Nigeria Abuja', 'website_url': 'https://frcn.gov.ng', 'location': 'Abuja', 'region': 'North Central'},
                {'name': 'Kapital FM', 'website_url': 'https://kapitalfm.com.ng', 'location': 'Abuja', 'region': 'North Central'},
                {'name': 'Raypower Abuja', 'website_url': 'https://raypower.fm', 'location': 'Abuja', 'region': 'North Central'},
                {'name': 'Vision FM', 'website_url': 'https://visionfm.com.ng', 'location': 'Abuja', 'region': 'North Central'},
                {'name': 'WEFM', 'website_url': 'https://wefm.com.ng', 'location': 'Abuja', 'region': 'North Central'},
            ],
            'North West': [
                {'name': 'Freedom Radio', 'website_url': 'https://freedomradio.com.ng', 'location': 'Kano', 'region': 'North West'},
                {'name': 'Arewa Radio', 'website_url': 'https://arewaradio.com.ng', 'location': 'Kano', 'region': 'North West'},
                {'name': 'FRCN Kaduna', 'website_url': 'https://frcn.gov.ng', 'location': 'Kaduna', 'region': 'North West'},
                {'name': 'BBC Hausa', 'website_url': 'https://bbc.com/hausa', 'location': 'Kano', 'region': 'North West'},
                {'name': 'VOA Hausa', 'website_url': 'https://voahausa.com', 'location': 'Kano', 'region': 'North West'},
                {'name': 'Raypower Kano', 'website_url': 'https://raypower.fm', 'location': 'Kano', 'region': 'North West'},
            ],
            'North East': [
                {'name': 'FRCN Yola', 'website_url': 'https://frcn.gov.ng', 'location': 'Yola', 'region': 'North East'},
                {'name': 'Dandal Kura', 'website_url': 'https://dandalkura.com', 'location': 'Borno', 'region': 'North East'},
                {'name': 'Gotel Radio', 'website_url': 'https://gotelradio.com', 'location': 'Adamawa', 'region': 'North East'},
                {'name': 'Peace FM Maiduguri', 'website_url': 'https://peacefm.com.ng', 'location': 'Maiduguri', 'region': 'North East'},
            ],
            'South South': [
                {'name': 'Wazobia FM Port Harcourt', 'website_url': 'https://wazobiafm.com', 'location': 'Port Harcourt', 'region': 'South South'},
                {'name': 'Nigeria Info Port Harcourt', 'website_url': 'https://nigeriainfo.fm', 'location': 'Port Harcourt', 'region': 'South South'},
                {'name': 'Cool FM Port Harcourt', 'website_url': 'https://coolfm.ng', 'location': 'Port Harcourt', 'region': 'South South'},
                {'name': 'Rhythm FM Port Harcourt', 'website_url': 'https://rhythmfm.com.ng', 'location': 'Port Harcourt', 'region': 'South South'},
                {'name': 'Raypower PH', 'website_url': 'https://raypower.fm', 'location': 'Port Harcourt', 'region': 'South South'},
                {'name': 'Radio Rivers', 'website_url': 'https://radiorivers.com.ng', 'location': 'Port Harcourt', 'region': 'South South'},
                {'name': 'Voice of Delta', 'website_url': 'https://voiceofdelta.com.ng', 'location': 'Delta', 'region': 'South South'},
            ]
        }

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
        
        # Apply additional filters if configured
        if hasattr(self.target_config, 'sources') and 'radio' in self.target_config.sources:
            radio_config = self.target_config.sources['radio']
            if hasattr(radio_config, 'filters') and radio_config.filters:
                filters = radio_config.filters
                
                # Check must_contain filters
                if 'must_contain' in filters:
                    must_contain = [term.lower() for term in filters['must_contain']]
                    if not any(term in content_lower for term in must_contain):
                        return False
                
                # Check exclude filters
                if 'exclude' in filters:
                    exclude_terms = [term.lower() for term in filters['exclude']]
                    if any(term in content_lower for term in exclude_terms):
                        return False
        
        return has_target_keywords

    def _scrape_radio_website(self, station: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape content from a radio station website with improved error handling"""
        articles = []
        station_name = station.get('name', 'Unknown Station')
        website_url = station.get('website_url', '')
        
        if not website_url:
            logger.warning(f"No website URL for {station_name}")
            return articles
        
        try:
            self._rate_limit()
            logger.info(f"Scraping {station_name} at {website_url}")
            
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
                    response = self.session.get(website_url, timeout=15, allow_redirects=True)
                    response.raise_for_status()
                    break
                except Exception as e:
                    if i == len(user_agents) - 1:  # Last attempt
                        raise e
                    logger.warning(f"Attempt {i+1} failed for {station_name}: {e}")
                    time.sleep(2)  # Wait before retry
            
            # Parse with different parsers if needed
            try:
                soup = BeautifulSoup(response.content, 'html.parser')
            except Exception:
                # Try with lxml if available
                try:
                    soup = BeautifulSoup(response.content, 'lxml')
                except Exception:
                    soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for common news/article patterns with more comprehensive selectors
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
                logger.info(f"No article elements found, searching all links for {station_name}")
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
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
                    has_news_keywords = any(keyword in href.lower() or keyword in text.lower() for keyword in news_keywords)
                    has_skip_keywords = any(skip in href.lower() or skip in text.lower() for skip in skip_keywords)
                    
                    if (len(text) > 20 and has_news_keywords and not has_skip_keywords):
                        found_articles.append(link)
            
            # Also look for headings that might be news titles
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for heading in headings:
                text = heading.get_text(strip=True)
                if len(text) > 20:
                    # Check if it's news-related
                    news_keywords = ['news', 'politics', 'government', 'policy', 'economy', 'business', 
                                   'national', 'public', 'official', 'announcement', 'statement', 'press', 
                                   'briefing', 'minister', 'president', 'governor', 'senate', 'house', 
                                   'assembly', 'election', 'vote', 'campaign', 'budget', 'revenue', 'tax', 
                                   'infrastructure', 'development', 'security', 'military', 'police', 'court', 
                                   'judge', 'law', 'bill', 'act', 'regulation', 'commission', 'agency', 
                                   'department', 'ministry', 'tinubu', 'shettima', 'apc', 'pdp', 'labour',
                                   'protest', 'workers', 'minimum wage', 'cost of living', 'lagos', 'abuja', 'nigeria']
                    
                    skip_keywords = ['entertainment', 'music', 'sports', 'showbiz', 'lifestyle', 'relationship', 
                                   'caller', 'confession', 'personal', 'advice', 'gossip', 'celebrity', 'movie', 
                                   'song', 'album', 'concert', 'match', 'game', 'player', 'team', 'football', 
                                   'basketball', 'boxing', 'athlete', 'advertisement', 'ad', 'sponsor', 'promotion', 
                                   'commercial', 'masturbate', 'sex', 'drunk', 'alcohol', 'piss', 'bed', 'belle', 
                                   'husband', 'wife', 'girlfriend', 'sister', 'divorce', 'marriage', 'dating', 
                                   'love', 'romance', 'kiss', 'kissing', 'wakeup', 'show', 'backyard', 'marketrunz', 
                                   'kulele', 'nightjolly', 'hottori', 'stories', 'exclusive-interviews', 'editorial']
                    
                    has_news_keywords = any(keyword in text.lower() for keyword in news_keywords)
                    has_skip_keywords = any(skip in text.lower() for skip in skip_keywords)
                    
                    if has_news_keywords and not has_skip_keywords:
                        found_articles.append(heading)
            
            # Process found articles
            for element in found_articles[:25]:  # Limit to 25 articles per station
                try:
                    article_data = self._extract_article_data(element, station, website_url)
                    if article_data and self._should_include_content(article_data.get('text', '')):
                        articles.append(article_data)
                except Exception as e:
                    logger.warning(f"Error processing article from {station_name}: {e}")
                    continue
            
            logger.info(f"Found {len(articles)} relevant articles from {station_name}")
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout scraping {station_name}")
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error scraping {station_name}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error scraping {station_name}: {e}")
        except Exception as e:
            logger.error(f"Error scraping {station_name}: {e}")
        
        return articles

    def _extract_article_data(self, element, station: Dict[str, Any], base_url: str) -> Optional[Dict[str, Any]]:
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
            
            # STRICT content filtering - reject anything that's not clearly news/political
            skip_content_keywords = [
                'masturbate', 'sex', 'relationship', 'caller', 'confession', 
                'personal', 'advice', 'gossip', 'celebrity', 'entertainment',
                'music', 'sports', 'showbiz', 'lifestyle', 'drunk', 'alcohol',
                'piss', 'bed', 'belle', 'husband', 'wife', 'girlfriend', 'sister',
                'divorce', 'marriage', 'dating', 'love', 'romance', 'kiss', 'kissing',
                'wakeup', 'show', 'backyard', 'marketrunz', 'kulele', 'nightjolly',
                'hottori', 'stories', 'exclusive-interviews', 'editorial', 'burna',
                'tiwa', 'savage', 'bayanni', 'davido', 'ayra', 'starr', '2baba',
                'billboard', 'mobo', 'awards', 'album', 'song', 'concert', 'artist',
                'super eagles', 'football', 'basketball', 'boxing', 'athlete', 'player',
                'team', 'match', 'game', 'sport', 'fitness', 'health', 'medical',
                'hiv', 'zobo', 'blood', 'kidnap', 'pikin', 'shop', 'sell'
            ]
            
            # Also check for news/political keywords - must have at least one
            news_content_keywords = [
                'government', 'president', 'minister', 'governor', 'senate', 'house',
                'assembly', 'election', 'vote', 'campaign', 'budget', 'revenue',
                'tax', 'infrastructure', 'development', 'security', 'military',
                'police', 'court', 'judge', 'law', 'bill', 'act', 'regulation',
                'commission', 'agency', 'department', 'ministry', 'policy',
                'economy', 'business', 'national', 'public', 'official',
                'announcement', 'statement', 'press', 'briefing', 'tinubu',
                'shettima', 'apc', 'pdp', 'labour', 'protest', 'workers',
                'minimum wage', 'cost of living', 'lagos', 'abuja', 'nigeria'
            ]
            
            has_news_content = any(keyword in text.lower() for keyword in news_content_keywords)
            has_skip_content = any(skip in text.lower() for skip in skip_content_keywords)
            
            if has_skip_content or not has_news_content:
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
            
            # Only return if we have meaningful content
            if title and len(title) > 10 and len(text) > 50:
                return {
                    'title': title,
                    'text': text,
                    'url': url,
                    'source': station.get('name', 'Unknown Radio Station'),
                    'source_url': station.get('website_url', ''),
                    'source_type': 'radio',
                    'platform': 'radio_website',
                    'language': station.get('language', 'English'),
                    'country': 'Nigeria',
                    'region': station.get('region', 'Unknown'),
                    'location': station.get('location', 'Unknown'),
                    'date': date,
                    'published_date': date,
                    'query': 'radio_collection',
                    'file_source': 'radio_stations',
                    'description': text[:200] + '...' if len(text) > 200 else text,
                    'content': text,
                    'id': f"radio_{hash(title + text)}_{int(time.time())}",
                    'favorite': False,
                    'tone': 'neutral',
                    'source_name': station.get('name', 'Unknown Radio Station'),
                    'parent_url': station.get('website_url', ''),
                    'parent_id': f"station_{station.get('name', '').replace(' ', '_').lower()}",
                    'children': [],
                    'direct_reach': 0,
                    'cumulative_reach': 0,
                    'domain_reach': 0,
                    'tags': ['radio', station.get('region', 'Unknown').lower()]
                }
        
        except Exception as e:
            logger.warning(f"Error extracting article data: {e}")
        
        return None

    def collect_from_station(self, station: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect content from a single radio station"""
        return self._scrape_radio_website(station)

    def collect_all(self, queries: List[str] = None, output_file: str = None) -> Dict[str, Any]:
        """Collect content from all configured radio stations"""
        logger.info("Starting radio station collection...")
        
        all_articles = []
        successful_stations = 0
        total_stations = 0
        
        # Determine which regions to collect from based on target config
        regions_to_collect = list(self.radio_stations.keys())
        if self.target_config and hasattr(self.target_config, 'sources') and 'radio' in self.target_config.sources:
            radio_config = self.target_config.sources['radio']
            if hasattr(radio_config, 'regions') and radio_config.regions:
                regions_to_collect = list(radio_config.regions.keys())
        
        for region in regions_to_collect:
            if region not in self.radio_stations:
                continue
                
            stations = self.radio_stations[region]
            logger.info(f"Collecting from {len(stations)} stations in {region}")
            
            for station in stations:
                total_stations += 1
                try:
                    articles = self.collect_from_station(station)
                    all_articles.extend(articles)
                    successful_stations += 1
                    logger.info(f"Collected {len(articles)} articles from {station.get('name', 'Unknown')}")
                except Exception as e:
                    logger.error(f"Failed to collect from {station.get('name', 'Unknown')}: {e}")
        
        # Save to CSV if output file specified
        if output_file and all_articles:
            df = pd.DataFrame(all_articles)
            df.to_csv(output_file, index=False, encoding='utf-8')
            logger.info(f"Saved {len(all_articles)} articles to {output_file}")
        
        results = {
            'total_articles': len(all_articles),
            'successful_stations': successful_stations,
            'total_stations': total_stations,
            'articles': all_articles
        }
        
        logger.info(f"Radio collection complete: {len(all_articles)} articles from {successful_stations}/{total_stations} stations")
        return results

def main(target_and_variations: List[str], user_id: str = None):
    """Main function to run radio station collection"""
    logger.info(f"Starting radio station collection for: {target_and_variations}")
    
    try:
        collector = RadioStationCollector()
        
        # Set up output file
        output_dir = Path(__file__).parent.parent.parent / "data" / "raw"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"radio_stations_{timestamp}.csv"
        
        # Collect data
        results = collector.collect_all(queries=target_and_variations, output_file=str(output_file))
        
        logger.info(f"Radio collection completed successfully. Collected {results['total_articles']} articles.")
        return results
        
    except Exception as e:
        logger.error(f"Error in radio station collection: {e}", exc_info=True)
        return {'total_articles': 0, 'error': str(e)}

if __name__ == "__main__":
    # Test the collector
    test_queries = ["Test Target", "nigeria", "politics"]
    main(test_queries)
