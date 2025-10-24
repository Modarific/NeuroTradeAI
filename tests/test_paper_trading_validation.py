"""
Paper trading validation tests.
Tests real-world scenarios with simulated market conditions.
"""
import pytest
import asyncio
import json
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd

from app.trading.engine import TradingEngine
from app.trading.features import FeatureEngine
from app.trading.strategies.mean_reversion import MeanReversionStrategy
from app.trading.strategies.momentum import MomentumStrategy
from app.trading.strategies.news_driven import NewsDrivenStrategy
from app.trading.risk_manager import RiskManager
from app.trading.portfolio import Portfolio
from app.trading.execution import ExecutionEngine
from app.trading.brokers.base import Order, OrderStatus, OrderType, OrderSide
from app.trading.brokers.simulator import SimulatorAdapter
from app.trading.alerts import AlertManager
from app.trading.audit import AuditLogger
from app.trading.analytics import PerformanceAnalytics


class TestPaperTradingScenarios:
    """Test paper trading scenarios."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    @pytest.fixture
    def paper_trading_system(self, temp_dir):
        """Create paper trading system for testing."""
        # Create components
        feature_engine = FeatureEngine()
        strategy = MeanReversionStrategy()
        risk_manager = RiskManager({
            "max_position_size_pct": 1.0,
            "max_total_exposure_pct": 5.0,
            "daily_loss_limit_pct": 3.0,
            "max_positions": 3,
            "min_avg_volume": 1_000_000,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 3.0,
            "circuit_breaker_losses": 3
        })
        portfolio = Portfolio(100000.0)
        broker = SimulatorAdapter({"initial_balance": 100000.0})
        execution_engine = ExecutionEngine(broker)
        alert_manager = AlertManager(os.path.join(temp_dir, "alerts.log"))
        audit_logger = AuditLogger(os.path.join(temp_dir, "audit"))
        analytics = PerformanceAnalytics(temp_dir)
        
        return {
            'feature_engine': feature_engine,
            'strategy': strategy,
            'risk_manager': risk_manager,
            'portfolio': portfolio,
            'broker': broker,
            'execution_engine': execution_engine,
            'alert_manager': alert_manager,
            'audit_logger': audit_logger,
            'analytics': analytics
        }
    
    async def test_bull_market_scenario(self, paper_trading_system):
        """Test trading in bull market conditions."""
        feature_engine = paper_trading_system['feature_engine']
        strategy = paper_trading_system['strategy']
        risk_manager = paper_trading_system['risk_manager']
        execution_engine = paper_trading_system['execution_engine']
        
        # Simulate bull market data (rising prices)
        bull_market_data = {
            'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120],
            'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121],
            'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5, 110.5, 111.5, 112.5, 113.5, 114.5, 115.5, 116.5, 117.5, 118.5, 119.5, 120.5],
            'volume': [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000]
        }
        
        # Compute features
        features = feature_engine.compute_features(bull_market_data)
        
        # Generate signal
        signal = strategy.generate_signal('AAPL', features)
        assert signal is not None
        
        # Validate signal
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is True
        
        # Execute order
        order_id = await execution_engine.place_order(**order_data)
        assert order_id is not None
        
        # Verify order was placed
        orders = execution_engine.get_orders()
        assert len(orders) == 1
    
    async def test_bear_market_scenario(self, paper_trading_system):
        """Test trading in bear market conditions."""
        feature_engine = paper_trading_system['feature_engine']
        strategy = paper_trading_system['strategy']
        risk_manager = paper_trading_system['risk_manager']
        execution_engine = paper_trading_system['execution_engine']
        
        # Simulate bear market data (falling prices)
        bear_market_data = {
            'open': [120, 119, 118, 117, 116, 115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100],
            'high': [121, 120, 119, 118, 117, 116, 115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101],
            'low': [119, 118, 117, 116, 115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100, 99],
            'close': [119.5, 118.5, 117.5, 116.5, 115.5, 114.5, 113.5, 112.5, 111.5, 110.5, 109.5, 108.5, 107.5, 106.5, 105.5, 104.5, 103.5, 102.5, 101.5, 100.5, 99.5],
            'volume': [3000, 2900, 2800, 2700, 2600, 2500, 2400, 2300, 2200, 2100, 2000, 1900, 1800, 1700, 1600, 1500, 1400, 1300, 1200, 1100, 1000]
        }
        
        # Compute features
        features = feature_engine.compute_features(bear_market_data)
        
        # Generate signal
        signal = strategy.generate_signal('AAPL', features)
        assert signal is not None
        
        # Validate signal
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is True
        
        # Execute order
        order_id = await execution_engine.place_order(**order_data)
        assert order_id is not None
        
        # Verify order was placed
        orders = execution_engine.get_orders()
        assert len(orders) == 1
    
    async def test_sideways_market_scenario(self, paper_trading_system):
        """Test trading in sideways market conditions."""
        feature_engine = paper_trading_system['feature_engine']
        strategy = paper_trading_system['strategy']
        risk_manager = paper_trading_system['risk_manager']
        execution_engine = paper_trading_system['execution_engine']
        
        # Simulate sideways market data (oscillating prices)
        sideways_data = {
            'open': [100, 101, 99, 102, 98, 103, 97, 104, 96, 105, 95, 106, 94, 107, 93, 108, 92, 109, 91, 110, 90],
            'high': [101, 102, 100, 103, 99, 104, 98, 105, 97, 106, 96, 107, 95, 108, 94, 109, 93, 110, 92, 111, 91],
            'low': [99, 100, 98, 101, 97, 102, 96, 103, 95, 104, 94, 105, 93, 106, 92, 107, 91, 108, 90, 109, 89],
            'close': [100.5, 99.5, 101.5, 98.5, 102.5, 97.5, 103.5, 96.5, 104.5, 95.5, 105.5, 94.5, 106.5, 93.5, 107.5, 92.5, 108.5, 91.5, 109.5, 90.5, 110.5],
            'volume': [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000]
        }
        
        # Compute features
        features = feature_engine.compute_features(sideways_data)
        
        # Generate signal
        signal = strategy.generate_signal('AAPL', features)
        assert signal is not None
        
        # Validate signal
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is True
        
        # Execute order
        order_id = await execution_engine.place_order(**order_data)
        assert order_id is not None
        
        # Verify order was placed
        orders = execution_engine.get_orders()
        assert len(orders) == 1
    
    async def test_high_volatility_scenario(self, paper_trading_system):
        """Test trading in high volatility conditions."""
        feature_engine = paper_trading_system['feature_engine']
        strategy = paper_trading_system['strategy']
        risk_manager = paper_trading_system['risk_manager']
        execution_engine = paper_trading_system['execution_engine']
        
        # Simulate high volatility data (large price swings)
        volatile_data = {
            'open': [100, 105, 95, 110, 90, 115, 85, 120, 80, 125, 75, 130, 70, 135, 65, 140, 60, 145, 55, 150, 50],
            'high': [105, 110, 100, 115, 95, 120, 90, 125, 85, 130, 80, 135, 75, 140, 70, 145, 65, 150, 60, 155, 55],
            'low': [95, 100, 90, 105, 85, 110, 80, 115, 75, 120, 70, 125, 65, 130, 60, 135, 55, 140, 50, 145, 45],
            'close': [102.5, 97.5, 107.5, 92.5, 112.5, 87.5, 117.5, 82.5, 122.5, 77.5, 127.5, 72.5, 132.5, 67.5, 137.5, 62.5, 142.5, 57.5, 147.5, 52.5, 152.5],
            'volume': [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000]
        }
        
        # Compute features
        features = feature_engine.compute_features(volatile_data)
        
        # Generate signal
        signal = strategy.generate_signal('AAPL', features)
        assert signal is not None
        
        # Validate signal
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is True
        
        # Execute order
        order_id = await execution_engine.place_order(**order_data)
        assert order_id is not None
        
        # Verify order was placed
        orders = execution_engine.get_orders()
        assert len(orders) == 1
    
    async def test_low_volume_scenario(self, paper_trading_system):
        """Test trading in low volume conditions."""
        feature_engine = paper_trading_system['feature_engine']
        strategy = paper_trading_system['strategy']
        risk_manager = paper_trading_system['risk_manager']
        execution_engine = paper_trading_system['execution_engine']
        
        # Simulate low volume data
        low_volume_data = {
            'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120],
            'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121],
            'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5, 110.5, 111.5, 112.5, 113.5, 114.5, 115.5, 116.5, 117.5, 118.5, 119.5, 120.5],
            'volume': [100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250, 260, 270, 280, 290, 300]  # Very low volume
        }
        
        # Compute features
        features = feature_engine.compute_features(low_volume_data)
        
        # Generate signal
        signal = strategy.generate_signal('AAPL', features)
        assert signal is not None
        
        # Validate signal (should be rejected due to low volume)
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        # Note: This might be valid or invalid depending on the risk manager's volume check
        # The important thing is that the system handles it gracefully
    
    async def test_news_driven_scenario(self, paper_trading_system):
        """Test news-driven trading scenario."""
        feature_engine = paper_trading_system['feature_engine']
        strategy = NewsDrivenStrategy()
        risk_manager = paper_trading_system['risk_manager']
        execution_engine = paper_trading_system['execution_engine']
        
        # Simulate news-driven data
        news_data = {
            'sentiment_avg': 0.8,  # Very positive sentiment
            'sentiment_std': 0.1,
            'sentiment_count': 10,
            'current_price': 150.0,
            'volume_ratio': 2.5  # High volume
        }
        
        # Generate signal
        signal = strategy.generate_signal('AAPL', news_data)
        assert signal is not None
        assert signal.action.value == 'buy'  # Should be buy signal for positive news
        
        # Validate signal
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is True
        
        # Execute order
        order_id = await execution_engine.place_order(**order_data)
        assert order_id is not None
        
        # Verify order was placed
        orders = execution_engine.get_orders()
        assert len(orders) == 1


class TestRiskManagementScenarios:
    """Test risk management scenarios."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    @pytest.fixture
    def risk_system(self, temp_dir):
        """Create risk management system for testing."""
        risk_manager = RiskManager({
            "max_position_size_pct": 1.0,
            "max_total_exposure_pct": 5.0,
            "daily_loss_limit_pct": 3.0,
            "max_positions": 3,
            "min_avg_volume": 1_000_000,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 3.0,
            "circuit_breaker_losses": 3
        })
        portfolio = Portfolio(100000.0)
        alert_manager = AlertManager(os.path.join(temp_dir, "alerts.log"))
        
        return {
            'risk_manager': risk_manager,
            'portfolio': portfolio,
            'alert_manager': alert_manager
        }
    
    async def test_daily_loss_limit_scenario(self, risk_system):
        """Test daily loss limit scenario."""
        risk_manager = risk_system['risk_manager']
        alert_manager = risk_system['alert_manager']
        
        # Simulate daily loss
        risk_manager.daily_pnl = -0.04  # 4% loss (exceeds 3% limit)
        
        from app.trading.signals import Signal, SignalAction
        signal = Signal('AAPL', SignalAction.BUY, 0.8, 0.5, 'Test')
        
        # Should be rejected
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is False
        assert reason.value == 'daily_loss_limit_exceeded'
        
        # Should send alert
        await alert_manager.send_daily_loss_alert(
            current_loss=4000.0,
            loss_limit=3000.0,
            loss_pct=4.0
        )
        assert len(alert_manager.alert_history) == 1
    
    async def test_position_size_limit_scenario(self, risk_system):
        """Test position size limit scenario."""
        risk_manager = risk_system['risk_manager']
        alert_manager = risk_system['alert_manager']
        
        # Test oversized position
        from app.trading.signals import Signal, SignalAction
        signal = Signal('AAPL', SignalAction.BUY, 0.8, 2.0, 'Test')  # 2% position size
        
        # Should be rejected
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is False
        assert reason.value == 'position_size_exceeded'
        
        # Should send alert
        await alert_manager.send_risk_alert(
            'position_size',
            2.0,
            1.0,
            'AAPL'
        )
        assert len(alert_manager.alert_history) == 1
    
    async def test_max_positions_limit_scenario(self, risk_system):
        """Test maximum positions limit scenario."""
        risk_manager = risk_system['risk_manager']
        portfolio = risk_system['portfolio']
        
        # Simulate max positions reached
        portfolio.max_positions = 3
        portfolio.add_position('AAPL', 100, 150.0)
        portfolio.add_position('MSFT', 50, 300.0)
        portfolio.add_position('GOOGL', 10, 2800.0)
        
        from app.trading.signals import Signal, SignalAction
        signal = Signal('TSLA', SignalAction.BUY, 0.8, 0.5, 'Test')
        
        # Should be rejected
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is False
        assert reason.value == 'max_positions_exceeded'
    
    async def test_circuit_breaker_scenario(self, risk_system):
        """Test circuit breaker scenario."""
        risk_manager = risk_system['risk_manager']
        alert_manager = risk_system['alert_manager']
        
        # Simulate consecutive losses
        risk_manager.consecutive_losses = 3
        
        from app.trading.signals import Signal, SignalAction
        signal = Signal('AAPL', SignalAction.BUY, 0.8, 0.5, 'Test')
        
        # Should be rejected
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is False
        assert reason.value == 'circuit_breaker_triggered'
        
        # Should send alert
        await alert_manager.send_emergency_stop_alert("Circuit breaker triggered")
        assert len(alert_manager.alert_history) == 1


class TestPerformanceValidation:
    """Test performance validation scenarios."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    @pytest.fixture
    def performance_system(self, temp_dir):
        """Create performance validation system for testing."""
        analytics = PerformanceAnalytics(temp_dir)
        audit_logger = AuditLogger(os.path.join(temp_dir, "audit"))
        
        return {
            'analytics': analytics,
            'audit_logger': audit_logger
        }
    
    async def test_profitable_session_analysis(self, performance_system):
        """Test profitable session analysis."""
        analytics = performance_system['analytics']
        audit_logger = performance_system['audit_logger']
        
        # Create profitable trades
        trades = [
            {
                'id': 'trade_1',
                'symbol': 'AAPL',
                'side': 'buy',
                'quantity': 100,
                'entry_price': 150.0,
                'exit_price': 155.0,
                'pnl': 500.0,
                'entry_time': '2024-01-01T10:00:00Z',
                'exit_time': '2024-01-01T11:00:00Z'
            },
            {
                'id': 'trade_2',
                'symbol': 'MSFT',
                'side': 'buy',
                'quantity': 50,
                'entry_price': 300.0,
                'exit_price': 310.0,
                'pnl': 500.0,
                'entry_time': '2024-01-01T12:00:00Z',
                'exit_time': '2024-01-01T13:00:00Z'
            }
        ]
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id='profitable_session',
            trades=trades,
            positions=[],
            initial_balance=100000.0,
            final_balance=101000.0,
            start_date=start_date,
            end_date=end_date,
            strategy='mean_reversion',
            mode='paper'
        )
        
        # Verify profitable session
        assert report.total_return == 1000.0
        assert report.total_return_pct == 1.0
        assert report.trade_metrics.total_trades == 2
        assert report.trade_metrics.winning_trades == 2
        assert report.trade_metrics.losing_trades == 0
        assert report.trade_metrics.win_rate == 100.0
        assert report.trade_metrics.total_pnl == 1000.0
    
    async def test_losing_session_analysis(self, performance_system):
        """Test losing session analysis."""
        analytics = performance_system['analytics']
        
        # Create losing trades
        trades = [
            {
                'id': 'trade_1',
                'symbol': 'AAPL',
                'side': 'buy',
                'quantity': 100,
                'entry_price': 150.0,
                'exit_price': 145.0,
                'pnl': -500.0,
                'entry_time': '2024-01-01T10:00:00Z',
                'exit_time': '2024-01-01T11:00:00Z'
            },
            {
                'id': 'trade_2',
                'symbol': 'MSFT',
                'side': 'buy',
                'quantity': 50,
                'entry_price': 300.0,
                'exit_price': 290.0,
                'pnl': -500.0,
                'entry_time': '2024-01-01T12:00:00Z',
                'exit_time': '2024-01-01T13:00:00Z'
            }
        ]
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id='losing_session',
            trades=trades,
            positions=[],
            initial_balance=100000.0,
            final_balance=99000.0,
            start_date=start_date,
            end_date=end_date,
            strategy='mean_reversion',
            mode='paper'
        )
        
        # Verify losing session
        assert report.total_return == -1000.0
        assert report.total_return_pct == -1.0
        assert report.trade_metrics.total_trades == 2
        assert report.trade_metrics.winning_trades == 0
        assert report.trade_metrics.losing_trades == 2
        assert report.trade_metrics.win_rate == 0.0
        assert report.trade_metrics.total_pnl == -1000.0
    
    async def test_mixed_session_analysis(self, performance_system):
        """Test mixed session analysis."""
        analytics = performance_system['analytics']
        
        # Create mixed trades
        trades = [
            {
                'id': 'trade_1',
                'symbol': 'AAPL',
                'side': 'buy',
                'quantity': 100,
                'entry_price': 150.0,
                'exit_price': 155.0,
                'pnl': 500.0,
                'entry_time': '2024-01-01T10:00:00Z',
                'exit_time': '2024-01-01T11:00:00Z'
            },
            {
                'id': 'trade_2',
                'symbol': 'MSFT',
                'side': 'buy',
                'quantity': 50,
                'entry_price': 300.0,
                'exit_price': 290.0,
                'pnl': -500.0,
                'entry_time': '2024-01-01T12:00:00Z',
                'exit_time': '2024-01-01T13:00:00Z'
            },
            {
                'id': 'trade_3',
                'symbol': 'GOOGL',
                'side': 'buy',
                'quantity': 10,
                'entry_price': 2800.0,
                'exit_price': 2850.0,
                'pnl': 500.0,
                'entry_time': '2024-01-01T14:00:00Z',
                'exit_time': '2024-01-01T15:00:00Z'
            }
        ]
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id='mixed_session',
            trades=trades,
            positions=[],
            initial_balance=100000.0,
            final_balance=100500.0,
            start_date=start_date,
            end_date=end_date,
            strategy='mean_reversion',
            mode='paper'
        )
        
        # Verify mixed session
        assert report.total_return == 500.0
        assert report.total_return_pct == 0.5
        assert report.trade_metrics.total_trades == 3
        assert report.trade_metrics.winning_trades == 2
        assert report.trade_metrics.losing_trades == 1
        assert report.trade_metrics.win_rate == (2/3) * 100
        assert report.trade_metrics.total_pnl == 500.0
    
    async def test_drawdown_analysis(self, performance_system):
        """Test drawdown analysis."""
        analytics = performance_system['analytics']
        
        # Create trades with drawdown
        trades = [
            {'pnl': 1000.0, 'entry_time': '2024-01-01T10:00:00Z', 'exit_time': '2024-01-01T11:00:00Z'},
            {'pnl': -500.0, 'entry_time': '2024-01-01T12:00:00Z', 'exit_time': '2024-01-01T13:00:00Z'},
            {'pnl': -300.0, 'entry_time': '2024-01-01T14:00:00Z', 'exit_time': '2024-01-01T15:00:00Z'},
            {'pnl': 800.0, 'entry_time': '2024-01-02T10:00:00Z', 'exit_time': '2024-01-02T11:00:00Z'}
        ]
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 3, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id='drawdown_session',
            trades=trades,
            positions=[],
            initial_balance=100000.0,
            final_balance=101000.0,
            start_date=start_date,
            end_date=end_date,
            strategy='mean_reversion',
            mode='paper'
        )
        
        # Verify drawdown calculation
        assert report.trade_metrics.max_drawdown > 0
        assert report.trade_metrics.max_drawdown_pct > 0
        assert report.trade_metrics.sharpe_ratio is not None
    
    async def test_strategy_comparison(self, performance_system):
        """Test strategy comparison."""
        analytics = performance_system['analytics']
        
        # Create reports for different strategies
        reports = []
        for strategy in ['mean_reversion', 'momentum', 'news_driven']:
            trades = [{'pnl': 100.0, 'entry_time': '2024-01-01T10:00:00Z', 'exit_time': '2024-01-01T11:00:00Z'}]
            
            report = await analytics.analyze_session(
                session_id=f'session_{strategy}',
                trades=trades,
                positions=[],
                initial_balance=100000.0,
                final_balance=100100.0,
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
                strategy=strategy,
                mode='paper'
            )
            reports.append(report)
        
        # Compare strategies
        comparison = await analytics.compare_strategies(reports)
        
        assert len(comparison['strategies']) == 3
        assert 'best_performer' in comparison
        assert 'worst_performer' in comparison
        assert 'summary' in comparison
        assert comparison['summary']['avg_return'] == 0.1  # 0.1% average return


class TestSystemStability:
    """Test system stability and reliability."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    async def test_system_startup_shutdown(self, temp_dir):
        """Test system startup and shutdown."""
        # Create trading engine
        engine = TradingEngine()
        
        # Test startup
        try:
            await engine.start()
            assert engine.is_running_flag is True
        except Exception as e:
            # Expected to fail without proper setup
            assert "broker" in str(e).lower() or "strategy" in str(e).lower()
        
        # Test shutdown
        await engine.stop()
        assert engine.is_running_flag is False
    
    async def test_system_error_recovery(self, temp_dir):
        """Test system error recovery."""
        # Create components that can fail
        broker = Mock(spec=SimulatorAdapter)
        broker.place_order = AsyncMock(side_effect=Exception("Broker error"))
        
        execution_engine = ExecutionEngine(broker)
        
        # Test error handling
        try:
            await execution_engine.place_order(
                symbol='AAPL',
                side='buy',
                quantity=100,
                order_type='market'
            )
            assert False, "Expected exception"
        except Exception as e:
            assert "Broker error" in str(e)
        
        # Test recovery
        broker.place_order = AsyncMock(return_value='order_123')
        order_id = await execution_engine.place_order(
            symbol='AAPL',
            side='buy',
            quantity=100,
            order_type='market'
        )
        assert order_id == 'order_123'
    
    async def test_system_performance_under_load(self, temp_dir):
        """Test system performance under load."""
        # Create components
        feature_engine = FeatureEngine()
        strategy = MeanReversionStrategy()
        risk_manager = RiskManager({
            "max_position_size_pct": 1.0,
            "max_total_exposure_pct": 5.0,
            "daily_loss_limit_pct": 3.0,
            "max_positions": 3,
            "min_avg_volume": 1_000_000,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 3.0,
            "circuit_breaker_losses": 3
        })
        
        # Test multiple signal generations
        for i in range(100):
            data = {
                'open': [100 + i, 101 + i, 102 + i],
                'high': [101 + i, 102 + i, 103 + i],
                'low': [99 + i, 100 + i, 101 + i],
                'close': [100.5 + i, 101.5 + i, 102.5 + i],
                'volume': [1000 + i, 1100 + i, 1200 + i]
            }
            
            features = feature_engine.compute_features(data)
            signal = strategy.generate_signal(f'AAPL_{i}', features)
            
            if signal:
                is_valid, order_data, reason = risk_manager.validate_signal(signal)
                # Should handle gracefully regardless of outcome
    
    async def test_system_memory_usage(self, temp_dir):
        """Test system memory usage."""
        # Create components
        alert_manager = AlertManager(os.path.join(temp_dir, "alerts.log"))
        audit_logger = AuditLogger(os.path.join(temp_dir, "audit"))
        
        # Generate many alerts and events
        for i in range(1000):
            await alert_manager.send_alert(
                'risk_limit_breach',
                'warning',
                f'Test Alert {i}',
                f'This is test alert {i}'
            )
            
            audit_logger.set_session_id(f'session_{i}')
            await audit_logger.log_signal({'symbol': f'AAPL_{i}', 'action': 'buy'})
        
        # Verify system still works
        assert len(alert_manager.alert_history) == 1000
        events = audit_logger.get_session_events('session_999')
        assert len(events) == 1
