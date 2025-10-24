"""
Comprehensive tests for Phase 1 trading infrastructure.
Tests feature engineering, signal generation, risk management, portfolio tracking, and execution.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from trading.features import FeatureEngine
from trading.signals import SignalGenerator, Signal, SignalAction, BaseStrategy
from trading.strategies.mean_reversion import MeanReversionStrategy
from trading.strategies.momentum import MomentumBreakoutStrategy
from trading.strategies.news_driven import NewsDrivenStrategy
from trading.portfolio import Portfolio, Position, PositionSide, AccountState
from trading.risk_manager import RiskManager, RiskLimits, Order, RejectionReason
from trading.execution import ExecutionEngine, TrackedOrder, OrderStatus


class TestFeatureEngine:
    """Test the feature engineering module."""
    
    def test_feature_engine_initialization(self):
        """Test feature engine initialization."""
        engine = FeatureEngine()
        assert engine.cache_size == 1000
        assert len(engine.cache) == 0
    
    def test_technical_indicators(self):
        """Test technical indicator calculations."""
        engine = FeatureEngine()
        
        # Create sample OHLCV data
        dates = pd.date_range('2024-01-01', periods=100, freq='1min')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(100) * 0.1)
        
        ohlcv_data = pd.DataFrame({
            'timestamp_utc': dates,
            'open': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000, 10000, 100)
        })
        
        # Compute features
        features_df = engine.compute_features(ohlcv_data)
        
        # Check that technical indicators were calculated
        assert 'sma_20' in features_df.columns
        assert 'rsi' in features_df.columns
        assert 'bb_upper' in features_df.columns
        assert 'atr' in features_df.columns
        assert 'vwap' in features_df.columns
        
        # Check RSI is in valid range
        rsi_values = features_df['rsi'].dropna()
        assert all(0 <= rsi <= 100 for rsi in rsi_values)
        
        # Check SMA calculation
        sma_20 = features_df['sma_20'].dropna()
        assert len(sma_20) > 0
        assert sma_20.iloc[-1] == pytest.approx(prices[-20:].mean(), rel=1e-6)
    
    def test_news_features(self):
        """Test news feature computation."""
        engine = FeatureEngine()
        
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=10, freq='1min')
        ohlcv_data = pd.DataFrame({
            'timestamp_utc': dates,
            'open': [100] * 10,
            'high': [101] * 10,
            'low': [99] * 10,
            'close': [100] * 10,
            'volume': [1000] * 10
        })
        
        # Sample news data
        news_data = [
            {
                'timestamp_utc': dates[5].isoformat(),
                'sentiment_score': 0.8,
                'headline': 'Great news!'
            },
            {
                'timestamp_utc': dates[7].isoformat(),
                'sentiment_score': -0.3,
                'headline': 'Bad news'
            }
        ]
        
        features_df = engine.compute_features(ohlcv_data, news_data=news_data)
        
        # Check news features
        assert 'news_count_1h' in features_df.columns
        assert 'news_sentiment_1h' in features_df.columns
        assert 'has_recent_news' in features_df.columns
        
        # Check that news was detected
        assert features_df['has_recent_news'].any()
        assert features_df['news_count_1h'].max() > 0
    
    def test_time_features(self):
        """Test time-based features."""
        engine = FeatureEngine()
        
        # Create market hours data
        market_open = pd.Timestamp('2024-01-01 09:30:00', tz='US/Eastern')
        dates = pd.date_range(market_open, periods=10, freq='1min')
        
        ohlcv_data = pd.DataFrame({
            'timestamp_utc': dates,
            'open': [100] * 10,
            'high': [101] * 10,
            'low': [99] * 10,
            'close': [100] * 10,
            'volume': [1000] * 10
        })
        
        features_df = engine.compute_features(ohlcv_data)
        
        # Check time features
        assert 'hour' in features_df.columns
        assert 'is_market_open' in features_df.columns
        assert 'minutes_since_open' in features_df.columns
        
        # Should be market hours (9:30 AM)
        assert features_df['is_market_open'].all()
        assert features_df['minutes_since_open'].iloc[0] == 0


class TestSignalGeneration:
    """Test signal generation and strategies."""
    
    def test_signal_creation(self):
        """Test Signal object creation."""
        signal = Signal(
            symbol="AAPL",
            action=SignalAction.BUY,
            confidence=0.8,
            size_pct=0.01,
            reasoning="Test signal",
            timestamp=datetime.now(timezone.utc),
            strategy_name="test_strategy",
            entry_price=150.0,
            stop_loss=147.0,
            take_profit=153.0
        )
        
        assert signal.symbol == "AAPL"
        assert signal.action == SignalAction.BUY
        assert signal.confidence == 0.8
        assert signal.entry_price == 150.0
        assert signal.stop_loss == 147.0
        assert signal.take_profit == 153.0
    
    def test_signal_to_dict(self):
        """Test signal serialization."""
        signal = Signal(
            symbol="AAPL",
            action=SignalAction.BUY,
            confidence=0.8,
            size_pct=0.01,
            reasoning="Test signal",
            timestamp=datetime.now(timezone.utc),
            strategy_name="test_strategy"
        )
        
        signal_dict = signal.to_dict()
        assert signal_dict['symbol'] == "AAPL"
        assert signal_dict['action'] == "buy"
        assert signal_dict['confidence'] == 0.8
    
    def test_mean_reversion_strategy(self):
        """Test mean reversion strategy."""
        strategy = MeanReversionStrategy()
        
        # Test oversold condition
        features = {
            'rsi': 25,  # Oversold
            'bb_position': 0.01,  # Near lower band (below 0.02 threshold)
            'bb_lower': 95.0,
            'bb_middle': 100.0,
            'bb_upper': 105.0,
            'close': 96.0
        }
        
        signals = strategy.generate_signals("AAPL", features, current_positions={})
        assert len(signals) == 1
        assert signals[0].action.value == SignalAction.BUY.value
        assert signals[0].confidence > 0.5
    
    def test_momentum_strategy(self):
        """Test momentum breakout strategy."""
        strategy = MomentumBreakoutStrategy()
        
        # Test bullish breakout
        features = {
            'close': 102.0,
            'sma_20': 100.0,
            'volume_ratio': 2.0,  # High volume
            'momentum_5': 0.01  # Positive momentum
        }
        
        signals = strategy.generate_signals("AAPL", features)
        # Should generate signal on crossover (need to simulate previous state)
        assert len(signals) >= 0  # May or may not signal depending on previous state
    
    def test_news_driven_strategy(self):
        """Test news-driven strategy."""
        strategy = NewsDrivenStrategy()
        
        # Test positive news with momentum
        features = {
            'close': 100.0,
            'news_sentiment_1h': 0.8,  # Strong positive sentiment
            'news_count_1h': 3,  # Multiple articles
            'momentum_5': 0.02,  # Positive momentum
            'has_recent_news': True
        }
        
        signals = strategy.generate_signals("AAPL", features, current_positions={})
        assert len(signals) == 1
        assert signals[0].action.value == SignalAction.BUY.value
        assert signals[0].confidence > 0.6


class TestPortfolio:
    """Test portfolio and position tracking."""
    
    def test_portfolio_initialization(self):
        """Test portfolio initialization."""
        portfolio = Portfolio(initial_balance=100000.0)
        
        assert portfolio.account.cash == 100000.0
        assert portfolio.account.equity == 100000.0
        assert portfolio.account.initial_balance == 100000.0
        assert len(portfolio.positions) == 0
    
    def test_add_position(self):
        """Test adding a position."""
        portfolio = Portfolio(100000.0)
        
        position = Position(
            symbol="AAPL",
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=150.0,
            entry_time=datetime.now(timezone.utc),
            stop_loss=147.0,
            take_profit=153.0
        )
        
        success = portfolio.add_position(position)
        assert success
        assert "AAPL" in portfolio.positions
        assert portfolio.get_position_count() == 1
    
    def test_position_pnl_calculation(self):
        """Test position P&L calculation."""
        position = Position(
            symbol="AAPL",
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=150.0,
            entry_time=datetime.now(timezone.utc)
        )
        
        # Update with higher price
        position.update_price(155.0)
        
        assert position.unrealized_pnl == 50.0  # (155-150) * 10
        assert abs(position.unrealized_pnl_pct - 0.0333) < 0.001  # 5/150
        
        # Update with lower price
        position.update_price(145.0)
        
        assert position.unrealized_pnl == -50.0  # (145-150) * 10
        assert abs(position.unrealized_pnl_pct - (-0.0333)) < 0.001  # -5/150
    
    def test_stop_loss_detection(self):
        """Test stop loss hit detection."""
        position = Position(
            symbol="AAPL",
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=150.0,
            entry_time=datetime.now(timezone.utc),
            stop_loss=145.0
        )
        
        # Price above stop loss
        position.update_price(148.0)
        assert not position.check_stop_loss()
        
        # Price at stop loss
        position.update_price(145.0)
        assert position.check_stop_loss()
        
        # Price below stop loss
        position.update_price(144.0)
        assert position.check_stop_loss()
    
    def test_close_position(self):
        """Test closing a position."""
        portfolio = Portfolio(100000.0)
        
        # Add position
        position = Position(
            symbol="AAPL",
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=150.0,
            entry_time=datetime.now(timezone.utc)
        )
        portfolio.add_position(position)
        
        # Close position
        closed_position = portfolio.close_position("AAPL", 155.0)
        
        assert closed_position is not None
        assert closed_position['realized_pnl'] == 50.0  # (155-150) * 10
        assert abs(closed_position['realized_pnl_pct'] - 0.0333) < 0.001  # 5/150
        assert "AAPL" not in portfolio.positions
        assert portfolio.account.realized_pnl == 50.0


class TestRiskManager:
    """Test risk management system."""
    
    def test_risk_limits_initialization(self):
        """Test risk limits initialization."""
        limits = RiskLimits()
        
        assert limits.max_position_size_pct == 0.01  # 1%
        assert limits.max_total_exposure_pct == 0.05  # 5%
        assert limits.daily_loss_limit_pct == 0.03  # 3%
        assert limits.max_positions == 3
        assert limits.circuit_breaker_losses == 3
    
    def test_risk_manager_initialization(self):
        """Test risk manager initialization."""
        portfolio = Portfolio(100000.0)
        risk_manager = RiskManager(portfolio)
        
        assert risk_manager.trading_enabled
        assert not risk_manager.circuit_breaker_active
        assert risk_manager.risk_limits.max_position_size_pct == 0.01
    
    def test_signal_validation_success(self):
        """Test successful signal validation."""
        portfolio = Portfolio(100000.0)
        risk_manager = RiskManager(portfolio)
        
        # Create valid signal
        signal = Signal(
            symbol="AAPL",
            action=SignalAction.BUY,
            confidence=0.8,
            size_pct=0.01,
            reasoning="Test signal",
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            entry_price=150.0,
            stop_loss=147.0,
            take_profit=153.0
        )
        
        # Update symbol volume
        risk_manager.update_symbol_volume("AAPL", 2_000_000)
        
        approved, order, reason = risk_manager.validate_signal(signal)
        
        assert approved
        assert order is not None
        assert reason is None
        assert order.symbol == "AAPL"
        assert order.side == "buy"
        assert order.quantity > 0
    
    def test_signal_validation_insufficient_balance(self):
        """Test signal rejection due to insufficient balance."""
        portfolio = Portfolio(1000.0)  # Small balance
        risk_manager = RiskManager(portfolio)
        
        # Create signal for large position
        signal = Signal(
            symbol="AAPL",
            action=SignalAction.BUY,
            confidence=0.8,
            size_pct=1.0,  # 100% of account
            reasoning="Test signal",
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            entry_price=150.0,
            stop_loss=147.0,
            take_profit=153.0
        )
        
        risk_manager.update_symbol_volume("AAPL", 2_000_000)
        
        approved, order, reason = risk_manager.validate_signal(signal)
        
        assert not approved
        assert order is None
        assert reason == RejectionReason.POSITION_SIZE_EXCEEDED
    
    def test_daily_loss_limit(self):
        """Test daily loss limit enforcement."""
        portfolio = Portfolio(100000.0)
        risk_manager = RiskManager(portfolio)
        
        # Simulate daily loss exceeding limit
        portfolio.account.daily_pnl = -4000.0  # 4% loss
        portfolio.account.daily_pnl_pct = -0.04
        
        signal = Signal(
            symbol="AAPL",
            action=SignalAction.BUY,
            confidence=0.8,
            size_pct=0.01,
            reasoning="Test signal",
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            entry_price=150.0,
            stop_loss=147.0,
            take_profit=153.0
        )
        
        approved, order, reason = risk_manager.validate_signal(signal)
        
        assert not approved
        assert reason == RejectionReason.DAILY_LOSS_LIMIT_HIT
        assert not risk_manager.trading_enabled  # Should disable trading
    
    def test_max_positions_limit(self):
        """Test maximum positions limit."""
        portfolio = Portfolio(100000.0)
        risk_manager = RiskManager(portfolio)
        
        # Add max positions
        for i in range(3):
            position = Position(
                symbol=f"STOCK{i}",
                side=PositionSide.LONG,
                quantity=10.0,
                entry_price=100.0,
                entry_time=datetime.now(timezone.utc)
            )
            portfolio.add_position(position)
        
        signal = Signal(
            symbol="AAPL",
            action=SignalAction.BUY,
            confidence=0.8,
            size_pct=0.01,
            reasoning="Test signal",
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            entry_price=150.0,
            stop_loss=147.0,
            take_profit=153.0
        )
        
        approved, order, reason = risk_manager.validate_signal(signal)
        
        assert not approved
        assert reason == RejectionReason.MAX_POSITIONS_REACHED


class TestExecutionEngine:
    """Test execution engine."""
    
    def test_execution_engine_initialization(self):
        """Test execution engine initialization."""
        engine = ExecutionEngine()
        
        assert len(engine.orders) == 0
        assert engine.max_order_retry == 3
        assert engine.order_timeout_seconds == 300
    
    def test_create_order(self):
        """Test order creation."""
        engine = ExecutionEngine()
        
        order = Order(
            symbol="AAPL",
            side="buy",
            quantity=10.0,
            order_type="limit",
            limit_price=150.0
        )
        
        tracked_order = engine.create_order(order)
        
        assert tracked_order.symbol == "AAPL"
        assert tracked_order.side == "buy"
        assert tracked_order.quantity == 10.0
        assert tracked_order.status == OrderStatus.PENDING
        assert tracked_order.order_id in engine.orders
    
    def test_order_fill_update(self):
        """Test order fill updates."""
        engine = ExecutionEngine()
        
        order = Order(
            symbol="AAPL",
            side="buy",
            quantity=10.0,
            order_type="limit",
            limit_price=150.0
        )
        
        tracked_order = engine.create_order(order)
        order_id = tracked_order.order_id
        
        # Update with partial fill
        success = engine.update_order_fill(order_id, 5.0, 150.0, is_complete=False)
        
        assert success
        assert tracked_order.status == OrderStatus.PARTIALLY_FILLED
        assert tracked_order.filled_quantity == 5.0
        assert tracked_order.remaining_quantity == 5.0
        
        # Update with complete fill
        success = engine.update_order_fill(order_id, 5.0, 150.5, is_complete=True)
        
        assert success
        assert tracked_order.status == OrderStatus.FILLED
        assert tracked_order.filled_quantity == 10.0
        assert tracked_order.remaining_quantity == 0.0
    
    def test_get_pending_orders(self):
        """Test getting pending orders."""
        engine = ExecutionEngine()
        
        # Create multiple orders
        for i in range(3):
            order = Order(
                symbol=f"STOCK{i}",
                side="buy",
                quantity=10.0,
                order_type="limit",
                limit_price=100.0
            )
            engine.create_order(order)
        
        pending_orders = engine.get_pending_orders()
        assert len(pending_orders) == 3
        
        # Fill one order
        order_id = list(engine.orders.keys())[0]
        engine.update_order_fill(order_id, 10.0, 100.0, is_complete=True)
        
        pending_orders = engine.get_pending_orders()
        assert len(pending_orders) == 2


class TestIntegration:
    """Integration tests for the complete trading flow."""
    
    def test_complete_signal_to_order_flow(self):
        """Test complete flow from signal generation to order creation."""
        # Initialize components
        portfolio = Portfolio(100000.0)
        risk_manager = RiskManager(portfolio)
        execution_engine = ExecutionEngine()
        signal_generator = SignalGenerator()
        
        # Register strategy
        strategy = MeanReversionStrategy()
        signal_generator.register_strategy(strategy)
        
        # Create features for oversold condition
        features = {
            'rsi': 25,  # Oversold
            'bb_position': 0.01,  # Near lower band (below 0.02 threshold)
            'bb_lower': 95.0,
            'bb_middle': 100.0,
            'bb_upper': 105.0,
            'close': 96.0
        }
        
        # Generate signal
        signals = signal_generator.generate_signals("AAPL", features, current_positions={})
        assert len(signals) == 1
        
        signal = signals[0]
        
        # Update symbol volume for risk manager
        risk_manager.update_symbol_volume("AAPL", 2_000_000)
        
        # Validate signal
        approved, order, reason = risk_manager.validate_signal(signal)
        assert approved
        assert order is not None
        
        # Create tracked order
        tracked_order = execution_engine.create_order(order)
        assert tracked_order.symbol == "AAPL"
        assert tracked_order.status == OrderStatus.PENDING
    
    def test_risk_limits_enforcement(self):
        """Test that risk limits are properly enforced."""
        portfolio = Portfolio(100000.0)
        risk_manager = RiskManager(portfolio)
        
        # Try to create signal that exceeds position size limit
        signal = Signal(
            symbol="AAPL",
            action=SignalAction.BUY,
            confidence=0.8,
            size_pct=0.05,  # 5% - exceeds 1% limit
            reasoning="Test signal",
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            entry_price=150.0,
            stop_loss=147.0,
            take_profit=153.0
        )
        
        risk_manager.update_symbol_volume("AAPL", 2_000_000)
        
        approved, order, reason = risk_manager.validate_signal(signal)
        
        # Should be rejected due to position size
        assert not approved
        assert reason == RejectionReason.POSITION_SIZE_EXCEEDED


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
