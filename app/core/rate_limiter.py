"""
Rate limiter implementation using token bucket algorithm.
Provides async-safe rate limiting for API requests.
"""
import asyncio
import time
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class TokenBucket:
    """Token bucket rate limiter implementation."""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False if not enough tokens
        """
        async with self._lock:
            now = time.time()
            time_passed = now - self.last_refill
            
            # Add tokens based on time passed
            self.tokens = min(self.capacity, self.tokens + time_passed * self.refill_rate)
            self.last_refill = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False
    
    async def wait_for_tokens(self, tokens: int = 1) -> float:
        """
        Wait until enough tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Time waited in seconds
        """
        start_time = time.time()
        
        while not await self.acquire(tokens):
            # Calculate how long to wait
            wait_time = (tokens - self.tokens) / self.refill_rate
            wait_time = max(0.1, min(wait_time, 60))  # Wait between 0.1s and 60s
            
            logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        return time.time() - start_time
    
    def get_status(self) -> Dict[str, float]:
        """Get current bucket status."""
        return {
            "tokens": self.tokens,
            "capacity": self.capacity,
            "refill_rate": self.refill_rate
        }


class RateLimiter:
    """Multi-source rate limiter manager."""
    
    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def add_source(self, source: str, requests_per_minute: int, burst_capacity: Optional[int] = None):
        """
        Add rate limiting for a data source.
        
        Args:
            source: Name of the data source
            requests_per_minute: Maximum requests per minute
            burst_capacity: Maximum burst capacity (defaults to requests_per_minute)
        """
        if burst_capacity is None:
            burst_capacity = requests_per_minute
        
        refill_rate = requests_per_minute / 60.0  # tokens per second
        self._buckets[source] = TokenBucket(burst_capacity, refill_rate)
        self._locks[source] = asyncio.Lock()
        
        logger.info(f"Added rate limiter for {source}: {requests_per_minute}/min, burst={burst_capacity}")
    
    async def acquire(self, source: str, tokens: int = 1) -> bool:
        """
        Try to acquire tokens for a source.
        
        Args:
            source: Name of the data source
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False if rate limited
        """
        if source not in self._buckets:
            logger.warning(f"No rate limiter configured for source: {source}")
            return True
        
        return await self._buckets[source].acquire(tokens)
    
    async def wait_for_tokens(self, source: str, tokens: int = 1) -> float:
        """
        Wait until tokens are available for a source.
        
        Args:
            source: Name of the data source
            tokens: Number of tokens needed
            
        Returns:
            Time waited in seconds
        """
        if source not in self._buckets:
            logger.warning(f"No rate limiter configured for source: {source}")
            return 0.0
        
        return await self._buckets[source].wait_for_tokens(tokens)
    
    async def rate_limited_request(self, source: str, request_func, *args, **kwargs):
        """
        Execute a request with rate limiting.
        
        Args:
            source: Name of the data source
            request_func: Async function to execute
            *args, **kwargs: Arguments for request_func
            
        Returns:
            Result of request_func or None if rate limited
        """
        # Wait for tokens
        await self.wait_for_tokens(source)
        
        try:
            return await request_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Request failed for {source}: {e}")
            return None
    
    def get_status(self, source: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        """
        Get rate limiter status.
        
        Args:
            source: Specific source to check, or None for all sources
            
        Returns:
            Status information for rate limiters
        """
        if source:
            if source in self._buckets:
                return {source: self._buckets[source].get_status()}
            else:
                return {}
        else:
            return {name: bucket.get_status() for name, bucket in self._buckets.items()}
    
    def remove_source(self, source: str):
        """Remove rate limiting for a source."""
        if source in self._buckets:
            del self._buckets[source]
            del self._locks[source]
            logger.info(f"Removed rate limiter for {source}")


# Global rate limiter instance
rate_limiter = RateLimiter()


def setup_rate_limiters(config: Dict[str, int]):
    """Setup rate limiters from configuration."""
    for source, requests_per_minute in config.items():
        rate_limiter.add_source(source, requests_per_minute)
    
    logger.info(f"Configured rate limiters for {len(config)} sources")


async def with_rate_limit(source: str, request_func, *args, **kwargs):
    """
    Decorator function to apply rate limiting to requests.
    
    Args:
        source: Name of the data source
        request_func: Async function to execute
        *args, **kwargs: Arguments for request_func
        
    Returns:
        Result of request_func or None if rate limited
    """
    return await rate_limiter.rate_limited_request(source, request_func, *args, **kwargs)
