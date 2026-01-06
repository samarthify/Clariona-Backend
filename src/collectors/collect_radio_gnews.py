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

# Import custom exceptions
from src.exceptions import ValidationError

# Force UTF-8 encoding for the entire script to prevent charmap codec errors
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

# Use centralized logging configuration
try:
    from src.config.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    # Fallback to basic config
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

class GNewsRadioCollector:
    """
    Radio news collector using GNews and NewsAPI.
    
    This collector fetches news articles from multiple APIs (GNews and NewsAPI)
    focusing on Nigerian radio station sources and online news sources. It uses
    domain filtering to target specific radio station websites.
    
    Attributes:
        path_manager: PathManager instance for file path management
        base_path: Base path for the project
        config: ConfigManager instance for configuration
        target_config: Target-specific configuration
        gnews_key: GNews API key
        newsapi_key: NewsAPI key
        radio_sources: List of radio station domain sources
        online_sources: List of online news sources
    """
    def __init__(self):
        # Load .env from collectors folder
        env_path = Path(__file__).parent / '.env'
        load_dotenv(env_path)
        from src.config.path_manager import PathManager
        from config.config_manager import ConfigManager
        self.path_manager = PathManager()
        self.base_path = self.path_manager.base_path
        self.config = ConfigManager()
        
        # Target-specific configuration
        self.target_config = None
        
        # API Keys
        self.gnews_key = os.getenv("GNEWS_API_KEY")
        self.newsapi_key = os.getenv("NEWSAPI_KEY")
        
        if not self.gnews_key and not self.newsapi_key:
            raise ValidationError(
                "Neither GNEWS_API_KEY nor NEWSAPI_KEY found in environment variables",
                details={"collector": "GNewsRadioCollector"}
            )
        
        # Nigerian radio station sources for both GNews and NewsAPI
        # Using domain filtering since these APIs don't have Nigerian radio stations as sources
        self.radio_sources = {
            'Wazobia FM': {
                'gnews_domains': 'wazobiafm.com',
                'newsapi_domains': 'wazobiafm.com',
                'region': 'Southwest',
                'location': 'Lagos'
            },
            'Cool FM': {
                'gnews_domains': 'coolfm.ng',
                'newsapi_domains': 'coolfm.ng',
                'region': 'Southwest', 
                'location': 'Lagos'
            },
            'Nigeria Info FM': {
                'gnews_domains': 'nigeriainfo.fm',
                'newsapi_domains': 'nigeriainfo.fm',
                'region': 'Southwest',
                'location': 'Lagos'
            },
            'Raypower FM': {
                'gnews_domains': 'raypower.fm',
                'newsapi_domains': 'raypower.fm',
                'region': 'Southwest',
                'location': 'Lagos'
            },
            'Fresh FM': {
                'gnews_domains': 'freshfm.com.ng',
                'newsapi_domains': 'freshfm.com.ng',
                'region': 'Southwest',
                'location': 'Ibadan'
            },
            'Brila FM': {
                'gnews_domains': 'brila.net',
                'newsapi_domains': 'brila.net',
                'region': 'Southwest',
                'location': 'Lagos'
            },
            'Rhythm FM': {
                'gnews_domains': 'rhythmfm.com.ng',
                'newsapi_domains': 'rhythmfm.com.ng',
                'region': 'Southwest',
                'location': 'Lagos'
            },
            'Radio Nigeria': {
                'gnews_domains': 'frcn.gov.ng,radionigeria.gov.ng',
                'newsapi_domains': 'frcn.gov.ng,radionigeria.gov.ng',
                'region': 'North Central',
                'location': 'Abuja'
            },
            'Vision FM': {
                'gnews_domains': 'visionfm.ng',
                'newsapi_domains': 'visionfm.ng',
                'region': 'North Central',
                'location': 'Abuja'
            },
            'Freedom Radio': {
                'gnews_domains': 'freedomradio.com.ng',
                'newsapi_domains': 'freedomradio.com.ng',
                'region': 'North West',
                'location': 'Kano'
            },
            'Arewa Radio': {
                'gnews_domains': 'arewaradio.com.ng',
                'newsapi_domains': 'arewaradio.com.ng',
                'region': 'North West',
                'location': 'Kano'
            },
            'BBC Hausa': {
                'gnews_domains': 'bbc.com',
                'newsapi_domains': 'bbc.com',
                'region': 'North West',
                'location': 'Kano'
            },
            'VOA Hausa': {
                'gnews_domains': 'voahausa.com',
                'newsapi_domains': 'voahausa.com',
                'region': 'North West',
                'location': 'Kano'
            }
        }

    def set_target_config(self, target_config):
        """Set target-specific configuration for this collector"""
        self.target_config = target_config
        logger.info(f"Set target config for: {target_config.name if target_config else 'None'}")

    def _get_target_keywords(self) -> List[str]:
        """Get keywords to filter content based on target configuration.
        
        Priority order:
        1. ConfigManager: collectors.keywords.<target_id>.radio_gnews (target-specific, from DB)
        2. ConfigManager: collectors.keywords.default.radio_gnews (default, from DB)
        3. target_config.keywords (backward compatibility)
        4. Hardcoded defaults (last resort)
        """
        from config.config_manager import ConfigManager
        config = ConfigManager()
        
        # Priority 1: Target-specific keywords from ConfigManager (enables DB editing)
        if self.target_config and hasattr(self.target_config, 'name'):
            target_name = self.target_config.name.lower().replace(" ", "_")
            target_key = f"collectors.keywords.{target_name}.radio_gnews"
            target_keywords = config.get_list(target_key, None)
            if target_keywords:
                logger.info(f"Using target-specific keywords from ConfigManager: {target_keywords}")
                return target_keywords
        
        # Priority 2: Default keywords from ConfigManager (enables DB editing)
        default_keywords = config.get_list("collectors.keywords.default.radio_gnews", None)
        if default_keywords:
            logger.info(f"Using default keywords from ConfigManager: {default_keywords}")
            return default_keywords
        
        # Priority 3: Legacy - target_config keywords (backward compatibility)
        if self.target_config and hasattr(self.target_config, 'keywords') and self.target_config.keywords:
            logger.info(f"Using keywords from target_config: {self.target_config.keywords}")
            return self.target_config.keywords
        
        # Priority 4: Hardcoded defaults (last resort)
        logger.warning("Using hardcoded default keywords - consider configuring in ConfigManager/DB")
        return ["nigeria", "government", "politics", "economy", "news"]

    def _should_include_article(self, content: str) -> bool:
        """Determine if article should be included based on target configuration"""
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

    def collect_from_radio_station(self, station_name: str, station_config: Dict[str, Any], queries: List[str]) -> List[Dict[str, Any]]:
        """Collect news from a specific radio station using GNews"""
        articles = []
        
        try:
            logger.info(f"Collecting from {station_name} using GNews")
            
            # Try domain filtering approach
            for approach in ['gnews_domains']:
                if approach not in station_config:
                    continue
                    
                source_value = station_config[approach]
                if not source_value:
                    continue
                
                for query in queries:
                    try:
                        # GNews API parameters
                        params = {
                            "q": f'"{query}"',  # Exact phrase matching
                            "token": self.gnews_key,
                            "lang": "en",
                            "country": "ng",  # Nigeria
                            "max": 50,  # Max articles per query
                            "sortby": "publishedAt",
                            "in": "title,description"  # Search in title and description
                        }
                        
                        # Add domain filtering
                        params["domains"] = source_value
                        
                        # Make API request
                        url = "https://gnews.io/api/v4/search"
                        http_timeout = self.config.get_int("collectors.radio_gnews.http_timeout_seconds", 30)
                        response = requests.get(url, params=params, timeout=http_timeout)
                        
                        if response.status_code != 200:
                            logger.warning(f"GNews API error for {station_name} ({approach}): {response.status_code}")
                            continue
                        
                        data = response.json()
                        results = data.get("articles", [])
                        
                        logger.info(f"GNews returned {len(results)} articles for {station_name} ({approach}) - query: {query}")
                        
                        # Process articles
                        for article in results:
                            content = f"{article.get('title', '')} {article.get('description', '')}"
                            
                            if self._should_include_article(content):
                                # Parse published date
                                published_date = datetime.now().strftime('%Y-%m-%d')
                                if article.get('publishedAt'):
                                    try:
                                        from dateutil import parser
                                        parsed_date = parser.parse(article['publishedAt'])
                                        published_date = parsed_date.strftime('%Y-%m-%d')
                                    except:
                                        pass
                                
                                article_data = {
                                    'title': article.get('title', ''),
                                    'text': content,
                                    'url': article.get('url', ''),
                                    'source': station_name,
                                    'source_url': article.get('url', ''),
                                    'source_type': 'radio',
                                    'platform': 'gnews_api',
                                    'language': 'English',
                                    'country': 'Nigeria',
                                    'region': station_config['region'],
                                    'location': station_config['location'],
                                    'date': published_date,
                                    'published_date': published_date,
                                    'query': query,
                                    'file_source': 'radio_gnews',
                                    'description': article.get('description', ''),
                                    'content': content,
                                    'id': f"radio_gnews_{hash(article.get('url', ''))}_{int(time.time())}",
                                    'favorite': False,
                                    'tone': 'neutral',
                                    'source_name': station_name,
                                    'parent_url': article.get('url', ''),
                                    'parent_id': f"gnews_{station_name.replace(' ', '_').lower()}",
                                    'children': [],
                                    'direct_reach': 0,
                                    'cumulative_reach': 0,
                                    'domain_reach': 0,
                                    'tags': ['radio', 'gnews', station_config['region'].lower()],
                                    'gnews_source': article.get('source', {}).get('name', 'Unknown'),
                                    'gnews_domain': article.get('url', '').split('/')[2] if article.get('url') else 'Unknown'
                                }
                                
                                articles.append(article_data)
                        
                        # Rate limiting - GNews has limits
                        delay = self.config.get_int("collectors.radio_gnews.delay_between_requests_seconds", 1)
                        time.sleep(delay)
                        
                    except Exception as e:
                        logger.error(f"Error collecting from {station_name} for query '{query}': {e}")
                        continue
            
            logger.info(f"Collected {len(articles)} articles from {station_name}")
            
        except Exception as e:
            logger.error(f"Error collecting from {station_name}: {e}")
        
        return articles

    def collect_from_newsapi(self, station_name: str, station_config: Dict[str, Any], queries: List[str]) -> List[Dict[str, Any]]:
        """Collect news from a specific radio station using NewsAPI"""
        articles: List[Dict[str, Any]] = []
        
        if not self.newsapi_key:
            logger.warning("NewsAPI key not available")
            return articles
        
        try:
            logger.info(f"Collecting from {station_name} using NewsAPI")
            
            # Try both sources and domains approaches
            for approach in ['newsapi_sources', 'newsapi_domains']:
                if approach not in station_config:
                    continue
                    
                source_value = station_config[approach]
                if not source_value:
                    continue
                
                for query in queries:
                    try:
                        # NewsAPI parameters
                        params = {
                            "q": f'"{query}"',  # Exact phrase matching
                            "apiKey": self.newsapi_key,
                            "language": "en",
                            "country": "ng",  # Nigeria
                            "pageSize": 50,  # Max articles per query
                            "sortBy": "publishedAt"
                        }
                        
                        # Add source filtering
                        if approach == 'newsapi_sources':
                            params["sources"] = source_value
                        elif approach == 'newsapi_domains':
                            params["domains"] = source_value
                        
                        # Make API request
                        url = "https://newsapi.org/v2/everything"
                        http_timeout = self.config.get_int("collectors.radio_gnews.http_timeout_seconds", 30)
                        response = requests.get(url, params=params, timeout=http_timeout)
                        
                        if response.status_code != 200:
                            logger.warning(f"NewsAPI error for {station_name} ({approach}): {response.status_code}")
                            continue
                        
                        data = response.json()
                        results = data.get("articles", [])
                        
                        logger.info(f"NewsAPI returned {len(results)} articles for {station_name} ({approach}) - query: {query}")
                        
                        # Process articles
                        for article in results:
                            content = f"{article.get('title', '')} {article.get('description', '')}"
                            
                            if self._should_include_article(content):
                                # Parse published date
                                published_date = datetime.now().strftime('%Y-%m-%d')
                                if article.get('publishedAt'):
                                    try:
                                        from dateutil import parser
                                        parsed_date = parser.parse(article['publishedAt'])
                                        published_date = parsed_date.strftime('%Y-%m-%d')
                                    except:
                                        pass
                                
                                article_data = {
                                    'title': article.get('title', ''),
                                    'text': content,
                                    'url': article.get('url', ''),
                                    'source': station_name,
                                    'source_url': article.get('url', ''),
                                    'source_type': 'radio',
                                    'platform': 'newsapi',
                                    'language': 'English',
                                    'country': 'Nigeria',
                                    'region': station_config['region'],
                                    'location': station_config['location'],
                                    'date': published_date,
                                    'published_date': published_date,
                                    'query': query,
                                    'file_source': 'radio_newsapi',
                                    'description': article.get('description', ''),
                                    'content': content,
                                    'id': f"radio_newsapi_{hash(article.get('url', ''))}_{int(time.time())}",
                                    'favorite': False,
                                    'tone': 'neutral',
                                    'source_name': station_name,
                                    'parent_url': article.get('url', ''),
                                    'parent_id': f"newsapi_{station_name.replace(' ', '_').lower()}",
                                    'children': [],
                                    'direct_reach': 0,
                                    'cumulative_reach': 0,
                                    'domain_reach': 0,
                                    'tags': ['radio', 'newsapi', station_config['region'].lower()],
                                    'newsapi_source': article.get('source', {}).get('name', 'Unknown'),
                                    'newsapi_domain': article.get('url', '').split('/')[2] if article.get('url') else 'Unknown'
                                }
                                
                                articles.append(article_data)
                        
                        # Rate limiting - NewsAPI has limits - use config delay
                        delay = self.config.get_int("collectors.radio_gnews.delay_between_requests_seconds", 1)
                        time.sleep(delay)
                        
                    except Exception as e:
                        logger.error(f"Error collecting from {station_name} for query '{query}' via NewsAPI: {e}")
                        continue
            
            logger.info(f"Collected {len(articles)} articles from {station_name} via NewsAPI")
            
        except Exception as e:
            logger.error(f"Error collecting from {station_name} via NewsAPI: {e}")
        
        return articles

    def collect_all(self, queries: Optional[List[str]] = None, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Collect news from all configured radio stations using both GNews and NewsAPI"""
        logger.info("Starting multi-API radio station collection...")
        
        if not queries:
            queries = self._get_target_keywords()
        
        all_articles = []
        successful_stations = 0
        total_stations = len(self.radio_sources)
        
        for station_name, station_config in self.radio_sources.items():
            station_articles = []
            
            try:
                # Collect from GNews if available
                if self.gnews_key:
                    gnews_articles = self.collect_from_radio_station(station_name, station_config, queries)
                    station_articles.extend(gnews_articles)
                    logger.info(f"GNews: {len(gnews_articles)} articles from {station_name}")
                
                # Collect from NewsAPI if available
                if self.newsapi_key:
                    newsapi_articles = self.collect_from_newsapi(station_name, station_config, queries)
                    station_articles.extend(newsapi_articles)
                    logger.info(f"NewsAPI: {len(newsapi_articles)} articles from {station_name}")
                
                all_articles.extend(station_articles)
                successful_stations += 1
                logger.info(f"Total collected {len(station_articles)} articles from {station_name}")
                
            except Exception as e:
                logger.error(f"Failed to collect from {station_name}: {e}")
        
        # Save to CSV if output file specified
        if output_file and all_articles:
            df = pd.DataFrame(all_articles)
            df.to_csv(output_file, index=False, encoding='utf-8')
            logger.info(f"Saved {len(all_articles)} articles to {output_file}")
        
        # Log breakdown by platform
        platform_breakdown: Dict[str, int] = {}
        for article in all_articles:
            platform = article.get('platform', 'unknown')
            platform_breakdown[platform] = platform_breakdown.get(platform, 0) + 1
        
        logger.info("Platform breakdown:")
        for platform, count in platform_breakdown.items():
            logger.info(f"  - {platform}: {count} articles")
        
        results = {
            'total_articles': len(all_articles),
            'successful_stations': successful_stations,
            'total_stations': total_stations,
            'articles': all_articles,
            'platform_breakdown': platform_breakdown
        }
        
        logger.info(f"Multi-API radio collection complete: {len(all_articles)} articles from {successful_stations}/{total_stations} stations")
        return results

def main(target_and_variations: List[str], user_id: Optional[str] = None):
    """Main function to run multi-API radio collection (GNews + NewsAPI)"""
    logger.info(f"Starting multi-API radio collection for: {target_and_variations}")
    
    try:
        collector = GNewsRadioCollector()
        
        # Set up output file
        from src.config.path_manager import PathManager
        path_manager = PathManager()
        output_dir = path_manager.data_raw
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"radio_gnews_{timestamp}.csv"
        
        # Collect data
        results = collector.collect_all(queries=target_and_variations, output_file=str(output_file))
        
        logger.info(f"GNews radio collection completed successfully. Collected {results['total_articles']} articles.")
        return results
        
    except Exception as e:
        logger.error(f"Error in GNews radio collection: {e}", exc_info=True)
        return {'total_articles': 0, 'error': str(e)}

if __name__ == "__main__":
    # Test the collector
    test_queries = ["Bola Ahmed Tinubu", "Bola Tinubu", "President Tinubu", "Tinubu", "Nigeria President", "Nigerian President", "Nigeria"]
    main(test_queries)
