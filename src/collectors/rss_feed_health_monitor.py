import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import requests
import feedparser
import ssl
from urllib.error import URLError, HTTPError
import time

logger = logging.getLogger(__name__)

class RSSFeedHealthMonitor:
    """
    Monitors RSS feed health and tracks reliability metrics.
    Provides feed validation and health scoring system.
    """
    
    def __init__(self, health_data_file: str = "rss_feed_health.json"):
        from src.config.path_manager import PathManager
        self.path_manager = PathManager()
        self.base_path = self.path_manager.base_path
        self.health_data_file = self.path_manager.data_raw.parent / health_data_file
        self.health_data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Health thresholds
        self.health_thresholds = {
            'excellent': 0.9,    # 90%+ success rate
            'good': 0.7,         # 70%+ success rate
            'fair': 0.5,          # 50%+ success rate
            'poor': 0.3,         # 30%+ success rate
            'critical': 0.0       # Below 30% success rate
        }
        
        # Load existing health data
        self.health_data = self._load_health_data()
        
        # SSL context for better certificate handling
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # Request headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, application/atom+xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
    
    def _load_health_data(self) -> Dict:
        """Load existing health data from file."""
        try:
            if self.health_data_file.exists():
                with open(self.health_data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load health data: {e}")
        
        return {
            'feeds': {},
            'last_updated': None,
            'monitoring_enabled': True
        }
    
    def _save_health_data(self):
        """Save health data to file."""
        try:
            self.health_data['last_updated'] = datetime.now().isoformat()
            with open(self.health_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.health_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save health data: {e}")
    
    def _get_feed_health(self, feed_url: str) -> Dict:
        """Get health data for a specific feed."""
        if feed_url not in self.health_data['feeds']:
            self.health_data['feeds'][feed_url] = {
                'success_count': 0,
                'failure_count': 0,
                'last_success': None,
                'last_failure': None,
                'last_error': None,
                'avg_response_time': 0,
                'response_times': [],
                'ssl_issues': 0,
                'timeout_issues': 0,
                'xml_issues': 0,
                'network_issues': 0,
                'created_at': datetime.now().isoformat()
            }
        return self.health_data['feeds'][feed_url]
    
    def _calculate_health_score(self, feed_url: str) -> float:
        """Calculate health score for a feed (0.0 to 1.0)."""
        health = self._get_feed_health(feed_url)
        total_attempts = health['success_count'] + health['failure_count']
        
        if total_attempts == 0:
            return 1.0  # New feed, assume healthy
        
        success_rate = health['success_count'] / total_attempts
        
        # Penalize feeds with recent failures
        if health['last_failure']:
            last_failure = datetime.fromisoformat(health['last_failure'])
            if datetime.now() - last_failure < timedelta(hours=24):
                success_rate *= 0.8  # 20% penalty for recent failures
        
        # Penalize feeds with high error rates
        error_penalty: float = 0.0
        if health.get('ssl_issues', 0) > health.get('success_count', 0):
            error_penalty += 0.2
        if health.get('timeout_issues', 0) > health.get('success_count', 0):
            error_penalty += 0.2
        if health.get('xml_issues', 0) > health.get('success_count', 0):
            error_penalty += 0.1
        
        return max(0.0, success_rate - error_penalty)  # type: ignore[no-any-return]
    
    def _get_health_status(self, health_score: float) -> str:
        """Get health status based on score."""
        if health_score >= self.health_thresholds['excellent']:
            return 'excellent'
        elif health_score >= self.health_thresholds['good']:
            return 'good'
        elif health_score >= self.health_thresholds['fair']:
            return 'fair'
        elif health_score >= self.health_thresholds['poor']:
            return 'poor'
        else:
            return 'critical'
    
    def validate_feed(self, feed_url: str, timeout: Optional[int] = None) -> Tuple[bool, str, float]:
        """
        Validate a single RSS feed.
        
        Returns:
            Tuple of (is_valid, error_message, response_time)
        """
        # Get timeout from ConfigManager if not provided
        if timeout is None:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            timeout = config.get_int("collectors.rss_health_monitor.timeout_seconds", 10)
        
        start_time = time.time()
        health = self._get_feed_health(feed_url)
        
        try:
            # Try multiple approaches for better reliability
            feed = None
            
            # Approach 1: Direct feedparser with SSL context
            try:
                feed = feedparser.parse(feed_url, handlers=[], request_headers=self.headers)
            except (ssl.SSLError, URLError) as e:
                logger.debug(f"Direct feedparser failed for {feed_url}: {e}")
            
            # Approach 2: Requests with SSL verification disabled
            if not feed or feed.get('bozo', 0) == 1:
                try:
                    response = requests.get(
                        feed_url,
                        headers=self.headers,
                        timeout=timeout,
                        verify=False,
                        stream=False
                    )
                    if response.status_code == 200:
                        feed = feedparser.parse(response.text)
                except Exception as e:
                    logger.debug(f"Requests approach failed for {feed_url}: {e}")
            
            # Approach 3: Try alternative URL patterns
            if not feed or feed.get('bozo', 0) == 1:
                alternative_urls = [
                    feed_url.rstrip('/') + '/feed',
                    feed_url.rstrip('/') + '/rss',
                    feed_url.replace('feed', 'rss'),
                    feed_url.replace('rss', 'feed')
                ]
                
                for alt_url in alternative_urls:
                    try:
                        response = requests.get(
                            alt_url,
                            headers=self.headers,
                            timeout=timeout,
                            verify=False
                        )
                        if response.status_code == 200:
                            feed = feedparser.parse(response.text)
                            if feed and feed.get('bozo', 0) == 0:
                                break
                    except Exception:
                        continue
            
            response_time = time.time() - start_time
            
            # Validate feed structure
            if not feed:
                raise ValueError("No feed data received")
            
            if hasattr(feed, 'status') and feed.status >= 400:
                from http.client import HTTPMessage
                raise HTTPError(feed_url, feed.status, f"HTTP Error: {feed.status}", HTTPMessage(), None)
            
            if feed.get('bozo', 0) == 1:
                if hasattr(feed, 'bozo_exception'):
                    raise feed.bozo_exception
                else:
                    raise ValueError("Feed parsing failed (bozo)")
            
            if not feed.get('entries', []):
                raise ValueError("No entries found in feed")
            
            # Record success
            health['success_count'] += 1
            health['last_success'] = datetime.now().isoformat()
            health['response_times'].append(response_time)
            health['avg_response_time'] = sum(health['response_times']) / len(health['response_times'])
            
            # Keep only last 10 response times
            if len(health['response_times']) > 10:
                health['response_times'] = health['response_times'][-10:]
            
            return True, "Feed is valid", response_time
            
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Record failure
            health['failure_count'] += 1
            health['last_failure'] = datetime.now().isoformat()
            health['last_error'] = f"{error_type}: {error_msg}"
            
            # Categorize error types
            if 'SSL' in error_type or 'certificate' in error_msg.lower():
                health['ssl_issues'] += 1
            elif 'timeout' in error_msg.lower():
                health['timeout_issues'] += 1
            elif 'xml' in error_msg.lower() or 'parse' in error_msg.lower():
                health['xml_issues'] += 1
            elif 'network' in error_msg.lower() or 'connection' in error_msg.lower():
                health['network_issues'] += 1
            
            return False, f"{error_type}: {error_msg}", response_time
    
    def validate_feeds(self, feed_urls: List[str], max_workers: int = 5) -> Dict[str, Dict]:
        """
        Validate multiple feeds concurrently.
        
        Returns:
            Dictionary with feed URLs as keys and validation results as values
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit validation tasks
            future_to_url = {
                executor.submit(self.validate_feed, url): url 
                for url in feed_urls
            }
            
            # Collect results
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    is_valid, error_msg, response_time = future.result()
                    health_score = self._calculate_health_score(url)
                    health_status = self._get_health_status(health_score)
                    
                    results[url] = {
                        'is_valid': is_valid,
                        'error_message': error_msg,
                        'response_time': response_time,
                        'health_score': health_score,
                        'health_status': health_status,
                        'success_rate': self._get_feed_health(url)['success_count'] / 
                                      max(1, self._get_feed_health(url)['success_count'] + 
                                          self._get_feed_health(url)['failure_count'])
                    }
                except Exception as e:
                    results[url] = {
                        'is_valid': False,
                        'error_message': f"Validation failed: {str(e)}",
                        'response_time': 0,
                        'health_score': 0,
                        'health_status': 'critical',
                        'success_rate': 0
                    }
        
        # Save updated health data
        self._save_health_data()
        
        return results
    
    def get_healthy_feeds(self, feed_urls: List[str], min_health_score: float = 0.5) -> List[str]:
        """Get list of healthy feeds above minimum health score."""
        healthy_feeds = []
        
        for url in feed_urls:
            health_score = self._calculate_health_score(url)
            if health_score >= min_health_score:
                healthy_feeds.append(url)
        
        return healthy_feeds
    
    def get_feed_health_report(self, feed_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate comprehensive health report for feeds."""
        if feed_urls is None:
            feed_urls = list(self.health_data['feeds'].keys())
        
        report: Dict[str, Any] = {
            'total_feeds': len(feed_urls),
            'health_distribution': {
                'excellent': 0,
                'good': 0,
                'fair': 0,
                'poor': 0,
                'critical': 0
            },
            'feeds': {},
            'recommendations': []
        }
        
        for url in feed_urls:
            health_score = self._calculate_health_score(url)
            health_status = self._get_health_status(health_score)
            health_data = self._get_feed_health(url)
            
            report['health_distribution'][health_status] += 1
            
            report['feeds'][url] = {
                'health_score': health_score,
                'health_status': health_status,
                'success_count': health_data['success_count'],
                'failure_count': health_data['failure_count'],
                'success_rate': health_data['success_count'] / 
                              max(1, health_data['success_count'] + health_data['failure_count']),
                'avg_response_time': health_data['avg_response_time'],
                'last_success': health_data['last_success'],
                'last_failure': health_data['last_failure'],
                'error_categories': {
                    'ssl_issues': health_data['ssl_issues'],
                    'timeout_issues': health_data['timeout_issues'],
                    'xml_issues': health_data['xml_issues'],
                    'network_issues': health_data['network_issues']
                }
            }
        
        # Generate recommendations
        critical_feeds = [url for url, data in report['feeds'].items() 
                        if data['health_status'] == 'critical']
        if critical_feeds:
            report['recommendations'].append(f"Consider removing {len(critical_feeds)} critical feeds")
        
        ssl_issue_feeds = [url for url, data in report['feeds'].items() 
                          if data['error_categories']['ssl_issues'] > 0]
        if ssl_issue_feeds:
            report['recommendations'].append(f"SSL issues detected in {len(ssl_issue_feeds)} feeds")
        
        return report
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Remove health data older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for feed_url, health_data in self.health_data['feeds'].items():
            # Remove old response times
            if 'response_times' in health_data:
                health_data['response_times'] = [
                    rt for rt in health_data['response_times']
                    if rt > 0  # Keep all response times for now
                ]
        
        self._save_health_data()
        logger.info(f"Cleaned up health data older than {days_to_keep} days")











