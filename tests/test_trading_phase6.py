"""
Tests for Phase 6: Monitoring & Safety
"""
import pytest
import asyncio
import json
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from app.trading.alerts import AlertManager, AlertType, AlertLevel, Alert
from app.trading.audit import AuditLogger, AuditEventType, AuditEvent
from app.trading.analytics import PerformanceAnalytics, PerformanceReport, TradeMetrics


class TestAlertSystem:
    """Test the multi-channel alert system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            # On Windows, files might still be in use
            import time
            time.sleep(0.1)
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                pass  # Ignore if still can't delete
    
    @pytest.fixture
    def alert_manager(self, temp_dir):
        """Create alert manager for testing."""
        log_file = os.path.join(temp_dir, "alerts.log")
        return AlertManager(log_file)
    
    def test_alert_creation(self):
        """Test alert object creation."""
        alert = Alert(
            AlertType.RISK_LIMIT_BREACH,
            AlertLevel.WARNING,
            "Test Alert",
            "This is a test alert",
            {"test": "data"}
        )
        
        assert alert.alert_type == AlertType.RISK_LIMIT_BREACH
        assert alert.level == AlertLevel.WARNING
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test alert"
        assert alert.data == {"test": "data"}
        assert alert.id is not None
        assert alert.hash is not None
    
    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = Alert(
            AlertType.RISK_LIMIT_BREACH,
            AlertLevel.WARNING,
            "Test Alert",
            "This is a test alert"
        )
        
        alert_dict = alert.to_dict()
        assert "id" in alert_dict
        assert "type" in alert_dict
        assert "level" in alert_dict
        assert "title" in alert_dict
        assert "message" in alert_dict
        assert "timestamp" in alert_dict
        assert "hash" in alert_dict
    
    def test_alert_to_json(self):
        """Test alert JSON serialization."""
        alert = Alert(
            AlertType.RISK_LIMIT_BREACH,
            AlertLevel.WARNING,
            "Test Alert",
            "This is a test alert"
        )
        
        json_str = alert.to_json()
        assert isinstance(json_str, str)
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["type"] == "risk_limit_breach"
        assert parsed["level"] == "warning"
    
    async def test_alert_manager_initialization(self, alert_manager):
        """Test alert manager initialization."""
        assert alert_manager.log_file is not None
        assert alert_manager.websocket_clients == set()
        assert alert_manager.alert_history == []
        assert alert_manager.max_history == 1000
    
    async def test_send_alert(self, alert_manager):
        """Test sending alerts."""
        success = await alert_manager.send_alert(
            AlertType.RISK_LIMIT_BREACH,
            AlertLevel.WARNING,
            "Test Alert",
            "This is a test alert",
            {"test": "data"}
        )
        
        assert success is True
        assert len(alert_manager.alert_history) == 1
        
        # Verify alert was added to history
        alert = alert_manager.alert_history[0]
        assert alert.alert_type == AlertType.RISK_LIMIT_BREACH
        assert alert.level == AlertLevel.WARNING
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test alert"
    
    async def test_send_risk_alert(self, alert_manager):
        """Test sending risk alerts."""
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
        assert alert.data["current_value"] == 1.5
        assert alert.data["limit_value"] == 1.0
        assert alert.data["symbol"] == "AAPL"
    
    async def test_send_daily_loss_alert(self, alert_manager):
        """Test sending daily loss alerts."""
        await alert_manager.send_daily_loss_alert(
            150.0,
            100.0,
            1.5
        )
        
        assert len(alert_manager.alert_history) == 1
        alert = alert_manager.alert_history[0]
        assert alert.alert_type == AlertType.DAILY_LOSS_LIMIT
        assert alert.level == AlertLevel.CRITICAL
        assert alert.data["current_loss"] == 150.0
        assert alert.data["loss_limit"] == 100.0
        assert alert.data["loss_pct"] == 1.5
    
    async def test_send_order_alert(self, alert_manager):
        """Test sending order alerts."""
        # Test rejected order
        await alert_manager.send_order_alert(
            "order_123",
            "AAPL",
            "buy",
            10.0,
            "rejected",
            "Insufficient balance"
        )
        
        assert len(alert_manager.alert_history) == 1
        alert = alert_manager.alert_history[0]
        assert alert.alert_type == AlertType.ORDER_REJECTED
        assert alert.level == AlertLevel.WARNING
        
        # Test filled order
        await alert_manager.send_order_alert(
            "order_124",
            "MSFT",
            "sell",
            5.0,
            "filled"
        )
        
        assert len(alert_manager.alert_history) == 2
        alert = alert_manager.alert_history[1]
        assert alert.alert_type == AlertType.POSITION_CLOSED
        assert alert.level == AlertLevel.INFO
    
    async def test_send_system_alert(self, alert_manager):
        """Test sending system alerts."""
        await alert_manager.send_system_alert(
            "broker",
            "Connection lost",
            {"retry_count": 3}
        )
        
        assert len(alert_manager.alert_history) == 1
        alert = alert_manager.alert_history[0]
        assert alert.alert_type == AlertType.SYSTEM_ERROR
        assert alert.level == AlertLevel.ERROR
        assert alert.data["component"] == "broker"
        assert alert.data["error"] == "Connection lost"
        assert alert.data["retry_count"] == 3
    
    async def test_send_emergency_stop_alert(self, alert_manager):
        """Test sending emergency stop alerts."""
        await alert_manager.send_emergency_stop_alert("Risk limit exceeded")
        
        assert len(alert_manager.alert_history) == 1
        alert = alert_manager.alert_history[0]
        assert alert.alert_type == AlertType.EMERGENCY_STOP
        assert alert.level == AlertLevel.CRITICAL
        assert alert.data["reason"] == "Risk limit exceeded"
    
    def test_get_recent_alerts(self, alert_manager):
        """Test getting recent alerts."""
        # Add some alerts
        for i in range(5):
            alert = Alert(
                AlertType.SIGNAL_GENERATED,
                AlertLevel.INFO,
                f"Alert {i}",
                f"Message {i}"
            )
            alert_manager.alert_history.append(alert)
        
        recent = alert_manager.get_recent_alerts(3)
        assert len(recent) == 3
        assert recent[0]["title"] == "Alert 2"  # Most recent first
        assert recent[2]["title"] == "Alert 4"
    
    def test_get_alerts_by_type(self, alert_manager):
        """Test getting alerts by type."""
        # Add different types of alerts
        alert1 = Alert(AlertType.SIGNAL_GENERATED, AlertLevel.INFO, "Signal", "Message")
        alert2 = Alert(AlertType.ORDER_REJECTED, AlertLevel.WARNING, "Order", "Message")
        alert3 = Alert(AlertType.SIGNAL_GENERATED, AlertLevel.INFO, "Signal2", "Message")
        
        alert_manager.alert_history = [alert1, alert2, alert3]
        
        signal_alerts = alert_manager.get_alerts_by_type(AlertType.SIGNAL_GENERATED)
        assert len(signal_alerts) == 2
        
        order_alerts = alert_manager.get_alerts_by_type(AlertType.ORDER_REJECTED)
        assert len(order_alerts) == 1
    
    def test_get_alerts_by_level(self, alert_manager):
        """Test getting alerts by level."""
        # Add different level alerts
        alert1 = Alert(AlertType.SIGNAL_GENERATED, AlertLevel.INFO, "Info", "Message")
        alert2 = Alert(AlertType.ORDER_REJECTED, AlertLevel.WARNING, "Warning", "Message")
        alert3 = Alert(AlertType.SIGNAL_GENERATED, AlertLevel.INFO, "Info2", "Message")
        
        alert_manager.alert_history = [alert1, alert2, alert3]
        
        info_alerts = alert_manager.get_alerts_by_level(AlertLevel.INFO)
        assert len(info_alerts) == 2
        
        warning_alerts = alert_manager.get_alerts_by_level(AlertLevel.WARNING)
        assert len(warning_alerts) == 1


class TestAuditSystem:
    """Test the immutable audit logging system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            # On Windows, files might still be in use
            import time
            time.sleep(0.1)
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                pass  # Ignore if still can't delete
    
    @pytest.fixture
    def audit_logger(self, temp_dir):
        """Create audit logger for testing."""
        log_dir = os.path.join(temp_dir, "audit")
        return AuditLogger(log_dir)
    
    def test_audit_event_creation(self):
        """Test audit event creation."""
        event = AuditEvent(
            AuditEventType.SIGNAL_GENERATED,
            "session_123",
            {"symbol": "AAPL", "action": "buy"}
        )
        
        assert event.event_type == AuditEventType.SIGNAL_GENERATED
        assert event.session_id == "session_123"
        assert event.data == {"symbol": "AAPL", "action": "buy"}
        assert event.id is not None
        assert event.hash is not None
    
    def test_audit_event_integrity(self):
        """Test audit event integrity verification."""
        event = AuditEvent(
            AuditEventType.SIGNAL_GENERATED,
            "session_123",
            {"symbol": "AAPL", "action": "buy"}
        )
        
        # Verify integrity
        assert event.verify_integrity() is True
        
        # Tamper with data
        event.data["symbol"] = "MSFT"
        assert event.verify_integrity() is False
    
    def test_audit_event_to_dict(self):
        """Test audit event serialization."""
        event = AuditEvent(
            AuditEventType.SIGNAL_GENERATED,
            "session_123",
            {"symbol": "AAPL", "action": "buy"}
        )
        
        event_dict = event.to_dict()
        assert "id" in event_dict
        assert "event_type" in event_dict
        assert "session_id" in event_dict
        assert "data" in event_dict
        assert "timestamp" in event_dict
        assert "hash" in event_dict
    
    async def test_audit_logger_initialization(self, audit_logger):
        """Test audit logger initialization."""
        assert audit_logger.log_dir is not None
        assert audit_logger.current_session_id is None
        assert audit_logger.daily_logs == {}
    
    async def test_set_session_id(self, audit_logger):
        """Test setting session ID."""
        audit_logger.set_session_id("session_123")
        assert audit_logger.current_session_id == "session_123"
    
    async def test_log_event(self, audit_logger):
        """Test logging events."""
        audit_logger.set_session_id("session_123")
        
        event_id = await audit_logger.log_event(
            AuditEventType.SIGNAL_GENERATED,
            {"symbol": "AAPL", "action": "buy"}
        )
        
        assert event_id is not None
        assert len(event_id) > 0
    
    async def test_log_signal(self, audit_logger):
        """Test logging signals."""
        audit_logger.set_session_id("session_123")
        
        signal = {"symbol": "AAPL", "action": "buy", "confidence": 0.8}
        await audit_logger.log_signal(signal)
        
        # Verify event was logged
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "signal_generated"
        assert events[0]["data"]["signal"] == signal
    
    async def test_log_signal_rejection(self, audit_logger):
        """Test logging signal rejections."""
        audit_logger.set_session_id("session_123")
        
        signal = {"symbol": "AAPL", "action": "buy", "confidence": 0.8}
        await audit_logger.log_signal_rejection(signal, "Risk limit exceeded")
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "signal_rejected"
        assert events[0]["data"]["reason"] == "Risk limit exceeded"
    
    async def test_log_order(self, audit_logger):
        """Test logging orders."""
        audit_logger.set_session_id("session_123")
        
        order = {"id": "order_123", "symbol": "AAPL", "side": "buy", "quantity": 10}
        await audit_logger.log_order(order)
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "order_placed"
        assert events[0]["data"]["order"] == order
    
    async def test_log_order_fill(self, audit_logger):
        """Test logging order fills."""
        audit_logger.set_session_id("session_123")
        
        fill_data = {"price": 150.0, "quantity": 10, "commission": 1.0}
        await audit_logger.log_order_fill("order_123", fill_data)
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "order_filled"
        assert events[0]["data"]["order_id"] == "order_123"
        assert events[0]["data"]["fill_data"] == fill_data
    
    async def test_log_position_opened(self, audit_logger):
        """Test logging position openings."""
        audit_logger.set_session_id("session_123")
        
        position = {"symbol": "AAPL", "quantity": 10, "entry_price": 150.0}
        await audit_logger.log_position_opened(position)
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "position_opened"
        assert events[0]["data"]["position"] == position
    
    async def test_log_position_closed(self, audit_logger):
        """Test logging position closings."""
        audit_logger.set_session_id("session_123")
        
        position = {"symbol": "AAPL", "quantity": 10, "exit_price": 155.0}
        await audit_logger.log_position_closed(position, "Take profit")
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "position_closed"
        assert events[0]["data"]["reason"] == "Take profit"
    
    async def test_log_risk_check(self, audit_logger):
        """Test logging risk checks."""
        audit_logger.set_session_id("session_123")
        
        await audit_logger.log_risk_check(
            "position_size",
            False,
            {"current": 1.5, "limit": 1.0}
        )
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "risk_check"
        assert events[0]["data"]["check_type"] == "position_size"
        assert events[0]["data"]["result"] is False
    
    async def test_log_feature_computation(self, audit_logger):
        """Test logging feature computation."""
        audit_logger.set_session_id("session_123")
        
        features = {"rsi": 30.0, "sma_20": 150.0}
        await audit_logger.log_feature_computation("AAPL", features, 0.05)
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "feature_computed"
        assert events[0]["data"]["symbol"] == "AAPL"
        assert events[0]["data"]["features"] == features
        assert events[0]["data"]["computation_time"] == 0.05
    
    async def test_log_strategy_change(self, audit_logger):
        """Test logging strategy changes."""
        audit_logger.set_session_id("session_123")
        
        await audit_logger.log_strategy_change("mean_reversion", "momentum")
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "strategy_changed"
        assert events[0]["data"]["old_strategy"] == "mean_reversion"
        assert events[0]["data"]["new_strategy"] == "momentum"
    
    async def test_log_trading_start(self, audit_logger):
        """Test logging trading start."""
        audit_logger.set_session_id("session_123")
        
        await audit_logger.log_trading_start("paper", "mean_reversion")
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "trading_started"
        assert events[0]["data"]["mode"] == "paper"
        assert events[0]["data"]["strategy"] == "mean_reversion"
    
    async def test_log_trading_stop(self, audit_logger):
        """Test logging trading stop."""
        audit_logger.set_session_id("session_123")
        
        await audit_logger.log_trading_stop("Manual stop")
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "trading_stopped"
        assert events[0]["data"]["reason"] == "Manual stop"
    
    async def test_log_emergency_stop(self, audit_logger):
        """Test logging emergency stop."""
        audit_logger.set_session_id("session_123")
        
        await audit_logger.log_emergency_stop("Risk limit exceeded")
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "emergency_stop"
        assert events[0]["data"]["reason"] == "Risk limit exceeded"
    
    async def test_log_system_error(self, audit_logger):
        """Test logging system errors."""
        audit_logger.set_session_id("session_123")
        
        await audit_logger.log_system_error("broker", "Connection lost", {"retry": 3})
        
        events = audit_logger.get_session_events("session_123")
        assert len(events) == 1
        assert events[0]["event_type"] == "system_error"
        assert events[0]["data"]["component"] == "broker"
        assert events[0]["data"]["error"] == "Connection lost"
        assert events[0]["data"]["data"]["retry"] == 3
    
    def test_get_events_by_type(self, audit_logger):
        """Test getting events by type."""
        # This would require setting up actual log files
        # For now, just test the method exists
        events = audit_logger.get_events_by_type(AuditEventType.SIGNAL_GENERATED)
        assert isinstance(events, list)
    
    def test_verify_session_integrity(self, audit_logger):
        """Test session integrity verification."""
        # This would require setting up actual log files
        # For now, just test the method exists
        integrity = audit_logger.verify_session_integrity("session_123")
        assert isinstance(integrity, dict)
        assert "session_id" in integrity
        assert "total_events" in integrity


class TestPerformanceAnalytics:
    """Test the performance analytics system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            # On Windows, files might still be in use
            import time
            time.sleep(0.1)
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                pass  # Ignore if still can't delete
    
    @pytest.fixture
    def analytics(self, temp_dir):
        """Create analytics system for testing."""
        return PerformanceAnalytics(temp_dir)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trades for testing."""
        return [
            {
                "id": "trade_1",
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 10,
                "entry_price": 150.0,
                "exit_price": 155.0,
                "pnl": 50.0,
                "entry_time": "2024-01-01T10:00:00Z",
                "exit_time": "2024-01-01T11:00:00Z"
            },
            {
                "id": "trade_2",
                "symbol": "MSFT",
                "side": "buy",
                "quantity": 5,
                "entry_price": 300.0,
                "exit_price": 295.0,
                "pnl": -25.0,
                "entry_time": "2024-01-01T12:00:00Z",
                "exit_time": "2024-01-01T13:00:00Z"
            },
            {
                "id": "trade_3",
                "symbol": "GOOGL",
                "side": "buy",
                "quantity": 2,
                "entry_price": 2800.0,
                "exit_price": 2850.0,
                "pnl": 100.0,
                "entry_time": "2024-01-02T10:00:00Z",
                "exit_time": "2024-01-02T14:00:00Z"
            }
        ]
    
    def test_trade_metrics_calculation(self, analytics, sample_trades):
        """Test trade metrics calculation."""
        metrics = analytics._calculate_trade_metrics(sample_trades)
        
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.win_rate == (2/3) * 100
        assert metrics.avg_winner == 75.0  # (50 + 100) / 2
        assert metrics.avg_loser == -25.0
        assert metrics.profit_factor == 150.0 / 25.0  # 6.0
        assert metrics.total_pnl == 125.0  # 50 - 25 + 100
        assert metrics.best_trade == 100.0
        assert metrics.worst_trade == -25.0
    
    def test_max_drawdown_calculation(self, analytics):
        """Test maximum drawdown calculation."""
        trades = [
            {"pnl": 50.0},
            {"pnl": -25.0},
            {"pnl": 100.0},
            {"pnl": -50.0}
        ]
        
        max_dd, max_dd_pct = analytics._calculate_max_drawdown(trades)
        assert max_dd > 0
        assert max_dd_pct > 0
    
    def test_sharpe_ratio_calculation(self, analytics):
        """Test Sharpe ratio calculation."""
        returns = [50.0, -25.0, 100.0, -50.0]
        sharpe = analytics._calculate_sharpe_ratio(returns)
        assert isinstance(sharpe, float)
    
    def test_daily_returns_calculation(self, analytics, sample_trades):
        """Test daily returns calculation."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 3, tzinfo=timezone.utc)
        
        daily_returns = analytics._calculate_daily_returns(
            sample_trades, start_date, end_date
        )
        
        assert len(daily_returns) == 3  # 3 days
        assert daily_returns[0] == 25.0  # 50 - 25
        assert daily_returns[1] == 100.0  # 100
        assert daily_returns[2] == 0.0  # No trades
    
    def test_equity_curve_generation(self, analytics, sample_trades):
        """Test equity curve generation."""
        initial_balance = 10000.0
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 3, tzinfo=timezone.utc)
        
        equity_curve = analytics._generate_equity_curve(
            sample_trades, initial_balance, start_date, end_date
        )
        
        assert len(equity_curve) == 3  # 3 trades
        assert equity_curve[0]["balance"] == 10050.0  # 10000 + 50 (first trade)
        assert equity_curve[1]["balance"] == 10025.0  # 10050 - 25 (second trade)
        assert equity_curve[2]["balance"] == 10125.0  # 10025 + 100 (third trade)
    
    async def test_analyze_session(self, analytics, sample_trades):
        """Test session analysis."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 3, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id="session_123",
            trades=sample_trades,
            positions=[],
            initial_balance=10000.0,
            final_balance=10125.0,
            start_date=start_date,
            end_date=end_date,
            strategy="mean_reversion",
            mode="paper"
        )
        
        assert report.session_id == "session_123"
        assert report.strategy == "mean_reversion"
        assert report.mode == "paper"
        assert report.initial_balance == 10000.0
        assert report.final_balance == 10125.0
        assert report.total_return == 125.0
        assert report.total_return_pct == 1.25
        assert report.trade_metrics.total_trades == 3
    
    async def test_generate_html_report(self, analytics, sample_trades):
        """Test HTML report generation."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 3, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id="session_123",
            trades=sample_trades,
            positions=[],
            initial_balance=10000.0,
            final_balance=10125.0,
            start_date=start_date,
            end_date=end_date,
            strategy="mean_reversion",
            mode="paper"
        )
        
        html_content = await analytics.generate_html_report(report)
        assert isinstance(html_content, str)
        assert "<html>" in html_content
        assert "Trading Performance Report" in html_content
        assert "session_123" in html_content
        assert "mean_reversion" in html_content
    
    async def test_generate_csv_report(self, analytics, sample_trades):
        """Test CSV report generation."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 3, tzinfo=timezone.utc)
        
        report = await analytics.analyze_session(
            session_id="session_123",
            trades=sample_trades,
            positions=[],
            initial_balance=10000.0,
            final_balance=10125.0,
            start_date=start_date,
            end_date=end_date,
            strategy="mean_reversion",
            mode="paper"
        )
        
        csv_content = await analytics.generate_csv_report(report)
        assert isinstance(csv_content, str)
        assert "Session ID,session_123" in csv_content
        assert "Strategy,mean_reversion" in csv_content
        assert "Total Return,125.0" in csv_content
    
    async def test_compare_strategies(self, analytics):
        """Test strategy comparison."""
        # Create mock reports
        report1 = PerformanceReport(
            session_id="session_1",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            strategy="mean_reversion",
            mode="paper",
            initial_balance=10000.0,
            final_balance=10500.0,
            total_return=500.0,
            total_return_pct=5.0,
            trade_metrics=TradeMetrics(
                total_trades=10, winning_trades=6, losing_trades=4,
                win_rate=60.0, avg_winner=100.0, avg_loser=-50.0,
                profit_factor=2.0, total_pnl=500.0, max_drawdown=100.0,
                max_drawdown_pct=1.0, sharpe_ratio=1.5, avg_holding_time=2.0,
                best_trade=200.0, worst_trade=-100.0
            ),
            daily_returns=[],
            equity_curve=[],
            trade_log=[]
        )
        
        report2 = PerformanceReport(
            session_id="session_2",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            strategy="momentum",
            mode="paper",
            initial_balance=10000.0,
            final_balance=10200.0,
            total_return=200.0,
            total_return_pct=2.0,
            trade_metrics=TradeMetrics(
                total_trades=8, winning_trades=4, losing_trades=4,
                win_rate=50.0, avg_winner=80.0, avg_loser=-40.0,
                profit_factor=1.5, total_pnl=200.0, max_drawdown=150.0,
                max_drawdown_pct=1.5, sharpe_ratio=1.0, avg_holding_time=1.5,
                best_trade=150.0, worst_trade=-80.0
            ),
            daily_returns=[],
            equity_curve=[],
            trade_log=[]
        )
        
        comparison = await analytics.compare_strategies([report1, report2])
        
        assert len(comparison["strategies"]) == 2
        assert comparison["best_performer"] == "mean_reversion"
        assert comparison["worst_performer"] == "momentum"
        assert "summary" in comparison
        assert comparison["summary"]["avg_return"] == 3.5  # (5.0 + 2.0) / 2


class TestPhase6Integration:
    """Integration tests for Phase 6 monitoring and safety."""
    
    async def test_alert_audit_integration(self):
        """Test integration between alert and audit systems."""
        # This would test that alerts are properly logged in audit trail
        pass
    
    async def test_analytics_audit_integration(self):
        """Test integration between analytics and audit systems."""
        # This would test that analytics can read from audit logs
        pass
    
    async def test_complete_monitoring_flow(self):
        """Test complete monitoring flow from signal to report."""
        # This would test the entire monitoring pipeline
        pass
