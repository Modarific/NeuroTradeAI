"""
Integration tests for end-to-end workflows.
"""
import pytest
import asyncio
import json
import os
from unittest.mock import patch, AsyncMock
from app.core.storage_simple import SimpleStorageManager
from app.core.rate_limiter import RateLimiter
from app.adapters.finnhub import FinnhubAdapter
from app.adapters.news import NewsAdapter
from app.adapters.edgar import EdgarAdapter

class TestEndToEndWorkflow:
    """Test complete data flow from source to storage."""
    
    @pytest.mark.asyncio
    async def test_finnhub_data_flow(self, temp_dir, sample_ohlcv_data):
        """Test complete Finnhub data flow."""
        # Setup
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        rate_limiter = RateLimiter()
        rate_limiter.add_rate_limiter("finnhub", 60, 60)
        
        config = {
            "name": "finnhub",
            "api_key": "test_key",
            "storage": storage,
            "rate_limiter": rate_limiter,
            "watchlist": ["AAPL", "MSFT"]
        }
        
        adapter = FinnhubAdapter("finnhub", config)
        
        # Mock successful API responses
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "c": 100.5,
                "h": 101.0,
                "l": 99.0,
                "o": 100.0,
                "v": 1000
            }
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            # Start adapter
            result = await adapter.start()
            assert result is True
            
            # Simulate data processing
            raw_data = {
                "s": "AAPL",
                "c": 100.5,
                "h": 101.0,
                "l": 99.0,
                "o": 100.0,
                "v": 1000,
                "t": 1640995200000
            }
            
            normalized = adapter.normalize(raw_data)
            assert normalized is not None
            
            # Store data
            storage.store_ohlcv([normalized])
            
            # Verify data was stored
            stored_data = storage.query_ohlcv("AAPL")
            assert len(stored_data) == 1
            assert stored_data[0]["symbol"] == "AAPL"
            assert stored_data[0]["close"] == 100.5
            
            await adapter.stop()
    
    @pytest.mark.asyncio
    async def test_news_data_flow(self, temp_dir, sample_news_data):
        """Test complete news data flow."""
        # Setup
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        rate_limiter = RateLimiter()
        rate_limiter.add_rate_limiter("news", 60, 60)
        
        config = {
            "name": "news",
            "api_key": "test_key",
            "storage": storage,
            "rate_limiter": rate_limiter,
            "watchlist": ["AAPL", "MSFT"]
        }
        
        adapter = NewsAdapter("news", config)
        
        # Mock successful API responses
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "result": [
                    {
                        "id": "news_1",
                        "datetime": 1640995200000,
                        "headline": "Test news",
                        "url": "https://example.com",
                        "summary": "Test summary"
                    }
                ]
            }
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            # Start adapter
            result = await adapter.start()
            assert result is True
            
            # Simulate data processing
            raw_data = {
                "id": "news_1",
                "datetime": 1640995200000,
                "headline": "Test news",
                "url": "https://example.com",
                "summary": "Test summary"
            }
            
            normalized = adapter.normalize(raw_data)
            assert normalized is not None
            
            # Store data
            storage.store_news([normalized])
            
            # Verify data was stored
            stored_data = storage.query_news()
            assert len(stored_data) == 1
            assert stored_data[0]["headline"] == "Test news"
            
            await adapter.stop()
    
    @pytest.mark.asyncio
    async def test_edgar_data_flow(self, temp_dir, sample_filing_data):
        """Test complete EDGAR data flow."""
        # Setup
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        rate_limiter = RateLimiter()
        rate_limiter.add_rate_limiter("edgar", 10, 60)
        
        config = {
            "name": "edgar",
            "storage": storage,
            "rate_limiter": rate_limiter,
            "watchlist": ["AAPL", "MSFT"]
        }
        
        adapter = EdgarAdapter("edgar", config)
        
        # Mock successful API responses
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "facts": {
                    "dei": {
                        "EntityRegistrantName": "Apple Inc.",
                        "10-K": {
                            "units": {
                                "USD": [
                                    {
                                        "end": "2025-09-30",
                                        "val": 1000000
                                    }
                                ]
                            }
                        }
                    }
                }
            }
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            # Start adapter
            result = await adapter.start()
            assert result is True
            
            # Simulate data processing
            raw_data = {
                "symbol": "AAPL",
                "filing_type": "10-K",
                "filing_date": "2025-10-20T00:00:00Z",
                "entity_name": "Apple Inc."
            }
            
            normalized = adapter.normalize(raw_data)
            assert normalized is not None
            
            # Store data
            storage.store_filings([normalized])
            
            # Verify data was stored
            stored_data = storage.query_filings("AAPL")
            assert len(stored_data) == 1
            assert stored_data[0]["symbol"] == "AAPL"
            assert stored_data[0]["filing_type"] == "10-K"
            
            await adapter.stop()
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, temp_dir):
        """Test rate limiting in integration scenario."""
        # Setup
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        rate_limiter = RateLimiter()
        rate_limiter.add_rate_limiter("test_source", 2, 1)  # 2 requests per second
        
        # Test rate limiting
        assert await rate_limiter.acquire_token("test_source") is True
        assert await rate_limiter.acquire_token("test_source") is True
        assert await rate_limiter.acquire_token("test_source") is False
        
        # Wait for refill
        await asyncio.sleep(1.1)
        assert await rate_limiter.acquire_token("test_source") is True
    
    @pytest.mark.asyncio
    async def test_concurrent_adapters(self, temp_dir):
        """Test multiple adapters running concurrently."""
        # Setup
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        rate_limiter = RateLimiter()
        rate_limiter.add_rate_limiter("finnhub", 60, 60)
        rate_limiter.add_rate_limiter("news", 60, 60)
        
        # Create adapters
        finnhub_config = {
            "name": "finnhub",
            "api_key": "test_key",
            "storage": storage,
            "rate_limiter": rate_limiter,
            "watchlist": ["AAPL"]
        }
        
        news_config = {
            "name": "news",
            "api_key": "test_key",
            "storage": storage,
            "rate_limiter": rate_limiter,
            "watchlist": ["AAPL"]
        }
        
        finnhub_adapter = FinnhubAdapter("finnhub", finnhub_config)
        news_adapter = NewsAdapter("news", news_config)
        
        # Mock sessions
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"test": "data"}
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            # Start both adapters concurrently
            tasks = [
                finnhub_adapter.start(),
                news_adapter.start()
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Both should start successfully
            assert all(results)
            
            # Stop adapters
            await asyncio.gather(
                finnhub_adapter.stop(),
                news_adapter.stop()
            )
    
    def test_data_persistence(self, temp_dir, sample_ohlcv_data, sample_news_data, sample_filing_data):
        """Test data persistence across restarts."""
        # Setup storage
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        
        # Store data
        storage.store_ohlcv(sample_ohlcv_data)
        storage.store_news(sample_news_data)
        storage.store_filings(sample_filing_data)
        
        # Create new storage instance (simulating restart)
        new_storage = SimpleStorageManager(temp_dir, db_path)
        
        # Verify data persists
        ohlcv_data = new_storage.query_ohlcv("AAPL")
        assert len(ohlcv_data) == 1
        
        news_data = new_storage.query_news()
        assert len(news_data) == 1
        
        filing_data = new_storage.query_filings("AAPL")
        assert len(filing_data) == 1
    
    def test_error_handling_integration(self, temp_dir):
        """Test error handling in integration scenarios."""
        # Setup
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        
        # Test with invalid data
        invalid_data = [{"invalid": "data"}]
        
        # Should not crash
        result = storage.store_ohlcv(invalid_data)
        assert result is True
        
        # Test with None data
        result = storage.store_ohlcv(None)
        assert result is True
        
        # Test with empty data
        result = storage.store_ohlcv([])
        assert result is True
