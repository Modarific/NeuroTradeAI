"""
Order execution engine.
Manages order lifecycle and execution.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from app.trading.brokers.base import BaseBroker
from app.core.trading_db import TradingDatabase

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Order execution engine.
    
    Responsibilities:
    - Place orders
    - Monitor order status
    - Handle order lifecycle
    - Manage order state
    """
    
    def __init__(self, broker: BaseBroker, trading_db: TradingDatabase):
        """
        Initialize execution engine.
        
        Args:
            broker: Broker adapter for order execution
            trading_db: Trading database for persistence
        """
        self.broker = broker
        self.trading_db = trading_db
        self.logger = logging.getLogger(__name__)
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        reasoning: str = "Strategy signal"
    ) -> Dict[str, Any]:
        """
        Place an order.
        
        Args:
            symbol: Trading symbol
            side: Order side (buy/sell)
            quantity: Order quantity
            order_type: Order type (market/limit/stop)
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            reasoning: Order reasoning
            
        Returns:
            Order information dictionary
        """
        try:
            # Create order object
            order_data = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'order_type': order_type,
                'limit_price': limit_price,
                'stop_price': stop_price,
                'reasoning': reasoning
            }
            
            # Place order with broker
            order = await self.broker.place_order(order_data)
            
            if order:
                # Store order in database
                session_id = self.trading_db.get_current_session_id()
                if session_id:
                    self.trading_db.add_order(
                        session_id=session_id,
                        order_id=order.id,
                        client_order_id=order.client_order_id,
                        symbol=order.symbol,
                        side=order.side,
                        order_type=order.order_type,
                        quantity=order.quantity,
                        time_in_force=order.time_in_force,
                        limit_price=order.limit_price,
                        stop_price=order.stop_price,
                        trail_price=order.trail_price,
                        trail_percent=order.trail_percent,
                        signal_reason=order.signal_reason,
                        strategy_name=order.strategy_name
                    )
                
                self.logger.info(f"Order placed: {side} {quantity} {symbol} ({order_type})")
                return order
            else:
                self.logger.error(f"Failed to place order: {side} {quantity} {symbol}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if order was cancelled successfully
        """
        try:
            success = await self.broker.cancel_order(order_id)
            
            if success:
                # Update order status in database
                self.trading_db.update_order_status(order_id, 'cancelled')
                self.logger.info(f"Order cancelled: {order_id}")
            else:
                self.logger.error(f"Failed to cancel order: {order_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def get_orders(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get order history.
        
        Args:
            status: Filter by order status
            limit: Maximum number of orders to return
            
        Returns:
            List of order dictionaries
        """
        try:
            orders = await self.broker.get_all_orders(status=status)
            
            # Convert to standardized format
            order_list = []
            for order in orders[:limit]:
                order_dict = {
                    'order_id': order.order_id,
                    'symbol': order.symbol,
                    'side': order.side,
                    'quantity': order.quantity,
                    'order_type': order.order_type,
                    'status': order.status.value,
                    'limit_price': order.limit_price,
                    'stop_price': order.stop_price,
                    'filled_price': order.filled_price,
                    'filled_quantity': order.filled_quantity,
                    'submission_time': order.submission_time.isoformat() if order.submission_time else None,
                    'close_time': order.close_time.isoformat() if order.close_time else None,
                    'reasoning': order.reasoning
                }
                order_list.append(order_dict)
            
            return order_list
            
        except Exception as e:
            self.logger.error(f"Error getting orders: {e}")
            return []
    
    async def get_order_status(self, order_id: str) -> Optional[str]:
        """
        Get order status.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order status or None
        """
        try:
            status = await self.broker.get_order_status(order_id)
            return status.value if hasattr(status, 'value') else status
            
        except Exception as e:
            self.logger.error(f"Error getting order status for {order_id}: {e}")
            return None
    
    async def monitor_orders(self):
        """
        Monitor pending orders for status updates.
        """
        try:
            # Get pending orders
            pending_orders = await self.get_orders(status='pending')
            
            for order in pending_orders:
                # Check order status
                current_status = await self.get_order_status(order['order_id'])
                
                if current_status and current_status != order['status']:
                    # Update order status
                    self.trading_db.update_order_status(order['order_id'], current_status)
                    
                    self.logger.info(f"Order status updated: {order['order_id']} -> {current_status}")
                    
        except Exception as e:
            self.logger.error(f"Error monitoring orders: {e}")
    
    async def get_order_summary(self) -> Dict[str, Any]:
        """
        Get order summary.
        
        Returns:
            Order summary dictionary
        """
        try:
            all_orders = await self.get_orders()
            
            # Calculate summary statistics
            total_orders = len(all_orders)
            filled_orders = len([o for o in all_orders if o['status'] == 'filled'])
            pending_orders = len([o for o in all_orders if o['status'] == 'pending'])
            cancelled_orders = len([o for o in all_orders if o['status'] == 'cancelled'])
            
            return {
                'total_orders': total_orders,
                'filled_orders': filled_orders,
                'pending_orders': pending_orders,
                'cancelled_orders': cancelled_orders,
                'fill_rate': filled_orders / total_orders if total_orders > 0 else 0.0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting order summary: {e}")
            return {
                'total_orders': 0,
                'filled_orders': 0,
                'pending_orders': 0,
                'cancelled_orders': 0,
                'fill_rate': 0.0
            }