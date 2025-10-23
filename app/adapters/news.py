"""
News adapter for collecting market news and headlines.
Supports multiple sources including Finnhub, RSS feeds, and other news APIs.
"""
import asyncio
import aiohttp
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import logging

from app.adapters.base import RESTAdapter
from app.core.normalizer import normalizer
from app.core.storage import StorageManager
from app.core.rate_limiter import with_rate_limit
from app.config import DATA_PATH, DB_PATH

logger = logging.getLogger(__name__)

class NewsAdapter(RESTAdapter):
    """News adapter for collecting market news and headlines."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.api_key = config.get('api_key')
        self.base_url = config.get('base_url', 'https://finnhub.io/api/v1')
        self.watchlist = config.get('watchlist', [])
        self.storage = StorageManager(DATA_PATH, DB_PATH)
        self.last_fetch_time = None
        self.polling_interval = config.get('polling_interval', 300)  # 5 minutes default
    
    async def start(self) -> bool:
        """Start news adapter."""
        try:
            if not self.api_key:
                logger.error("No API key provided for news adapter")
                return False
            
            # Start REST session
            self.session = aiohttp.ClientSession()
            
            # Start background task for news polling
            await self._start_background_task()
            
            logger.info("News adapter started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start news adapter: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop news adapter."""
        try:
            await self._stop_background_task()
            if self.session:
                await self.session.close()
            return True
        except Exception as e:
            logger.error(f"Error stopping news adapter: {e}")
            return False
    
    async def _fetch_data(self):
        """Fetch news data from API."""
        try:
            # Fetch general market news
            await self._fetch_market_news()
            
            # Fetch company-specific news for watchlist
            for symbol in self.watchlist[:10]:  # Limit to avoid rate limits
                await self._fetch_company_news(symbol)
                await asyncio.sleep(1)  # Rate limiting delay
                
        except Exception as e:
            logger.error(f"Error fetching news data: {e}")
    
    async def _fetch_market_news(self):
        """Fetch general market news."""
        try:
            url = f"{self.base_url}/news"
            params = {
                'category': 'general',
                'token': self.api_key,
                'minId': 0  # Get latest news
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list):
                        for news_item in data[:20]:  # Limit to 20 items
                            normalized = self.normalize(news_item)
                            if normalized:
                                await self._handle_data(normalized)
                else:
                    logger.warning(f"HTTP {response.status} from news API")
                    
        except Exception as e:
            logger.error(f"Error fetching market news: {e}")
    
    async def _fetch_company_news(self, symbol: str):
        """Fetch company-specific news."""
        try:
            url = f"{self.base_url}/company-news"
            params = {
                'symbol': symbol,
                'from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                'to': datetime.now().strftime('%Y-%m-%d'),
                'token': self.api_key
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list):
                        for news_item in data[:10]:  # Limit to 10 items per company
                            normalized = self.normalize(news_item)
                            if normalized:
                                await self._handle_data(normalized)
                else:
                    logger.warning(f"HTTP {response.status} from company news API for {symbol}")
                    
        except Exception as e:
            logger.error(f"Error fetching company news for {symbol}: {e}")
    
    def normalize(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize news data to canonical schema."""
        return normalizer.normalize_news(raw_data, "finnhub")
    
    async def _handle_data(self, data: Dict[str, Any]):
        """Handle processed news data."""
        try:
            # Store news data
            self.storage.store_news([data])
            
            # Broadcast to WebSocket clients
            from app.api.websocket import broadcast_news_update
            await broadcast_news_update(data)
            
            logger.info(f"Processed news: {data.get('headline', 'Unknown')[:50]}...")
            
        except Exception as e:
            logger.error(f"Error handling news data: {e}")
    
    async def health_check(self) -> bool:
        """Check if news API is accessible."""
        try:
            if not self.session:
                return False
            
            # Test API endpoint
            url = f"{self.base_url}/news"
            params = {
                'category': 'general',
                'token': self.api_key
            }
            
            async with self.session.get(url, params=params) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def fetch_historical_news(self, symbol: Optional[str] = None, 
                                  days_back: int = 30) -> List[Dict[str, Any]]:
        """Fetch historical news data."""
        try:
            if not self.session:
                return []
            
            if symbol:
                # Fetch company-specific news
                url = f"{self.base_url}/company-news"
                params = {
                    'symbol': symbol,
                    'from': (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
                    'to': datetime.now().strftime('%Y-%m-%d'),
                    'token': self.api_key
                }
            else:
                # Fetch general market news
                url = f"{self.base_url}/news"
                params = {
                    'category': 'general',
                    'token': self.api_key
                }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list):
                        news_items = []
                        for item in data:
                            normalized = self.normalize(item)
                            if normalized:
                                news_items.append(normalized)
                        return news_items
                else:
                    logger.warning(f"HTTP {response.status} from historical news API")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching historical news: {e}")
            return []
    
    def get_news_sentiment(self, text: str) -> float:
        """Calculate sentiment score for news text."""
        try:
            # Simple sentiment analysis using keyword matching
            positive_words = ['beat', 'exceed', 'strong', 'growth', 'profit', 'gain', 'rise', 'up', 'positive']
            negative_words = ['miss', 'fall', 'decline', 'loss', 'weak', 'down', 'negative', 'drop', 'crash']
            
            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            if positive_count + negative_count == 0:
                return 0.0  # Neutral
            
            sentiment = (positive_count - negative_count) / (positive_count + negative_count)
            return max(-1.0, min(1.0, sentiment))  # Clamp between -1 and 1
            
        except Exception as e:
            logger.error(f"Error calculating sentiment: {e}")
            return 0.0
