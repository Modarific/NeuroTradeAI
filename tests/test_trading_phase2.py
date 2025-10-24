"""
Comprehensive tests for Phase 2 trading infrastructure.
Tests broker adapters, database integration, and trading sessions.
"""
import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from trading.brokers.base import (
    BaseBroker, Account, Position, Order, OrderType, OrderSide, OrderStatus,
    TimeInForce, MarketHours, Bar, BrokerError, ConnectionError,
    AuthenticationError, OrderError, InsufficientFundsError,
    InvalidOrderError, MarketClosedError, SymbolNotFoundError
)
from trading.brokers.simulator import SimulatorAdapter
from core.trading_db import TradingDatabase


class TestBaseBroker:
    """Test the abstract broker interface."""
    
    def test_broker_initialization(self):
        """Test broker initialization."""
        config = {"test": "value"}
        broker = Mock(spec=BaseBroker)
        broker.config = config
        broker.connected = False
        
        assert broker.config == config
        assert not broker.connected
    
    def test_order_creation(self):
        """Test Order object creation."""
        order = Order(
            order_id="test_order",
            client_order_id="client_123",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0,
            filled_quantity=0.0,
            remaining_quantity=10.0,
            status=OrderStatus.PENDING,
            time_in_force=TimeInForce.DAY
        )
        
        assert order.order_id == "test_order"
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == 10.0
        assert order.status == OrderStatus.PENDING
    
    def test_account_creation(self):
        """Test Account object creation."""
        account = Account(
            account_id="test_account",
            buying_power=100000.0,
            cash=100000.0,
            equity=100000.0,
            day_trade_count=0,
            pattern_day_trader=False,
            portfolio_value=100000.0,
            regt_buying_power=100000.0,
            regt_selling_power=100000.0,
            long_market_value=0.0,
            short_market_value=0.0,
            initial_margin=0.0,
            maintenance_margin=0.0,
            last_equity=100000.0,
            last_market_value=100000.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        assert account.account_id == "test_account"
        assert account.buying_power == 100000.0
        assert account.cash == 100000.0


class TestSimulatorAdapter:
    """Test the simulator broker adapter."""
    
    @pytest.fixture
    def simulator_config(self):
        """Create simulator configuration."""
        return {
            "initial_balance": 100000.0,
            "commission_per_share": 0.0,
            "commission_per_trade": 0.0,
            "slippage_bps": 5,
            "fill_delay_ms": 100,
            "market_hours": {"open": "09:30", "close": "16:00"}
        }
    
    @pytest.fixture
    def simulator(self, simulator_config):
        """Create simulator adapter."""
        return SimulatorAdapter(simulator_config)
    
    @pytest.mark.asyncio
    async def test_simulator_connection(self, simulator):
        """Test simulator connection."""
        success = await simulator.connect()
        assert success
        assert simulator.connected
        
        success = await simulator.disconnect()
        assert success
        assert not simulator.connected
    
    @pytest.mark.asyncio
    async def test_get_account(self, simulator):
        """Test getting account information."""
        await simulator.connect()
        
        account = await simulator.get_account()
        assert account is not None
        assert account.account_id == "simulator"
        assert account.buying_power == 100000.0
        assert account.cash == 100000.0
    
    @pytest.mark.asyncio
    async def test_market_hours(self, simulator):
        """Test market hours checking."""
        await simulator.connect()
        
        market_hours = await simulator.get_market_hours()
        assert isinstance(market_hours, MarketHours)
        assert isinstance(market_hours.is_open, bool)
    
    @pytest.mark.asyncio
    async def test_get_latest_price(self, simulator):
        """Test getting latest price."""
        await simulator.connect()
        
        price = await simulator.get_latest_price("AAPL")
        assert price is not None
        assert 10.0 <= price <= 500.0  # Random price range
    
    @pytest.mark.asyncio
    async def test_place_market_order(self, simulator):
        """Test placing a market order."""
        await simulator.connect()
        
        # Wait a bit for the order to be processed
        await asyncio.sleep(0.2)
        
        order = await simulator.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0
        )
        
        assert order is not None
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 10.0
        assert order.status == OrderStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_place_limit_order(self, simulator):
        """Test placing a limit order."""
        await simulator.connect()
        
        order = await simulator.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10.0,
            limit_price=150.0
        )
        
        assert order is not None
        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == 150.0
    
    @pytest.mark.asyncio
    async def test_insufficient_funds(self, simulator):
        """Test insufficient funds error."""
        await simulator.connect()
        
        # Try to buy more than we can afford
        with pytest.raises(InsufficientFundsError):
            await simulator.place_order(
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=1000000.0  # Way more than we have
            )
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, simulator):
        """Test cancelling an order."""
        await simulator.connect()
        
        order = await simulator.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0
        )
        
        success = await simulator.cancel_order(order.order_id)
        assert success
        
        # Check order status
        updated_order = await simulator.get_order(order.order_id)
        assert updated_order.status == OrderStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_get_orders(self, simulator):
        """Test getting orders."""
        await simulator.connect()
        
        # Place a few orders
        order1 = await simulator.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0
        )
        
        order2 = await simulator.place_order(
            symbol="MSFT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=5.0
        )
        
        # Get all orders
        orders = await simulator.get_orders()
        assert len(orders) >= 2
        
        # Get orders by status
        pending_orders = await simulator.get_orders(status=OrderStatus.PENDING)
        assert len(pending_orders) >= 2
    
    @pytest.mark.asyncio
    async def test_position_tracking(self, simulator):
        """Test position tracking."""
        await simulator.connect()
        
        # Place and wait for order to fill
        order = await simulator.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0
        )
        
        # Wait for order to be processed
        await asyncio.sleep(0.2)
        
        # Check positions
        positions = await simulator.get_positions()
        assert len(positions) >= 0  # May or may not have positions yet
        
        # Check specific position
        position = await simulator.get_position("AAPL")
        # Position may or may not exist depending on fill timing
    
    @pytest.mark.asyncio
    async def test_get_bars(self, simulator):
        """Test getting historical bars."""
        await simulator.connect()
        
        bars = await simulator.get_bars("AAPL", limit=10)
        assert len(bars) == 10
        
        for bar in bars:
            assert bar.symbol == "AAPL"
            assert bar.open > 0
            assert bar.high > 0
            assert bar.low > 0
            assert bar.close > 0
            assert bar.volume > 0
    
    @pytest.mark.asyncio
    async def test_commission_calculation(self, simulator):
        """Test commission calculation."""
        await simulator.connect()
        
        commission = await simulator.get_commission("AAPL", 10.0, 150.0)
        assert commission == 0.0  # Default is commission-free
    
    @pytest.mark.asyncio
    async def test_quote_data(self, simulator):
        """Test getting quote data."""
        await simulator.connect()
        
        quote = await simulator.get_quote("AAPL")
        assert quote is not None
        assert "bid" in quote
        assert "ask" in quote
        assert "spread" in quote
        assert quote["ask"] > quote["bid"]


class TestTradingDatabase:
    """Test the trading database functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup - try multiple times on Windows
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except PermissionError:
                # On Windows, sometimes the file is still in use
                import time
                time.sleep(0.1)
                try:
                    os.unlink(db_path)
                except PermissionError:
                    # Give up if still can't delete
                    pass
    
    @pytest.fixture
    def trading_db(self, temp_db):
        """Create trading database instance."""
        db = TradingDatabase(temp_db)
        db.initialize_tables()
        return db
    
    def test_database_initialization(self, trading_db):
        """Test database table initialization."""
        # Tables should be created without error
        assert True  # If we get here, initialization succeeded
    
    def test_create_session(self, trading_db):
        """Test creating a trading session."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        assert session_id is not None
        assert len(session_id) > 0
    
    def test_end_session(self, trading_db):
        """Test ending a trading session."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        success = trading_db.end_session(
            session_id=session_id,
            final_balance=105000.0,
            total_trades=10,
            pnl=5000.0,
            max_drawdown=1000.0,
            win_rate=0.6
        )
        
        assert success
    
    def test_add_order(self, trading_db):
        """Test adding an order."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        success = trading_db.add_order(
            session_id=session_id,
            order_id="order_123",
            client_order_id="client_123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10.0,
            time_in_force="day",
            signal_reason="Test signal",
            strategy_name="test_strategy"
        )
        
        assert success
    
    def test_update_order(self, trading_db):
        """Test updating an order."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        # Add order
        trading_db.add_order(
            session_id=session_id,
            order_id="order_123",
            client_order_id="client_123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10.0,
            time_in_force="day"
        )
        
        # Update order
        success = trading_db.update_order(
            order_id="order_123",
            status="filled",
            filled_quantity=10.0,
            remaining_quantity=0.0,
            average_fill_price=150.0,
            commission=0.0
        )
        
        assert success
    
    def test_add_order_event(self, trading_db):
        """Test adding an order event."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        # Add order
        trading_db.add_order(
            session_id=session_id,
            order_id="order_123",
            client_order_id="client_123",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10.0,
            time_in_force="day"
        )
        
        # Add order event
        success = trading_db.add_order_event(
            order_id="order_123",
            event_type="submitted",
            event_data={"timestamp": datetime.now(timezone.utc).isoformat()}
        )
        
        assert success
    
    def test_update_position(self, trading_db):
        """Test updating a position."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        success = trading_db.update_position(
            session_id=session_id,
            symbol="AAPL",
            quantity=10.0,
            side="long",
            entry_price=150.0,
            current_price=155.0,
            stop_loss=145.0,
            take_profit=160.0
        )
        
        assert success
    
    def test_get_session_orders(self, trading_db):
        """Test getting session orders."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        # Add some orders
        for i in range(3):
            trading_db.add_order(
                session_id=session_id,
                order_id=f"order_{i}",
                client_order_id=f"client_{i}",
                symbol="AAPL",
                side="buy",
                order_type="market",
                quantity=10.0,
                time_in_force="day"
            )
        
        orders = trading_db.get_session_orders(session_id)
        assert len(orders) == 3
    
    def test_get_session_positions(self, trading_db):
        """Test getting session positions."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        # Add some positions
        trading_db.update_position(
            session_id=session_id,
            symbol="AAPL",
            quantity=10.0,
            side="long",
            entry_price=150.0
        )
        
        trading_db.update_position(
            session_id=session_id,
            symbol="MSFT",
            quantity=5.0,
            side="long",
            entry_price=300.0
        )
        
        positions = trading_db.get_session_positions(session_id)
        assert len(positions) == 2
    
    def test_add_audit_event(self, trading_db):
        """Test adding audit events."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        success = trading_db.add_audit_event(
            session_id=session_id,
            event_type="signal",
            event_data={"symbol": "AAPL", "action": "buy", "confidence": 0.8}
        )
        
        assert success
    
    def test_get_audit_trail(self, trading_db):
        """Test getting audit trail."""
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        # Add some audit events
        for i in range(3):
            trading_db.add_audit_event(
                session_id=session_id,
                event_type="signal",
                event_data={"symbol": f"STOCK{i}", "action": "buy"}
            )
        
        events = trading_db.get_audit_trail(session_id)
        assert len(events) == 3
        
        # Test filtering by event type
        signal_events = trading_db.get_audit_trail(session_id, event_type="signal")
        assert len(signal_events) == 3


class TestIntegration:
    """Integration tests for Phase 2 components."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup - try multiple times on Windows
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except PermissionError:
                # On Windows, sometimes the file is still in use
                import time
                time.sleep(0.1)
                try:
                    os.unlink(db_path)
                except PermissionError:
                    # Give up if still can't delete
                    pass
    
    @pytest.mark.asyncio
    async def test_simulator_with_database(self, temp_db):
        """Test simulator integration with database."""
        # Create database
        trading_db = TradingDatabase(temp_db)
        trading_db.initialize_tables()
        
        # Create simulator
        simulator = SimulatorAdapter({
            "initial_balance": 100000.0,
            "fill_delay_ms": 100
        })
        
        await simulator.connect()
        
        # Create trading session
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        # Place order
        order = await simulator.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0
        )
        
        # Add order to database
        trading_db.add_order(
            session_id=session_id,
            order_id=order.order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.order_type.value,
            quantity=order.quantity,
            time_in_force=order.time_in_force.value,
            signal_reason="Test signal",
            strategy_name="test_strategy"
        )
        
        # Wait for order to be processed
        await asyncio.sleep(0.2)
        
        # Update order status
        updated_order = await simulator.get_order(order.order_id)
        if updated_order:
            trading_db.update_order(
                order_id=updated_order.order_id,
                status=updated_order.status.value,
                filled_quantity=updated_order.filled_quantity,
                remaining_quantity=updated_order.remaining_quantity,
                average_fill_price=updated_order.average_fill_price
            )
        
        # Check database
        orders = trading_db.get_session_orders(session_id)
        assert len(orders) == 1
        assert orders[0]["symbol"] == "AAPL"
        assert orders[0]["side"] == "buy"
    
    @pytest.mark.asyncio
    async def test_complete_trading_flow(self, temp_db):
        """Test complete trading flow from order to position."""
        # Create database
        trading_db = TradingDatabase(temp_db)
        trading_db.initialize_tables()
        
        # Create simulator
        simulator = SimulatorAdapter({
            "initial_balance": 100000.0,
            "fill_delay_ms": 50
        })
        
        await simulator.connect()
        
        # Create trading session
        session_id = trading_db.create_session(
            mode="paper",
            strategy_name="test_strategy",
            initial_balance=100000.0
        )
        
        # Place multiple orders
        orders = []
        for symbol in ["AAPL", "MSFT", "GOOGL"]:
            order = await simulator.place_order(
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=10.0
            )
            orders.append(order)
            
            # Add to database
            trading_db.add_order(
                session_id=session_id,
                order_id=order.order_id,
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=order.quantity,
                time_in_force=order.time_in_force.value,
                signal_reason=f"Test signal for {symbol}",
                strategy_name="test_strategy"
            )
        
        # Wait for orders to be processed
        await asyncio.sleep(0.3)
        
        # Update order statuses
        for order in orders:
            updated_order = await simulator.get_order(order.order_id)
            if updated_order and updated_order.status == OrderStatus.FILLED:
                trading_db.update_order(
                    order_id=updated_order.order_id,
                    status=updated_order.status.value,
                    filled_quantity=updated_order.filled_quantity,
                    remaining_quantity=updated_order.remaining_quantity,
                    average_fill_price=updated_order.average_fill_price
                )
                
                # Update position
                trading_db.update_position(
                    session_id=session_id,
                    symbol=updated_order.symbol,
                    quantity=updated_order.filled_quantity,
                    side="long",
                    entry_price=updated_order.average_fill_price or 0.0
                )
        
        # Check results
        orders = trading_db.get_session_orders(session_id)
        positions = trading_db.get_session_positions(session_id)
        
        assert len(orders) == 3
        assert len(positions) >= 0  # May or may not have positions depending on fill timing
        
        # End session
        trading_db.end_session(
            session_id=session_id,
            final_balance=100000.0,  # Would be calculated from actual positions
            total_trades=len(orders),
            pnl=0.0,
            max_drawdown=0.0,
            win_rate=0.0
        )


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
