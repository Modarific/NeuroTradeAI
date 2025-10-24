"""
Simple Phase 7 tests to verify basic functionality.
"""
import pytest
import asyncio
import os
import tempfile
import shutil
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from app.trading.alerts import AlertManager, AlertType, AlertLevel
from app.trading.audit import AuditLogger, AuditEventType
from app.trading.analytics import PerformanceAnalytics
from app.trading.risk_manager import RiskManager, RejectionReason
from app.trading.portfolio import Portfolio
from app.trading.brokers.simulator import SimulatorAdapter
from app.trading.signals import Signal, SignalAction


class TestBasicComponents:
    """Test basic component functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    def test_alert_manager_creation(self, temp_dir):
        """Test alert manager creation."""
        log_file = os.path.join(temp_dir, "alerts.log")
        alert_manager = AlertManager(log_file)
        
        assert alert_manager is not None
        assert alert_manager.log_file == log_file
        assert alert_manager.alert_history == []
    
    async def test_alert_sending(self, temp_dir):
        """Test alert sending."""
        log_file = os.path.join(temp_dir, "alerts.log")
        alert_manager = AlertManager(log_file)
        
        success = await alert_manager.send_alert(
            AlertType.RISK_LIMIT_BREACH,
            AlertLevel.WARNING,
            "Test Alert",
            "This is a test alert"
        )
        
        assert success is True
        assert len(alert_manager.alert_history) == 1
    
    def test_audit_logger_creation(self, temp_dir):
        """Test audit logger creation."""
        log_dir = os.path.join(temp_dir, "audit")
        audit_logger = AuditLogger(log_dir)
        
        assert audit_logger is not None
        assert audit_logger.log_dir == log_dir
    
    async def test_audit_logging(self, temp_dir):
        """Test audit logging."""
        log_dir = os.path.join(temp_dir, "audit")
        audit_logger = AuditLogger(log_dir)
        audit_logger.set_session_id("session_123")
        
        await audit_logger.log_signal({"symbol": "AAPL", "action": "buy"})
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "signal_generated"
    
    def test_analytics_creation(self, temp_dir):
        """Test analytics creation."""
        analytics = PerformanceAnalytics(temp_dir)
        
        assert analytics is not None
        assert analytics.data_dir == temp_dir
    
    def test_risk_manager_creation(self):
        """Test risk manager creation."""
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
        
        assert risk_manager is not None
        assert risk_manager.risk_limits.max_position_size_pct == 1.0
    
    def test_portfolio_creation(self):
        """Test portfolio creation."""
        portfolio = Portfolio(100000.0)
        
        assert portfolio is not None
        assert portfolio.initial_balance == 100000.0
        assert portfolio.balance == 100000.0
    
    def test_simulator_adapter_creation(self):
        """Test simulator adapter creation."""
        config = {"initial_balance": 100000.0}
        adapter = SimulatorAdapter(config)
        
        assert adapter is not None
        assert adapter.name == "simulator"
        assert adapter.initial_balance == 100000.0
    
    def test_signal_creation(self):
        """Test signal creation."""
        signal = Signal(
            symbol="AAPL",
            action=SignalAction.BUY,
            confidence=0.8,
            size_pct=0.01,
            reasoning="Test signal",
            timestamp=datetime.now(timezone.utc),
            strategy_name="test"
        )
        
        assert signal.symbol == "AAPL"
        assert signal.action == SignalAction.BUY
        assert signal.confidence == 0.8
        assert signal.size_pct == 0.01


class TestRiskManagement:
    """Test risk management functionality."""
    
    def test_position_size_validation(self):
        """Test position size validation."""
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
        
        # Test valid signal
        signal = Signal("AAPL", SignalAction.BUY, 0.8, 0.5, "Test", datetime.now(timezone.utc), "test")
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is True
        
        # Test oversized position
        signal = Signal("AAPL", SignalAction.BUY, 0.8, 2.0, "Test", datetime.now(timezone.utc), "test")
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is False
        assert reason == RejectionReason.POSITION_SIZE_EXCEEDED
    
    def test_daily_loss_limit(self):
        """Test daily loss limit."""
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
        
        # Simulate daily loss
        risk_manager.daily_pnl = -0.04  # 4% loss
        
        signal = Signal("AAPL", SignalAction.BUY, 0.8, 0.5, "Test", datetime.now(timezone.utc), "test")
        is_valid, order_data, reason = risk_manager.validate_signal(signal)
        assert is_valid is False
        assert reason == RejectionReason.DAILY_LOSS_LIMIT_EXCEEDED


class TestPortfolioManagement:
    """Test portfolio management functionality."""
    
    def test_position_management(self):
        """Test position management."""
        portfolio = Portfolio(100000.0)
        
        # Add position
        portfolio.add_position("AAPL", 100, 150.0)
        
        positions = portfolio.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"
        assert positions[0].quantity == 100
        assert positions[0].entry_price == 150.0
        
        # Update position price
        portfolio.update_prices({"AAPL": 155.0})
        
        position = portfolio.get_position("AAPL")
        assert position.current_price == 155.0
        assert position.unrealized_pnl == 500.0  # 100 * (155 - 150)
    
    def test_pnl_calculation(self):
        """Test P&L calculation."""
        portfolio = Portfolio(100000.0)
        
        portfolio.add_position("AAPL", 100, 150.0)
        portfolio.update_prices({"AAPL": 155.0})
        
        total_pnl = portfolio.get_total_pnl()
        assert total_pnl == 500.0
        
        total_pnl_pct = portfolio.get_total_pnl_pct()
        assert total_pnl_pct == 0.005  # 0.5%


class TestAlertSystem:
    """Test alert system functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    async def test_risk_alert(self, temp_dir):
        """Test risk alert."""
        log_file = os.path.join(temp_dir, "alerts.log")
        alert_manager = AlertManager(log_file)
        
        await alert_manager.send_risk_alert(
            "position_size",
            1.5,
            1.0,
            "AAPL"
        )
        
        assert len(alert_manager.alert_history) == 1
        alert = alert_manager.alert_history[0]
        assert alert.alert_type == AlertType.RISK_LIMIT_BREACH
        assert alert.data["risk_type"] == "position_size"
    
    async def test_emergency_stop_alert(self, temp_dir):
        """Test emergency stop alert."""
        log_file = os.path.join(temp_dir, "alerts.log")
        alert_manager = AlertManager(log_file)
        
        await alert_manager.send_emergency_stop_alert("Risk limit exceeded")
        
        assert len(alert_manager.alert_history) == 1
        alert = alert_manager.alert_history[0]
        assert alert.alert_type == AlertType.EMERGENCY_STOP
        assert alert.level == AlertLevel.CRITICAL


class TestAuditSystem:
    """Test audit system functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    async def test_signal_logging(self, temp_dir):
        """Test signal logging."""
        log_dir = os.path.join(temp_dir, "audit")
        audit_logger = AuditLogger(log_dir)
        audit_logger.set_session_id("session_123")
        
        signal = {"symbol": "AAPL", "action": "buy", "confidence": 0.8}
        await audit_logger.log_signal(signal)
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "signal_generated"
    
    async def test_order_logging(self, temp_dir):
        """Test order logging."""
        log_dir = os.path.join(temp_dir, "audit")
        audit_logger = AuditLogger(log_dir)
        audit_logger.set_session_id("session_123")
        
        order = {"id": "order_123", "symbol": "AAPL", "side": "buy", "quantity": 100}
        await audit_logger.log_order(order)
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "order_placed"


class TestPerformanceAnalytics:
    """Test performance analytics functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass
    
    async def test_session_analysis(self, temp_dir):
        """Test session analysis."""
        analytics = PerformanceAnalytics(temp_dir)
        
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
            }
        ]
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id='session_123',
            trades=trades,
            positions=[],
            initial_balance=100000.0,
            final_balance=100500.0,
            start_date=start_date,
            end_date=end_date,
            strategy='mean_reversion',
            mode='paper'
        )
        
        assert report.total_return == 500.0
        assert report.total_return_pct == 0.5
        assert report.trade_metrics.total_trades == 1
        assert report.trade_metrics.winning_trades == 1
        assert report.trade_metrics.losing_trades == 0
        assert report.trade_metrics.win_rate == 100.0
    
    async def test_html_report_generation(self, temp_dir):
        """Test HTML report generation."""
        analytics = PerformanceAnalytics(temp_dir)
        
        trades = [{'pnl': 100.0, 'entry_time': '2024-01-01T10:00:00Z', 'exit_time': '2024-01-01T11:00:00Z'}]
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id='session_123',
            trades=trades,
            positions=[],
            initial_balance=100000.0,
            final_balance=100100.0,
            start_date=start_date,
            end_date=end_date,
            strategy='mean_reversion',
            mode='paper'
        )
        
        html_content = await analytics.generate_html_report(report)
        assert isinstance(html_content, str)
        assert "<html>" in html_content
        assert "Trading Performance Report" in html_content


class TestIntegration:
    """Test integration between components."""
    
    async def test_alert_audit_integration(self):
        """Test alert and audit integration."""
        # This would test that alerts are properly logged in audit trail
        pass
    
    async def test_analytics_audit_integration(self):
        """Test analytics and audit integration."""
        # This would test that analytics can read from audit logs
        pass
    
    async def test_complete_monitoring_flow(self):
        """Test complete monitoring flow."""
        # This would test the entire monitoring pipeline
        pass
