"""
Rate limiter for OpenAI API calls to prevent hitting rate limits.
Tracks token usage per minute and limits concurrent requests.
"""

import time
import threading
import logging
from typing import Optional, Dict, Tuple, Deque
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger('OpenAIRateLimiter')

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    # Tokens per minute limit (default: 200,000 for gpt-5-nano)
    tokens_per_minute: int = 200000
    # Maximum concurrent requests
    max_concurrent_requests: int = 10
    # Estimated tokens per request (conservative estimate, updated after optimizations)
    estimated_tokens_per_request: int = 5000
    # Retry delay on 429 errors (seconds)
    retry_delay_base: float = 1.0
    # Maximum retry delay (seconds)
    retry_delay_max: float = 60.0

class OpenAIRateLimiter:
    """
    Rate limiter for OpenAI API calls.
    Tracks token usage per minute and limits concurrent requests.
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize the rate limiter.
        
        Args:
            config: Rate limit configuration. If None, uses defaults.
        """
        self.config = config or RateLimitConfig()
        
        # Token usage tracking (sliding window)
        self.token_usage: Deque[Tuple[float, int]] = deque()  # List of (timestamp, tokens) tuples
        self.lock = threading.Lock()
        
        # Semaphore to limit concurrent requests
        self.semaphore = threading.Semaphore(self.config.max_concurrent_requests)
        
        # Track retry attempts
        self.retry_counts: Dict[str, int] = {}
        
        logger.info(
            f"OpenAIRateLimiter initialized: "
            f"TPM={self.config.tokens_per_minute}, "
            f"max_concurrent={self.config.max_concurrent_requests}, "
            f"est_tokens_per_req={self.config.estimated_tokens_per_request}"
        )
    
    def _cleanup_old_entries(self):
        """Remove token usage entries older than 1 minute."""
        current_time = time.time()
        cutoff_time = current_time - 60.0  # 1 minute ago
        
        while self.token_usage and self.token_usage[0][0] < cutoff_time:
            self.token_usage.popleft()
    
    def _get_current_token_usage(self) -> int:
        """Get total token usage in the last minute."""
        with self.lock:
            self._cleanup_old_entries()
            return sum(tokens for _, tokens in self.token_usage)
    
    def _can_make_request(self, estimated_tokens: Optional[int] = None) -> bool:
        """
        Check if we can make a request without exceeding rate limits.
        
        Args:
            estimated_tokens: Estimated tokens for this request. If None, uses default.
        
        Returns:
            True if request can be made, False otherwise.
        """
        if estimated_tokens is None:
            estimated_tokens = self.config.estimated_tokens_per_request
        
        current_usage = self._get_current_token_usage()
        available_tokens = self.config.tokens_per_minute - current_usage
        
        return available_tokens >= estimated_tokens
    
    def _wait_for_token_availability(self, estimated_tokens: Optional[int] = None):
        """
        Wait until we have enough tokens available.
        
        Args:
            estimated_tokens: Estimated tokens for this request.
        """
        if estimated_tokens is None:
            estimated_tokens = self.config.estimated_tokens_per_request
        
        while not self._can_make_request(estimated_tokens):
            # Calculate wait time based on oldest token usage entry
            with self.lock:
                if self.token_usage:
                    oldest_time = self.token_usage[0][0]
                    wait_time = max(0.1, 60.0 - (time.time() - oldest_time))
                else:
                    wait_time = 0.1
            
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s for token availability")
            time.sleep(min(wait_time, 1.0))  # Sleep in small increments
    
    def _record_token_usage(self, tokens: int):
        """
        Record token usage for rate limiting.
        
        Args:
            tokens: Number of tokens used.
        """
        current_time = time.time()
        with self.lock:
            self.token_usage.append((current_time, tokens))
            self._cleanup_old_entries()
    
    def acquire(self, estimated_tokens: Optional[int] = None):
        """
        Acquire permission to make an API request.
        Blocks until permission is granted.
        
        Args:
            estimated_tokens: Estimated tokens for this request.
        
        Returns:
            Context manager that releases the semaphore when done.
        """
        # Wait for token availability
        self._wait_for_token_availability(estimated_tokens)
        
        # Acquire semaphore (blocks if too many concurrent requests)
        self.semaphore.acquire()
        
        # Record token usage
        if estimated_tokens is None:
            estimated_tokens = self.config.estimated_tokens_per_request
        self._record_token_usage(estimated_tokens)
        
        return self
    
    def release(self):
        """Release the semaphore after request completes."""
        self.semaphore.release()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False
    
    def handle_rate_limit_error(self, request_id: str, retry_after: Optional[float] = None):
        """
        Handle a 429 rate limit error.
        
        Args:
            request_id: Unique identifier for this request.
            retry_after: Seconds to wait before retrying (from API response).
        """
        if retry_after is None:
            # Exponential backoff based on retry count
            retry_count = self.retry_counts.get(request_id, 0)
            retry_after = min(
                self.config.retry_delay_base * (2 ** retry_count),
                self.config.retry_delay_max
            )
            self.retry_counts[request_id] = retry_count + 1
        
        logger.warning(
            f"Rate limit hit for request {request_id}. "
            f"Waiting {retry_after:.2f}s before retry."
        )
        
        time.sleep(retry_after)
    
    def reset_retry_count(self, request_id: str):
        """Reset retry count for a successful request."""
        if request_id in self.retry_counts:
            del self.retry_counts[request_id]
    
    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        with self.lock:
            current_usage = self._get_current_token_usage()
            available = self.config.tokens_per_minute - current_usage
            concurrent = self.config.max_concurrent_requests - self.semaphore._value
        
        return {
            'tokens_used': current_usage,
            'tokens_available': available,
            'tokens_limit': self.config.tokens_per_minute,
            'concurrent_requests': concurrent,
            'max_concurrent': self.config.max_concurrent_requests,
            'utilization_percent': (current_usage / self.config.tokens_per_minute) * 100
        }


# Global rate limiter instance
_global_rate_limiter: Optional[OpenAIRateLimiter] = None
_global_rate_limiter_lock = threading.Lock()

def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> OpenAIRateLimiter:
    """
    Get the global rate limiter instance.
    
    Args:
        config: Rate limit configuration. Only used on first call.
    
    Returns:
        Global OpenAIRateLimiter instance.
    """
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        with _global_rate_limiter_lock:
            if _global_rate_limiter is None:
                _global_rate_limiter = OpenAIRateLimiter(config)
    
    return _global_rate_limiter

