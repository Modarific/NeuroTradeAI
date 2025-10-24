"""
Risk Manager - Non-negotiable safety layer for trading.
Validates and approves/rejects all trading signals based on risk limits.
"""
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging

from app.trading.signals import Signal, SignalAction
from app.trading.portfolio import Portfolio
from app.trading.brokers.base import Position, PositionSide

logger = logging.getLogger(__name__)


class RejectionReason(Enum):
    """Reasons for signal rejection."""
    INSUFFICIENT_BALANCE = "insufficient_balance"
    POSITION_SIZE_EXCEEDED = "position_size_exceeded"
    TOTAL_EXPOSURE_EXCEEDED = "total_exposure_exceeded"
    DAILY_LOSS_LIMIT_HIT = "daily_loss_limit_hit"
    MAX_POSITIONS_REACHED = "max_positions_reached"
    LIQUIDITY_TOO_LOW = "liquidity_too_low"
    CIRCUIT_BREAKER_ACTIVE = "circuit_breaker_active"
    TRADING_DISABLED = "trading_disabled"
    MISSING_STOP_LOSS = "missing_stop_loss"
    MARKET_CLOSED = "market_closed"
    SYMBOL_NOT_ALLOWED = "symbol_not_allowed"


@dataclass
class Order:
    """
    Approved order ready for execution.
    """
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    order_type: str  # 'market', 'limit', 'stop_loss'
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    
    # Risk parameters
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Metadata
    signal_id: Optional[str] = None
    strategy_name: Optional[str] = None
    reasoning: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "signal_id": self.signal_id,
            "strategy_name": self.strategy_name,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


@dataclass
class RiskLimits:
    """
    Risk limit configuration.
    """
    # Position sizing
    max_position_size_pct: float = 0.01  # 1% of account per trade
    max_total_exposure_pct: float = 0.05  # 5% total exposure
    max_positions: int = 3  # Max simultaneous positions
    
    # Daily limits
    daily_loss_limit_pct: float = 0.03  # 3% daily loss limit (hard stop)
    
    # Liquidity
    min_avg_volume: int = 1_000_000  # Minimum average daily volume
    
    # Stop loss/take profit
    required_stop_loss: bool = True
    min_stop_loss_pct: float = 0.02  # Minimum 2% stop loss
    min_take_profit_pct: float = 0.03  # Minimum 3% take profit
    
    # Circuit breaker
    circuit_breaker_losses: int = 3  # Pause after N consecutive losses
    
    # Allowed symbols
    allowed_symbols: Optional[List[str]] = None  # None = all symbols allowed


class RiskManager:
    """
    Validates trading signals and enforces risk limits.
    This is a NON-NEGOTIABLE safety layer - all orders MUST pass through here.
    """
    
    def __init__(self, 
                 portfolio: Portfolio,
                 risk_limits: Optional[RiskLimits] = None):
        """
        Initialize risk manager.
        
        Args:
            portfolio: Portfolio instance for tracking positions
            risk_limits: Optional risk limits configuration
        """
        self.portfolio = portfolio
        self.risk_limits = risk_limits or RiskLimits()
        
        self.trading_enabled = True
        self.circuit_breaker_active = False
        
        # Track symbol liquidity
        self.symbol_avg_volume: Dict[str, int] = {}
        
        logger.info("Risk Manager initialized with limits:")
        logger.info(f"  Max position size: {self.risk_limits.max_position_size_pct:.1%}")
        logger.info(f"  Max total exposure: {self.risk_limits.max_total_exposure_pct:.1%}")
        logger.info(f"  Daily loss limit: {self.risk_limits.daily_loss_limit_pct:.1%}")
        logger.info(f"  Max positions: {self.risk_limits.max_positions}")
        logger.info(f"  Circuit breaker: {self.risk_limits.circuit_breaker_losses} consecutive losses")
    
    def validate_signal(self, signal: Signal) -> Tuple[bool, Optional[Order], Optional[RejectionReason]]:
        """
        Validate a trading signal and convert to order if approved.
        
        Args:
            signal: Trading signal to validate
            
        Returns:
            Tuple of (approved: bool, order: Optional[Order], rejection_reason: Optional[RejectionReason])
        """
        # Check if trading is enabled
        if not self.trading_enabled:
            logger.warning(f"Signal rejected: Trading is disabled")
            return False, None, RejectionReason.TRADING_DISABLED
        
        # Check circuit breaker
        if self.circuit_breaker_active:
            logger.warning(f"Signal rejected: Circuit breaker is active")
            return False, None, RejectionReason.CIRCUIT_BREAKER_ACTIVE
        
        # Check if signal is for closing a position
        if signal.action.value == SignalAction.CLOSE.value:
            return self._validate_close_signal(signal)
        
        # Check allowed symbols
        if (self.risk_limits.allowed_symbols and 
            signal.symbol not in self.risk_limits.allowed_symbols):
            logger.warning(f"Signal rejected: {signal.symbol} not in allowed symbols")
            return False, None, RejectionReason.SYMBOL_NOT_ALLOWED
        
        # Check daily loss limit
        daily_loss_pct = self.portfolio.account.daily_pnl_pct
        if daily_loss_pct <= -self.risk_limits.daily_loss_limit_pct:
            logger.error(f"DAILY LOSS LIMIT HIT: {daily_loss_pct:.2%} <= -{self.risk_limits.daily_loss_limit_pct:.2%}")
            self.disable_trading()  # Disable trading for the day
            return False, None, RejectionReason.DAILY_LOSS_LIMIT_HIT
        
        # Check max positions
        if self.portfolio.get_position_count() >= self.risk_limits.max_positions:
            logger.warning(f"Signal rejected: Max positions reached ({self.risk_limits.max_positions})")
            return False, None, RejectionReason.MAX_POSITIONS_REACHED
        
        # Check if we already have a position in this symbol
        if self.portfolio.get_position(signal.symbol):
            logger.warning(f"Signal rejected: Already have position in {signal.symbol}")
            return False, None, RejectionReason.MAX_POSITIONS_REACHED
        
        # Check required stop loss
        if self.risk_limits.required_stop_loss and not signal.stop_loss:
            logger.warning(f"Signal rejected: Missing required stop loss")
            return False, None, RejectionReason.MISSING_STOP_LOSS
        
        # Check if signal size exceeds maximum position size
        if signal.size_pct > self.risk_limits.max_position_size_pct:
            logger.warning(f"Signal rejected: Position size exceeds limit ({signal.size_pct:.2%} > {self.risk_limits.max_position_size_pct:.2%})")
            return False, None, RejectionReason.POSITION_SIZE_EXCEEDED
        
        # Calculate position size
        account_equity = self.portfolio.account.equity
        max_position_value = account_equity * self.risk_limits.max_position_size_pct
        
        # Adjust for signal size_pct (strategy suggestion)
        position_value = max_position_value * signal.size_pct
        
        # Calculate quantity based on entry price
        if not signal.entry_price or signal.entry_price <= 0:
            logger.warning(f"Signal rejected: Invalid entry price {signal.entry_price}")
            return False, None, RejectionReason.INSUFFICIENT_BALANCE
        
        quantity = position_value / signal.entry_price
        
        # Check if we have enough buying power
        if position_value > self.portfolio.account.buying_power:
            logger.warning(f"Signal rejected: Insufficient buying power (need ${position_value:.2f}, have ${self.portfolio.account.buying_power:.2f})")
            return False, None, RejectionReason.INSUFFICIENT_BALANCE
        
        # Check total exposure
        current_exposure = self.portfolio.get_total_exposure()
        new_exposure = current_exposure + (position_value / account_equity)
        
        if new_exposure > self.risk_limits.max_total_exposure_pct:
            logger.warning(f"Signal rejected: Total exposure would exceed limit ({new_exposure:.2%} > {self.risk_limits.max_total_exposure_pct:.2%})")
            return False, None, RejectionReason.TOTAL_EXPOSURE_EXCEEDED
        
        # Check liquidity
        avg_volume = self.symbol_avg_volume.get(signal.symbol, float('inf'))
        if avg_volume < self.risk_limits.min_avg_volume:
            logger.warning(f"Signal rejected: {signal.symbol} average volume too low ({avg_volume:,} < {self.risk_limits.min_avg_volume:,})")
            return False, None, RejectionReason.LIQUIDITY_TOO_LOW
        
        # Validate stop loss and take profit
        if signal.stop_loss:
            stop_loss_pct = abs(signal.stop_loss - signal.entry_price) / signal.entry_price
            if stop_loss_pct < self.risk_limits.min_stop_loss_pct:
                logger.warning(f"Signal rejected: Stop loss too tight ({stop_loss_pct:.2%} < {self.risk_limits.min_stop_loss_pct:.2%})")
                # Adjust stop loss to minimum
                if signal.action == SignalAction.BUY:
                    signal.stop_loss = signal.entry_price * (1 - self.risk_limits.min_stop_loss_pct)
                else:
                    signal.stop_loss = signal.entry_price * (1 + self.risk_limits.min_stop_loss_pct)
                logger.info(f"Adjusted stop loss to ${signal.stop_loss:.2f}")
        
        # All checks passed - create order
        side = "buy" if signal.action.value == SignalAction.BUY.value else "sell"
        
        order = Order(
            symbol=signal.symbol,
            side=side,
            quantity=quantity,
            order_type="limit",  # Default to limit orders
            limit_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy_name=signal.strategy_name,
            reasoning=signal.reasoning,
            timestamp=signal.timestamp
        )
        
        logger.info(f"Signal APPROVED: {signal.action.value.upper()} {quantity:.4f} {signal.symbol} @ ${signal.entry_price:.2f}")
        logger.info(f"  Stop Loss: ${signal.stop_loss:.2f}, Take Profit: ${signal.take_profit:.2f}")
        logger.info(f"  Position value: ${position_value:.2f} ({position_value/account_equity:.2%} of account)")
        logger.debug(f"Order created with side: {order.side}")
        
        return True, order, None
    
    def _validate_close_signal(self, signal: Signal) -> Tuple[bool, Optional[Order], Optional[RejectionReason]]:
        """Validate a position close signal."""
        # Check if position exists
        position = self.portfolio.get_position(signal.symbol)
        if not position:
            logger.warning(f"Close signal rejected: No position in {signal.symbol}")
            return False, None, RejectionReason.MAX_POSITIONS_REACHED  # Reusing enum
        
        # Create close order (opposite side)
        side = "sell" if position.side == PositionSide.LONG else "buy"
        
        order = Order(
            symbol=signal.symbol,
            side=side,
            quantity=position.quantity,
            order_type="market",  # Use market orders for closes (faster execution)
            strategy_name=signal.strategy_name,
            reasoning=signal.reasoning,
            timestamp=signal.timestamp
        )
        
        logger.info(f"Close signal APPROVED: {side.upper()} {position.quantity:.4f} {signal.symbol}")
        
        return True, order, None
    
    def update_symbol_volume(self, symbol: str, avg_volume: int):
        """Update average volume for a symbol."""
        self.symbol_avg_volume[symbol] = avg_volume
    
    def check_circuit_breaker(self):
        """Check and activate circuit breaker if needed."""
        if self.portfolio.consecutive_losses >= self.risk_limits.circuit_breaker_losses:
            self.circuit_breaker_active = True
            logger.error(f"CIRCUIT BREAKER ACTIVATED: {self.portfolio.consecutive_losses} consecutive losses")
            return True
        return False
    
    def reset_circuit_breaker(self):
        """Reset circuit breaker (manual action)."""
        self.circuit_breaker_active = False
        logger.info("Circuit breaker reset")
    
    def enable_trading(self):
        """Enable trading."""
        self.trading_enabled = True
        logger.info("Trading ENABLED")
    
    def disable_trading(self):
        """Disable trading."""
        self.trading_enabled = False
        logger.warning("Trading DISABLED")
    
    def update_risk_limits(self, new_limits: Dict[str, Any]):
        """Update risk limits configuration."""
        for key, value in new_limits.items():
            if hasattr(self.risk_limits, key):
                setattr(self.risk_limits, key, value)
                logger.info(f"Updated risk limit: {key} = {value}")
    
    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        return {
            "trading_enabled": self.trading_enabled,
            "circuit_breaker_active": self.circuit_breaker_active,
            "current_exposure_pct": self.portfolio.get_total_exposure(),
            "open_positions": self.portfolio.get_position_count(),
            "daily_pnl_pct": self.portfolio.account.daily_pnl_pct,
            "consecutive_losses": self.portfolio.consecutive_losses,
            "risk_limits": {
                "max_position_size_pct": self.risk_limits.max_position_size_pct,
                "max_total_exposure_pct": self.risk_limits.max_total_exposure_pct,
                "daily_loss_limit_pct": self.risk_limits.daily_loss_limit_pct,
                "max_positions": self.risk_limits.max_positions,
                "circuit_breaker_losses": self.risk_limits.circuit_breaker_losses
            }
        }

