"""
Unit tests for rate limiter component.
"""
import pytest
import asyncio
import time
from app.core.rate_limiter import RateLimiter

class TestRateLimiter:
    """Test the RateLimiter class."""
    
    def test_init(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter()
        assert limiter.limiters == {}
    
    def test_add_rate_limiter(self):
        """Test adding a rate limiter."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("test_source", 10, 5)
        
        assert "test_source" in limiter.limiters
        assert limiter.limiters["test_source"].max_rate == 10
        assert limiter.limiters["test_source"].time_period == 5
    
    @pytest.mark.asyncio
    async def test_acquire_token_success(self):
        """Test successful token acquisition."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("test_source", 10, 60)  # 10 tokens per minute
        
        # Should be able to acquire tokens within limit
        for _ in range(10):
            result = await limiter.acquire_token("test_source")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_acquire_token_rate_limit(self):
        """Test rate limiting when limit is exceeded."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("test_source", 2, 1)  # 2 tokens per second
        
        # Should be able to acquire 2 tokens
        assert await limiter.acquire_token("test_source") is True
        assert await limiter.acquire_token("test_source") is True
        
        # Third token should be rate limited
        assert await limiter.acquire_token("test_source") is False
    
    @pytest.mark.asyncio
    async def test_acquire_token_unknown_source(self):
        """Test acquiring token for unknown source."""
        limiter = RateLimiter()
        
        # Should return False for unknown source
        result = await limiter.acquire_token("unknown_source")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_token_refill(self):
        """Test token refill over time."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("test_source", 1, 1)  # 1 token per second
        
        # Acquire the one token
        assert await limiter.acquire_token("test_source") is True
        assert await limiter.acquire_token("test_source") is False
        
        # Wait for refill
        await asyncio.sleep(1.1)
        
        # Should be able to acquire token again
        assert await limiter.acquire_token("test_source") is True
    
    def test_get_status(self):
        """Test getting rate limiter status."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("test_source", 10, 60)
        
        status = limiter.get_status()
        assert "test_source" in status
        assert status["test_source"]["max_rate"] == 10
        assert status["test_source"]["time_period"] == 60
    
    def test_get_status_unknown_source(self):
        """Test getting status for unknown source."""
        limiter = RateLimiter()
        
        status = limiter.get_status()
        assert status == {}
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test concurrent token acquisition."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("test_source", 5, 60)  # 5 tokens per minute
        
        # Create multiple concurrent requests
        tasks = [limiter.acquire_token("test_source") for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Should have exactly 5 successful acquisitions
        assert sum(results) == 5
    
    @pytest.mark.asyncio
    async def test_multiple_sources(self):
        """Test rate limiting for multiple sources."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("source1", 2, 60)
        limiter.add_rate_limiter("source2", 3, 60)
        
        # Should be able to acquire tokens from both sources
        assert await limiter.acquire_token("source1") is True
        assert await limiter.acquire_token("source1") is True
        assert await limiter.acquire_token("source2") is True
        assert await limiter.acquire_token("source2") is True
        assert await limiter.acquire_token("source2") is True
        
        # Should be rate limited for both sources
        assert await limiter.acquire_token("source1") is False
        assert await limiter.acquire_token("source2") is False
    
    @pytest.mark.asyncio
    async def test_burst_capacity(self):
        """Test burst capacity functionality."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("test_source", 10, 60, burst=20)  # 10/min with 20 burst
        
        # Should be able to acquire burst tokens immediately
        for _ in range(20):
            assert await limiter.acquire_token("test_source") is True
        
        # Should be rate limited after burst
        assert await limiter.acquire_token("test_source") is False
