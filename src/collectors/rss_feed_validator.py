import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import feedparser
import ssl
from urllib.error import URLError, HTTPError
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import warnings
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

logger = logging.getLogger(__name__)

class RSSFeedValidator:
    """
    Validates RSS feeds before collection runs.
    Provides comprehensive feed validation and health checking.
    """
    
    def __init__(self, config_file: str = "reliable_rss_feeds.json"):
        self.base_path = Path(__file__).parent
        self.config_file = self.base_path / config_file
        
        # Load configuration
        self.config = self._load_config()
        
        # SSL contexts for different scenarios
        self.ssl_contexts = {
            'strict': ssl.create_default_context(),
            'relaxed': ssl.create_default_context(),
            'disabled': ssl.create_default_context()
        }
        
        # Configure SSL contexts
        self.ssl_contexts['relaxed'].check_hostname = False
        self.ssl_contexts['relaxed'].verify_mode = ssl.CERT_NONE
        self.ssl_contexts['disabled'].check_hostname = False
        self.ssl_contexts['disabled'].verify_mode = ssl.CERT_NONE
        
        # Request headers
        self.headers = {
            'User-Agent': self.config.get('feed_validation', {}).get('user_agent', 
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'),
            'Accept': 'application/rss+xml, application/xml, application/atom+xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        }
        
        # Validation settings
        self.timeout = self.config.get('feed_validation', {}).get('timeout_seconds', 10)
        self.max_retries = self.config.get('feed_validation', {}).get('max_retries', 3)
        self.min_health_score = self.config.get('feed_validation', {}).get('min_health_score', 0.5)
    
    def _load_config(self) -> Dict:
        """Load configuration from JSON file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
        
        return {
            'rss_feeds': {},
            'feed_validation': {
                'timeout_seconds': 10,
                'max_retries': 3,
                'min_health_score': 0.5,
                'ssl_verification': False
            }
        }
    
    def _get_all_feeds(self) -> List[str]:
        """Get all RSS feeds from configuration."""
        feeds = []
        
        for category, subcategories in self.config.get('rss_feeds', {}).items():
            if isinstance(subcategories, dict):
                for subcategory, feed_list in subcategories.items():
                    if isinstance(feed_list, list):
                        feeds.extend(feed_list)
            elif isinstance(subcategories, list):
                feeds.extend(subcategories)
        
        return list(set(feeds))  # Remove duplicates
    
    def _get_replacement_feed(self, original_feed: str) -> Optional[str]:
        """Get replacement feed for a failing feed."""
        replacements = self.config.get('replacement_mapping', {})
        return replacements.get(original_feed)
    
    def _validate_feed_structure(self, feed) -> Tuple[bool, str]:
        """Validate RSS feed structure and content."""
        if not feed:
            return False, "No feed data received"
        
        if hasattr(feed, 'status') and feed.status >= 400:
            return False, f"HTTP Error: {feed.status}"
        
        if feed.get('bozo', 0) == 1:
            if hasattr(feed, 'bozo_exception'):
                return False, f"Feed parsing error: {feed.bozo_exception}"
            else:
                return False, "Feed parsing failed (bozo)"
        
        entries = feed.get('entries', [])
        if not entries:
            return False, "No entries found in feed"
        
        # Check for minimum required fields
        valid_entries = 0
        for entry in entries:
            if entry.get('title') and entry.get('link'):
                valid_entries += 1
        
        if valid_entries == 0:
            return False, "No valid entries found"
        
        if valid_entries < len(entries) * 0.5:  # Less than 50% valid entries
            return False, f"Too many invalid entries: {valid_entries}/{len(entries)}"
        
        return True, f"Feed structure valid with {valid_entries} entries"
    
    def _fetch_feed_with_multiple_approaches(self, feed_url: str) -> Tuple[Optional[object], str, float]:
        """Try multiple approaches to fetch and parse a feed."""
        start_time = time.time()
        
        approaches = [
            ("Direct feedparser", self._approach_direct_feedparser),
            ("Requests with SSL disabled", self._approach_requests_no_ssl),
            ("Requests with SSL enabled", self._approach_requests_with_ssl),
            ("Alternative URL patterns", self._approach_alternative_urls)
        ]
        
        for approach_name, approach_func in approaches:
            try:
                logger.debug(f"Trying {approach_name} for {feed_url}")
                feed, error_msg = approach_func(feed_url)
                
                if feed:
                    response_time = time.time() - start_time
                    is_valid, validation_msg = self._validate_feed_structure(feed)
                    
                    if is_valid:
                        logger.debug(f"{approach_name} succeeded for {feed_url}")
                        return feed, validation_msg, response_time
                    else:
                        logger.debug(f"{approach_name} failed validation for {feed_url}: {validation_msg}")
                        continue
                else:
                    logger.debug(f"{approach_name} failed for {feed_url}: {error_msg}")
                    continue
                    
            except Exception as e:
                logger.debug(f"{approach_name} exception for {feed_url}: {str(e)}")
                continue
        
        response_time = time.time() - start_time
        return None, "All approaches failed", response_time
    
    def _approach_direct_feedparser(self, feed_url: str) -> Tuple[Optional[object], str]:
        """Direct feedparser approach."""
        try:
            feed = feedparser.parse(feed_url, handlers=[], request_headers=self.headers)
            if feed and feed.get('bozo', 0) == 0:
                return feed, "Success"
            return None, "Feed parsing failed"
        except Exception as e:
            return None, str(e)
    
    def _approach_requests_no_ssl(self, feed_url: str) -> Tuple[Optional[object], str]:
        """Requests approach with SSL verification disabled."""
        try:
            response = requests.get(
                feed_url,
                headers=self.headers,
                timeout=self.timeout,
                verify=False,
                stream=False
            )
            if response.status_code == 200:
                feed = feedparser.parse(response.text)
                return feed, "Success"
            return None, f"HTTP {response.status_code}"
        except Exception as e:
            return None, str(e)
    
    def _approach_requests_with_ssl(self, feed_url: str) -> Tuple[Optional[object], str]:
        """Requests approach with SSL verification enabled."""
        try:
            response = requests.get(
                feed_url,
                headers=self.headers,
                timeout=self.timeout,
                verify=True,
                stream=False
            )
            if response.status_code == 200:
                feed = feedparser.parse(response.text)
                return feed, "Success"
            return None, f"HTTP {response.status_code}"
        except Exception as e:
            return None, str(e)
    
    def _approach_alternative_urls(self, feed_url: str) -> Tuple[Optional[object], str]:
        """Try alternative URL patterns."""
        alternative_urls = [
            feed_url.rstrip('/') + '/feed',
            feed_url.rstrip('/') + '/rss',
            feed_url.replace('feed', 'rss'),
            feed_url.replace('rss', 'feed'),
            feed_url + '/feed',
            feed_url + '/rss'
        ]
        
        for alt_url in alternative_urls:
            if alt_url == feed_url:
                continue
                
            try:
                response = requests.get(
                    alt_url,
                    headers=self.headers,
                    timeout=self.timeout,
                    verify=False
                )
                if response.status_code == 200:
                    feed = feedparser.parse(response.text)
                    if feed and feed.get('bozo', 0) == 0:
                        return feed, f"Success with alternative URL: {alt_url}"
            except Exception:
                continue
        
        return None, "No alternative URLs worked"
    
    def validate_single_feed(self, feed_url: str) -> Dict:
        """Validate a single RSS feed."""
        logger.info(f"Validating feed: {feed_url}")
        
        feed, message, response_time = self._fetch_feed_with_multiple_approaches(feed_url)
        
        result = {
            'url': feed_url,
            'is_valid': feed is not None,
            'message': message,
            'response_time': response_time,
            'entries_count': len(feed.get('entries', [])) if feed else 0,
            'feed_title': feed.feed.get('title', '') if feed and hasattr(feed, 'feed') else '',
            'last_updated': datetime.now().isoformat()
        }
        
        if feed:
            # Additional validation metrics
            entries = feed.get('entries', [])
            valid_entries = sum(1 for entry in entries if entry.get('title') and entry.get('link'))
            
            result.update({
                'valid_entries_count': valid_entries,
                'validity_ratio': valid_entries / len(entries) if entries else 0,
                'has_description': sum(1 for entry in entries if entry.get('description')) / len(entries) if entries else 0,
                'has_pubdate': sum(1 for entry in entries if entry.get('published')) / len(entries) if entries else 0
            })
        
        return result
    
    def validate_feeds_batch(self, feed_urls: List[str], max_workers: int = 5) -> Dict[str, Dict]:
        """Validate multiple feeds concurrently."""
        logger.info(f"Validating {len(feed_urls)} feeds with {max_workers} workers")
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit validation tasks
            future_to_url = {
                executor.submit(self.validate_single_feed, url): url 
                for url in feed_urls
            }
            
            # Collect results
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results[url] = result
                    
                    status = "✓" if result['is_valid'] else "✗"
                    logger.info(f"{status} {url}: {result['message']} ({result['response_time']:.2f}s)")
                    
                except Exception as e:
                    results[url] = {
                        'url': url,
                        'is_valid': False,
                        'message': f"Validation failed: {str(e)}",
                        'response_time': 0,
                        'entries_count': 0,
                        'feed_title': '',
                        'last_updated': datetime.now().isoformat()
                    }
                    logger.error(f"✗ {url}: Validation exception: {str(e)}")
        
        return results
    
    def get_healthy_feeds(self, feed_urls: List[str] = None) -> List[str]:
        """Get list of healthy feeds."""
        if feed_urls is None:
            feed_urls = self._get_all_feeds()
        
        logger.info(f"Checking health of {len(feed_urls)} feeds")
        validation_results = self.validate_feeds_batch(feed_urls)
        
        healthy_feeds = []
        unhealthy_feeds = []
        
        for url, result in validation_results.items():
            if result['is_valid'] and result['entries_count'] > 0:
                healthy_feeds.append(url)
            else:
                unhealthy_feeds.append(url)
                # Try to get replacement
                replacement = self._get_replacement_feed(url)
                if replacement:
                    logger.info(f"Found replacement for {url}: {replacement}")
                    healthy_feeds.append(replacement)
        
        logger.info(f"Found {len(healthy_feeds)} healthy feeds, {len(unhealthy_feeds)} unhealthy feeds")
        
        return healthy_feeds
    
    def generate_validation_report(self, feed_urls: List[str] = None) -> Dict:
        """Generate comprehensive validation report."""
        if feed_urls is None:
            feed_urls = self._get_all_feeds()
        
        validation_results = self.validate_feeds_batch(feed_urls)
        
        report = {
            'summary': {
                'total_feeds': len(feed_urls),
                'valid_feeds': sum(1 for r in validation_results.values() if r['is_valid']),
                'invalid_feeds': sum(1 for r in validation_results.values() if not r['is_valid']),
                'avg_response_time': sum(r['response_time'] for r in validation_results.values()) / len(validation_results),
                'total_entries': sum(r['entries_count'] for r in validation_results.values())
            },
            'feeds': validation_results,
            'recommendations': [],
            'generated_at': datetime.now().isoformat()
        }
        
        # Generate recommendations
        invalid_feeds = [url for url, result in validation_results.items() if not result['is_valid']]
        if invalid_feeds:
            report['recommendations'].append(f"Remove or replace {len(invalid_feeds)} invalid feeds")
        
        slow_feeds = [url for url, result in validation_results.items() if result['response_time'] > 5.0]
        if slow_feeds:
            report['recommendations'].append(f"Consider removing {len(slow_feeds)} slow feeds (>5s response time)")
        
        empty_feeds = [url for url, result in validation_results.items() if result['entries_count'] == 0]
        if empty_feeds:
            report['recommendations'].append(f"Remove {len(empty_feeds)} feeds with no entries")
        
        return report
    
    def save_validation_report(self, report: Dict, filename: str = None) -> str:
        """Save validation report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rss_validation_report_{timestamp}.json"
        
        report_file = self.base_path.parent.parent / "data" / filename
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Validation report saved to {report_file}")
        return str(report_file)











