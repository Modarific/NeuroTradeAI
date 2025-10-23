"""
Unit tests for storage components.
"""
import pytest
import json
import os
from datetime import datetime, timezone
from app.core.storage_simple import SimpleStorageManager

class TestSimpleStorageManager:
    """Test the SimpleStorageManager class."""
    
    def test_init(self, temp_dir):
        """Test storage manager initialization."""
        db_path = os.path.join(temp_dir, "test.db")
        storage = SimpleStorageManager(temp_dir, db_path)
        
        assert storage.data_path == temp_dir
        assert storage.db_path == db_path
        assert os.path.exists(os.path.join(temp_dir, "ohlcv", "1m"))
        assert os.path.exists(os.path.join(temp_dir, "news"))
        assert os.path.exists(os.path.join(temp_dir, "filings"))
    
    def test_store_ohlcv(self, test_storage, sample_ohlcv_data):
        """Test storing OHLCV data."""
        result = test_storage.store_ohlcv(sample_ohlcv_data)
        assert result is True
        
        # Verify data was stored
        stored_data = test_storage.query_ohlcv("AAPL")
        assert len(stored_data) == 1
        assert stored_data[0]["symbol"] == "AAPL"
        assert stored_data[0]["close"] == 100.5
    
    def test_store_news(self, test_storage, sample_news_data):
        """Test storing news data."""
        result = test_storage.store_news(sample_news_data)
        assert result is True
        
        # Verify data was stored
        stored_data = test_storage.query_news()
        assert len(stored_data) == 1
        assert stored_data[0]["headline"] == "Apple reports strong quarterly earnings"
        assert stored_data[0]["tickers"] == ["AAPL"]
    
    def test_store_filings(self, test_storage, sample_filing_data):
        """Test storing filing data."""
        result = test_storage.store_filings(sample_filing_data)
        assert result is True
        
        # Verify data was stored
        stored_data = test_storage.query_filings("AAPL")
        assert len(stored_data) == 1
        assert stored_data[0]["symbol"] == "AAPL"
        assert stored_data[0]["filing_type"] == "10-K"
    
    def test_query_ohlcv_with_filters(self, test_storage, sample_ohlcv_data):
        """Test querying OHLCV data with filters."""
        # Store test data
        test_storage.store_ohlcv(sample_ohlcv_data)
        
        # Test symbol filter
        aapl_data = test_storage.query_ohlcv("AAPL")
        assert len(aapl_data) == 1
        assert aapl_data[0]["symbol"] == "AAPL"
        
        # Test non-existent symbol
        empty_data = test_storage.query_ohlcv("NONEXISTENT")
        assert len(empty_data) == 0
    
    def test_query_news_with_filters(self, test_storage, sample_news_data):
        """Test querying news data with filters."""
        # Store test data
        test_storage.store_news(sample_news_data)
        
        # Test ticker filter
        aapl_news = test_storage.query_news(ticker="AAPL")
        assert len(aapl_news) == 1
        assert aapl_news[0]["tickers"] == ["AAPL"]
        
        # Test non-existent ticker
        empty_news = test_storage.query_news(ticker="NONEXISTENT")
        assert len(empty_news) == 0
    
    def test_query_filings_with_filters(self, test_storage, sample_filing_data):
        """Test querying filing data with filters."""
        # Store test data
        test_storage.store_filings(sample_filing_data)
        
        # Test symbol filter
        aapl_filings = test_storage.query_filings(symbol="AAPL")
        assert len(aapl_filings) == 1
        assert aapl_filings[0]["symbol"] == "AAPL"
        
        # Test filing type filter
        ten_k_filings = test_storage.query_filings(filing_type="10-K")
        assert len(ten_k_filings) == 1
        assert ten_k_filings[0]["filing_type"] == "10-K"
        
        # Test non-existent filters
        empty_filings = test_storage.query_filings(symbol="NONEXISTENT")
        assert len(empty_filings) == 0
    
    def test_get_storage_stats(self, test_storage, sample_ohlcv_data, sample_news_data, sample_filing_data):
        """Test getting storage statistics."""
        # Store test data
        test_storage.store_ohlcv(sample_ohlcv_data)
        test_storage.store_news(sample_news_data)
        test_storage.store_filings(sample_filing_data)
        
        # Get stats
        stats = test_storage.get_storage_stats()
        
        assert "ohlcv_records" in stats
        assert "news_records" in stats
        assert "filings_records" in stats
        assert stats["ohlcv_records"] >= 2  # At least 2 OHLCV records
        assert stats["news_records"] >= 1  # At least 1 news record
        assert stats["filings_records"] >= 1  # At least 1 filing record
    
    def test_empty_data_handling(self, test_storage):
        """Test handling of empty data."""
        # Test empty OHLCV data
        result = test_storage.store_ohlcv([])
        assert result is True
        
        # Test empty news data
        result = test_storage.store_news([])
        assert result is True
        
        # Test empty filing data
        result = test_storage.store_filings([])
        assert result is True
    
    def test_invalid_data_handling(self, test_storage):
        """Test handling of invalid data."""
        # Test None data
        result = test_storage.store_ohlcv(None)
        assert result is True
        
        # Test malformed data
        malformed_data = [{"invalid": "data"}]
        result = test_storage.store_ohlcv(malformed_data)
        assert result is True  # Should not crash
