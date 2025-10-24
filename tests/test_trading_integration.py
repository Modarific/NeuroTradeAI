"""
Integration tests for end-to-end trading system testing.
Tests complete signal-to-execution flow, backtesting, and system integration.
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
from app.backtesting.data_loader import DataLoader
from app.backtesting.vectorized_engine import VectorizedBacktestEngine
from app.backtesting.event_driven_engine import EventDrivenBacktestEngine


class TestEndToEndTradingFlow:
    """Test complete end-to-end trading flow."""
    
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
    def mock_storage_manager(self):
        """Create mock storage manager."""
        storage = Mock()
        storage.get_latest_ohlcv = Mock(return_value={
            'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120],
            'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121],
            'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5, 110.5, 111.5, 112.5, 113.5, 114.5, 115.5, 116.5, 117.5, 118.5, 119.5, 120.5],
            'volume': [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000]
        })
        storage.get_latest_news = Mock(return_value=[
            {'sentiment': 0.8, 'timestamp': '2024-01-01T10:00:00Z'},
            {'sentiment': -0.2, 'timestamp': '2024-01-01T11:00:00Z'}
        ])
        return storage
    
    @pytest.fixture
    def trading_system(self, temp_dir, mock_storage_manager):
        """Create complete trading system for testing."""
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
        
        return {
            'feature_engine': feature_engine,
            'strategy': strategy,
            'risk_manager': risk_manager,
            'portfolio': portfolio,
            'broker': broker,
            'execution_engine': execution_engine,
            'alert_manager': alert_manager,
            'audit_logger': audit_logger,
            'storage_manager': mock_storage_manager
        }
    
    async def test_complete_trading_cycle(self, trading_system):
        """Test complete trading cycle from data to execution."""
        # Setup
        feature_engine = trading_system['feature_engine']
        strategy = trading_system['strategy']
        risk_manager = trading_system['risk_manager']
        execution_engine = trading_system['execution_engine']
        storage_manager = trading_system['storage_manager']
        
        # 1. Get market data
        data = storage_manager.get_latest_ohlcv('AAPL')
        assert data is not None
        
        # 2. Compute features
        features = feature_engine.compute_features(data)
        assert 'rsi' in features
        assert 'sma_20' in features
        assert 'bb_upper' in features
        assert 'bb_lower' in features
        
        # 3. Generate signal
        signal = strategy.generate_signal('AAPL', features)
        assert signal is not None
        
        # 4. Validate signal through risk manager
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is True
        assert order_data is not None
        
        # 5. Execute order
        order_id = await execution_engine.place_order(**order_data)
        assert order_id is not None
        
        # 6. Verify order was placed
        orders = execution_engine.get_orders()
        assert len(orders) == 1
        assert orders[0].symbol == 'AAPL'
    
    async def test_risk_limits_enforcement(self, trading_system):
        """Test that risk limits are properly enforced."""
        risk_manager = trading_system['risk_manager']
        execution_engine = trading_system['execution_engine']
        
        # Test position size limit
        from app.trading.signals import Signal, SignalAction
        oversized_signal = Signal('AAPL', SignalAction.BUY, 0.8, 2.0, 'Test')  # 2% position size
        
        is_valid, order_data, reason = risk_manager.validate_signal(oversized_signal)
        assert is_valid is False
        assert reason.value == 'position_size_exceeded'
        
        # Test daily loss limit
        risk_manager.daily_pnl = -0.04  # 4% loss
        normal_signal = Signal('AAPL', SignalAction.BUY, 0.8, 0.5, 'Test')
        
        is_valid, order_data, reason = risk_manager.validate_signal(normal_signal)
        assert is_valid is False
        assert reason.value == 'daily_loss_limit_exceeded'
    
    async def test_position_monitoring(self, trading_system):
        """Test position monitoring and management."""
        portfolio = trading_system['portfolio']
        broker = trading_system['broker']
        
        # Add position
        portfolio.add_position('AAPL', 100, 150.0)
        
        # Update price
        portfolio.update_prices({'AAPL': 155.0})
        
        # Check P&L
        total_pnl = portfolio.get_total_pnl()
        assert total_pnl == 500.0  # 100 * (155 - 150)
        
        # Check position limits
        portfolio.max_positions = 2
        portfolio.add_position('MSFT', 50, 300.0)
        
        can_add = portfolio.can_add_position('GOOGL')
        assert can_add is False
    
    async def test_alert_system_integration(self, trading_system):
        """Test alert system integration."""
        alert_manager = trading_system['alert_manager']
        
        # Send risk alert
        await alert_manager.send_risk_alert(
            'position_size',
            1.5,
            1.0,
            'AAPL'
        )
        
        assert len(alert_manager.alert_history) == 1
        alert = alert_manager.alert_history[0]
        assert alert.alert_type.value == 'risk_limit_breach'
        assert alert.level == AlertLevel.WARNING
    
    async def test_audit_trail_integration(self, trading_system):
        """Test audit trail integration."""
        audit_logger = trading_system['audit_logger']
        audit_logger.set_session_id('session_123')
        
        # Log signal
        signal = {'symbol': 'AAPL', 'action': 'buy', 'confidence': 0.8}
        await audit_logger.log_signal(signal)
        
        # Log order
        order = {'id': 'order_123', 'symbol': 'AAPL', 'side': 'buy', 'quantity': 100}
        await audit_logger.log_order(order)
        
        # Log position
        position = {'symbol': 'AAPL', 'quantity': 100, 'entry_price': 150.0}
        await audit_logger.log_position_opened(position)
        
        events = audit_logger.get_session_events('session_123')
        assert len(events) == 3
        assert events[0]['event_type'] == 'signal_generated'
        assert events[1]['event_type'] == 'order_placed'
        assert events[2]['event_type'] == 'position_opened'


class TestBacktestingIntegration:
    """Test backtesting system integration."""
    
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
    def sample_data(self):
        """Create sample historical data."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        data = pd.DataFrame({
            'open': 100 + (dates.day % 10) * 0.1,
            'high': 101 + (dates.day % 10) * 0.1,
            'low': 99 + (dates.day % 10) * 0.1,
            'close': 100.5 + (dates.day % 10) * 0.1,
            'volume': 1000 + (dates.day % 10) * 100
        }, index=dates)
        return data
    
    def test_data_loader(self, temp_dir, sample_data):
        """Test data loader functionality."""
        data_loader = DataLoader()
        
        # Save sample data
        data_file = os.path.join(temp_dir, 'test_data.parquet')
        sample_data.to_parquet(data_file)
        
        # Load data
        loaded_data = data_loader.load_ohlcv_data(data_file)
        assert len(loaded_data) == 100
        assert 'open' in loaded_data.columns
        assert 'high' in loaded_data.columns
        assert 'low' in loaded_data.columns
        assert 'close' in loaded_data.columns
        assert 'volume' in loaded_data.columns
    
    def test_vectorized_backtesting(self, sample_data):
        """Test vectorized backtesting engine."""
        engine = VectorizedBacktestEngine()
        
        # Create sample features
        features = pd.DataFrame({
            'rsi': [30, 35, 40, 45, 50, 55, 60, 65, 70, 75],
            'sma_20': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            'bb_upper': [105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
            'bb_lower': [95, 96, 97, 98, 99, 100, 101, 102, 103, 104]
        })
        
        # Run backtest
        results = engine.run_backtest(
            data=sample_data,
            features=features,
            strategy_name='mean_reversion',
            initial_balance=100000.0
        )
        
        assert 'total_return' in results
        assert 'sharpe_ratio' in results
        assert 'max_drawdown' in results
        assert 'win_rate' in results
        assert results['total_return'] is not None
    
    def test_event_driven_backtesting(self, sample_data):
        """Test event-driven backtesting engine."""
        engine = EventDrivenBacktestEngine()
        
        # Create sample features
        features = pd.DataFrame({
            'rsi': [30, 35, 40, 45, 50, 55, 60, 65, 70, 75],
            'sma_20': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            'bb_upper': [105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
            'bb_lower': [95, 96, 97, 98, 99, 100, 101, 102, 103, 104]
        })
        
        # Run backtest
        results = engine.run_backtest(
            data=sample_data,
            features=features,
            strategy_name='mean_reversion',
            initial_balance=100000.0
        )
        
        assert 'total_return' in results
        assert 'sharpe_ratio' in results
        assert 'max_drawdown' in results
        assert 'win_rate' in results
        assert results['total_return'] is not None
    
    def test_strategy_comparison(self, sample_data):
        """Test strategy comparison functionality."""
        # Test multiple strategies
        strategies = ['mean_reversion', 'momentum', 'news_driven']
        results = {}
        
        for strategy in strategies:
            engine = VectorizedBacktestEngine()
            features = pd.DataFrame({
                'rsi': [30, 35, 40, 45, 50, 55, 60, 65, 70, 75],
                'sma_20': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
                'bb_upper': [105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
                'bb_lower': [95, 96, 97, 98, 99, 100, 101, 102, 103, 104]
            })
            
            result = engine.run_backtest(
                data=sample_data,
                features=features,
                strategy_name=strategy,
                initial_balance=100000.0
            )
            results[strategy] = result
        
        # Compare results
        assert len(results) == 3
        for strategy, result in results.items():
            assert 'total_return' in result
            assert 'sharpe_ratio' in result
            assert 'max_drawdown' in result


class TestSystemRecovery:
    """Test system recovery and error handling."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    async def test_broker_connection_recovery(self, temp_dir):
        """Test broker connection recovery."""
        # Create broker that initially fails
        broker = Mock(spec=SimulatorAdapter)
        broker.place_order = AsyncMock(side_effect=Exception("Connection lost"))
        
        execution_engine = ExecutionEngine(broker)
        
        # Try to place order (should fail)
        try:
            await execution_engine.place_order(
                symbol='AAPL',
                side='buy',
                quantity=100,
                order_type='market'
            )
            assert False, "Expected exception"
        except Exception as e:
            assert "Connection lost" in str(e)
        
        # Fix broker
        broker.place_order = AsyncMock(return_value='order_123')
        
        # Try again (should succeed)
        order_id = await execution_engine.place_order(
            symbol='AAPL',
            side='buy',
            quantity=100,
            order_type='market'
        )
        assert order_id == 'order_123'
    
    async def test_data_failure_recovery(self, temp_dir):
        """Test data failure recovery."""
        # Create storage manager that fails
        storage = Mock()
        storage.get_latest_ohlcv = Mock(side_effect=Exception("Data unavailable"))
        
        feature_engine = FeatureEngine()
        
        # Try to get data (should fail gracefully)
        try:
            data = storage.get_latest_ohlcv('AAPL')
            features = feature_engine.compute_features(data)
            assert False, "Expected exception"
        except Exception as e:
            assert "Data unavailable" in str(e)
        
        # Fix storage
        storage.get_latest_ohlcv = Mock(return_value={
            'open': [100, 101, 102],
            'high': [101, 102, 103],
            'low': [99, 100, 101],
            'close': [100.5, 101.5, 102.5],
            'volume': [1000, 1100, 1200]
        })
        
        # Try again (should succeed)
        data = storage.get_latest_ohlcv('AAPL')
        features = feature_engine.compute_features(data)
        assert 'rsi' in features
        assert 'sma_20' in features
    
    async def test_risk_manager_recovery(self, temp_dir):
        """Test risk manager recovery."""
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
        
        # Simulate daily loss limit
        risk_manager.daily_pnl = -0.04  # 4% loss
        
        from app.trading.signals import Signal, SignalAction
        signal = Signal('AAPL', SignalAction.BUY, 0.8, 0.5, 'Test')
        
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is False
        assert reason.value == 'daily_loss_limit_exceeded'
        
        # Reset daily P&L
        risk_manager.daily_pnl = 0.0
        
        # Try again (should succeed)
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is True
        assert order_data is not None


class TestPerformanceValidation:
    """Test performance validation and metrics."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    async def test_performance_metrics_calculation(self, temp_dir):
        """Test performance metrics calculation."""
        analytics = PerformanceAnalytics(temp_dir)
        
        # Create sample trades
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
                'exit_price': 295.0,
                'pnl': -250.0,
                'entry_time': '2024-01-01T12:00:00Z',
                'exit_time': '2024-01-01T13:00:00Z'
            }
        ]
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id='session_123',
            trades=trades,
            positions=[],
            initial_balance=100000.0,
            final_balance=100250.0,
            start_date=start_date,
            end_date=end_date,
            strategy='mean_reversion',
            mode='paper'
        )
        
        assert report.total_return == 250.0
        assert report.total_return_pct == 0.25
        assert report.trade_metrics.total_trades == 2
        assert report.trade_metrics.winning_trades == 1
        assert report.trade_metrics.losing_trades == 1
        assert report.trade_metrics.win_rate == 50.0
    
    async def test_risk_metrics_validation(self, temp_dir):
        """Test risk metrics validation."""
        analytics = PerformanceAnalytics(temp_dir)
        
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
            session_id='session_123',
            trades=trades,
            positions=[],
            initial_balance=100000.0,
            final_balance=101000.0,
            start_date=start_date,
            end_date=end_date,
            strategy='mean_reversion',
            mode='paper'
        )
        
        # Check drawdown calculation
        assert report.trade_metrics.max_drawdown > 0
        assert report.trade_metrics.max_drawdown_pct > 0
        
        # Check Sharpe ratio
        assert report.trade_metrics.sharpe_ratio is not None
    
    async def test_strategy_comparison(self, temp_dir):
        """Test strategy comparison functionality."""
        analytics = PerformanceAnalytics(temp_dir)
        
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


class TestSystemIntegration:
    """Test complete system integration."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    async def test_complete_system_initialization(self, temp_dir):
        """Test complete system initialization."""
        # Create all components
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
        
        # Verify all components are initialized
        assert feature_engine is not None
        assert strategy is not None
        assert risk_manager is not None
        assert portfolio is not None
        assert broker is not None
        assert execution_engine is not None
        assert alert_manager is not None
        assert audit_logger is not None
        assert analytics is not None
    
    async def test_system_communication(self, temp_dir):
        """Test system component communication."""
        # Create components
        alert_manager = AlertManager(os.path.join(temp_dir, "alerts.log"))
        audit_logger = AuditLogger(os.path.join(temp_dir, "audit"))
        analytics = PerformanceAnalytics(temp_dir)
        
        # Test alert system
        await alert_manager.send_alert(
            'risk_limit_breach',
            'warning',
            'Test Alert',
            'This is a test alert'
        )
        assert len(alert_manager.alert_history) == 1
        
        # Test audit system
        audit_logger.set_session_id('session_123')
        await audit_logger.log_signal({'symbol': 'AAPL', 'action': 'buy'})
        events = audit_logger.get_session_events('session_123')
        assert len(events) == 1
        
        # Test analytics system
        trades = [{'pnl': 100.0, 'entry_time': '2024-01-01T10:00:00Z', 'exit_time': '2024-01-01T11:00:00Z'}]
        report = await analytics.analyze_session(
            session_id='session_123',
            trades=trades,
            positions=[],
            initial_balance=100000.0,
            final_balance=100100.0,
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            strategy='mean_reversion',
            mode='paper'
        )
        assert report.total_return == 100.0
    
    async def test_system_error_handling(self, temp_dir):
        """Test system error handling."""
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
