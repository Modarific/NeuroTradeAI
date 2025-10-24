"""
Local execution simulator for offline testing.
Simulates realistic order execution with slippage and commission models.
"""
import asyncio
import random
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import uuid

from .base import (
    BaseBroker, Account, Position, Order, OrderType, OrderSide, OrderStatus,
    TimeInForce, MarketHours, Bar, BrokerError, ConnectionError,
    AuthenticationError, OrderError, InsufficientFundsError,
    InvalidOrderError, MarketClosedError, SymbolNotFoundError
)

logger = logging.getLogger(__name__)


class SimulatorAdapter(BaseBroker):
    """
    Local execution simulator for offline testing.
    
    Features:
    - Realistic order fills with slippage
    - Configurable commission model
    - Market hours simulation
    - Position tracking
    - Order state management
    - Real-time price updates
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize simulator adapter.
        
        Config parameters:
            initial_balance: Starting account balance (default: 100000)
            commission_per_share: Commission per share (default: 0.0)
            commission_per_trade: Fixed commission per trade (default: 0.0)
            slippage_bps: Slippage in basis points (default: 5)
            fill_delay_ms: Delay for order fills in milliseconds (default: 1000)
            market_hours: Market hours simulation (default: 9:30-16:00 ET)
            price_data_source: Source for price data (optional)
        """
        super().__init__(config)
        
        self.initial_balance = config.get('initial_balance', 100000.0)
        self.commission_per_share = config.get('commission_per_share', 0.0)
        self.commission_per_trade = config.get('commission_per_trade', 0.0)
        self.slippage_bps = config.get('slippage_bps', 5)  # 5 basis points
        self.fill_delay_ms = config.get('fill_delay_ms', 1000)
        self.market_hours = config.get('market_hours', {'open': '09:30', 'close': '16:00'})
        self.price_data_source = config.get('price_data_source')
        
        # Broker name
        self.name = "simulator"
        
        # Internal state
        self.account = Account(
            account_id="simulator",
            buying_power=self.initial_balance,
            cash=self.initial_balance,
            equity=self.initial_balance,
            day_trade_count=0,
            pattern_day_trader=False,
            portfolio_value=self.initial_balance,
            regt_buying_power=self.initial_balance,
            regt_selling_power=self.initial_balance,
            long_market_value=0.0,
            short_market_value=0.0,
            initial_margin=0.0,
            maintenance_margin=0.0,
            last_equity=self.initial_balance,
            last_market_value=self.initial_balance,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.price_data: Dict[str, float] = {}
        self.order_counter = 0
        
        # Market hours simulation
        self.market_open_time = self.market_hours['open']
        self.market_close_time = self.market_hours['close']
        
    async def connect(self) -> bool:
        """Connect to simulator (always succeeds)."""
        self.connected = True
        self.logger.info("Connected to Simulator")
        return True
    
    async def disconnect(self) -> bool:
        """Disconnect from simulator."""
        self.connected = False
        self.logger.info("Disconnected from Simulator")
        return True
    
    async def get_account(self) -> Optional[Account]:
        """Get account information."""
        if not self.connected:
            raise ConnectionError("Not connected to simulator")
        
        # Update account values
        await self._update_account()
        return self.account
    
    async def get_positions(self) -> List[Position]:
        """Get all current positions."""
        if not self.connected:
            raise ConnectionError("Not connected to simulator")
        
        return list(self.positions.values())
    
    async def get_open_positions(self) -> List[Position]:
        """Get all open positions (alias for get_positions)."""
        return await self.get_positions()
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for specific symbol."""
        if not self.connected:
            raise ConnectionError("Not connected to simulator")
        
        return self.positions.get(symbol)
    
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
            raise ConnectionError("Not connected to simulator")
        
        # Check if market is open
        if not await self.is_market_open():
            raise MarketClosedError("Market is closed")
        
        # Validate order
        if quantity <= 0:
            raise InvalidOrderError("Quantity must be positive")
        
        # Check buying power for buy orders
        if side == OrderSide.BUY:
            current_price = await self.get_latest_price(symbol)
            if not current_price:
                raise SymbolNotFoundError(f"Symbol {symbol} not found")
            
            required_cash = current_price * quantity
            if required_cash > self.account.buying_power:
                raise InsufficientFundsError(f"Insufficient buying power: need ${required_cash:.2f}, have ${self.account.buying_power:.2f}")
        
        # Create order
        order_id = str(uuid.uuid4())
        client_order_id = client_order_id or f"sim_{self.order_counter}"
        self.order_counter += 1
        
        order = Order(
            order_id=order_id,
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            filled_quantity=0.0,
            remaining_quantity=quantity,
            status=OrderStatus.PENDING,
            time_in_force=time_in_force,
            limit_price=limit_price,
            stop_price=stop_price,
            trail_price=trail_price,
            trail_percent=trail_percent,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        self.orders[order_id] = order
        
        # Process order asynchronously
        asyncio.create_task(self._process_order(order_id))
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self.connected:
            raise ConnectionError("Not connected to simulator")
        
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now(timezone.utc)
                self.logger.info(f"Cancelled order {order_id}")
                return True
        
        return False
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        if not self.connected:
            raise ConnectionError("Not connected to simulator")
        
        return self.orders.get(order_id)
    
    async def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """Get order status by ID."""
        if not self.connected:
            raise ConnectionError("Not connected to simulator")
        
        order = self.orders.get(order_id)
        return order.status if order else None
    
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
            raise ConnectionError("Not connected to simulator")
        
        orders = list(self.orders.values())
        
        # Apply filters
        if status:
            orders = [o for o in orders if o.status == status]
        
        if after:
            orders = [o for o in orders if o.created_at and o.created_at >= after]
        
        if until:
            orders = [o for o in orders if o.created_at and o.created_at <= until]
        
        # Sort by created_at
        orders.sort(key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=(direction == "desc"))
        
        if limit:
            orders = orders[:limit]
        
        return orders
    
    async def get_market_hours(self) -> MarketHours:
        """Get market hours information."""
        now = datetime.now(timezone.utc)
        is_open = await self.is_market_open()
        
        # Calculate next open/close times
        next_open = None
        next_close = None
        
        if not is_open:
            # Market is closed, next open is tomorrow at 9:30 AM ET
            tomorrow = now + timedelta(days=1)
            next_open = tomorrow.replace(hour=14, minute=30, second=0, microsecond=0)  # 9:30 AM ET = 2:30 PM UTC
        else:
            # Market is open, next close is today at 4:00 PM ET
            next_close = now.replace(hour=21, minute=0, second=0, microsecond=0)  # 4:00 PM ET = 9:00 PM UTC
        
        return MarketHours(
            is_open=is_open,
            next_open=next_open,
            next_close=next_close,
            timezone="US/Eastern"
        )
    
    async def is_market_open(self) -> bool:
        """Check if market is currently open."""
        now = datetime.now(timezone.utc)
        
        # Convert to ET (UTC-5 or UTC-4 depending on DST)
        # For simplicity, assume ET is UTC-5
        et_time = now - timedelta(hours=5)
        
        # Check if it's a weekday (Monday=0, Sunday=6)
        if et_time.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check time
        market_open = datetime.strptime(self.market_open_time, "%H:%M").time()
        market_close = datetime.strptime(self.market_close_time, "%H:%M").time()
        
        return market_open <= et_time.time() <= market_close
    
    async def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for symbol."""
        if not self.connected:
            raise ConnectionError("Not connected to simulator")
        
        # Return cached price or generate random price
        if symbol in self.price_data:
            return self.price_data[symbol]
        
        # Generate random price between $10-$500
        price = random.uniform(10.0, 500.0)
        self.price_data[symbol] = price
        return price
    
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
            raise ConnectionError("Not connected to simulator")
        
        # Generate mock bars
        bars = []
        current_price = await self.get_latest_price(symbol)
        if not current_price:
            return bars
        
        # Generate bars going backwards from now
        now = datetime.now(timezone.utc)
        bar_count = limit or 100
        
        for i in range(bar_count):
            # Generate random price movement
            change_pct = random.uniform(-0.02, 0.02)  # ±2% change
            new_price = current_price * (1 + change_pct)
            
            # Create OHLC
            high = max(current_price, new_price) * random.uniform(1.0, 1.01)
            low = min(current_price, new_price) * random.uniform(0.99, 1.0)
            open_price = current_price
            close_price = new_price
            
            # Generate volume
            volume = random.randint(1000, 10000)
            
            bar = Bar(
                symbol=symbol,
                timestamp=now - timedelta(minutes=i),
                open=open_price,
                high=high,
                low=low,
                close=close_price,
                volume=volume,
                trade_count=random.randint(10, 100),
                vwap=(high + low + close_price) / 3
            )
            bars.append(bar)
            
            current_price = new_price
        
        return bars
    
    async def get_buying_power(self) -> float:
        """Get available buying power."""
        await self._update_account()
        return self.account.buying_power
    
    async def get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        await self._update_account()
        return self.account.portfolio_value
    
    async def get_commission(self, symbol: str, quantity: float, price: float) -> float:
        """Calculate commission for trade."""
        return self.commission_per_share * quantity + self.commission_per_trade
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get real-time quote (bid/ask)."""
        price = await self.get_latest_price(symbol)
        if price:
            spread = price * 0.001  # 0.1% spread
            return {
                'bid': price - spread / 2,
                'ask': price + spread / 2,
                'spread': spread
            }
        return None
    
    async def _process_order(self, order_id: str):
        """Process order asynchronously."""
        try:
            order = self.orders[order_id]
            
            # Simulate order submission delay
            await asyncio.sleep(self.fill_delay_ms / 1000.0)
            
            # Check if order was cancelled
            if order.status == OrderStatus.CANCELLED:
                return
            
            # Update status to submitted
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now(timezone.utc)
            order.updated_at = datetime.now(timezone.utc)
            
            # Get current price
            current_price = await self.get_latest_price(order.symbol)
            if not current_price:
                order.status = OrderStatus.REJECTED
                order.updated_at = datetime.now(timezone.utc)
                return
            
            # Calculate fill price with slippage
            fill_price = await self._calculate_fill_price(order, current_price)
            
            # Check if order should be filled
            should_fill = await self._should_fill_order(order, fill_price)
            
            if should_fill:
                # Fill the order
                await self._fill_order(order, fill_price)
            else:
                # Reject the order
                order.status = OrderStatus.REJECTED
                order.updated_at = datetime.now(timezone.utc)
                
        except Exception as e:
            self.logger.error(f"Error processing order {order_id}: {e}")
            if order_id in self.orders:
                self.orders[order_id].status = OrderStatus.REJECTED
                self.orders[order_id].updated_at = datetime.now(timezone.utc)
    
    async def _calculate_fill_price(self, order: Order, current_price: float) -> float:
        """Calculate fill price with slippage."""
        if order.order_type == OrderType.MARKET:
            # Market orders get filled at current price with slippage
            slippage = current_price * (self.slippage_bps / 10000)
            if order.side == OrderSide.BUY:
                return current_price + slippage
            else:
                return current_price - slippage
        
        elif order.order_type == OrderType.LIMIT:
            # Limit orders get filled at limit price if favorable
            if order.side == OrderSide.BUY and order.limit_price >= current_price:
                return order.limit_price
            elif order.side == OrderSide.SELL and order.limit_price <= current_price:
                return order.limit_price
            else:
                return current_price
        
        else:
            # Other order types use current price
            return current_price
    
    async def _should_fill_order(self, order: Order, fill_price: float) -> bool:
        """Determine if order should be filled."""
        if order.order_type == OrderType.MARKET:
            return True
        
        elif order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY:
                return order.limit_price >= fill_price
            else:
                return order.limit_price <= fill_price
        
        else:
            # For now, fill all other order types
            return True
    
    async def _fill_order(self, order: Order, fill_price: float):
        """Fill the order and update positions."""
        try:
            # Calculate commission
            commission = await self.get_commission(order.symbol, order.quantity, fill_price)
            
            # Update order
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.remaining_quantity = 0.0
            order.average_fill_price = fill_price
            order.filled_at = datetime.now(timezone.utc)
            order.updated_at = datetime.now(timezone.utc)
            
            # Update position
            await self._update_position(order, fill_price, commission)
            
            self.logger.info(f"Filled order {order.order_id}: {order.side.value} {order.quantity} {order.symbol} @ ${fill_price:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error filling order {order.order_id}: {e}")
            order.status = OrderStatus.REJECTED
            order.updated_at = datetime.now(timezone.utc)
    
    async def _update_position(self, order: Order, fill_price: float, commission: float):
        """Update position after order fill."""
        symbol = order.symbol
        quantity = order.quantity
        side = order.side
        
        if symbol in self.positions:
            position = self.positions[symbol]
        else:
            position = Position(
                symbol=symbol,
                quantity=0.0,
                side='long',
                market_value=0.0,
                cost_basis=0.0,
                unrealized_pl=0.0,
                unrealized_plpc=0.0,
                current_price=fill_price,
                lastday_price=fill_price,
                change_today=0.0,
                change_today_percent=0.0,
                avg_entry_price=0.0,
                qty_available=0.0,
                qty_held_for_sells=0.0,
                qty_held_for_buys=0.0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            self.positions[symbol] = position
        
        # Update position
        if side == OrderSide.BUY:
            # Buying shares
            if position.quantity >= 0:
                # Adding to long position
                new_quantity = position.quantity + quantity
                new_cost_basis = (position.cost_basis * position.quantity + fill_price * quantity) / new_quantity
                position.quantity = new_quantity
                position.cost_basis = new_cost_basis
            else:
                # Covering short position
                if quantity <= abs(position.quantity):
                    # Partial cover
                    position.quantity += quantity
                else:
                    # Full cover + new long position
                    excess = quantity - abs(position.quantity)
                    position.quantity = excess
                    position.cost_basis = fill_price
        else:
            # Selling shares
            if position.quantity <= 0:
                # Adding to short position
                new_quantity = position.quantity - quantity
                new_cost_basis = (position.cost_basis * abs(position.quantity) + fill_price * quantity) / abs(new_quantity)
                position.quantity = new_quantity
                position.cost_basis = new_cost_basis
            else:
                # Reducing long position
                if quantity <= position.quantity:
                    # Partial sale
                    position.quantity -= quantity
                else:
                    # Full sale + new short position
                    excess = quantity - position.quantity
                    position.quantity = -excess
                    position.cost_basis = fill_price
        
        # Update position metadata
        position.updated_at = datetime.now(timezone.utc)
        position.current_price = fill_price
        
        # Remove position if quantity is zero
        if position.quantity == 0:
            del self.positions[symbol]
    
    async def _update_account(self):
        """Update account values based on current positions."""
        # Calculate portfolio value
        portfolio_value = self.account.cash
        long_market_value = 0.0
        short_market_value = 0.0
        
        for position in self.positions.values():
            current_price = await self.get_latest_price(position.symbol)
            if current_price:
                position.current_price = current_price
                market_value = current_price * position.quantity
                position.market_value = market_value
                
                if position.quantity > 0:
                    long_market_value += market_value
                    position.unrealized_pl = market_value - (position.cost_basis * position.quantity)
                else:
                    short_market_value += abs(market_value)
                    position.unrealized_pl = (position.cost_basis * abs(position.quantity)) - abs(market_value)
                
                if position.cost_basis > 0:
                    position.unrealized_plpc = position.unrealized_pl / (position.cost_basis * abs(position.quantity))
        
        # Update account
        self.account.portfolio_value = portfolio_value + long_market_value - short_market_value
        self.account.equity = self.account.portfolio_value
        self.account.long_market_value = long_market_value
        self.account.short_market_value = short_market_value
        self.account.buying_power = self.account.cash
        self.account.updated_at = datetime.now(timezone.utc)
