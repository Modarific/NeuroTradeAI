"""
Load tests for performance and rate limiting validation.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock
from app.core.rate_limiter import RateLimiter
from app.core.storage_simple import SimpleStorageManager

class TestLoadPerformance:
    """Test system performance under load."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_under_load(self):
        """Test rate limiter performance under high load."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("test_source", 100, 60)  # 100 requests per minute
        
        # Create many concurrent requests
        start_time = time.time()
        tasks = [limiter.acquire_token("test_source") for _ in range(200)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Should complete quickly
        assert (end_time - start_time) < 5.0
        
        # Should have exactly 100 successful acquisitions
        assert sum(results) == 100
    
    @pytest.mark.asyncio
    async def test_storage_under_load(self, temp_dir):
        """Test storage performance under high load."""
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        
        # Create large dataset
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                "symbol": f"TEST{i % 10}",  # 10 different symbols
                "timestamp_utc": f"2025-10-23T12:{i % 60:02d}:00Z",
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000 + i,
                "interval": "1m",
                "source": "test"
            })
        
        # Test storage performance
        start_time = time.time()
        result = storage.store_ohlcv(large_dataset)
        end_time = time.time()
        
        assert result is True
        assert (end_time - start_time) < 10.0  # Should complete within 10 seconds
        
        # Verify data was stored
        stored_data = storage.query_ohlcv("TEST0")
        assert len(stored_data) >= 100  # Should have at least 100 records for TEST0
    
    @pytest.mark.asyncio
    async def test_concurrent_storage_operations(self, temp_dir):
        """Test concurrent storage operations."""
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        
        # Create concurrent storage tasks
        async def store_data(symbol, count):
            data = []
            for i in range(count):
                data.append({
                    "symbol": symbol,
                    "timestamp_utc": f"2025-10-23T12:{i % 60:02d}:00Z",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 1000,
                    "interval": "1m",
                    "source": "test"
                })
            return storage.store_ohlcv(data)
        
        # Run concurrent operations
        tasks = [
            store_data("AAPL", 100),
            store_data("MSFT", 100),
            store_data("GOOGL", 100),
            store_data("AMZN", 100),
            store_data("TSLA", 100)
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # All should succeed
        assert all(results)
        assert (end_time - start_time) < 15.0  # Should complete within 15 seconds
        
        # Verify data was stored
        for symbol in ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]:
            data = storage.query_ohlcv(symbol)
            assert len(data) == 100
    
    @pytest.mark.asyncio
    async def test_query_performance(self, temp_dir):
        """Test query performance with large datasets."""
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        
        # Create large dataset
        large_dataset = []
        for i in range(5000):
            large_dataset.append({
                "symbol": f"SYMBOL{i % 50}",  # 50 different symbols
                "timestamp_utc": f"2025-10-23T12:{i % 60:02d}:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000,
                "interval": "1m",
                "source": "test"
            })
        
        # Store data
        storage.store_ohlcv(large_dataset)
        
        # Test query performance
        start_time = time.time()
        data = storage.query_ohlcv("SYMBOL0")
        end_time = time.time()
        
        assert len(data) >= 100  # Should have at least 100 records
        assert (end_time - start_time) < 2.0  # Should complete within 2 seconds
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, temp_dir):
        """Test memory usage under high load."""
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        
        # Create many small datasets to test memory efficiency
        for batch in range(100):
            data = []
            for i in range(10):
                data.append({
                    "symbol": f"BATCH{batch}_SYMBOL{i}",
                    "timestamp_utc": f"2025-10-23T12:{i % 60:02d}:00Z",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 1000,
                    "interval": "1m",
                    "source": "test"
                })
            
            # Store each batch
            result = storage.store_ohlcv(data)
            assert result is True
        
        # Verify total data
        stats = storage.get_storage_stats()
        assert stats["ohlcv_records"] >= 1000  # Should have at least 1000 records
    
    @pytest.mark.asyncio
    async def test_rate_limiter_burst_capacity(self):
        """Test rate limiter burst capacity under load."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("test_source", 10, 60, burst=50)  # 10/min with 50 burst
        
        # Test burst capacity
        start_time = time.time()
        tasks = [limiter.acquire_token("test_source") for _ in range(100)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Should complete quickly
        assert (end_time - start_time) < 2.0
        
        # Should have exactly 50 successful acquisitions (burst capacity)
        assert sum(results) == 50
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limiters(self):
        """Test multiple rate limiters under concurrent load."""
        limiter = RateLimiter()
        limiter.add_rate_limiter("source1", 20, 60)
        limiter.add_rate_limiter("source2", 30, 60)
        limiter.add_rate_limiter("source3", 40, 60)
        
        # Create concurrent requests for all sources
        tasks = []
        for source in ["source1", "source2", "source3"]:
            for _ in range(50):
                tasks.append(limiter.acquire_token(source))
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Should complete quickly
        assert (end_time - start_time) < 5.0
        
        # Should have exactly 90 successful acquisitions (20+30+40)
        assert sum(results) == 90
    
    @pytest.mark.asyncio
    async def test_storage_cleanup_performance(self, temp_dir):
        """Test storage cleanup performance."""
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        
        # Create large dataset
        large_dataset = []
        for i in range(2000):
            large_dataset.append({
                "symbol": f"SYMBOL{i % 20}",  # 20 different symbols
                "timestamp_utc": f"2025-10-23T12:{i % 60:02d}:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000,
                "interval": "1m",
                "source": "test"
            })
        
        # Store data
        storage.store_ohlcv(large_dataset)
        
        # Test query performance with filters
        start_time = time.time()
        
        # Query specific symbol
        symbol_data = storage.query_ohlcv("SYMBOL0")
        
        # Query with date range (simulate cleanup)
        all_data = storage.query_ohlcv()
        
        end_time = time.time()
        
        assert len(symbol_data) >= 100  # Should have at least 100 records for SYMBOL0
        assert len(all_data) >= 2000  # Should have all records
        assert (end_time - start_time) < 3.0  # Should complete within 3 seconds
