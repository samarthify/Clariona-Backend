"""
Multi-model rate limiter for OpenAI API calls.
Tracks token usage per model and limits concurrent requests per model.
Supports: gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano
"""

import time
import threading
import logging
from typing import Optional, Dict, Tuple, Deque
from collections import deque
from dataclasses import dataclass

# Use centralized logging configuration
try:
    from src.config.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# Load model rate limits from ConfigManager
def _get_model_rate_limits():
    """Get model rate limits from ConfigManager with fallback defaults."""
    try:
        from config.config_manager import ConfigManager
        config = ConfigManager()
        tpm_capacities = config.get_dict("models.llm_models.tpm_capacities", {})
        # Default rate limits if not in config
        default_limits = {
            "gpt-5-mini": 500000,  # 500k TPM
            "gpt-5-nano": 200000,  # 200k TPM
            "gpt-4.1-mini": 200000,  # 200k TPM
            "gpt-4.1-nano": 200000,  # 200k TPM
        }
        # Merge config values with defaults
        return {**default_limits, **tpm_capacities}
    except Exception as e:
        logger.warning(f"Could not load ConfigManager for model rate limits, using defaults: {e}")
        return {
            "gpt-5-mini": 500000,  # 500k TPM
            "gpt-5-nano": 200000,  # 200k TPM
            "gpt-4.1-mini": 200000,  # 200k TPM
            "gpt-4.1-nano": 200000,  # 200k TPM
        }

# Module-level constant loaded from config
MODEL_RATE_LIMITS = _get_model_rate_limits()

@dataclass
class ModelRateLimitConfig:
    """Configuration for a specific model."""
    model_name: str
    tokens_per_minute: int
    max_concurrent_requests: int = 50  # Increased from 20 to 50 for better throughput
    estimated_tokens_per_request: int = 2600

class ModelRateLimiter:
    """Rate limiter for a specific model."""
    
    def __init__(self, config: ModelRateLimitConfig):
        self.config = config
        self.token_usage: Deque[Tuple[float, int]] = deque()  # (timestamp, tokens) tuples
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(self.config.max_concurrent_requests)
        self.retry_counts: Dict[str, int] = {}
        
        logger.info(
            f"ModelRateLimiter initialized for {config.model_name}: "
            f"TPM={config.tokens_per_minute}, "
            f"max_concurrent={config.max_concurrent_requests}"
        )
    
    def _cleanup_old_entries(self):
        """Remove token usage entries older than 1 minute."""
        current_time = time.time()
        cutoff_time = current_time - 60.0
        
        while self.token_usage and self.token_usage[0][0] < cutoff_time:
            self.token_usage.popleft()
    
    def _get_current_token_usage(self) -> int:
        """Get total token usage in the last minute."""
        with self.lock:
            self._cleanup_old_entries()
            return sum(tokens for _, tokens in self.token_usage)
    
    def _can_make_request(self, estimated_tokens: Optional[int] = None) -> bool:
        """Check if we can make a request without exceeding rate limits."""
        if estimated_tokens is None:
            estimated_tokens = self.config.estimated_tokens_per_request
        
        current_usage = self._get_current_token_usage()
        available_tokens = self.config.tokens_per_minute - current_usage
        
        return available_tokens >= estimated_tokens
    
    def _wait_for_token_availability(self, estimated_tokens: Optional[int] = None):
        """Wait until we have enough tokens available."""
        if estimated_tokens is None:
            estimated_tokens = self.config.estimated_tokens_per_request
        
        while not self._can_make_request(estimated_tokens):
            with self.lock:
                if self.token_usage:
                    oldest_time = self.token_usage[0][0]
                    wait_time = max(0.1, 60.0 - (time.time() - oldest_time))
                else:
                    wait_time = 0.1
            
            logger.debug(f"Rate limit ({self.config.model_name}): waiting {wait_time:.2f}s")
            time.sleep(min(wait_time, 1.0))
    
    def _record_token_usage(self, tokens: int):
        """Record token usage for rate limiting."""
        current_time = time.time()
        with self.lock:
            self.token_usage.append((current_time, tokens))
            self._cleanup_old_entries()
    
    def acquire(self, estimated_tokens: Optional[int] = None):
        """Acquire permission to make an API request."""
        self._wait_for_token_availability(estimated_tokens)
        self.semaphore.acquire()
        
        if estimated_tokens is None:
            estimated_tokens = self.config.estimated_tokens_per_request
        self._record_token_usage(estimated_tokens)
        
        return self
    
    def release(self):
        """Release the semaphore after request completes."""
        self.semaphore.release()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
    
    def handle_rate_limit_error(self, request_id: str, retry_after: Optional[float] = None):
        """Handle a 429 rate limit error."""
        if retry_after is None:
            retry_count = self.retry_counts.get(request_id, 0)
            retry_after = min(1.0 * (2 ** retry_count), 60.0)
            self.retry_counts[request_id] = retry_count + 1
        
        logger.warning(
            f"Rate limit hit for {self.config.model_name} request {request_id}. "
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
            'model': self.config.model_name,
            'tokens_used': current_usage,
            'tokens_available': available,
            'tokens_limit': self.config.tokens_per_minute,
            'concurrent_requests': concurrent,
            'max_concurrent': self.config.max_concurrent_requests,
            'utilization_percent': (current_usage / self.config.tokens_per_minute) * 100 if self.config.tokens_per_minute > 0 else 0
        }


class MultiModelRateLimiter:
    """
    Rate limiter that manages multiple models with separate rate limits.
    """
    
    def __init__(self):
        self.limiters: Dict[str, ModelRateLimiter] = {}
        self.lock = threading.Lock()
        
        # Initialize rate limiters for all models
        for model_name, tpm_limit in MODEL_RATE_LIMITS.items():
            config = ModelRateLimitConfig(
                model_name=model_name,
                tokens_per_minute=tpm_limit,
                max_concurrent_requests=50,  # Increased from 20 to 50 for better throughput
                estimated_tokens_per_request=2600
            )
            self.limiters[model_name] = ModelRateLimiter(config)
        
        logger.info(f"MultiModelRateLimiter initialized with {len(self.limiters)} models")
    
    def get_limiter(self, model_name: str) -> Optional[ModelRateLimiter]:
        """Get rate limiter for a specific model."""
        return self.limiters.get(model_name)
    
    def acquire(self, model_name: str, estimated_tokens: Optional[int] = None):
        """
        Acquire permission to make an API request for a specific model.
        
        Args:
            model_name: Name of the model (e.g., 'gpt-5-mini')
            estimated_tokens: Estimated tokens for this request.
        
        Returns:
            Context manager that releases when done.
        """
        limiter = self.get_limiter(model_name)
        if limiter is None:
            logger.warning(f"No rate limiter found for model {model_name}, using default")
            # Fallback to gpt-5-nano limiter
            limiter = self.limiters.get("gpt-5-nano", list(self.limiters.values())[0])
        
        return limiter.acquire(estimated_tokens)
    
    def handle_rate_limit_error(self, model_name: str, request_id: str, retry_after: Optional[float] = None):
        """Handle a 429 rate limit error for a specific model."""
        limiter = self.get_limiter(model_name)
        if limiter:
            limiter.handle_rate_limit_error(request_id, retry_after)
    
    def reset_retry_count(self, model_name: str, request_id: str):
        """Reset retry count for a successful request."""
        limiter = self.get_limiter(model_name)
        if limiter:
            limiter.reset_retry_count(request_id)
    
    def get_all_stats(self) -> Dict[str, dict]:
        """Get statistics for all models."""
        return {model: limiter.get_stats() for model, limiter in self.limiters.items()}


# Global multi-model rate limiter instance
_global_multi_model_limiter: Optional[MultiModelRateLimiter] = None
_global_multi_model_limiter_lock = threading.Lock()

def get_multi_model_rate_limiter() -> MultiModelRateLimiter:
    """Get the global multi-model rate limiter instance."""
    global _global_multi_model_limiter
    
    if _global_multi_model_limiter is None:
        with _global_multi_model_limiter_lock:
            if _global_multi_model_limiter is None:
                _global_multi_model_limiter = MultiModelRateLimiter()
    
    return _global_multi_model_limiter

