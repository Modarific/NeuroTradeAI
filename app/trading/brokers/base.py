"""
Abstract broker interface for all trading brokers.
Defines standardized methods and data models for broker integration.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Supported order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"


class PositionSide(Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"


class OrderStatus(Enum):
    """Order status values."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(Enum):
    """Time in force options."""
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill


@dataclass
class Account:
    """Account information."""
    account_id: str
    buying_power: float
    cash: float
    equity: float
    day_trade_count: int
    pattern_day_trader: bool
    portfolio_value: float
    regt_buying_power: float
    regt_selling_power: float
    long_market_value: float
    short_market_value: float
    initial_margin: float
    maintenance_margin: float
    last_equity: float
    last_market_value: float
    created_at: datetime
    updated_at: datetime


@dataclass
class Position:
    """Position information."""
    symbol: str
    quantity: float
    side: str  # 'long' or 'short'
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float  # unrealized P&L percentage
    current_price: float
    lastday_price: float
    change_today: float
    change_today_percent: float
    avg_entry_price: float
    qty_available: float  # available for trading
    qty_held_for_sells: float
    qty_held_for_buys: float
    created_at: datetime
    updated_at: datetime


@dataclass
class Order:
    """Order information."""
    order_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    filled_quantity: float
    remaining_quantity: float
    status: OrderStatus
    time_in_force: TimeInForce
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trail_price: Optional[float] = None
    trail_percent: Optional[float] = None
    average_fill_price: Optional[float] = None
    filled_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    legs: Optional[List['Order']] = None  # For complex orders
    replaced_by: Optional[str] = None
    replaces: Optional[str] = None


@dataclass
class MarketHours:
    """Market hours information."""
    is_open: bool
    next_open: Optional[datetime] = None
    next_close: Optional[datetime] = None
    timezone: str = "US/Eastern"


@dataclass
class Bar:
    """Price bar data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    trade_count: Optional[int] = None
    vwap: Optional[float] = None


class BaseBroker(ABC):
    """
    Abstract base class for all broker implementations.
    
    Provides standardized interface for:
    - Account management
    - Position tracking
    - Order placement and management
    - Market data access
    - Market hours checking
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize broker with configuration.
        
        Args:
            config: Broker-specific configuration dictionary
        """
        self.config = config
        self.connected = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to broker API.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from broker API.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_account(self) -> Optional[Account]:
        """
        Get account information.
        
        Returns:
            Account object or None if failed
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """
        Get all current positions.
        
        Returns:
            List of Position objects
        """
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for specific symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Position object or None if no position
        """
        pass
    
    @abstractmethod
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
        """
        Place a new order.
        
        Args:
            symbol: Stock symbol
            side: Order side (BUY/SELL)
            order_type: Order type
            quantity: Order quantity
            time_in_force: Time in force
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            trail_price: Trail price (for trailing stops)
            trail_percent: Trail percentage (for trailing stops)
            client_order_id: Client-specified order ID
            
        Returns:
            Order object or None if failed
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order object or None if not found
        """
        pass
    
    @abstractmethod
    async def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: Optional[int] = None,
        after: Optional[datetime] = None,
        until: Optional[datetime] = None,
        direction: str = "desc"
    ) -> List[Order]:
        """
        Get orders with optional filtering.
        
        Args:
            status: Filter by order status
            limit: Maximum number of orders to return
            after: Return orders after this timestamp
            until: Return orders until this timestamp
            direction: Sort direction (asc/desc)
            
        Returns:
            List of Order objects
        """
        pass
    
    @abstractmethod
    async def get_market_hours(self) -> MarketHours:
        """
        Get market hours information.
        
        Returns:
            MarketHours object
        """
        pass
    
    @abstractmethod
    async def is_market_open(self) -> bool:
        """
        Check if market is currently open.
        
        Returns:
            True if market is open, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get latest price for symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Latest price or None if failed
        """
        pass
    
    @abstractmethod
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1min",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Bar]:
        """
        Get historical bars for symbol.
        
        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe (1min, 5min, 1hour, 1day)
            start: Start time
            end: End time
            limit: Maximum number of bars
            
        Returns:
            List of Bar objects
        """
        pass
    
    @abstractmethod
    async def get_buying_power(self) -> float:
        """
        Get available buying power.
        
        Returns:
            Available buying power amount
        """
        pass
    
    @abstractmethod
    async def get_portfolio_value(self) -> float:
        """
        Get total portfolio value.
        
        Returns:
            Total portfolio value
        """
        pass
    
    # Optional methods for advanced features
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Get real-time quote (bid/ask).
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with 'bid' and 'ask' prices or None
        """
        return None
    
    async def get_volume(self, symbol: str) -> Optional[int]:
        """
        Get current volume for symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current volume or None
        """
        return None
    
    async def is_tradable(self, symbol: str) -> bool:
        """
        Check if symbol is tradable.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if tradable, False otherwise
        """
        return True
    
    async def get_commission(self, symbol: str, quantity: float, price: float) -> float:
        """
        Calculate commission for trade.
        
        Args:
            symbol: Stock symbol
            quantity: Trade quantity
            price: Trade price
            
        Returns:
            Commission amount
        """
        return 0.0
    
    # WebSocket streaming (optional)
    
    async def start_streaming(self, symbols: List[str]) -> bool:
        """
        Start real-time data streaming.
        
        Args:
            symbols: List of symbols to stream
            
        Returns:
            True if streaming started successfully
        """
        return False
    
    async def stop_streaming(self) -> bool:
        """
        Stop real-time data streaming.
        
        Returns:
            True if streaming stopped successfully
        """
        return False
    
    async def get_streaming_data(self) -> Optional[Dict[str, Any]]:
        """
        Get latest streaming data.
        
        Returns:
            Latest streaming data or None
        """
        return None


class BrokerError(Exception):
    """Base exception for broker-related errors."""
    pass


class ConnectionError(BrokerError):
    """Connection-related errors."""
    pass


class AuthenticationError(BrokerError):
    """Authentication-related errors."""
    pass


class OrderError(BrokerError):
    """Order-related errors."""
    pass


class InsufficientFundsError(OrderError):
    """Insufficient funds for order."""
    pass


class InvalidOrderError(OrderError):
    """Invalid order parameters."""
    pass


class MarketClosedError(OrderError):
    """Market is closed."""
    pass


class SymbolNotFoundError(BrokerError):
    """Symbol not found or not tradable."""
    pass
