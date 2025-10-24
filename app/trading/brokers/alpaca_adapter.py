"""
Alpaca broker adapter for paper and live trading.
Implements the BaseBroker interface for Alpaca Markets API.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import json

try:
    import alpaca_trade_api as tradeapi
    from alpaca_trade_api.rest import APIError
    from alpaca_trade_api.entity import Account as AlpacaAccount
    from alpaca_trade_api.entity import Position as AlpacaPosition
    from alpaca_trade_api.entity import Order as AlpacaOrder
    from alpaca_trade_api.entity import Bar as AlpacaBar
    from alpaca_trade_api.stream import Stream
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    tradeapi = None
    APIError = Exception
    AlpacaAccount = None
    AlpacaPosition = None
    AlpacaOrder = None
    AlpacaBar = None
    Stream = None

from .base import (
    BaseBroker, Account, Position, Order, OrderType, OrderSide, OrderStatus,
    TimeInForce, MarketHours, Bar, BrokerError, ConnectionError,
    AuthenticationError, OrderError, InsufficientFundsError,
    InvalidOrderError, MarketClosedError, SymbolNotFoundError
)

logger = logging.getLogger(__name__)


class AlpacaAdapter(BaseBroker):
    """
    Alpaca broker adapter for paper and live trading.
    
    Supports:
    - Paper trading (default)
    - Live trading (requires explicit configuration)
    - Real-time data streaming
    - Order management
    - Position tracking
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Alpaca adapter.
        
        Config parameters:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            base_url: API base URL (default: paper trading)
            data_url: Data API base URL
            paper: Use paper trading (default: True)
            stream_url: WebSocket streaming URL
        """
        super().__init__(config)
        
        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-trade-api is required for AlpacaAdapter")
        
        self.api_key = config.get('api_key')
        self.secret_key = config.get('secret_key')
        self.base_url = config.get('base_url', 'https://paper-api.alpaca.markets')
        self.data_url = config.get('data_url', 'https://data.alpaca.markets')
        self.paper = config.get('paper', True)
        self.stream_url = config.get('stream_url', 'wss://stream.data.alpaca.markets/v2/iex')
        
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API key and secret key are required")
        
        self.api = None
        self.stream = None
        self.streaming_symbols = []
        self.streaming_data = {}
    
    def _parse_datetime(self, dt_input) -> datetime:
        """Parse datetime from Alpaca API (handles both strings and Timestamp objects)."""
        try:
            # If it's already a datetime object, return it
            if isinstance(dt_input, datetime):
                return dt_input
            
            # If it's a Timestamp object, convert to datetime
            if hasattr(dt_input, 'to_pydatetime'):
                return dt_input.to_pydatetime()
            
            # If it's a string, parse it
            if isinstance(dt_input, str):
                # Handle ISO format with Z suffix
                if dt_input.endswith('Z'):
                    dt_input = dt_input.replace('Z', '+00:00')
                return datetime.fromisoformat(dt_input)
            
            # If it's a pandas Timestamp, convert to datetime
            if hasattr(dt_input, 'timestamp'):
                return datetime.fromtimestamp(dt_input.timestamp(), tz=timezone.utc)
            
            # Fallback: try to convert to string and parse
            dt_str = str(dt_input)
            if dt_str.endswith('Z'):
                dt_str = dt_str.replace('Z', '+00:00')
            return datetime.fromisoformat(dt_str)
            
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.warning(f"Failed to parse datetime '{dt_input}': {e}")
            return datetime.now(timezone.utc)
        
    async def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            self.api = tradeapi.REST(
                self.api_key,
                self.secret_key,
                self.base_url,
                api_version='v2'
            )
            
            # Test connection by getting account info
            account = self.api.get_account()
            if account:
                self.connected = True
                self.logger.info(f"Connected to Alpaca {'Paper' if self.paper else 'Live'} Trading")
                return True
            else:
                self.logger.error("Failed to connect to Alpaca API")
                return False
                
        except APIError as e:
            self.logger.error(f"Alpaca API error: {e}")
            if "401" in str(e) or "authentication" in str(e).lower():
                raise AuthenticationError(f"Alpaca authentication failed: {e}")
            else:
                raise ConnectionError(f"Failed to connect to Alpaca: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to Alpaca: {e}")
            raise ConnectionError(f"Failed to connect to Alpaca: {e}")
    
    async def disconnect(self) -> bool:
        """Disconnect from Alpaca API."""
        try:
            if self.stream:
                await self.stop_streaming()
            
            self.api = None
            self.connected = False
            self.logger.info("Disconnected from Alpaca API")
            return True
        except Exception as e:
            self.logger.error(f"Error disconnecting from Alpaca: {e}")
            return False
    
    async def get_account(self) -> Optional[Account]:
        """Get account information."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            alpaca_account = self.api.get_account()
            if not alpaca_account:
                return None
            
            return Account(
                account_id=alpaca_account.id,
                buying_power=float(alpaca_account.buying_power),
                cash=float(alpaca_account.cash),
                equity=float(alpaca_account.equity),
                day_trade_count=getattr(alpaca_account, 'day_trade_count', 0),
                pattern_day_trader=getattr(alpaca_account, 'pattern_day_trader', False),
                portfolio_value=float(alpaca_account.portfolio_value),
                regt_buying_power=float(getattr(alpaca_account, 'regt_buying_power', alpaca_account.buying_power)),
                regt_selling_power=float(getattr(alpaca_account, 'regt_selling_power', alpaca_account.buying_power)),
                long_market_value=float(getattr(alpaca_account, 'long_market_value', 0)),
                short_market_value=float(getattr(alpaca_account, 'short_market_value', 0)),
                initial_margin=float(getattr(alpaca_account, 'initial_margin', 0)),
                maintenance_margin=float(getattr(alpaca_account, 'maintenance_margin', 0)),
                last_equity=float(getattr(alpaca_account, 'last_equity', alpaca_account.equity)),
                last_market_value=float(getattr(alpaca_account, 'last_market_value', alpaca_account.portfolio_value)),
                created_at=self._parse_datetime(alpaca_account.created_at),
                updated_at=self._parse_datetime(getattr(alpaca_account, 'updated_at', alpaca_account.created_at))
            )
        except APIError as e:
            self.logger.error(f"Error getting account info: {e}")
            return None
    
    async def get_positions(self) -> List[Position]:
        """Get all current positions."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            alpaca_positions = self.api.list_positions()
            positions = []
            
            for pos in alpaca_positions:
                position = Position(
                    symbol=pos.symbol,
                    quantity=float(pos.qty),
                    side='long' if float(pos.qty) > 0 else 'short',
                    market_value=float(pos.market_value),
                    cost_basis=float(pos.cost_basis),
                    unrealized_pl=float(pos.unrealized_pl),
                    unrealized_plpc=float(pos.unrealized_plpc),
                    current_price=float(pos.current_price),
                    lastday_price=float(pos.lastday_price),
                    change_today=float(pos.change_today),
                    change_today_percent=float(pos.change_today_percent),
                    avg_entry_price=float(pos.avg_entry_price),
                    qty_available=float(pos.qty_available),
                    qty_held_for_sells=float(pos.qty_held_for_sells),
                    qty_held_for_buys=float(pos.qty_held_for_buys),
                    created_at=self._parse_datetime(pos.created_at),
                    updated_at=self._parse_datetime(pos.updated_at)
                )
                positions.append(position)
            
            return positions
        except APIError as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for specific symbol."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            alpaca_position = self.api.get_position(symbol)
            if not alpaca_position:
                return None
            
            return Position(
                symbol=alpaca_position.symbol,
                quantity=float(alpaca_position.qty),
                side='long' if float(alpaca_position.qty) > 0 else 'short',
                market_value=float(alpaca_position.market_value),
                cost_basis=float(alpaca_position.cost_basis),
                unrealized_pl=float(alpaca_position.unrealized_pl),
                unrealized_plpc=float(alpaca_position.unrealized_plpc),
                current_price=float(alpaca_position.current_price),
                lastday_price=float(alpaca_position.lastday_price),
                change_today=float(alpaca_position.change_today),
                change_today_percent=float(alpaca_position.change_today_percent),
                avg_entry_price=float(alpaca_position.avg_entry_price),
                qty_available=float(alpaca_position.qty_available),
                qty_held_for_sells=float(alpaca_position.qty_held_for_sells),
                qty_held_for_buys=float(alpaca_position.qty_held_for_buys),
                created_at=self._parse_datetime(alpaca_position.created_at),
                updated_at=self._parse_datetime(alpaca_position.updated_at)
            )
        except APIError as e:
            if "position not found" in str(e).lower():
                return None
            self.logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        time_in_force: TimeInForce = TimeInForce.DAY,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        trail_price: Optional[float] = None,
        trail_percent: Optional[float] = None,
        client_order_id: Optional[str] = None
    ) -> Optional[Order]:
        """Place a new order."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            # Convert our enums to Alpaca format
            alpaca_side = side.value
            alpaca_order_type = order_type.value
            alpaca_time_in_force = time_in_force.value
            
            # Build order parameters
            order_params = {
                'symbol': symbol,
                'qty': int(quantity),
                'side': alpaca_side,
                'type': alpaca_order_type,
                'time_in_force': alpaca_time_in_force
            }
            
            if client_order_id:
                order_params['client_order_id'] = client_order_id
            
            if order_type == OrderType.LIMIT and limit_price:
                order_params['limit_price'] = limit_price
            elif order_type == OrderType.STOP and stop_price:
                order_params['stop_price'] = stop_price
            elif order_type == OrderType.STOP_LIMIT and limit_price and stop_price:
                order_params['limit_price'] = limit_price
                order_params['stop_price'] = stop_price
            elif order_type == OrderType.TRAILING_STOP:
                if trail_price:
                    order_params['trail_price'] = trail_price
                elif trail_percent:
                    order_params['trail_percent'] = trail_percent
            
            # Place order
            alpaca_order = self.api.submit_order(**order_params)
            
            if alpaca_order:
                return self._convert_alpaca_order(alpaca_order)
            else:
                return None
                
        except APIError as e:
            self.logger.error(f"Error placing order: {e}")
            if "insufficient" in str(e).lower():
                raise InsufficientFundsError(f"Insufficient funds: {e}")
            elif "invalid" in str(e).lower():
                raise InvalidOrderError(f"Invalid order: {e}")
            elif "market closed" in str(e).lower():
                raise MarketClosedError(f"Market is closed: {e}")
            else:
                raise OrderError(f"Order placement failed: {e}")
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            self.api.cancel_order(order_id)
            return True
        except APIError as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            alpaca_order = self.api.get_order(order_id)
            if alpaca_order:
                return self._convert_alpaca_order(alpaca_order)
            return None
        except APIError as e:
            self.logger.error(f"Error getting order {order_id}: {e}")
            return None
    
    async def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: Optional[int] = None,
        after: Optional[datetime] = None,
        until: Optional[datetime] = None,
        direction: str = "desc"
    ) -> List[Order]:
        """Get orders with optional filtering."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            # Convert status filter
            alpaca_status = None
            if status:
                alpaca_status = status.value
            
            # Get orders
            alpaca_orders = self.api.list_orders(
                status=alpaca_status,
                limit=limit,
                after=after,
                until=until,
                direction=direction
            )
            
            orders = []
            for alpaca_order in alpaca_orders:
                order = self._convert_alpaca_order(alpaca_order)
                if order:
                    orders.append(order)
            
            return orders
        except APIError as e:
            self.logger.error(f"Error getting orders: {e}")
            return []
    
    async def get_market_hours(self) -> MarketHours:
        """Get market hours information."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            clock = self.api.get_clock()
            return MarketHours(
                is_open=clock.is_open,
                next_open=clock.next_open,
                next_close=clock.next_close,
                timezone="US/Eastern"
            )
        except APIError as e:
            self.logger.error(f"Error getting market hours: {e}")
            return MarketHours(is_open=False)
    
    async def is_market_open(self) -> bool:
        """Check if market is currently open."""
        market_hours = await self.get_market_hours()
        return market_hours.is_open
    
    async def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for symbol."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            quote = self.api.get_latest_quote(symbol)
            if quote:
                return (float(quote.bid) + float(quote.ask)) / 2
            return None
        except APIError as e:
            self.logger.error(f"Error getting latest price for {symbol}: {e}")
            return None
    
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1min",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Bar]:
        """Get historical bars for symbol."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            # Convert timeframe to Alpaca format
            timeframe_map = {
                '1min': '1Min',
                '5min': '5Min',
                '15min': '15Min',
                '1hour': '1Hour',
                '1day': '1Day'
            }
            alpaca_timeframe = timeframe_map.get(timeframe, '1Min')
            
            # Get bars
            bars = self.api.get_bars(
                symbol,
                alpaca_timeframe,
                start=start,
                end=end,
                limit=limit
            )
            
            result = []
            for bar in bars:
                bar_obj = Bar(
                    symbol=bar.symbol,
                    timestamp=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume),
                    trade_count=getattr(bar, 'trade_count', None),
                    vwap=getattr(bar, 'vwap', None)
                )
                result.append(bar_obj)
            
            return result
        except APIError as e:
            self.logger.error(f"Error getting bars for {symbol}: {e}")
            return []
    
    async def get_buying_power(self) -> float:
        """Get available buying power."""
        account = await self.get_account()
        if account:
            return account.buying_power
        return 0.0
    
    async def get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        account = await self.get_account()
        if account:
            return account.portfolio_value
        return 0.0
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get real-time quote (bid/ask)."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            quote = self.api.get_latest_quote(symbol)
            if quote:
                return {
                    'bid': float(quote.bid),
                    'ask': float(quote.ask),
                    'spread': float(quote.ask) - float(quote.bid)
                }
            return None
        except APIError as e:
            self.logger.error(f"Error getting quote for {symbol}: {e}")
            return None
    
    async def get_commission(self, symbol: str, quantity: float, price: float) -> float:
        """Calculate commission for trade."""
        # Alpaca commission-free trading
        return 0.0
    
    async def start_streaming(self, symbols: List[str]) -> bool:
        """Start real-time data streaming."""
        if not self.connected:
            raise ConnectionError("Not connected to Alpaca API")
        
        try:
            self.streaming_symbols = symbols
            self.stream = Stream(
                self.api_key,
                self.secret_key,
                self.stream_url,
                data_feed='iex'  # or 'sip' for live
            )
            
            # Start streaming
            self.stream.subscribe_quotes(symbols)
            self.stream.subscribe_trades(symbols)
            
            # Start in background
            asyncio.create_task(self._stream_worker())
            
            self.logger.info(f"Started streaming for symbols: {symbols}")
            return True
        except Exception as e:
            self.logger.error(f"Error starting streaming: {e}")
            return False
    
    async def stop_streaming(self) -> bool:
        """Stop real-time data streaming."""
        try:
            if self.stream:
                self.stream.unsubscribe_quotes(self.streaming_symbols)
                self.stream.unsubscribe_trades(self.streaming_symbols)
                self.stream = None
            
            self.streaming_symbols = []
            self.streaming_data = {}
            
            self.logger.info("Stopped streaming")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping streaming: {e}")
            return False
    
    async def get_streaming_data(self) -> Optional[Dict[str, Any]]:
        """Get latest streaming data."""
        return self.streaming_data.copy() if self.streaming_data else None
    
    def _convert_alpaca_order(self, alpaca_order) -> Order:
        """Convert Alpaca order to our Order format."""
        try:
            # Convert status
            status_map = {
                'new': OrderStatus.PENDING,
                'accepted': OrderStatus.SUBMITTED,
                'partially_filled': OrderStatus.PARTIALLY_FILLED,
                'filled': OrderStatus.FILLED,
                'done_for_day': OrderStatus.FILLED,
                'canceled': OrderStatus.CANCELLED,
                'expired': OrderStatus.EXPIRED,
                'replaced': OrderStatus.CANCELLED,
                'pending_cancel': OrderStatus.CANCELLED,
                'pending_replace': OrderStatus.CANCELLED,
                'rejected': OrderStatus.REJECTED
            }
            status = status_map.get(alpaca_order.status, OrderStatus.PENDING)
            
            # Convert side
            side = OrderSide.BUY if alpaca_order.side == 'buy' else OrderSide.SELL
            
            # Convert order type
            order_type_map = {
                'market': OrderType.MARKET,
                'limit': OrderType.LIMIT,
                'stop': OrderType.STOP,
                'stop_limit': OrderType.STOP_LIMIT,
                'trailing_stop': OrderType.TRAILING_STOP
            }
            order_type = order_type_map.get(alpaca_order.order_type, OrderType.MARKET)
            
            # Convert time in force
            tif_map = {
                'day': TimeInForce.DAY,
                'gtc': TimeInForce.GTC,
                'ioc': TimeInForce.IOC,
                'fok': TimeInForce.FOK
            }
            time_in_force = tif_map.get(alpaca_order.time_in_force, TimeInForce.DAY)
            
            return Order(
                order_id=alpaca_order.id,
                client_order_id=alpaca_order.client_order_id,
                symbol=alpaca_order.symbol,
                side=side,
                order_type=order_type,
                quantity=float(alpaca_order.qty),
                filled_quantity=float(alpaca_order.filled_qty),
                remaining_quantity=float(alpaca_order.qty) - float(alpaca_order.filled_qty),
                status=status,
                time_in_force=time_in_force,
                limit_price=float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
                stop_price=float(alpaca_order.stop_price) if alpaca_order.stop_price else None,
                trail_price=float(alpaca_order.trail_price) if alpaca_order.trail_price else None,
                trail_percent=float(alpaca_order.trail_percent) if alpaca_order.trail_percent else None,
                average_fill_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
                filled_at=self._parse_datetime(alpaca_order.filled_at) if alpaca_order.filled_at else None,
                submitted_at=self._parse_datetime(alpaca_order.submitted_at) if alpaca_order.submitted_at else None,
                created_at=self._parse_datetime(alpaca_order.created_at) if alpaca_order.created_at else None,
                updated_at=self._parse_datetime(alpaca_order.updated_at) if alpaca_order.updated_at else None,
                expires_at=self._parse_datetime(alpaca_order.expires_at) if alpaca_order.expires_at else None,
                cancel_reason=alpaca_order.cancel_reason,
                replaced_by=alpaca_order.replaced_by,
                replaces=alpaca_order.replaces
            )
        except Exception as e:
            self.logger.error(f"Error converting Alpaca order: {e}")
            return None
    
    async def _stream_worker(self):
        """Background worker for streaming data."""
        try:
            while self.stream and self.connected:
                # This would need to be implemented with proper async streaming
                # For now, we'll just log that streaming is active
                await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"Error in streaming worker: {e}")
