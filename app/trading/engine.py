"""
Main trading engine orchestrator.
Coordinates all trading components and manages the trading loop.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import json
import uuid

from app.trading.brokers.alpaca_adapter import AlpacaAdapter
from app.trading.brokers.simulator import SimulatorAdapter
from app.trading.strategies.mean_reversion import MeanReversionStrategy
from app.trading.strategies.momentum import MomentumStrategy
from app.trading.strategies.news_driven import NewsDrivenStrategy
from app.trading.risk_manager import RiskManager
from app.trading.execution import ExecutionEngine
from app.trading.portfolio import Portfolio
from app.trading.alerts import AlertManager
from app.trading.audit import AuditLogger
from app.core.trading_db import TradingDatabase
from app.config import TRADING_CONFIG
from app.core.storage import StorageManager

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Main trading engine orchestrator.
    
    Responsibilities:
    - Coordinate all trading components
    - Manage trading loop
    - Handle system state
    - Provide API interface
    """
    
    def __init__(self):
        """Initialize trading engine."""
        self.config = TRADING_CONFIG
        self.is_running_flag = False
        self.is_armed = False
        self.current_session_id = None
        self._pending_strategy = None
        
        # Initialize components
        self.storage_manager = StorageManager("data", "data/trading.db")
        self.trading_db = TradingDatabase("data/trading.db")
        self.trading_db.initialize_tables()
        self.alert_manager = AlertManager()
        self.audit_logger = AuditLogger()
        
        # Initialize broker
        self.broker = self._create_broker()
        
        # Initialize trading components
        self.risk_manager = RiskManager(self.config.get('risk_limits', {}))
        self.execution_engine = ExecutionEngine(self.broker, self.trading_db)
        self.portfolio = Portfolio(self.broker, self.trading_db)
        
        # Initialize strategy
        self.current_strategy = None
        self._set_default_strategy()
        
        # Trading loop task
        self.trading_task = None
        
        logger.info("Trading engine initialized")
    
    def _create_broker(self):
        """Create broker adapter based on configuration."""
        broker_name = self.config.get('broker', 'simulator')
        
        if broker_name == 'alpaca':
            return AlpacaAdapter({
                'paper': self.config.get('mode', 'paper') == 'paper'
            })
        else:
            return SimulatorAdapter({"initial_balance": 100000.0})
    
    def _set_default_strategy(self):
        """Set default strategy."""
        strategy_name = self.config.get('default_strategy', 'mean_reversion')
        # Store strategy name for later async initialization
        self._pending_strategy = strategy_name
    
    async def start(self):
        """Start the trading engine."""
        try:
            if self.is_running_flag:
                logger.warning("Trading engine already running")
                return
            
            # Connect to broker
            try:
                connected = await self.broker.connect()
                if not connected:
                    logger.warning("Broker connection failed, using simulator")
                    # Fallback to simulator if broker connection fails
                    from app.trading.brokers.simulator_adapter import SimulatorAdapter
                    self.broker = SimulatorAdapter()
                    await self.broker.connect()
            except Exception as e:
                logger.warning(f"Broker connection error: {e}, using simulator")
                # Fallback to simulator
                from app.trading.brokers.simulator_adapter import SimulatorAdapter
                self.broker = SimulatorAdapter()
                await self.broker.connect()
            
            # Set pending strategy if any
            if self._pending_strategy:
                await self.set_strategy(self._pending_strategy)
                self._pending_strategy = None
            
            # Start trading session
            self.current_session_id = self.trading_db.create_session(
                mode="paper" if self.config.get('mode', 'paper') == 'paper' else "live",
                strategy_name=self.current_strategy.name if self.current_strategy else "unknown",
                initial_balance=await self._get_account_equity()
            )
            
            # Start trading loop
            self.is_running_flag = True
            self.trading_task = asyncio.create_task(self._trading_loop())
            
            logger.info(f"Trading engine started with session {self.current_session_id}")
            
        except Exception as e:
            logger.error(f"Error starting trading engine: {e}")
            self.is_running_flag = False
            raise
    
    async def stop(self):
        """Stop the trading engine."""
        try:
            if not self.is_running_flag:
                logger.warning("Trading engine not running")
                return
            
            # Stop trading loop
            self.is_running_flag = False
            
            if self.trading_task:
                self.trading_task.cancel()
                try:
                    await self.trading_task
                except asyncio.CancelledError:
                    pass
            
            # End trading session
            if self.current_session_id:
                final_equity = await self._get_account_equity()
                # Calculate session metrics (simplified for now)
                total_trades = 0  # TODO: Get actual trade count
                pnl = final_equity - 100000.0  # TODO: Get actual P&L
                max_drawdown = 0.0  # TODO: Calculate actual drawdown
                win_rate = 0.0  # TODO: Calculate actual win rate
                
                self.trading_db.end_session(
                    self.current_session_id, 
                    final_equity, 
                    total_trades, 
                    pnl, 
                    max_drawdown, 
                    win_rate
                )
                self.current_session_id = None
            
            # Disconnect from broker
            await self.broker.disconnect()
            
            logger.info("Trading engine stopped")
            
        except Exception as e:
            logger.error(f"Error stopping trading engine: {e}")
            raise
    
    async def emergency_stop(self):
        """Emergency stop - close all positions immediately."""
        try:
            logger.warning("Emergency stop initiated")
            
            # Close all positions
            positions = await self.portfolio.get_positions()
            for position in positions:
                await self.execution_engine.close_position(position['symbol'])
            
            # Stop trading engine
            await self.stop()
            
            # Send emergency alert
            await self.alert_manager.send_alert(
                "EMERGENCY_STOP",
                "Emergency stop executed - all positions closed",
                {"timestamp": datetime.now(timezone.utc).isoformat()}
            )
            
            logger.warning("Emergency stop completed")
            
        except Exception as e:
            logger.error(f"Error executing emergency stop: {e}")
            raise
    
    async def arm_live_trading(self, confirmation_key: str) -> bool:
        """Arm live trading with confirmation key."""
        # Simple confirmation key validation (in production, use proper 2FA)
        if confirmation_key != "LIVE_TRADING_CONFIRM":
            return False
        
        self.is_armed = True
        logger.warning("Live trading armed")
        return True
    
    async def disarm_live_trading(self):
        """Disarm live trading."""
        self.is_armed = False
        logger.info("Live trading disarmed")
    
    async def set_strategy(self, strategy_name: str, parameters: Optional[Dict[str, Any]] = None):
        """Set active trading strategy."""
        try:
            if strategy_name == "mean_reversion":
                self.current_strategy = MeanReversionStrategy(parameters)
            elif strategy_name == "momentum":
                self.current_strategy = MomentumStrategy(parameters)
            elif strategy_name == "news_driven":
                self.current_strategy = NewsDrivenStrategy(parameters)
            else:
                raise ValueError(f"Unknown strategy: {strategy_name}")
            
            logger.info(f"Strategy changed to {strategy_name}")
            
        except Exception as e:
            logger.error(f"Error setting strategy: {e}")
            raise
    
    async def place_manual_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        reasoning: str = "Manual order"
    ) -> Dict[str, Any]:
        """Place a manual order."""
        try:
            order = await self.execution_engine.place_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                reasoning=reasoning
            )
            
            # Log manual order
            await self.audit_logger.log_event(
                "MANUAL_ORDER",
                f"Manual order placed: {side} {quantity} {symbol}",
                {"order_id": order['order_id'], "reasoning": reasoning}
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error placing manual order: {e}")
            raise
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current trading system status."""
        try:
            account = await self.broker.get_account()
            positions = await self.portfolio.get_positions()
            
            return {
                "is_running": self.is_running_flag,
                "mode": self.config.get('mode', 'paper'),
                "broker": self.broker.name,
                "strategy": self.current_strategy.name if self.current_strategy else None,
                "is_armed": self.is_armed,
                "positions_count": len(positions),
                "total_pnl": account.unrealized_pnl if account else 0.0,
                "total_pnl_pct": account.unrealized_pnl / account.equity * 100 if account and account.equity > 0 else 0.0,
                "daily_pnl": 0.0,  # TODO: Calculate daily P&L
                "risk_status": await self._get_risk_status()
            }
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {
                "is_running": False,
                "mode": "paper",
                "broker": "unknown",
                "strategy": None,
                "is_armed": False,
                "positions_count": 0,
                "total_pnl": 0.0,
                "total_pnl_pct": 0.0,
                "daily_pnl": 0.0,
                "risk_status": "unknown"
            }
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        try:
            return await self.portfolio.get_positions()
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get order history."""
        try:
            return await self.execution_engine.get_orders(status=status, limit=limit)
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        try:
            # Get session performance
            if self.current_session_id:
                session_orders = self.trading_db.get_session_orders(self.current_session_id)
                session_positions = self.trading_db.get_session_positions(self.current_session_id)
                
                # Calculate metrics
                total_trades = len(session_orders)
                winning_trades = len([o for o in session_orders if o.get('pnl', 0) > 0])
                losing_trades = total_trades - winning_trades
                
                return {
                    "total_return": 0.0,  # TODO: Calculate from session data
                    "total_return_pct": 0.0,
                    "daily_return": 0.0,
                    "daily_return_pct": 0.0,
                    "win_rate": winning_trades / total_trades if total_trades > 0 else 0.0,
                    "profit_factor": 0.0,  # TODO: Calculate
                    "max_drawdown": 0.0,  # TODO: Calculate
                    "sharpe_ratio": 0.0,  # TODO: Calculate
                    "total_trades": total_trades,
                    "winning_trades": winning_trades,
                    "losing_trades": losing_trades,
                    "avg_winner": 0.0,  # TODO: Calculate
                    "avg_loser": 0.0  # TODO: Calculate
                }
            else:
                return {
                    "total_return": 0.0,
                    "total_return_pct": 0.0,
                    "daily_return": 0.0,
                    "daily_return_pct": 0.0,
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                    "max_drawdown": 0.0,
                    "sharpe_ratio": 0.0,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "avg_winner": 0.0,
                    "avg_loser": 0.0
                }
                
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    async def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        try:
            return await self.risk_manager.get_risk_status()
        except Exception as e:
            logger.error(f"Error getting risk status: {e}")
            return {"status": "unknown", "warnings": []}
    
    async def get_current_session(self) -> Dict[str, Any]:
        """Get current trading session."""
        try:
            if self.current_session_id:
                return {
                    "session_id": self.current_session_id,
                    "start_time": datetime.now(timezone.utc).isoformat(),
                    "strategy": self.current_strategy.name if self.current_strategy else None,
                    "broker": self.broker.name
                }
            else:
                return {}
        except Exception as e:
            logger.error(f"Error getting current session: {e}")
            return {}
    
    async def get_session_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get trading session history."""
        try:
            # TODO: Implement session history retrieval
            return []
        except Exception as e:
            logger.error(f"Error getting session history: {e}")
            return []
    
    async def get_recent_alerts(self) -> List[Dict[str, Any]]:
        """Get recent trading alerts."""
        try:
            return await self.alert_manager.get_recent_alerts()
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []
    
    def is_running(self) -> bool:
        """Check if trading engine is running."""
        return self.is_running_flag
    
    async def _trading_loop(self):
        """Main trading loop - Phase 5 enhanced implementation."""
        logger.info("Trading loop started")
        
        while self.is_running_flag:
            try:
                logger.info("Trading loop iteration started")
                
                # 1. Check market hours and trading enabled
                market_open = await self._is_market_open()
                logger.info(f"Market open: {market_open}")
                
                if not market_open:
                    logger.debug("Market closed, waiting...")
                    await asyncio.sleep(60)
                    continue
                
                if not self.is_armed and self.config.get('mode') == 'live':
                    logger.debug("Live trading not armed, waiting...")
                    await asyncio.sleep(60)
                    continue
                
                # 2. Fetch latest data from storage
                data = await self._get_latest_data()
                logger.info(f"Data fetched: {len(data)} symbols")
                if not data:
                    logger.debug("No data available, waiting...")
                    await asyncio.sleep(60)
                    continue
                
                # 3. Compute features
                features = await self._compute_features(data)
                logger.info(f"Features computed: {len(features)} features")
                
                # 4. Generate signals from active strategy
                signals = await self._generate_signals(features)
                logger.info(f"Signals generated: {len(signals)} signals")
                
                # 5. Pass signals through risk manager
                approved_orders = await self._process_signals(signals)
                logger.info(f"Approved orders: {len(approved_orders)} orders")
                
                # 6. Execute approved orders
                for order in approved_orders:
                    try:
                        logger.info(f"Placing order: {order}")
                        await self.execution_engine.place_order(**order)
                        logger.info(f"Order placed: {order['symbol']} {order['side']} {order['quantity']}")
                    except Exception as e:
                        logger.error(f"Failed to place order: {e}")
                        await self.alert_manager.send_alert(
                            "ORDER_PLACEMENT_FAILED",
                            f"Failed to place order: {e}",
                            {"order": order, "error": str(e)}
                        )
                
                # 7. Monitor existing positions (check stops/targets)
                await self._monitor_positions()
                
                # 8. Update dashboard via WebSocket
                await self._broadcast_status_update()
                
                # 9. Log all decisions
                await self._log_trading_decisions(signals, approved_orders)
                
                # Wait for next iteration (shorter for testing)
                logger.info("Trading loop iteration completed, waiting 10 seconds...")
                polling_interval = self.config.get('polling_interval', 10)  # 10 seconds for testing
                await asyncio.sleep(polling_interval)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await self.alert_manager.send_alert(
                    "TRADING_LOOP_ERROR",
                    f"Trading loop error: {e}",
                    {"error": str(e)}
                )
                await asyncio.sleep(60)  # Wait before retrying
        
        logger.info("Trading loop stopped")
    
    async def _is_market_open(self) -> bool:
        """Check if market is open."""
        try:
            # For testing purposes, always allow trading
            # TODO: Implement proper market hours check for production
            logger.info("Market hours check: Always open for testing")
            return True
            
            # Check broker market hours (disabled for testing)
            # if hasattr(self.broker, 'is_market_open'):
            #     return await self.broker.is_market_open()
            
            # Fallback: basic market hours check (9:30 AM - 4:00 PM ET)
            # now = datetime.now(timezone.utc)
            # # Convert to ET (simplified)
            # et_hour = (now.hour - 5) % 24  # UTC-5 for ET
            # et_minute = now.minute
            # 
            # # Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
            # if now.weekday() < 5:  # Monday = 0, Friday = 4
            #     market_open = et_hour > 9 or (et_hour == 9 and et_minute >= 30)
            #     market_close = et_hour < 16
            #     return market_open and market_close
            # 
            # return False
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False
    
    async def _get_latest_data(self) -> Dict[str, Any]:
        """Get latest market data from storage manager."""
        try:
            # Get latest OHLCV data for all watched symbols
            symbols = self.config.get('watchlist', ['AAPL', 'MSFT', 'GOOGL'])
            data = {}
            
            for symbol in symbols:
                try:
                    # Try to get latest OHLCV data if method exists
                    if hasattr(self.storage_manager, 'get_latest_ohlcv'):
                        ohlcv_data = self.storage_manager.get_latest_ohlcv(symbol)
                        if ohlcv_data is not None:
                            data[symbol] = ohlcv_data
                    
                    # Try to get latest news if method exists
                    if hasattr(self.storage_manager, 'get_latest_news'):
                        news_data = self.storage_manager.get_latest_news(symbol)
                        if news_data:
                            data[f"{symbol}_news"] = news_data
                        
                except Exception as e:
                    logger.warning(f"Failed to get data for {symbol}: {e}")
                    continue
            
            # If no real data available, return mock data for testing
            if not data:
                logger.info("No real data available, using mock data for testing")
                import random
                for symbol in symbols:
                    base_price = 100 + random.random() * 200
                    
                    # Create more extreme conditions to trigger signals
                    # Randomly create oversold or overbought conditions
                    if random.random() < 0.3:  # 30% chance of extreme conditions
                        if random.random() < 0.5:  # Oversold
                            close_price = base_price - random.random() * 20  # Lower price
                        else:  # Overbought
                            close_price = base_price + random.random() * 20  # Higher price
                    else:
                        close_price = base_price + (random.random() - 0.5) * 10
                    
                    data[symbol] = {
                        'symbol': symbol,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'open': base_price,
                        'high': base_price + random.random() * 5,
                        'low': base_price - random.random() * 5,
                        'close': close_price,
                        'volume': int(random.random() * 1000000) + 100000
                    }
            
            return data
        except Exception as e:
            logger.error(f"Error getting latest data: {e}")
            return {}
    
    async def _compute_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute technical features from market data."""
        try:
            features = {}
            
            for symbol, ohlcv_data in data.items():
                if isinstance(ohlcv_data, dict) and 'close' in ohlcv_data:
                    # Compute basic technical indicators
                    close_price = ohlcv_data.get('close', 0)
                    
                    # If we only have a single price, create mock historical data for testing
                    if isinstance(close_price, (int, float)):
                        # Create mock historical data for testing
                        import random
                        base_price = float(close_price)
                        close_prices = [base_price + (random.random() - 0.5) * 10 for _ in range(50)]
                    else:
                        close_prices = close_price
                    
                    if len(close_prices) >= 20:  # Need enough data for indicators
                        # Simple moving averages
                        sma_20 = sum(close_prices[-20:]) / 20
                        sma_50 = sum(close_prices[-50:]) / 50 if len(close_prices) >= 50 else sma_20
                        
                        # RSI calculation (simplified)
                        rsi = self._calculate_rsi(close_prices)
                        
                        # Bollinger Bands (simplified)
                        bb_upper, bb_lower = self._calculate_bollinger_bands(close_prices)
                        bb_middle = sma_20  # Use SMA as middle band
                        
                        # Calculate BB position (0 = lower band, 1 = upper band)
                        bb_position = (close_prices[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
                        
                        # Handle volume field
                        volume = ohlcv_data.get('volume', 0)
                        if isinstance(volume, (int, float)):
                            current_volume = volume
                        else:
                            current_volume = volume[-1] if volume else 0
                        
                        features[symbol] = {
                            'sma_20': sma_20,
                            'sma_50': sma_50,
                            'rsi': rsi,
                            'bb_upper': bb_upper,
                            'bb_lower': bb_lower,
                            'bb_middle': bb_middle,
                            'bb_position': bb_position,
                            'close': close_prices[-1],  # Required by strategy
                            'current_price': close_prices[-1],
                            'volume': current_volume
                        }
            
            return features
        except Exception as e:
            logger.error(f"Error computing features: {e}")
            return {}
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI indicator."""
        if len(prices) < period + 1:
            return 50.0  # Neutral RSI
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0) -> tuple:
        """Calculate Bollinger Bands."""
        if len(prices) < period:
            return prices[-1], prices[-1]
        
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period
        variance = sum((p - sma) ** 2 for p in recent_prices) / period
        std = variance ** 0.5
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        return upper_band, lower_band
    
    async def _generate_signals(self, features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate trading signals from computed features."""
        try:
            if not self.current_strategy:
                logger.debug("No active strategy")
                return []
            
            signals = []
            for symbol, feature_data in features.items():
                if isinstance(feature_data, dict):
                    try:
                        # Generate signal using current strategy
                        signal = await self.current_strategy.generate_signal(symbol, feature_data)
                        if signal:
                            signals.append(signal)
                    except Exception as e:
                        logger.warning(f"Failed to generate signal for {symbol}: {e}")
                        continue
            
            return signals
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return []
    
    async def _process_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process signals through risk manager."""
        try:
            approved_orders = []
            
            for signal in signals:
                try:
                    # Validate signal through risk manager
                    is_valid, order_data, reason = await self.risk_manager.validate_signal(signal)
                    
                    if is_valid and order_data:
                        approved_orders.append(order_data)
                        logger.info(f"Signal approved for {signal.get('symbol', 'unknown')}: {reason}")
                    else:
                        logger.debug(f"Signal rejected for {signal.get('symbol', 'unknown')}: {reason}")
                        
                except Exception as e:
                    logger.warning(f"Failed to process signal: {e}")
                    continue
            
            return approved_orders
        except Exception as e:
            logger.error(f"Error processing signals: {e}")
            return []
    
    async def _monitor_positions(self):
        """Monitor existing positions for stop-loss and take-profit."""
        try:
            # Get current positions
            positions = await self.portfolio.get_positions()
            
            for position in positions:
                try:
                    # Check stop-loss and take-profit levels
                    current_price = position.get('current_price', 0)
                    entry_price = position.get('entry_price', 0)
                    stop_loss = position.get('stop_loss', 0)
                    take_profit = position.get('take_profit', 0)
                    
                    # Check stop-loss
                    if stop_loss > 0 and current_price <= stop_loss:
                        logger.info(f"Stop-loss triggered for {position['symbol']}")
                        await self._close_position(position, "STOP_LOSS")
                    
                    # Check take-profit
                    elif take_profit > 0 and current_price >= take_profit:
                        logger.info(f"Take-profit triggered for {position['symbol']}")
                        await self._close_position(position, "TAKE_PROFIT")
                        
                except Exception as e:
                    logger.warning(f"Failed to monitor position {position.get('symbol', 'unknown')}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error monitoring positions: {e}")
    
    async def _close_position(self, position: Dict[str, Any], reason: str):
        """Close a position."""
        try:
            symbol = position['symbol']
            quantity = position['quantity']
            
            # Create close order
            order_data = {
                'symbol': symbol,
                'side': 'sell' if position.get('side') == 'long' else 'buy',
                'quantity': abs(quantity),
                'order_type': 'market',
                'reason': reason
            }
            
            # Place order through execution engine
            await self.execution_engine.place_order(**order_data)
            logger.info(f"Position closed for {symbol}: {reason}")
            
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
    
    async def _broadcast_status_update(self):
        """Broadcast status update via WebSocket."""
        try:
            # Get current status
            status = await self.get_status()
            
            # Broadcast to WebSocket clients
            # TODO: Implement WebSocket broadcasting
            logger.debug("Status update broadcasted")
            
        except Exception as e:
            logger.error(f"Error broadcasting status update: {e}")
    
    async def _log_trading_decisions(self, signals: List[Dict[str, Any]], orders: List[Dict[str, Any]]):
        """Log all trading decisions for audit trail."""
        try:
            # Log signals
            for signal in signals:
                await self.audit_logger.log_signal(signal)
            
            # Log orders
            for order in orders:
                await self.audit_logger.log_order(order)
                
        except Exception as e:
            logger.error(f"Error logging trading decisions: {e}")
    
    async def _get_account_equity(self) -> float:
        """Get current account equity."""
        try:
            account = await self.broker.get_account()
            return account.equity if account else 0.0
        except Exception as e:
            logger.error(f"Error getting account equity: {e}")
            return 0.0
    
    async def configure_broker(self, broker_config: dict) -> dict:
        """
        Configure broker settings.
        
        Args:
            broker_config: Broker configuration
            
        Returns:
            Configuration result
        """
        try:
            broker_type = broker_config.get('broker', 'simulator')
            
            if broker_type == 'alpaca':
                # Store Alpaca configuration
                self.broker_config = {
                    'api_key': broker_config.get('api_key'),
                    'secret_key': broker_config.get('secret_key'),
                    'paper_trading': broker_config.get('paper_trading', True)
                }
                
                # Create new Alpaca broker instance
                from app.trading.brokers.alpaca_adapter import AlpacaAdapter
                self.broker = AlpacaAdapter(self.broker_config)
                
                logger.info("Alpaca broker configured successfully")
                return {"message": "Alpaca broker configured successfully", "broker": "alpaca"}
            
            else:
                # Keep simulator
                logger.info("Using simulator broker")
                return {"message": "Using simulator broker", "broker": "simulator"}
                
        except Exception as e:
            logger.error(f"Error configuring broker: {e}")
            raise Exception(f"Error configuring broker: {e}")
    
    async def test_broker_connection(self, broker_type: str) -> dict:
        """
        Test broker connection.
        
        Args:
            broker_type: Type of broker to test
            
        Returns:
            Connection test result
        """
        try:
            if broker_type == 'alpaca':
                if not hasattr(self, 'broker') or not hasattr(self.broker, 'connect'):
                    raise Exception("Alpaca broker not configured")
                
                # Connect to Alpaca first
                connected = await self.broker.connect()
                if not connected:
                    raise Exception("Failed to connect to Alpaca API")
                
                # Test connection by getting account info
                account = await self.broker.get_account()
                return {
                    "success": True,
                    "account_id": account.account_id if account else "unknown",
                    "broker": "alpaca"
                }
            
            elif broker_type == 'simulator':
                return {
                    "success": True,
                    "account_id": "simulator",
                    "broker": "simulator"
                }
            
            else:
                raise Exception(f"Unknown broker type: {broker_type}")
                
        except Exception as e:
            logger.error(f"Error testing broker connection: {e}")
            raise Exception(f"Error testing broker connection: {e}")
