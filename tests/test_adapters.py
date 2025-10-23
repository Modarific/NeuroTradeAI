"""
Unit tests for adapter components.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from app.adapters.finnhub import FinnhubAdapter
from app.adapters.news import NewsAdapter
from app.adapters.edgar import EdgarAdapter

class TestFinnhubAdapter:
    """Test the FinnhubAdapter class."""
    
    @pytest.fixture
    def finnhub_config(self, mock_vault, test_storage, test_rate_limiter):
        """Create Finnhub adapter configuration."""
        return {
            "name": "finnhub",
            "api_key": "test_api_key",
            "storage": test_storage,
            "rate_limiter": test_rate_limiter,
            "watchlist": ["AAPL", "MSFT"]
        }
    
    @pytest.mark.asyncio
    async def test_init(self, finnhub_config):
        """Test Finnhub adapter initialization."""
        adapter = FinnhubAdapter("finnhub", finnhub_config)
        
        assert adapter.name == "finnhub"
        assert adapter.watchlist == ["AAPL", "MSFT"]
        assert adapter.storage is not None
        assert adapter.rate_limiter is not None
    
    @pytest.mark.asyncio
    async def test_start_success(self, finnhub_config):
        """Test successful adapter start."""
        adapter = FinnhubAdapter("finnhub", finnhub_config)
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            result = await adapter.start()
            
            assert result is True
            assert adapter.session is not None
    
    @pytest.mark.asyncio
    async def test_start_failure(self, finnhub_config):
        """Test adapter start failure."""
        adapter = FinnhubAdapter("finnhub", finnhub_config)
        
        with patch('aiohttp.ClientSession', side_effect=Exception("Connection failed")):
            result = await adapter.start()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_stop(self, finnhub_config):
        """Test adapter stop."""
        adapter = FinnhubAdapter("finnhub", finnhub_config)
        adapter.session = AsyncMock()
        
        await adapter.stop()
        
        adapter.session.close.assert_called_once()
    
    def test_normalize_ohlcv(self, finnhub_config):
        """Test OHLCV data normalization."""
        adapter = FinnhubAdapter("finnhub", finnhub_config)
        
        raw_data = {
            "s": "AAPL",
            "p": 100.0,
            "t": 1640995200000,
            "v": 1000
        }
        
        normalized = adapter.normalize(raw_data)
        
        assert normalized is not None
        assert normalized["symbol"] == "AAPL"
        assert normalized["close"] == 100.0
        assert normalized["source"] == "finnhub"
    
    def test_normalize_invalid_data(self, finnhub_config):
        """Test normalization of invalid data."""
        adapter = FinnhubAdapter("finnhub", finnhub_config)
        
        # Test with missing required fields
        raw_data = {"invalid": "data"}
        normalized = adapter.normalize(raw_data)
        
        assert normalized is None
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, finnhub_config):
        """Test successful health check."""
        adapter = FinnhubAdapter("finnhub", finnhub_config)
        adapter.session = AsyncMock()
        
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        adapter.session.get.return_value.__aenter__.return_value = mock_response
        
        result = await adapter.health_check()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, finnhub_config):
        """Test health check failure."""
        adapter = FinnhubAdapter("finnhub", finnhub_config)
        adapter.session = AsyncMock()
        
        # Mock failed response
        mock_response = AsyncMock()
        mock_response.status = 500
        adapter.session.get.return_value.__aenter__.return_value = mock_response
        
        result = await adapter.health_check()
        
        assert result is False

class TestNewsAdapter:
    """Test the NewsAdapter class."""
    
    @pytest.fixture
    def news_config(self, mock_vault, test_storage, test_rate_limiter):
        """Create news adapter configuration."""
        return {
            "name": "news",
            "api_key": "test_api_key",
            "storage": test_storage,
            "rate_limiter": test_rate_limiter,
            "watchlist": ["AAPL", "MSFT"]
        }
    
    @pytest.mark.asyncio
    async def test_init(self, news_config):
        """Test news adapter initialization."""
        adapter = NewsAdapter("news", news_config)
        
        assert adapter.name == "news"
        assert adapter.watchlist == ["AAPL", "MSFT"]
        assert adapter.storage is not None
        assert adapter.rate_limiter is not None
    
    @pytest.mark.asyncio
    async def test_start_success(self, news_config):
        """Test successful news adapter start."""
        adapter = NewsAdapter("news", news_config)
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            result = await adapter.start()
            
            assert result is True
            assert adapter.session is not None
    
    def test_normalize_news(self, news_config):
        """Test news data normalization."""
        adapter = NewsAdapter("news", news_config)
        
        raw_data = {
            "id": "news_1",
            "datetime": 1640995200000,
            "headline": "Test news",
            "url": "https://example.com",
            "summary": "Test summary"
        }
        
        normalized = adapter.normalize(raw_data)
        
        assert normalized is not None
        assert normalized["headline"] == "Test news"
        assert normalized["source"] == "news"
        assert "sentiment_score" in normalized

class TestEdgarAdapter:
    """Test the EdgarAdapter class."""
    
    @pytest.fixture
    def edgar_config(self, test_storage, test_rate_limiter):
        """Create EDGAR adapter configuration."""
        return {
            "name": "edgar",
            "storage": test_storage,
            "rate_limiter": test_rate_limiter,
            "watchlist": ["AAPL", "MSFT"]
        }
    
    @pytest.mark.asyncio
    async def test_init(self, edgar_config):
        """Test EDGAR adapter initialization."""
        adapter = EdgarAdapter("edgar", edgar_config)
        
        assert adapter.name == "edgar"
        assert adapter.watchlist == ["AAPL", "MSFT"]
        assert adapter.storage is not None
        assert adapter.rate_limiter is not None
    
    @pytest.mark.asyncio
    async def test_start_success(self, edgar_config):
        """Test successful EDGAR adapter start."""
        adapter = EdgarAdapter("edgar", edgar_config)
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            result = await adapter.start()
            
            assert result is True
            assert adapter.session is not None
    
    def test_normalize_filing(self, edgar_config):
        """Test filing data normalization."""
        adapter = EdgarAdapter("edgar", edgar_config)
        
        raw_data = {
            "symbol": "AAPL",
            "filing_type": "10-K",
            "filing_date": "2025-10-20T00:00:00Z",
            "entity_name": "Apple Inc."
        }
        
        normalized = adapter.normalize(raw_data)
        
        assert normalized is not None
        assert normalized["symbol"] == "AAPL"
        assert normalized["filing_type"] == "10-K"
        assert normalized["source"] == "edgar"
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, edgar_config):
        """Test successful EDGAR health check."""
        adapter = EdgarAdapter("edgar", edgar_config)
        adapter.session = AsyncMock()
        
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        adapter.session.get.return_value.__aenter__.return_value = mock_response
        
        result = await adapter.health_check()
        
        assert result is True
