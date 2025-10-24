"""
Tests for Phase 5: Trading Loop & Orchestration
"""
import pytest
import asyncio
import inspect
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from app.trading.engine import TradingEngine
from app.trading.brokers.simulator import SimulatorAdapter
from app.trading.strategies.mean_reversion import MeanReversionStrategy
from app.trading.risk_manager import RiskManager
from app.trading.execution import ExecutionEngine
from app.trading.portfolio import Portfolio
from app.trading.alerts import AlertManager
from app.trading.audit import AuditLogger
from app.core.trading_db import TradingDatabase
from app.core.storage import StorageManager


class TestTradingEnginePhase5:
    """Test enhanced trading engine with Phase 5 features."""
    
    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing."""
        # Mock broker
        broker = Mock(spec=SimulatorAdapter)
        broker.get_account = AsyncMock(return_value=Mock(equity=100000.0))
        broker.is_market_open = AsyncMock(return_value=True)
        
        # Mock strategy
        strategy = Mock(spec=MeanReversionStrategy)
        strategy.name = "mean_reversion"
        strategy.generate_signal = AsyncMock(return_value={
            'symbol': 'AAPL',
            'action': 'buy',
            'confidence': 0.8,
            'size_pct': 0.01,
            'reason': 'RSI oversold'
        })
        
        # Mock risk manager
        risk_manager = Mock(spec=RiskManager)
        risk_manager.validate_signal = AsyncMock(return_value=(True, {
            'symbol': 'AAPL',
            'side': 'buy',
            'quantity': 10,
            'order_type': 'limit',
            'limit_price': 150.0
        }, "Signal approved"))
        
        # Mock execution engine
        execution_engine = Mock(spec=ExecutionEngine)
        execution_engine.place_order = AsyncMock(return_value="order_123")
        
        # Mock portfolio
        portfolio = Mock(spec=Portfolio)
        portfolio.get_positions = AsyncMock(return_value=[])
        
        # Mock alert manager
        alert_manager = Mock(spec=AlertManager)
        alert_manager.send_alert = AsyncMock()
        
        # Mock audit logger
        audit_logger = Mock(spec=AuditLogger)
        audit_logger.log_signal = AsyncMock()
        audit_logger.log_order = AsyncMock()
        
        return {
            'broker': broker,
            'strategy': strategy,
            'risk_manager': risk_manager,
            'execution_engine': execution_engine,
            'portfolio': portfolio,
            'alert_manager': alert_manager,
            'audit_logger': audit_logger
        }
    
    @pytest.fixture
    def trading_engine(self, mock_components):
        """Create trading engine with mocked components."""
        engine = TradingEngine()
        
        # Replace components with mocks
        engine.broker = mock_components['broker']
        engine.current_strategy = mock_components['strategy']
        engine.risk_manager = mock_components['risk_manager']
        engine.execution_engine = mock_components['execution_engine']
        engine.portfolio = mock_components['portfolio']
        engine.alert_manager = mock_components['alert_manager']
        engine.audit_logger = mock_components['audit_logger']
        
        return engine
    
    def test_trading_engine_initialization(self, trading_engine):
        """Test trading engine initialization."""
        assert trading_engine is not None
        assert trading_engine.config is not None
        assert trading_engine.is_running_flag is False
        assert trading_engine.is_armed is False
    
    async def test_market_hours_check(self, trading_engine):
        """Test market hours checking."""
        # Test with broker that has is_market_open method
        is_open = await trading_engine._is_market_open()
        assert isinstance(is_open, bool)
        
        # Test broker method was called
        trading_engine.broker.is_market_open.assert_called_once()
    
    async def test_market_hours_fallback(self):
        """Test market hours fallback when broker doesn't have method."""
        engine = TradingEngine()
        # Create a mock broker without is_market_open method
        engine.broker = Mock()
        del engine.broker.is_market_open  # Remove the method to trigger fallback
        
        # Test during market hours (simplified)
        with patch('app.trading.engine.datetime') as mock_datetime:
            # Mock datetime.now() to return a Monday at 2:30 PM UTC (9:30 AM ET)
            mock_now = datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)  # Monday, 2:30 PM UTC = 9:30 AM ET
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            
            is_open = await engine._is_market_open()
            assert is_open is True
    
    async def test_get_latest_data(self, trading_engine):
        """Test getting latest market data."""
        # Mock storage manager
        mock_storage = Mock(spec=StorageManager)
        mock_storage.get_latest_ohlcv = Mock(return_value={
            'close': [150.0, 151.0, 152.0],
            'volume': [1000, 1100, 1200]
        })
        mock_storage.get_latest_news = Mock(return_value=[{'headline': 'Test news'}])
        
        trading_engine.storage_manager = mock_storage
        
        data = await trading_engine._get_latest_data()
        assert isinstance(data, dict)
    
    async def test_compute_features(self, trading_engine):
        """Test feature computation."""
        # Mock data with OHLCV
        data = {
            'AAPL': {
                'close': [150.0, 151.0, 152.0, 153.0, 154.0, 155.0, 156.0, 157.0, 158.0, 159.0,
                         160.0, 161.0, 162.0, 163.0, 164.0, 165.0, 166.0, 167.0, 168.0, 169.0],
                'volume': [1000] * 20
            }
        }
        
        features = await trading_engine._compute_features(data)
        assert isinstance(features, dict)
        
        if 'AAPL' in features:
            feature_data = features['AAPL']
            assert 'sma_20' in feature_data
            assert 'rsi' in feature_data
            assert 'current_price' in feature_data
    
    def test_rsi_calculation(self, trading_engine):
        """Test RSI calculation."""
        # Test with known price sequence
        prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113, 115]
        rsi = trading_engine._calculate_rsi(prices)
        
        assert isinstance(rsi, float)
        assert 0 <= rsi <= 100
    
    def test_bollinger_bands_calculation(self, trading_engine):
        """Test Bollinger Bands calculation."""
        # Test with known price sequence
        prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113, 115, 117, 116, 118, 120]
        upper, lower = trading_engine._calculate_bollinger_bands(prices)
        
        assert isinstance(upper, float)
        assert isinstance(lower, float)
        assert upper > lower
    
    async def test_generate_signals(self, trading_engine):
        """Test signal generation."""
        features = {
            'AAPL': {
                'sma_20': 150.0,
                'rsi': 30.0,
                'current_price': 145.0,
                'volume': 1000
            }
        }
        
        signals = await trading_engine._generate_signals(features)
        assert isinstance(signals, list)
        
        # Strategy should have been called
        trading_engine.current_strategy.generate_signal.assert_called()
    
    async def test_process_signals(self, trading_engine):
        """Test signal processing through risk manager."""
        signals = [{
            'symbol': 'AAPL',
            'action': 'buy',
            'confidence': 0.8,
            'size_pct': 0.01
        }]
        
        orders = await trading_engine._process_signals(signals)
        assert isinstance(orders, list)
        
        # Risk manager should have been called
        trading_engine.risk_manager.validate_signal.assert_called()
    
    async def test_monitor_positions(self, trading_engine):
        """Test position monitoring."""
        # Mock positions with stop-loss and take-profit
        positions = [{
            'symbol': 'AAPL',
            'quantity': 10,
            'side': 'long',
            'entry_price': 150.0,
            'current_price': 145.0,
            'stop_loss': 140.0,
            'take_profit': 160.0
        }]
        
        trading_engine.portfolio.get_positions.return_value = positions
        
        await trading_engine._monitor_positions()
        
        # Portfolio should have been queried
        trading_engine.portfolio.get_positions.assert_called()
    
    async def test_close_position(self, trading_engine):
        """Test position closing."""
        position = {
            'symbol': 'AAPL',
            'quantity': 10,
            'side': 'long'
        }
        
        await trading_engine._close_position(position, "STOP_LOSS")
        
        # Execution engine should have been called
        trading_engine.execution_engine.place_order.assert_called()
    
    async def test_broadcast_status_update(self, trading_engine):
        """Test status update broadcasting."""
        # Mock get_status method
        trading_engine.get_status = AsyncMock(return_value={'status': 'running'})
        
        await trading_engine._broadcast_status_update()
        
        # get_status should have been called
        trading_engine.get_status.assert_called_once()
    
    async def test_log_trading_decisions(self, trading_engine):
        """Test trading decision logging."""
        signals = [{'symbol': 'AAPL', 'action': 'buy'}]
        orders = [{'symbol': 'AAPL', 'side': 'buy', 'quantity': 10}]
        
        await trading_engine._log_trading_decisions(signals, orders)
        
        # Audit logger should have been called
        trading_engine.audit_logger.log_signal.assert_called()
        trading_engine.audit_logger.log_order.assert_called()
    
    async def test_get_account_equity(self, trading_engine):
        """Test getting account equity."""
        equity = await trading_engine._get_account_equity()
        assert isinstance(equity, float)
        assert equity == 100000.0
        
        # Broker should have been called
        trading_engine.broker.get_account.assert_called_once()
    
    async def test_enhanced_trading_loop_structure(self, trading_engine):
        """Test that the enhanced trading loop has all required components."""
        # This test verifies the structure without running the full loop
        
        # Check that all required methods exist
        assert hasattr(trading_engine, '_is_market_open')
        assert hasattr(trading_engine, '_get_latest_data')
        assert hasattr(trading_engine, '_compute_features')
        assert hasattr(trading_engine, '_generate_signals')
        assert hasattr(trading_engine, '_process_signals')
        assert hasattr(trading_engine, '_monitor_positions')
        assert hasattr(trading_engine, '_broadcast_status_update')
        assert hasattr(trading_engine, '_log_trading_decisions')
        
        # Test method signatures are correct
        assert inspect.iscoroutinefunction(trading_engine._is_market_open)
        assert inspect.iscoroutinefunction(trading_engine._get_latest_data)
        assert inspect.iscoroutinefunction(trading_engine._compute_features)
        assert inspect.iscoroutinefunction(trading_engine._generate_signals)
        assert inspect.iscoroutinefunction(trading_engine._process_signals)
        assert inspect.iscoroutinefunction(trading_engine._monitor_positions)
        assert inspect.iscoroutinefunction(trading_engine._broadcast_status_update)
        assert inspect.iscoroutinefunction(trading_engine._log_trading_decisions)


class TestTradingEngineIntegration:
    """Integration tests for Phase 5 trading engine."""
    
    async def test_trading_engine_start_stop_cycle(self):
        """Test complete start/stop cycle."""
        engine = TradingEngine()
        
        # Test initialization
        assert not engine.is_running()
        assert not engine.is_armed
        
        # Test starting (should not run without proper setup)
        try:
            await engine.start()
            # If it starts, it should be running
            assert engine.is_running()
        except Exception as e:
            # Expected to fail without proper broker setup
            assert "broker" in str(e).lower() or "strategy" in str(e).lower()
        
        # Test stopping
        await engine.stop()
        assert not engine.is_running()
    
    async def test_trading_engine_arming_system(self):
        """Test live trading arming system."""
        engine = TradingEngine()
        
        # Test initial state
        assert not engine.is_armed
        
        # Test arming with correct key
        success = await engine.arm_live_trading("LIVE_TRADING_CONFIRM")
        assert success is True
        assert engine.is_armed is True
        
        # Test disarming
        await engine.disarm_live_trading()
        assert not engine.is_armed
        
        # Test arming with incorrect key
        success = await engine.arm_live_trading("WRONG_KEY")
        assert success is False
        assert not engine.is_armed


class TestTradingEngineErrorHandling:
    """Test error handling in trading engine."""
    
    async def test_trading_loop_error_recovery(self):
        """Test that trading loop handles errors gracefully."""
        engine = TradingEngine()
        
        # Mock components that will raise errors
        engine.broker = Mock()
        engine.broker.is_market_open = AsyncMock(side_effect=Exception("Broker error"))
        
        engine.storage_manager = Mock()
        engine.storage_manager.get_latest_ohlcv = Mock(side_effect=Exception("Storage error"))
        
        # Test that methods handle errors gracefully
        is_open = await engine._is_market_open()
        assert is_open is False  # Should return False on error
        
        data = await engine._get_latest_data()
        assert data == {}  # Should return empty dict on error
    
    async def test_feature_computation_error_handling(self):
        """Test feature computation error handling."""
        engine = TradingEngine()
        
        # Test with invalid data
        invalid_data = {'AAPL': 'invalid_data'}
        features = await engine._compute_features(invalid_data)
        assert features == {}
        
        # Test with empty data
        empty_data = {}
        features = await engine._compute_features(empty_data)
        assert features == {}
    
    async def test_signal_generation_error_handling(self):
        """Test signal generation error handling."""
        engine = TradingEngine()
        
        # Test with no strategy
        engine.current_strategy = None
        features = {'AAPL': {'sma_20': 150.0}}
        signals = await engine._generate_signals(features)
        assert signals == []
        
        # Test with strategy that raises error
        mock_strategy = Mock()
        mock_strategy.generate_signal = AsyncMock(side_effect=Exception("Strategy error"))
        engine.current_strategy = mock_strategy
        
        signals = await engine._generate_signals(features)
        assert signals == []  # Should return empty list on error
