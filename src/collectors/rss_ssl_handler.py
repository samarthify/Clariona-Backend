import ssl
import requests
import urllib3
import logging
from typing import Optional, Dict, Any
import warnings
from urllib3.exceptions import InsecureRequestWarning
import socket
from urllib.error import URLError, HTTPError

# Try to import certifi, but don't fail if it's not available
try:
    import certifi
    CERTIFI_AVAILABLE = True
except ImportError:
    CERTIFI_AVAILABLE = False

# Suppress SSL warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings('ignore', category=InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class RSSSSLHandler:
    """
    Advanced SSL handler for RSS feed collection.
    Provides multiple SSL strategies and automatic fallback mechanisms.
    """
    
    def __init__(self):
        self.ssl_strategies = {
            'strict': self._create_strict_ssl_context(),
            'relaxed': self._create_relaxed_ssl_context(),
            'disabled': self._create_disabled_ssl_context(),
            'custom_ca': self._create_custom_ca_context()
        }
        
        # Track SSL issues per domain
        self.ssl_issues = {}
        
        # Load timeout from ConfigManager
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            self.ssl_timeout = config.get_int("collectors.rss_validator.timeout_seconds", 10)
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for SSL timeout, using default 10s: {e}")
            self.ssl_timeout = 10
        
        # Default headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, application/atom+xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
    
    def _create_strict_ssl_context(self) -> ssl.SSLContext:
        """Create strict SSL context with full verification."""
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Use certifi for certificate bundle if available
        if CERTIFI_AVAILABLE:
            try:
                context.load_verify_locations(certifi.where())
            except Exception as e:
                logger.warning(f"Failed to load certifi certificates: {e}")
        
        return context
    
    def _create_relaxed_ssl_context(self) -> ssl.SSLContext:
        """Create relaxed SSL context with hostname checking disabled."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Use certifi for certificate bundle if available
        if CERTIFI_AVAILABLE:
            try:
                context.load_verify_locations(certifi.where())
            except Exception as e:
                logger.warning(f"Failed to load certifi certificates: {e}")
        
        return context
    
    def _create_disabled_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context with verification disabled."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    
    def _create_custom_ca_context(self) -> ssl.SSLContext:
        """Create SSL context with custom CA handling."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Add common CA certificates
        try:
            context.load_verify_locations(certifi.where())
        except Exception as e:
            logger.warning(f"Failed to load certifi certificates: {e}")
        
        # Note: set_verify is not available in Python's ssl module
        # We'll use the context as-is with relaxed verification
        
        return context
    
    
    def _get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return url
    
    def _record_ssl_issue(self, url: str, error: Exception):
        """Record SSL issue for a domain."""
        domain = self._get_domain_from_url(url)
        if domain not in self.ssl_issues:
            self.ssl_issues[domain] = []
        
        self.ssl_issues[domain].append({
            'error': str(error),
            'error_type': type(error).__name__,
            'timestamp': str(logger.handlers[0].formatter.formatTime(logger.handlers[0], None) if logger.handlers else 'unknown')
        })
    
    def _should_use_strategy(self, url: str, strategy: str) -> bool:
        """Determine if a strategy should be used for a URL."""
        domain = self._get_domain_from_url(url)
        
        # Check if domain has known SSL issues
        if domain in self.ssl_issues:
            recent_issues = self.ssl_issues[domain][-3:]  # Last 3 issues
            
            # If recent issues with strict verification, skip it
            if strategy == 'strict' and any('CERTIFICATE_VERIFY_FAILED' in issue['error'] for issue in recent_issues):
                return False
            
            # If recent timeout issues, try disabled first
            if strategy == 'strict' and any('timeout' in issue['error'].lower() for issue in recent_issues):
                return False
        
        return True
    
    def fetch_with_ssl_strategy(self, url: str, strategy: str, timeout: int = 10) -> Optional[requests.Response]:
        """Fetch URL using specific SSL strategy."""
        if not self._should_use_strategy(url, strategy):
            return None
        
        try:
            if strategy == 'strict':
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=timeout,
                    verify=True,
                    stream=False
                )
            elif strategy == 'relaxed':
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=timeout,
                    verify=True,
                    stream=False
                )
            elif strategy == 'disabled':
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=timeout,
                    verify=False,
                    stream=False
                )
            elif strategy == 'custom_ca':
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=timeout,
                    verify=False,
                    stream=False
                )
            else:
                return None
            
            return response
            
        except Exception as e:
            self._record_ssl_issue(url, e)
            logger.debug(f"SSL strategy '{strategy}' failed for {url}: {str(e)}")
            return None
    
    def fetch_with_auto_ssl(self, url: str, timeout: int = 10) -> Optional[requests.Response]:
        """Fetch URL with automatic SSL strategy selection."""
        strategies = ['strict', 'relaxed', 'disabled', 'custom_ca']
        
        for strategy in strategies:
            logger.debug(f"Trying SSL strategy '{strategy}' for {url}")
            response = self.fetch_with_ssl_strategy(url, strategy, timeout)
            
            if response and response.status_code == 200:
                logger.debug(f"SSL strategy '{strategy}' succeeded for {url}")
                return response
        
        logger.warning(f"All SSL strategies failed for {url}")
        return None
    
    def test_ssl_connectivity(self, url: str) -> Dict[str, Any]:
        """Test SSL connectivity for a URL."""
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            
            results = {}
            
            for strategy_name, context in self.ssl_strategies.items():
                try:
                    with socket.create_connection((hostname, port), timeout=self.ssl_timeout) as sock:
                        if parsed.scheme == 'https':
                            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                                results[strategy_name] = {
                                    'success': True,
                                    'certificate': ssock.getpeercert(),
                                    'cipher': ssock.cipher(),
                                    'version': ssock.version()
                                }
                        else:
                            results[strategy_name] = {
                                'success': True,
                                'certificate': None,
                                'cipher': None,
                                'version': None
                            }
                except Exception as e:
                    results[strategy_name] = {
                        'success': False,
                        'error': str(e),
                        'error_type': type(e).__name__
                    }
            
            return results
            
        except Exception as e:
            return {
                'error': f"Failed to test SSL connectivity: {str(e)}",
                'error_type': type(e).__name__
            }
    
    def get_ssl_report(self) -> Dict[str, Any]:
        """Get SSL issues report."""
        report = {
            'total_domains_with_issues': len(self.ssl_issues),
            'domains': {}
        }
        
        for domain, issues in self.ssl_issues.items():
            report['domains'][domain] = {
                'total_issues': len(issues),
                'recent_issues': issues[-5:],  # Last 5 issues
                'error_types': list(set(issue['error_type'] for issue in issues))
            }
        
        return report
    
    def clear_ssl_issues(self):
        """Clear SSL issues history."""
        self.ssl_issues.clear()
        logger.info("SSL issues history cleared")
    
    def get_recommended_strategy(self, url: str) -> str:
        """Get recommended SSL strategy for a URL."""
        domain = self._get_domain_from_url(url)
        
        if domain in self.ssl_issues:
            recent_issues = self.ssl_issues[domain][-3:]
            
            # If recent certificate issues, use disabled
            if any('CERTIFICATE_VERIFY_FAILED' in issue['error'] for issue in recent_issues):
                return 'disabled'
            
            # If recent timeout issues, use relaxed
            if any('timeout' in issue['error'].lower() for issue in recent_issues):
                return 'relaxed'
        
        # Default to strict for new domains
        return 'strict'
