"""
News-driven strategy.
Trades based on news sentiment and price movement correlation.
"""
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone

from .base import BaseStrategy
from ..signals import Signal, SignalAction

logger = logging.getLogger(__name__)


class NewsDrivenStrategy(BaseStrategy):
    """
    News-driven strategy.
    
    Signals:
    - BUY: Positive news sentiment + price increase
    - SELL: Negative news sentiment + price decrease
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize news-driven strategy.
        
        Args:
            config: Strategy configuration
        """
        super().__init__("News Driven Strategy", config)
        
        # Strategy parameters
        self.sentiment_threshold = self.config.get('sentiment_threshold', 0.7)
        self.price_change_threshold = self.config.get('price_change_threshold', 0.02)
        self.min_confidence = self.config.get('min_confidence', 0.6)
        
        logger.info(f"Initialized {self.name} with sentiment threshold: {self.sentiment_threshold}")
    
    def generate_signals(
        self,
        symbol: str,
        features: Dict[str, Any],
        current_positions: Dict[str, Any]
    ) -> List[Signal]:
        """
        Generate trading signals based on news sentiment.
        
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
            required_features = ['close', 'news_sentiment_1h', 'has_recent_news_1h']
            if not all(feat in features for feat in required_features):
                return signals
            
            current_price = features['close']
            news_sentiment = features.get('news_sentiment_1h', 0)
            has_recent_news = features.get('has_recent_news_1h', 0)
            
            # Only trade if there's recent news
            if not has_recent_news:
                return signals
            
            # Calculate price change (simplified - in real implementation, use previous close)
            price_change = 0.0  # This would be calculated from previous close
            
            # Check for positive news sentiment
            if news_sentiment >= self.sentiment_threshold:
                confidence = min(0.9, 0.5 + (news_sentiment - 0.5) * 0.8)
                
                if confidence >= self.min_confidence:
                    signal = Signal(
                        symbol=symbol,
                        action=SignalAction.BUY,
                        confidence=confidence,
                        size_pct=0.015,  # 1.5% position size
                        reasoning=f"Positive news sentiment: {news_sentiment:.2f}, price change: {price_change:.2%}",
                        timestamp=datetime.now(timezone.utc),
                        strategy_name=self.name,
                        entry_price=current_price,
                        stop_loss=current_price * 0.98,  # 2% stop loss
                        take_profit=current_price * 1.05  # 5% take profit
                    )
                    signals.append(signal)
            
            # Check for negative news sentiment
            elif news_sentiment <= -self.sentiment_threshold:
                confidence = min(0.9, 0.5 + abs(news_sentiment - 0.5) * 0.8)
                
                if confidence >= self.min_confidence:
                    signal = Signal(
                        symbol=symbol,
                        action=SignalAction.SELL,
                        confidence=confidence,
                        size_pct=0.015,  # 1.5% position size
                        reasoning=f"Negative news sentiment: {news_sentiment:.2f}, price change: {price_change:.2%}",
                        timestamp=datetime.now(timezone.utc),
                        strategy_name=self.name,
                        entry_price=current_price,
                        stop_loss=current_price * 1.02,  # 2% stop loss
                        take_profit=current_price * 0.95  # 5% take profit
                    )
                    signals.append(signal)
            
            # Check for sentiment reversal (exit signal)
            elif symbol in current_positions:
                # If sentiment has reversed, consider exiting
                if abs(news_sentiment) < 0.3:  # Neutral sentiment
                    signal = Signal(
                        symbol=symbol,
                        action=SignalAction.CLOSE,
                        confidence=0.6,
                        size_pct=1.0,  # Close entire position
                        reasoning=f"News sentiment neutralized: {news_sentiment:.2f}, exiting position",
                        entry_price=current_price,
                        strategy_name=self.name
                    )
                    signals.append(signal)
            
        except Exception as e:
            logger.error(f"Error generating news-driven signals for {symbol}: {e}")
        
        return signals