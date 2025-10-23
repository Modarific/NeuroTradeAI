"""
Finnhub adapter for real-time market data and news.
Supports both WebSocket and REST API endpoints.
"""
import asyncio
import aiohttp
import websockets
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

from app.adapters.base import WebSocketAdapter, RESTAdapter
from app.core.normalizer import normalizer
from app.core.storage import StorageManager
from app.core.rate_limiter import with_rate_limit
from app.config import DATA_PATH, DB_PATH

logger = logging.getLogger(__name__)

class FinnhubAdapter(WebSocketAdapter):
    """Finnhub adapter for real-time market data."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.api_key = config.get('api_key')
        self.watchlist = config.get('watchlist', [])
        self.base_url = config.get('base_url', 'https://finnhub.io/api/v1')
        self.websocket_url = config.get('websocket_url')
        self.session = None
        self.storage = StorageManager(DATA_PATH, DB_PATH)
        self.subscribed_symbols = set()
    
    async def start(self) -> bool:
        """Start Finnhub adapter."""
        try:
            if not self.api_key:
                logger.error("No API key provided for Finnhub")
                return False
            
            # Start REST session for historical data
            self.session = aiohttp.ClientSession()
            
            # For now, skip WebSocket to avoid concurrency issues
            # We'll use REST-only mode for initial implementation
            logger.info("Starting Finnhub adapter in REST-only mode")
            
            # Start background task for REST polling
            await self._start_background_task()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Finnhub adapter: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop Finnhub adapter."""
        try:
            # Stop WebSocket
            await super().stop()
            
            # Close REST session
            if self.session:
                await self.session.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping Finnhub adapter: {e}")
            return False
    
    async def _subscribe_to_symbols(self):
        """Subscribe to WebSocket for watchlist symbols."""
        if not self.websocket:
            return
        
        try:
            for symbol in self.watchlist:
                # Subscribe to quote updates
                subscribe_msg = {
                    "type": "subscribe",
                    "symbol": symbol
                }
                await self.websocket.send(json.dumps(subscribe_msg))
                self.subscribed_symbols.add(symbol)
                logger.info(f"Subscribed to {symbol}")
                
        except Exception as e:
            logger.error(f"Error subscribing to symbols: {e}")
    
    async def _process_websocket_message(self, message: str) -> Optional[Dict[str, Any]]:
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            if data.get('type') == 'trade':
                # Process trade data
                return self._process_trade_data(data)
            elif data.get('type') == 'quote':
                # Process quote data
                return self._process_quote_data(data)
            else:
                logger.debug(f"Unknown message type: {data.get('type')}")
                return None
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in WebSocket message: {message}")
            return None
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
            return None
    
    def _process_trade_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process trade data from WebSocket."""
        try:
            symbol = data.get('s')
            price = data.get('p')
            volume = data.get('v')
            timestamp = data.get('t')
            
            if not all([symbol, price, volume, timestamp]):
                return None
            
            # Convert timestamp from milliseconds to seconds
            timestamp_sec = timestamp / 1000
            
            # Create OHLCV record (using price as OHLC for tick data)
            raw_data = {
                'symbol': symbol,
                'timestamp': timestamp_sec,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume,
                'interval': 'tick'
            }
            
            return raw_data
            
        except Exception as e:
            logger.error(f"Error processing trade data: {e}")
            return None
    
    def _process_quote_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process quote data from WebSocket."""
        try:
            symbol = data.get('s')
            bid = data.get('b')
            ask = data.get('a')
            timestamp = data.get('t')
            
            if not all([symbol, bid, ask, timestamp]):
                return None
            
            # Convert timestamp from milliseconds to seconds
            timestamp_sec = timestamp / 1000
            
            # Create quote record
            raw_data = {
                'symbol': symbol,
                'timestamp': timestamp_sec,
                'bid': bid,
                'ask': ask,
                'interval': 'quote'
            }
            
            return raw_data
            
        except Exception as e:
            logger.error(f"Error processing quote data: {e}")
            return None
    
    async def _fetch_data(self):
        """Fetch data using REST API polling instead of WebSocket."""
        try:
            # Poll for quote data for each symbol in watchlist
            for symbol in self.watchlist[:5]:  # Limit to first 5 symbols to avoid rate limits
                try:
                    url = f"{self.base_url}/quote"
                    params = {
                        'symbol': symbol,
                        'token': self.api_key
                    }
                    
                    async with self.session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            # Convert to our format
                            if data.get('c'):  # Current price exists
                                raw_data = {
                                    'symbol': symbol,
                                    'timestamp': int(datetime.now().timestamp()),
                                    'open': data.get('o', data.get('c')),
                                    'high': data.get('h', data.get('c')),
                                    'low': data.get('l', data.get('c')),
                                    'close': data.get('c'),
                                    'volume': data.get('v', 0),
                                    'interval': '1m'
                                }
                                
                                normalized = self.normalize(raw_data)
                                if normalized:
                                    await self._handle_data(normalized)
                                    
                except Exception as e:
                    logger.error(f"Error fetching data for {symbol}: {e}")
                    
                # Small delay between requests to respect rate limits
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in REST polling: {e}")

    async def _handle_data(self, data: Dict[str, Any]):
        """Handle processed data."""
        try:
            # Store data
            self.storage.store_ohlcv([data])
            
            # Broadcast to WebSocket clients
            from app.api.websocket import broadcast_ohlcv_update
            await broadcast_ohlcv_update(data['symbol'], data)
            
            logger.info(f"Processed OHLCV: {data['symbol']} = ${data.get('close', 0):.2f}")
            
        except Exception as e:
            logger.error(f"Error handling data: {e}")
    
    def normalize(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize raw data to canonical schema."""
        return normalizer.normalize_ohlcv(raw_data, "finnhub")
    
    async def health_check(self) -> bool:
        """Check if Finnhub API is accessible."""
        try:
            if not self.session:
                return False
            
            # Test API endpoint
            url = f"{self.base_url}/quote"
            params = {
                'symbol': 'AAPL',
                'token': self.api_key
            }
            
            async with self.session.get(url, params=params) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def fetch_historical_bars(self, symbol: str, resolution: str = "1", 
                                   from_timestamp: int = None, to_timestamp: int = None) -> List[Dict[str, Any]]:
        """Fetch historical bars from Finnhub."""
        try:
            if not self.session:
                return []
            
            url = f"{self.base_url}/stock/candle"
            params = {
                'symbol': symbol,
                'resolution': resolution,
                'token': self.api_key
            }
            
            if from_timestamp:
                params['from'] = from_timestamp
            if to_timestamp:
                params['to'] = to_timestamp
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._process_historical_data(data, symbol, resolution)
                else:
                    logger.warning(f"HTTP {response.status} from Finnhub historical API")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching historical bars: {e}")
            return []
    
    def _process_historical_data(self, data: Dict[str, Any], symbol: str, resolution: str) -> List[Dict[str, Any]]:
        """Process historical data from Finnhub."""
        try:
            if data.get('s') != 'ok':
                logger.warning(f"Finnhub API returned error: {data.get('s')}")
                return []
            
            timestamps = data.get('t', [])
            opens = data.get('o', [])
            highs = data.get('h', [])
            lows = data.get('l', [])
            closes = data.get('c', [])
            volumes = data.get('v', [])
            
            bars = []
            for i in range(len(timestamps)):
                raw_data = {
                    'symbol': symbol,
                    'timestamp': timestamps[i],
                    'open': opens[i],
                    'high': highs[i],
                    'low': lows[i],
                    'close': closes[i],
                    'volume': volumes[i],
                    'interval': resolution
                }
                
                normalized = self.normalize(raw_data)
                if normalized:
                    bars.append(normalized)
            
            return bars
            
        except Exception as e:
            logger.error(f"Error processing historical data: {e}")
            return []
    
    async def fetch_news(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch news from Finnhub."""
        try:
            if not self.session:
                return []
            
            url = f"{self.base_url}/company-news"
            params = {
                'token': self.api_key,
                'limit': limit
            }
            
            if symbol:
                params['symbol'] = symbol
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._process_news_data(data)
                else:
                    logger.warning(f"HTTP {response.status} from Finnhub news API")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []
    
    def _process_news_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process news data from Finnhub."""
        try:
            news_items = []
            for item in data:
                normalized = normalizer.normalize_news(item, "finnhub")
                if normalized:
                    news_items.append(normalized)
            
            return news_items
            
        except Exception as e:
            logger.error(f"Error processing news data: {e}")
            return []
