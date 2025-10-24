"""
Mean Reversion Strategy.
Trades based on RSI oversold/overbought conditions and Bollinger Band touches.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

from app.trading.signals import BaseStrategy, Signal, SignalAction

logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using RSI and Bollinger Bands.
    
    Entry Rules:
    - BUY when RSI < 30 and price touches lower Bollinger Band
    - SELL when RSI > 70 and price touches upper Bollinger Band
    
    Exit Rules:
    - Exit when price returns to middle Bollinger Band
    - Stop loss at 2% below entry
    - Take profit at 3% above entry
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize mean reversion strategy.
        
        Config parameters:
            rsi_oversold: RSI threshold for oversold (default: 30)
            rsi_overbought: RSI threshold for overbought (default: 70)
            bb_touch_threshold: Distance from BB to be considered a "touch" (default: 0.02)
            position_size: Base position size as % of account (default: 0.01 = 1%)
            stop_loss_pct: Stop loss percentage (default: 0.02 = 2%)
            take_profit_pct: Take profit percentage (default: 0.03 = 3%)
        """
        default_config = {
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "bb_touch_threshold": 0.02,
            "position_size": 0.01,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.03,
            "min_confidence": 0.5
        }
        if config:
            default_config.update(config)
        
        super().__init__("mean_reversion", default_config)
    
    def generate_signals(self,
                        symbol: str,
                        features: Dict[str, Any],
                        current_positions: Optional[Dict[str, Any]] = None) -> List[Signal]:
        """
        Generate mean reversion signals.
        
        Args:
            symbol: Stock symbol
            features: Dictionary of computed features
            current_positions: Current open positions
            
        Returns:
            List of signals (0 or 1 signal)
        """
        signals = []
        
        try:
            # Check if we have all required features
            required_features = ['rsi', 'bb_lower', 'bb_upper', 'bb_middle', 'bb_position', 'close']
            if not all(feat in features for feat in required_features):
                logger.debug(f"Missing required features for {symbol}")
                return signals
            
            # Get feature values
            rsi = features['rsi']
            bb_position = features['bb_position']
            close_price = features['close']
            bb_lower = features['bb_lower']
            bb_upper = features['bb_upper']
            bb_middle = features['bb_middle']
            
            # Skip if we have NaN values
            if any(pd.isna(val) for val in [rsi, bb_position, close_price]):
                return signals
            
            # Check if we have an open position
            has_position = False
            if current_positions and symbol in current_positions:
                has_position = True
                position = current_positions[symbol]
                
                # Check exit conditions for existing position
                if position['side'] == 'long':
                    # Exit long if price reaches middle BB or take profit
                    if close_price >= bb_middle:
                        signals.append(Signal(
                            symbol=symbol,
                            action=SignalAction.CLOSE,
                            confidence=0.8,
                            size_pct=1.0,  # Close entire position
                            reasoning=f"Mean reversion: price returned to middle BB (${close_price:.2f} >= ${bb_middle:.2f})",
                            timestamp=datetime.now(timezone.utc),
                            strategy_name=self.name,
                            entry_price=close_price
                        ))
                
                elif position['side'] == 'short':
                    # Exit short if price reaches middle BB
                    if close_price <= bb_middle:
                        signals.append(Signal(
                            symbol=symbol,
                            action=SignalAction.CLOSE,
                            confidence=0.8,
                            size_pct=1.0,
                            reasoning=f"Mean reversion: price returned to middle BB (${close_price:.2f} <= ${bb_middle:.2f})",
                            timestamp=datetime.now(timezone.utc),
                            strategy_name=self.name,
                            entry_price=close_price
                        ))
                
                return signals
            
            # Entry signals (only if no position)
            if not has_position:
                # BUY signal: RSI oversold + price near lower BB
                if rsi < self.config['rsi_oversold'] and bb_position < self.config['bb_touch_threshold']:
                    # Calculate confidence based on how oversold
                    confidence = min(0.9, 0.5 + (self.config['rsi_oversold'] - rsi) / 100)
                    
                    if confidence >= self.config['min_confidence']:
                        stop_loss = close_price * (1 - self.config['stop_loss_pct'])
                        take_profit = close_price * (1 + self.config['take_profit_pct'])
                        
                        signals.append(Signal(
                            symbol=symbol,
                            action=SignalAction.BUY,
                            confidence=confidence,
                            size_pct=self.config['position_size'],
                            reasoning=f"Mean reversion BUY: RSI={rsi:.1f} (oversold), BB position={bb_position:.3f} (near lower band)",
                            timestamp=datetime.now(timezone.utc),
                            strategy_name=self.name,
                            entry_price=close_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            metadata={
                                'rsi': rsi,
                                'bb_position': bb_position,
                                'bb_lower': bb_lower
                            }
                        ))
                
                # SELL signal: RSI overbought + price near upper BB
                elif rsi > self.config['rsi_overbought'] and bb_position > (1 - self.config['bb_touch_threshold']):
                    # Calculate confidence based on how overbought
                    confidence = min(0.9, 0.5 + (rsi - self.config['rsi_overbought']) / 100)
                    
                    if confidence >= self.config['min_confidence']:
                        stop_loss = close_price * (1 + self.config['stop_loss_pct'])
                        take_profit = close_price * (1 - self.config['take_profit_pct'])
                        
                        signals.append(Signal(
                            symbol=symbol,
                            action=SignalAction.SELL,
                            confidence=confidence,
                            size_pct=self.config['position_size'],
                            reasoning=f"Mean reversion SELL: RSI={rsi:.1f} (overbought), BB position={bb_position:.3f} (near upper band)",
                            timestamp=datetime.now(timezone.utc),
                            strategy_name=self.name,
                            entry_price=close_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            metadata={
                                'rsi': rsi,
                                'bb_position': bb_position,
                                'bb_upper': bb_upper
                            }
                        ))
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating mean reversion signals for {symbol}: {e}")
            return []


# Import pandas for NaN checking
import pandas as pd

