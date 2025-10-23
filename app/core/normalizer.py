"""
Data normalizer for converting raw API responses to canonical schemas.
Ensures consistent data format across all data sources.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class DataNormalizer:
    """Normalizes data from various sources to canonical schemas."""
    
    def __init__(self):
        self.schemas = {
            "ohlcv": [
                "symbol", "exchange", "timestamp_utc", "interval", 
                "open", "high", "low", "close", "volume", "source", "recv_ts"
            ],
            "news": [
                "id", "timestamp_utc", "source", "headline", "url", 
                "tickers", "sentiment_score", "raw_payload"
            ],
            "filings": [
                "symbol", "filing_type", "filing_date", "url", "summary", "raw_xbrl"
            ]
        }
    
    def normalize_ohlcv(self, raw_data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """
        Normalize OHLCV data to canonical schema.
        
        Args:
            raw_data: Raw data from API
            source: Data source name
            
        Returns:
            Normalized OHLCV record
        """
        try:
            # Extract common fields
            symbol = self._extract_symbol(raw_data)
            timestamp = self._extract_timestamp(raw_data)
            interval = self._extract_interval(raw_data)
            
            # Extract OHLCV values
            ohlcv = self._extract_ohlcv_values(raw_data)
            
            # Create normalized record
            normalized = {
                "symbol": symbol,
                "exchange": self._extract_exchange(raw_data),
                "timestamp_utc": timestamp,
                "interval": interval,
                "open": ohlcv.get("open"),
                "high": ohlcv.get("high"),
                "low": ohlcv.get("low"),
                "close": ohlcv.get("close"),
                "volume": ohlcv.get("volume"),
                "source": source,
                "recv_ts": datetime.now(timezone.utc).isoformat()
            }
            
            # Validate required fields
            if not all(normalized.get(field) is not None for field in ["symbol", "timestamp_utc"]):
                logger.warning(f"Missing required fields in OHLCV data: {raw_data}")
                return None
            
            return normalized
            
        except Exception as e:
            logger.error(f"Failed to normalize OHLCV data: {e}")
            return None
    
    def normalize_news(self, raw_data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """
        Normalize news data to canonical schema.
        
        Args:
            raw_data: Raw data from API
            source: Data source name
            
        Returns:
            Normalized news record
        """
        try:
            # Extract common fields
            news_id = self._extract_news_id(raw_data)
            timestamp = self._extract_timestamp(raw_data)
            headline = self._extract_headline(raw_data)
            url = self._extract_url(raw_data)
            tickers = self._extract_tickers(raw_data)
            sentiment = self._extract_sentiment(raw_data)
            
            # Create normalized record
            normalized = {
                "id": news_id,
                "timestamp_utc": timestamp,
                "source": source,
                "headline": headline,
                "url": url,
                "tickers": tickers,
                "sentiment_score": sentiment,
                "raw_payload": raw_data
            }
            
            # Validate required fields
            if not all(normalized.get(field) is not None for field in ["id", "timestamp_utc", "headline"]):
                logger.warning(f"Missing required fields in news data: {raw_data}")
                return None
            
            return normalized
            
        except Exception as e:
            logger.error(f"Failed to normalize news data: {e}")
            return None
    
    def normalize_filing(self, raw_data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """
        Normalize filing data to canonical schema.
        
        Args:
            raw_data: Raw data from API
            source: Data source name
            
        Returns:
            Normalized filing record
        """
        try:
            # Extract common fields
            symbol = self._extract_symbol(raw_data)
            filing_type = self._extract_filing_type(raw_data)
            filing_date = self._extract_filing_date(raw_data)
            url = self._extract_url(raw_data)
            summary = self._extract_summary(raw_data)
            
            # Create normalized record
            normalized = {
                "symbol": symbol,
                "filing_type": filing_type,
                "filing_date": filing_date,
                "url": url,
                "summary": summary,
                "raw_xbrl": raw_data
            }
            
            # Validate required fields
            if not all(normalized.get(field) is not None for field in ["symbol", "filing_type", "filing_date"]):
                logger.warning(f"Missing required fields in filing data: {raw_data}")
                return None
            
            return normalized
            
        except Exception as e:
            logger.error(f"Failed to normalize filing data: {e}")
            return None
    
    def _extract_symbol(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract symbol from raw data."""
        return (data.get("symbol") or 
                data.get("ticker") or 
                data.get("s") or 
                data.get("t"))
    
    def _extract_timestamp(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract and normalize timestamp."""
        timestamp = (data.get("timestamp") or 
                    data.get("time") or 
                    data.get("t") or 
                    data.get("datetime"))
        
        if timestamp:
            try:
                # Try to parse various timestamp formats
                if isinstance(timestamp, (int, float)):
                    # Unix timestamp
                    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                elif isinstance(timestamp, str):
                    # ISO format or other string format
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    return None
                
                return dt.isoformat()
            except (ValueError, TypeError):
                logger.warning(f"Could not parse timestamp: {timestamp}")
                return None
        
        return None
    
    def _extract_interval(self, data: Dict[str, Any]) -> str:
        """Extract data interval."""
        return data.get("interval", "1m")
    
    def _extract_exchange(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract exchange information."""
        return (data.get("exchange") or 
                data.get("market") or 
                data.get("mic"))
    
    def _extract_ohlcv_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract OHLCV values from raw data."""
        return {
            "open": self._safe_float(data.get("open") or data.get("o")),
            "high": self._safe_float(data.get("high") or data.get("h")),
            "low": self._safe_float(data.get("low") or data.get("l")),
            "close": self._safe_float(data.get("close") or data.get("c")),
            "volume": self._safe_int(data.get("volume") or data.get("v"))
        }
    
    def _extract_news_id(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract news ID."""
        return (data.get("id") or 
                data.get("news_id") or 
                data.get("uuid"))
    
    def _extract_headline(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract headline."""
        return (data.get("headline") or 
                data.get("title") or 
                data.get("summary"))
    
    def _extract_url(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract URL."""
        return (data.get("url") or 
                data.get("link") or 
                data.get("source_url"))
    
    def _extract_tickers(self, data: Dict[str, Any]) -> List[str]:
        """Extract ticker symbols from news."""
        tickers = data.get("tickers", [])
        if isinstance(tickers, str):
            # Split comma-separated tickers
            tickers = [t.strip() for t in tickers.split(",")]
        elif not isinstance(tickers, list):
            tickers = []
        
        # If no tickers found, try to extract from headline
        if not tickers:
            headline = data.get("headline", "")
            if headline:
                # Simple ticker extraction (look for common patterns)
                import re
                # Look for patterns like "AAPL", "MSFT", etc.
                ticker_pattern = r'\b[A-Z]{1,5}\b'
                potential_tickers = re.findall(ticker_pattern, headline)
                # Filter out common words that aren't tickers
                common_words = {'THE', 'AND', 'FOR', 'WITH', 'FROM', 'THIS', 'THAT', 'WILL', 'CAN', 'ARE', 'NOT'}
                tickers = [t for t in potential_tickers if t not in common_words and len(t) <= 5]
        
        return tickers
    
    def _extract_sentiment(self, data: Dict[str, Any]) -> float:
        """Extract sentiment score."""
        sentiment = data.get("sentiment", 0.0)
        if isinstance(sentiment, (int, float)):
            return float(sentiment)
        
        # If no sentiment provided, try to calculate from headline
        headline = data.get("headline", "")
        if headline:
            # Simple sentiment analysis
            positive_words = ['beat', 'exceed', 'strong', 'growth', 'profit', 'gain', 'rise', 'up', 'positive']
            negative_words = ['miss', 'fall', 'decline', 'loss', 'weak', 'down', 'negative', 'drop', 'crash']
            
            text_lower = headline.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            if positive_count + negative_count > 0:
                sentiment = (positive_count - negative_count) / (positive_count + negative_count)
                return max(-1.0, min(1.0, sentiment))  # Clamp between -1 and 1
        
        return 0.0
    
    def _extract_filing_type(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract filing type."""
        return (data.get("filing_type") or 
                data.get("form_type") or 
                data.get("type"))
    
    def _extract_filing_date(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract filing date."""
        date = (data.get("filing_date") or 
                data.get("date") or 
                data.get("filed_date"))
        
        if date:
            try:
                # Parse date and return in ISO format
                if isinstance(date, str):
                    dt = datetime.fromisoformat(date)
                else:
                    dt = date
                
                return dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                logger.warning(f"Could not parse filing date: {date}")
                return None
        
        return None
    
    def _extract_summary(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract filing summary."""
        return (data.get("summary") or 
                data.get("description") or 
                data.get("abstract"))
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def validate_schema(self, data: Dict[str, Any], schema_type: str) -> bool:
        """
        Validate data against canonical schema.
        
        Args:
            data: Data to validate
            schema_type: Type of schema (ohlcv, news, filings)
            
        Returns:
            True if valid, False otherwise
        """
        if schema_type not in self.schemas:
            return False
        
        required_fields = self.schemas[schema_type]
        return all(field in data for field in required_fields)
    
    def get_schema(self, schema_type: str) -> List[str]:
        """Get canonical schema fields for a data type."""
        return self.schemas.get(schema_type, [])


# Global normalizer instance
normalizer = DataNormalizer()
