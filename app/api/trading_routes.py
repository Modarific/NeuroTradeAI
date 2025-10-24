"""
Trading API routes.
REST endpoints for trading control, positions, orders, and performance.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging
import uuid
import json

from app.trading.engine import TradingEngine
from app.trading.brokers.alpaca_adapter import AlpacaAdapter
from app.trading.brokers.simulator import SimulatorAdapter
from app.trading.strategies.mean_reversion import MeanReversionStrategy
from app.trading.strategies.momentum import MomentumStrategy
from app.trading.strategies.news_driven import NewsDrivenStrategy
from app.core.trading_db import TradingDatabase
from app.config import TRADING_CONFIG

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/trading", tags=["trading"])

# Global trading state
trading_engine = None
trading_db = None
websocket_connections = []


class TradingStatus(BaseModel):
    """Trading system status."""
    is_running: bool
    mode: str  # 'paper' or 'live'
    broker: str
    strategy: Optional[str]
    is_armed: bool
    positions_count: int
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    risk_status: str  # 'safe', 'warning', 'critical'


class PositionInfo(BaseModel):
    """Position information."""
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_time: str
    stop_loss: Optional[float]
    take_profit: Optional[float]


class OrderInfo(BaseModel):
    """Order information."""
    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    status: str
    limit_price: Optional[float]
    stop_price: Optional[float]
    filled_price: Optional[float]
    filled_quantity: Optional[float]
    submission_time: str
    close_time: Optional[str]
    reasoning: Optional[str]


class PerformanceMetrics(BaseModel):
    """Performance metrics."""
    total_return: float
    total_return_pct: float
    daily_return: float
    daily_return_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_winner: float
    avg_loser: float


class ArmRequest(BaseModel):
    """Arm/disarm trading request."""
    action: str  # 'arm' or 'disarm'
    confirmation_key: str


class StrategyRequest(BaseModel):
    """Strategy selection request."""
    strategy_name: str
    parameters: Optional[Dict[str, Any]] = None


class ManualOrderRequest(BaseModel):
    """Manual order request."""
    symbol: str
    side: str
    quantity: float
    order_type: str = "market"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    reasoning: str = "Manual order"


def get_trading_engine() -> TradingEngine:
    """Get trading engine instance."""
    global trading_engine
    if trading_engine is None:
        trading_engine = TradingEngine()
    return trading_engine


def get_trading_db() -> TradingDatabase:
    """Get trading database instance."""
    global trading_db
    if trading_db is None:
        trading_db = TradingDatabase("data/trading.db")
    return trading_db


@router.get("/status", response_model=TradingStatus)
async def get_trading_status(engine: TradingEngine = Depends(get_trading_engine)):
    """
    Get current trading system status.
    
    Returns:
        Trading system status
    """
    try:
        status = await engine.get_status()
        return TradingStatus(**status)
    except Exception as e:
        logger.error(f"Error getting trading status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {e}")


@router.post("/arm")
async def arm_trading(
    request: ArmRequest,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """
    Arm or disarm live trading.
    
    Args:
        request: Arm/disarm request with confirmation key
        engine: Trading engine instance
        
    Returns:
        Success message
    """
    try:
        if request.action == "arm":
            success = await engine.arm_live_trading(request.confirmation_key)
            if not success:
                raise HTTPException(status_code=400, detail="Invalid confirmation key")
            message = "Live trading armed successfully"
        else:
            await engine.disarm_live_trading()
            message = "Live trading disarmed"
        
        # Broadcast status update
        await broadcast_trading_update("status_update", await engine.get_status())
        
        return {"message": message, "armed": request.action == "arm"}
        
    except Exception as e:
        logger.error(f"Error arming/disarming trading: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.post("/start")
async def start_trading(
    engine: TradingEngine = Depends(get_trading_engine),
    background_tasks: BackgroundTasks = None
):
    """
    Start the trading engine.
    
    Args:
        engine: Trading engine instance
        background_tasks: FastAPI background tasks
        
    Returns:
        Success message
    """
    try:
        if engine.is_running():
            raise HTTPException(status_code=400, detail="Trading engine already running")
        
        # Start trading engine in background
        if background_tasks:
            background_tasks.add_task(engine.start)
        else:
            await engine.start()
        
        # Broadcast status update
        await broadcast_trading_update("status_update", await engine.get_status())
        
        logger.info("Trading engine started")
        return {"message": "Trading engine started successfully"}
        
    except Exception as e:
        logger.error(f"Error starting trading engine: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting trading: {e}")


@router.post("/stop")
async def stop_trading(engine: TradingEngine = Depends(get_trading_engine)):
    """
    Stop the trading engine.
    
    Args:
        engine: Trading engine instance
        
    Returns:
        Success message
    """
    try:
        if not engine.is_running():
            raise HTTPException(status_code=400, detail="Trading engine not running")
        
        await engine.stop()
        
        # Broadcast status update
        await broadcast_trading_update("status_update", await engine.get_status())
        
        logger.info("Trading engine stopped")
        return {"message": "Trading engine stopped successfully"}
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error stopping trading engine: {e}")
        raise HTTPException(status_code=500, detail=f"Error stopping trading: {e}")


@router.post("/emergency_stop")
async def emergency_stop(engine: TradingEngine = Depends(get_trading_engine)):
    """
    Emergency stop - close all positions immediately.
    
    Args:
        engine: Trading engine instance
        
    Returns:
        Success message
    """
    try:
        await engine.emergency_stop()
        
        # Broadcast status update
        await broadcast_trading_update("emergency_stop", {"message": "Emergency stop executed"})
        
        logger.warning("Emergency stop executed")
        return {"message": "Emergency stop executed - all positions closed"}
        
    except Exception as e:
        logger.error(f"Error executing emergency stop: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing emergency stop: {e}")


@router.get("/positions", response_model=List[PositionInfo])
async def get_positions(engine: TradingEngine = Depends(get_trading_engine)):
    """
    Get current positions.
    
    Args:
        engine: Trading engine instance
        
    Returns:
        List of current positions
    """
    try:
        positions = await engine.get_positions()
        return [PositionInfo(**pos) for pos in positions]
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting positions: {e}")


@router.get("/orders", response_model=List[OrderInfo])
async def get_orders(
    status: Optional[str] = None,
    limit: int = 100,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """
    Get order history.
    
    Args:
        status: Filter by order status
        limit: Maximum number of orders to return
        engine: Trading engine instance
        
    Returns:
        List of orders
    """
    try:
        orders = await engine.get_orders(status=status, limit=limit)
        return [OrderInfo(**order) for order in orders]
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting orders: {e}")


@router.get("/performance", response_model=PerformanceMetrics)
async def get_performance(engine: TradingEngine = Depends(get_trading_engine)):
    """
    Get performance metrics.
    
    Args:
        engine: Trading engine instance
        
    Returns:
        Performance metrics
    """
    try:
        metrics = await engine.get_performance_metrics()
        return PerformanceMetrics(**metrics)
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting performance: {e}")


@router.post("/strategy/select")
async def select_strategy(
    request: StrategyRequest,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """
    Change active trading strategy.
    
    Args:
        request: Strategy selection request
        engine: Trading engine instance
        
    Returns:
        Success message
    """
    try:
        await engine.set_strategy(request.strategy_name, request.parameters)
        
        # Broadcast status update
        await broadcast_trading_update("strategy_changed", {
            "strategy": request.strategy_name,
            "parameters": request.parameters
        })
        
        return {"message": f"Strategy changed to {request.strategy_name}"}
        
    except Exception as e:
        logger.error(f"Error changing strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Error changing strategy: {e}")


@router.post("/manual_order")
async def place_manual_order(
    request: ManualOrderRequest,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """
    Place a manual order (override).
    
    Args:
        request: Manual order request
        engine: Trading engine instance
        
    Returns:
        Order information
    """
    try:
        order = await engine.place_manual_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            reasoning=request.reasoning
        )
        
        # Broadcast order update
        await broadcast_trading_update("order_placed", order)
        
        return {"message": "Manual order placed successfully", "order": order}
        
    except Exception as e:
        logger.error(f"Error placing manual order: {e}")
        raise HTTPException(status_code=500, detail=f"Error placing order: {e}")


@router.websocket("/ws")
async def trading_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time trading updates.
    
    Args:
        websocket: WebSocket connection
    """
    await websocket.accept()
    websocket_connections.append(websocket)
    
    try:
        # Send initial status
        engine = get_trading_engine()
        status = await engine.get_status()
        await websocket.send_text(json.dumps({
            "type": "status_update",
            "data": status
        }))
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        logger.info("Trading WebSocket disconnected")
    except Exception as e:
        logger.error(f"Trading WebSocket error: {e}")
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


async def broadcast_trading_update(message_type: str, data: Any):
    """
    Broadcast trading update to all connected WebSocket clients.
    
    Args:
        message_type: Type of update
        data: Update data
    """
    if not websocket_connections:
        return
    
    message = {
        "type": message_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    message_text = json.dumps(message)
    disconnected = []
    
    for websocket in websocket_connections:
        try:
            await websocket.send_text(message_text)
        except Exception as e:
            logger.error(f"Error broadcasting to WebSocket: {e}")
            disconnected.append(websocket)
    
    # Remove disconnected connections
    for websocket in disconnected:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


@router.get("/risk/status")
async def get_risk_status(engine: TradingEngine = Depends(get_trading_engine)):
    """
    Get current risk status.
    
    Args:
        engine: Trading engine instance
        
    Returns:
        Risk status information
    """
    try:
        risk_status = await engine.get_risk_status()
        return risk_status
    except Exception as e:
        logger.error(f"Error getting risk status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting risk status: {e}")


@router.get("/session/current")
async def get_current_session(engine: TradingEngine = Depends(get_trading_engine)):
    """
    Get current trading session information.
    
    Args:
        engine: Trading engine instance
        
    Returns:
        Current session information
    """
    try:
        session = await engine.get_current_session()
        return session
    except Exception as e:
        logger.error(f"Error getting current session: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting session: {e}")


@router.get("/session/history")
async def get_session_history(
    limit: int = 50,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """
    Get trading session history.
    
    Args:
        limit: Maximum number of sessions to return
        engine: Trading engine instance
        
    Returns:
        List of trading sessions
    """
    try:
        sessions = await engine.get_session_history(limit=limit)
        return sessions
    except Exception as e:
        logger.error(f"Error getting session history: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting session history: {e}")


@router.get("/alerts")
async def get_alerts(engine: TradingEngine = Depends(get_trading_engine)):
    """
    Get recent trading alerts.
    
    Args:
        engine: Trading engine instance
        
    Returns:
        List of recent alerts
    """
    try:
        alerts = await engine.get_recent_alerts()
        return alerts
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting alerts: {e}")


@router.post("/broker/configure")
async def configure_broker(
    broker_config: dict,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """
    Configure broker settings.
    
    Args:
        broker_config: Broker configuration including API keys
        engine: Trading engine instance
        
    Returns:
        Configuration result
    """
    try:
        # Store broker configuration
        result = await engine.configure_broker(broker_config)
        return result
    except Exception as e:
        logger.error(f"Error configuring broker: {e}")
        raise HTTPException(status_code=500, detail=f"Error configuring broker: {e}")


@router.post("/broker/test")
async def test_broker_connection(
    broker_info: dict,
    engine: TradingEngine = Depends(get_trading_engine)
):
    """
    Test broker connection.
    
    Args:
        broker_info: Broker information
        engine: Trading engine instance
        
    Returns:
        Connection test result
    """
    try:
        result = await engine.test_broker_connection(broker_info.get('broker'))
        return result
    except Exception as e:
        logger.error(f"Error testing broker connection: {e}")
        raise HTTPException(status_code=500, detail=f"Error testing broker connection: {e}")


@router.get("/data/latest")
async def get_latest_market_data():
    """
    Get latest market data for all tracked symbols.
    
    Returns:
        Dictionary of latest data for each symbol
    """
    try:
        from app.core.storage import StorageManager
        from app.config import DATA_PATH, DB_PATH
        from datetime import datetime, timezone
        import sqlite3
        
        storage = StorageManager(DATA_PATH, DB_PATH)
        
        # Try to get real data from database
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                
                # Get latest data for each symbol
                cursor.execute("""
                    SELECT symbol, timestamp, open, high, low, close, volume
                    FROM bars 
                    WHERE timestamp = (
                        SELECT MAX(timestamp) 
                        FROM bars b2 
                        WHERE b2.symbol = bars.symbol
                    )
                    ORDER BY symbol
                """)
                
                rows = cursor.fetchall()
                
                # Convert to dictionary format
                latest_data = {}
                for row in rows:
                    symbol, timestamp, open_price, high, low, close, volume = row
                    latest_data[symbol] = {
                        "price": close,
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": volume,
                        "change": 0,  # Calculate if needed
                        "change_percent": 0,  # Calculate if needed
                        "timestamp": timestamp,
                        "signal": "HOLD",  # Default signal
                        "rsi": 50,  # Default RSI
                        "bb_position": 0.5  # Default BB position
                    }
                
                if latest_data:
                    return latest_data
        except Exception as db_error:
            logger.warning(f"Database query failed, using sample data: {db_error}")
        
        # Return sample data for testing
        return {
            "AAPL": {
                "price": 150.25,
                "open": 149.80,
                "high": 151.20,
                "low": 149.50,
                "close": 150.25,
                "volume": 45000000,
                "change": 0.45,
                "change_percent": 0.30,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal": "BUY",
                "rsi": 45.2,
                "bb_position": 0.3
            },
            "MSFT": {
                "price": 330.15,
                "open": 328.90,
                "high": 331.50,
                "low": 328.20,
                "close": 330.15,
                "volume": 28000000,
                "change": 1.25,
                "change_percent": 0.38,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal": "HOLD",
                "rsi": 52.8,
                "bb_position": 0.6
            },
            "GOOGL": {
                "price": 2750.80,
                "open": 2745.20,
                "high": 2755.90,
                "low": 2740.10,
                "close": 2750.80,
                "volume": 1200000,
                "change": 5.60,
                "change_percent": 0.20,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal": "SELL",
                "rsi": 65.4,
                "bb_position": 0.8
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting latest market data: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting latest market data: {e}")
