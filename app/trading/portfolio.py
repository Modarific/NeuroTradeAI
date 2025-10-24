"""
Portfolio management for tracking positions and P&L.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from app.trading.brokers.base import BaseBroker
from app.core.trading_db import TradingDatabase

logger = logging.getLogger(__name__)


class Portfolio:
    """
    Portfolio management for tracking positions and P&L.
    
    Responsibilities:
    - Track open positions
    - Calculate P&L
    - Monitor position limits
    - Update position data
    """
    
    def __init__(self, broker: BaseBroker, trading_db: TradingDatabase):
        """
        Initialize portfolio manager.
        
        Args:
            broker: Broker adapter for position data
            trading_db: Trading database for persistence
        """
        self.broker = broker
        self.trading_db = trading_db
        self.logger = logging.getLogger(__name__)
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions.
        
        Returns:
            List of position dictionaries
        """
        try:
            positions = await self.broker.get_open_positions()
            
            # Convert to standardized format
            position_list = []
            for position in positions:
                position_dict = {
                    'symbol': position.symbol,
                    'side': position.side.value,
                    'quantity': position.quantity,
                    'entry_price': position.entry_price,
                    'current_price': position.current_price,
                    'unrealized_pnl': position.unrealized_pnl,
                    'unrealized_pnl_pct': position.unrealized_pnl_pct,
                    'entry_time': position.entry_time.isoformat(),
                    'stop_loss': position.stop_loss,
                    'take_profit': position.take_profit
                }
                position_list.append(position_dict)
            
            return position_list
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get position for a specific symbol.
        
        Args:
            symbol: Symbol to get position for
            
        Returns:
            Position dictionary or None
        """
        try:
            positions = await self.get_positions()
            for position in positions:
                if position['symbol'] == symbol:
                    return position
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    async def get_total_pnl(self) -> float:
        """
        Get total unrealized P&L.
        
        Returns:
            Total unrealized P&L
        """
        try:
            positions = await self.get_positions()
            total_pnl = sum(pos['unrealized_pnl'] for pos in positions)
            return total_pnl
            
        except Exception as e:
            self.logger.error(f"Error getting total P&L: {e}")
            return 0.0
    
    async def get_total_pnl_pct(self) -> float:
        """
        Get total unrealized P&L percentage.
        
        Returns:
            Total unrealized P&L percentage
        """
        try:
            account = await self.broker.get_account()
            if not account or account.equity <= 0:
                return 0.0
            
            total_pnl = await self.get_total_pnl()
            return (total_pnl / account.equity) * 100
            
        except Exception as e:
            self.logger.error(f"Error getting total P&L percentage: {e}")
            return 0.0
    
    async def get_position_count(self) -> int:
        """
        Get number of open positions.
        
        Returns:
            Number of open positions
        """
        try:
            positions = await self.get_positions()
            return len(positions)
            
        except Exception as e:
            self.logger.error(f"Error getting position count: {e}")
            return 0
    
    async def get_exposure_pct(self) -> float:
        """
        Get total exposure percentage.
        
        Returns:
            Total exposure as percentage of account
        """
        try:
            account = await self.broker.get_account()
            if not account or account.equity <= 0:
                return 0.0
            
            positions = await self.get_positions()
            total_exposure = sum(
                pos['quantity'] * pos['current_price'] 
                for pos in positions
            )
            
            return (total_exposure / account.equity) * 100
            
        except Exception as e:
            self.logger.error(f"Error getting exposure percentage: {e}")
            return 0.0
    
    async def update_positions(self, session_id: str):
        """
        Update positions in database.
        
        Args:
            session_id: Trading session ID
        """
        try:
            positions = await self.get_positions()
            
            for position in positions:
                # Update position in database
                self.trading_db.update_position(session_id, position)
            
            self.logger.debug(f"Updated {len(positions)} positions for session {session_id}")
            
        except Exception as e:
            self.logger.error(f"Error updating positions: {e}")
    
    async def close_position(self, symbol: str) -> bool:
        """
        Close a position.
        
        Args:
            symbol: Symbol to close position for
            
        Returns:
            True if position was closed successfully
        """
        try:
            position = await self.get_position(symbol)
            if not position:
                self.logger.warning(f"No position found for {symbol}")
                return False
            
            # Place sell order to close position
            order = await self.broker.place_order({
                'symbol': symbol,
                'side': 'sell',
                'quantity': position['quantity'],
                'order_type': 'market',
                'reasoning': 'Close position'
            })
            
            if order:
                self.logger.info(f"Position closed for {symbol}")
                return True
            else:
                self.logger.error(f"Failed to close position for {symbol}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error closing position for {symbol}: {e}")
            return False
    
    async def get_position_summary(self) -> Dict[str, Any]:
        """
        Get portfolio summary.
        
        Returns:
            Portfolio summary dictionary
        """
        try:
            positions = await self.get_positions()
            total_pnl = await self.get_total_pnl()
            total_pnl_pct = await self.get_total_pnl_pct()
            exposure_pct = await self.get_exposure_pct()
            
            return {
                'position_count': len(positions),
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl_pct,
                'exposure_pct': exposure_pct,
                'positions': positions
            }
            
        except Exception as e:
            self.logger.error(f"Error getting position summary: {e}")
            return {
                'position_count': 0,
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'exposure_pct': 0.0,
                'positions': []
            }