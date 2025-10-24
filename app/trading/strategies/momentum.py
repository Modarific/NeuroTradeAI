"""
Momentum breakout strategy.
Trades on momentum breakouts using moving averages and volume confirmation.
"""
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone

from .base import BaseStrategy
from ..signals import Signal, SignalAction

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """
    Momentum breakout strategy.
    
    Signals:
    - BUY: Price crosses above SMA with volume confirmation
    - SELL: Price crosses below SMA or volume drops
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize momentum strategy.
        
        Args:
            config: Strategy configuration
        """
        super().__init__("Momentum Strategy", config)
        
        # Strategy parameters
        self.sma_period = self.config.get('sma_period', 20)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        self.min_confidence = self.config.get('min_confidence', 0.6)
        
        logger.info(f"Initialized {self.name} with SMA period: {self.sma_period}")
    
    def generate_signals(
        self,
        symbol: str,
        features: Dict[str, Any],
        current_positions: Dict[str, Any]
    ) -> List[Signal]:
        """
        Generate trading signals based on momentum.
        
        Args:
            symbol: Trading symbol
            features: Market features
            current_positions: Current positions
            
        Returns:
            List of trading signals
        """
        signals = []
        
        try:
            # Check if we have required features
            required_features = ['close', 'volume', f'sma_{self.sma_period}', 'volume_sma']
            if not all(feat in features for feat in required_features):
                return signals
            
            current_price = features['close']
            sma = features[f'sma_{self.sma_period}']
            volume = features['volume']
            volume_sma = features['volume_sma']
            
            # Calculate volume ratio
            volume_ratio = volume / volume_sma if volume_sma > 0 else 1.0
            
            # Check for momentum breakout
            if current_price > sma and volume_ratio >= self.volume_threshold:
                # Strong momentum breakout
                confidence = min(0.9, 0.5 + (volume_ratio - 1.0) * 0.2)
                
                if confidence >= self.min_confidence:
                    signal = Signal(
                        symbol=symbol,
                        action=SignalAction.BUY,
                        confidence=confidence,
                        size_pct=0.02,  # 2% position size
                        reasoning=f"Momentum breakout: price {current_price:.2f} > SMA {sma:.2f}, volume {volume_ratio:.2f}x",
                        timestamp=datetime.now(timezone.utc),
                        strategy_name=self.name,
                        entry_price=current_price,
                        stop_loss=current_price * 0.98,  # 2% stop loss
                        take_profit=current_price * 1.06  # 6% take profit
                    )
                    signals.append(signal)
            
            # Check for momentum breakdown
            elif current_price < sma and volume_ratio >= self.volume_threshold:
                # Strong momentum breakdown
                confidence = min(0.9, 0.5 + (volume_ratio - 1.0) * 0.2)
                
                if confidence >= self.min_confidence:
                    signal = Signal(
                        symbol=symbol,
                        action=SignalAction.SELL,
                        confidence=confidence,
                        size_pct=0.02,  # 2% position size
                        reasoning=f"Momentum breakdown: price {current_price:.2f} < SMA {sma:.2f}, volume {volume_ratio:.2f}x",
                        timestamp=datetime.now(timezone.utc),
                        strategy_name=self.name,
                        entry_price=current_price,
                        stop_loss=current_price * 1.02,  # 2% stop loss
                        take_profit=current_price * 0.94  # 6% take profit
                    )
                    signals.append(signal)
            
            # Check for volume drop (exit signal)
            elif volume_ratio < 0.5 and symbol in current_positions:
                # Volume dropped significantly, exit position
                signal = Signal(
                    symbol=symbol,
                    action=SignalAction.CLOSE,
                    confidence=0.7,
                    size_pct=1.0,  # Close entire position
                    reasoning=f"Volume drop: {volume_ratio:.2f}x, exiting position",
                    entry_price=current_price,
                    strategy_name=self.name
                )
                signals.append(signal)
            
        except Exception as e:
            logger.error(f"Error generating momentum signals for {symbol}: {e}")
        
        return signals