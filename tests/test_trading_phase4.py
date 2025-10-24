"""
Tests for Phase 4: Web Dashboard Integration
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json

from app.main import app
from app.trading.engine import TradingEngine
from app.trading.brokers.simulator import SimulatorAdapter
from app.trading.strategies.mean_reversion import MeanReversionStrategy


class TestTradingAPI:
    """Test trading API endpoints."""
    
    def test_trading_status_endpoint(self):
        """Test trading status endpoint."""
        with TestClient(app) as client:
            response = client.get("/api/v1/trading/status")
            assert response.status_code == 200
            data = response.json()
            assert "is_running" in data
            assert "mode" in data
            assert "broker" in data
    
    def test_trading_start_endpoint(self):
        """Test trading start endpoint."""
        with TestClient(app) as client:
            response = client.post("/api/v1/trading/start")
            # Should return 200 or 400 (already running)
            assert response.status_code in [200, 400]
    
    def test_trading_stop_endpoint(self):
        """Test trading stop endpoint."""
        with TestClient(app) as client:
            response = client.post("/api/v1/trading/stop")
            # Should return 200 or 400 (not running)
            assert response.status_code in [200, 400]
    
    def test_emergency_stop_endpoint(self):
        """Test emergency stop endpoint."""
        with TestClient(app) as client:
            response = client.post("/api/v1/trading/emergency_stop")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
    
    def test_positions_endpoint(self):
        """Test positions endpoint."""
        with TestClient(app) as client:
            response = client.get("/api/v1/trading/positions")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
    
    def test_orders_endpoint(self):
        """Test orders endpoint."""
        with TestClient(app) as client:
            response = client.get("/api/v1/trading/orders")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
    
    def test_performance_endpoint(self):
        """Test performance endpoint."""
        with TestClient(app) as client:
            response = client.get("/api/v1/trading/performance")
            assert response.status_code == 200
            data = response.json()
            assert "total_return" in data
            assert "win_rate" in data
            assert "total_trades" in data
    
    def test_strategy_selection_endpoint(self):
        """Test strategy selection endpoint."""
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/trading/strategy/select",
                json={"strategy_name": "mean_reversion"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
    
    def test_manual_order_endpoint(self):
        """Test manual order endpoint."""
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/trading/manual_order",
                json={
                    "symbol": "AAPL",
                    "side": "buy",
                    "quantity": 10,
                    "reasoning": "Test order"
                }
            )
            # Should return 200 or 500 (depending on broker state)
            assert response.status_code in [200, 500]
    
    def test_arm_trading_endpoint(self):
        """Test arm trading endpoint."""
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/trading/arm",
                json={"action": "arm", "confirmation_key": "LIVE_TRADING_CONFIRM"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "armed" in data
    
    def test_disarm_trading_endpoint(self):
        """Test disarm trading endpoint."""
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/trading/arm",
                json={"action": "disarm", "confirmation_key": ""}
            )
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "armed" in data


class TestBacktestAPI:
    """Test backtesting API endpoints."""
    
    def test_backtest_run_endpoint(self):
        """Test backtest run endpoint."""
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/backtest/run",
                json={
                    "strategy_name": "mean_reversion",
                    "symbols": ["AAPL"],
                    "start_date": "2023-01-01T00:00:00Z",
                    "end_date": "2023-01-02T00:00:00Z",
                    "initial_balance": 100000.0
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "backtest_id" in data
            assert "status" in data
    
    def test_backtest_status_endpoint(self):
        """Test backtest status endpoint."""
        with TestClient(app) as client:
            # First run a backtest
            run_response = client.post(
                "/api/v1/backtest/run",
                json={
                    "strategy_name": "mean_reversion",
                    "symbols": ["AAPL"],
                    "start_date": "2023-01-01T00:00:00Z",
                    "end_date": "2023-01-02T00:00:00Z"
                }
            )
            
            if run_response.status_code == 200:
                backtest_id = run_response.json()["backtest_id"]
                
                # Check status
                status_response = client.get(f"/api/v1/backtest/status/{backtest_id}")
                assert status_response.status_code == 200
                data = status_response.json()
                assert "backtest_id" in data
                assert "status" in data
    
    def test_backtest_list_endpoint(self):
        """Test backtest list endpoint."""
        with TestClient(app) as client:
            response = client.get("/api/v1/backtest/list")
            assert response.status_code == 200
            data = response.json()
            assert "backtests" in data
            assert "total" in data
    
    def test_backtest_strategies_endpoint(self):
        """Test available strategies endpoint."""
        with TestClient(app) as client:
            response = client.get("/api/v1/backtest/strategies")
            assert response.status_code == 200
            data = response.json()
            assert "strategies" in data
            assert len(data["strategies"]) > 0
    
    def test_backtest_metrics_endpoint(self):
        """Test backtest metrics endpoint."""
        with TestClient(app) as client:
            # First run a backtest
            run_response = client.post(
                "/api/v1/backtest/run",
                json={
                    "strategy_name": "mean_reversion",
                    "symbols": ["AAPL"],
                    "start_date": "2023-01-01T00:00:00Z",
                    "end_date": "2023-01-02T00:00:00Z"
                }
            )
            
            if run_response.status_code == 200:
                backtest_id = run_response.json()["backtest_id"]
                
                # Check metrics
                metrics_response = client.get(f"/api/v1/backtest/metrics/{backtest_id}")
                # Should return 200 or 400 (depending on completion status)
                assert metrics_response.status_code in [200, 400]


class TestTradingEngine:
    """Test trading engine functionality."""
    
    def test_trading_engine_initialization(self):
        """Test trading engine initialization."""
        engine = TradingEngine()
        assert engine is not None
        assert not engine.is_running()
    
    async def test_trading_engine_set_strategy(self):
        """Test setting trading strategy."""
        engine = TradingEngine()
        
        # Test setting mean reversion strategy
        await engine.set_strategy("mean_reversion")
        assert engine.current_strategy is not None
        assert engine.current_strategy.name == "mean_reversion"
    
    async def test_trading_engine_arm_disarm(self):
        """Test arming and disarming trading."""
        engine = TradingEngine()
        
        # Test arming
        success = await engine.arm_live_trading("LIVE_TRADING_CONFIRM")
        assert success is True
        assert engine.is_armed is True
        
        # Test disarming
        await engine.disarm_live_trading()
        assert engine.is_armed is False
    
    async def test_trading_engine_invalid_arm_key(self):
        """Test arming with invalid key."""
        engine = TradingEngine()
        
        success = await engine.arm_live_trading("INVALID_KEY")
        assert success is False
        assert engine.is_armed is False


class TestTradingComponents:
    """Test trading components integration."""
    
    def test_portfolio_initialization(self):
        """Test portfolio initialization."""
        from app.trading.portfolio import Portfolio
        from app.trading.brokers.simulator import SimulatorAdapter
        from app.core.trading_db import TradingDatabase
        
        broker = SimulatorAdapter({"initial_balance": 100000.0})
        trading_db = TradingDatabase(":memory:")
        portfolio = Portfolio(broker, trading_db)
        
        assert portfolio is not None
        assert portfolio.broker == broker
        assert portfolio.trading_db == trading_db
    
    def test_execution_engine_initialization(self):
        """Test execution engine initialization."""
        from app.trading.execution import ExecutionEngine
        from app.trading.brokers.simulator import SimulatorAdapter
        from app.core.trading_db import TradingDatabase
        
        broker = SimulatorAdapter({"initial_balance": 100000.0})
        trading_db = TradingDatabase(":memory:")
        execution_engine = ExecutionEngine(broker, trading_db)
        
        assert execution_engine is not None
        assert execution_engine.broker == broker
        assert execution_engine.trading_db == trading_db
    
    def test_alert_manager_initialization(self):
        """Test alert manager initialization."""
        from app.trading.alerts import AlertManager
        
        alert_manager = AlertManager()
        assert alert_manager is not None
        assert alert_manager.alert_history == []
    
    def test_audit_logger_initialization(self):
        """Test audit logger initialization."""
        from app.trading.audit import AuditLogger
        
        audit_logger = AuditLogger()
        assert audit_logger is not None
        assert audit_logger.log_dir == "logs"


class TestWebSocketIntegration:
    """Test WebSocket integration for trading updates."""
    
    def test_trading_websocket_endpoint(self):
        """Test trading WebSocket endpoint."""
        with TestClient(app) as client:
            with client.websocket_connect("/api/v1/trading/ws") as websocket:
                # Should receive initial status update
                data = websocket.receive_text()
                message = json.loads(data)
                assert "type" in message
                assert "data" in message


class TestDashboardIntegration:
    """Test dashboard integration."""
    
    def test_dashboard_serves_trading_controls(self):
        """Test that dashboard includes trading controls."""
        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            content = response.text
            
            # Check for trading control elements
            assert "Trading Panel" in content
            assert "Backtesting" in content
            assert "Risk Monitor" in content
            assert "trading.js" in content
    
    def test_trading_modals_present(self):
        """Test that trading modals are present in HTML."""
        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            content = response.text
            
            # Check for trading modals
            assert "tradingModal" in content
            assert "backtestModal" in content
            assert "riskModal" in content
    
    def test_trading_dashboard_cards_present(self):
        """Test that trading dashboard cards are present."""
        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            content = response.text
            
            # Check for trading dashboard cards
            assert "Trading Status" in content
            assert "Positions" in content
            assert "Orders" in content
            assert "Performance" in content


class TestIntegration:
    """Integration tests for Phase 4."""
    
    def test_complete_trading_flow(self):
        """Test complete trading flow from API to dashboard."""
        with TestClient(app) as client:
            # 1. Check initial status
            status_response = client.get("/api/v1/trading/status")
            assert status_response.status_code == 200
            
            # 2. Change strategy
            strategy_response = client.post(
                "/api/v1/trading/strategy/select",
                json={"strategy_name": "mean_reversion"}
            )
            assert strategy_response.status_code == 200
            
            # 3. Arm trading
            arm_response = client.post(
                "/api/v1/trading/arm",
                json={"action": "arm", "confirmation_key": "LIVE_TRADING_CONFIRM"}
            )
            assert arm_response.status_code == 200
            
            # 4. Start trading
            start_response = client.post("/api/v1/trading/start")
            assert start_response.status_code in [200, 400]  # May already be running
            
            # 5. Check positions
            positions_response = client.get("/api/v1/trading/positions")
            assert positions_response.status_code == 200
            
            # 6. Check orders
            orders_response = client.get("/api/v1/trading/orders")
            assert orders_response.status_code == 200
            
            # 7. Check performance
            performance_response = client.get("/api/v1/trading/performance")
            assert performance_response.status_code == 200
    
    def test_backtest_workflow(self):
        """Test complete backtesting workflow."""
        with TestClient(app) as client:
            # 1. Run backtest
            run_response = client.post(
                "/api/v1/backtest/run",
                json={
                    "strategy_name": "mean_reversion",
                    "symbols": ["AAPL"],
                    "start_date": "2023-01-01T00:00:00Z",
                    "end_date": "2023-01-02T00:00:00Z",
                    "initial_balance": 100000.0
                }
            )
            assert run_response.status_code == 200
            backtest_id = run_response.json()["backtest_id"]
            
            # 2. Check status
            status_response = client.get(f"/api/v1/backtest/status/{backtest_id}")
            assert status_response.status_code == 200
            
            # 3. List backtests
            list_response = client.get("/api/v1/backtest/list")
            assert list_response.status_code == 200
            
            # 4. Get available strategies
            strategies_response = client.get("/api/v1/backtest/strategies")
            assert strategies_response.status_code == 200
    
    def test_websocket_trading_updates(self):
        """Test WebSocket trading updates."""
        with TestClient(app) as client:
            with client.websocket_connect("/api/v1/trading/ws") as websocket:
                # Should receive initial status update
                data = websocket.receive_text()
                message = json.loads(data)
                assert message["type"] == "status_update"
                assert "data" in message


if __name__ == "__main__":
    pytest.main([__file__])
