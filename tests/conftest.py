"""
Pytest configuration and shared fixtures for the test suite.
"""
import pytest
import asyncio
import tempfile
import os
import shutil
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

# Add the app directory to the path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from app.core.storage_simple import SimpleStorageManager
from app.core.rate_limiter import RateLimiter
from app.security.vault import CredentialVault
from app.adapters.finnhub import FinnhubAdapter
from app.adapters.news import NewsAdapter
from app.adapters.edgar import EdgarAdapter

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    try:
        shutil.rmtree(temp_path)
    except PermissionError:
        # On Windows, sometimes files are still in use
        import time
        time.sleep(0.1)
        try:
            shutil.rmtree(temp_path)
        except PermissionError:
            # If still failing, just leave it for OS cleanup
            pass

@pytest.fixture
def test_storage(temp_dir):
    """Create a test storage manager."""
    db_path = os.path.join(temp_dir, "test.db")
    return SimpleStorageManager(temp_dir, db_path)

@pytest.fixture
def test_rate_limiter():
    """Create a test rate limiter."""
    return RateLimiter()

@pytest.fixture
def mock_vault():
    """Create a mock vault for testing."""
    vault = Mock(spec=CredentialVault)
    vault.is_unlocked.return_value = True
    vault.get_key.return_value = "test_api_key"
    vault.get_api_key.return_value = "test_api_key"
    return vault

@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = AsyncMock()
    session.get.return_value.__aenter__.return_value.status = 200
    session.get.return_value.__aenter__.return_value.json.return_value = {"test": "data"}
    return session

@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing."""
    return [
        {
            "symbol": "AAPL",
            "timestamp_utc": "2025-10-23T12:00:00Z",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
            "interval": "1m",
            "source": "finnhub"
        },
        {
            "symbol": "MSFT",
            "timestamp_utc": "2025-10-23T12:00:00Z",
            "open": 200.0,
            "high": 201.0,
            "low": 199.0,
            "close": 200.5,
            "volume": 2000,
            "interval": "1m",
            "source": "finnhub"
        }
    ]

@pytest.fixture
def sample_news_data():
    """Sample news data for testing."""
    return [
        {
            "id": "news_1",
            "timestamp_utc": "2025-10-23T12:00:00Z",
            "source": "finnhub",
            "headline": "Apple reports strong quarterly earnings",
            "url": "https://example.com/news1",
            "tickers": ["AAPL"],
            "sentiment_score": 0.8,
            "raw_payload": {"test": "data"}
        }
    ]

@pytest.fixture
def sample_filing_data():
    """Sample filing data for testing."""
    return [
        {
            "symbol": "AAPL",
            "filing_type": "10-K",
            "filing_date": "2025-10-20T00:00:00Z",
            "entity_name": "Apple Inc.",
            "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000123/aapl-20250930.htm",
            "summary": "Annual report for fiscal year ended September 30, 2025",
            "source": "edgar",
            "timestamp_utc": "2025-10-20T12:00:00Z"
        }
    ]

@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    websocket = AsyncMock()
    websocket.recv.return_value = '{"type": "test", "data": "test"}'
    return websocket
