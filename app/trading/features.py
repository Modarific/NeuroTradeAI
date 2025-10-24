"""
Feature engineering module for trading signals.
Computes technical indicators, market microstructure, news features, and time features.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class FeatureEngine:
    """
    Computes trading features from OHLCV data, news, and filings.
    Features include technical indicators, microstructure metrics, and event flags.
    """
    
    def __init__(self, cache_size: int = 1000):
        """
        Initialize feature engine.
        
        Args:
            cache_size: Number of computed feature sets to cache
        """
        self.cache = {}
        self.cache_size = cache_size
        
    def compute_features(self, 
                        ohlcv_data: pd.DataFrame,
                        news_data: Optional[List[Dict[str, Any]]] = None,
                        filing_data: Optional[List[Dict[str, Any]]] = None) -> pd.DataFrame:
        """
        Compute all features for the given data.
        
        Args:
            ohlcv_data: DataFrame with OHLCV data (must have columns: open, high, low, close, volume, timestamp_utc)
            news_data: Optional list of news articles
            filing_data: Optional list of SEC filings
            
        Returns:
            DataFrame with all computed features
        """
        if ohlcv_data.empty:
            return pd.DataFrame()
        
        try:
            # Make a copy to avoid modifying original
            df = ohlcv_data.copy()
            
            # Ensure we have a datetime index
            if 'timestamp_utc' in df.columns:
                df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
                df = df.set_index('timestamp_utc')
            
            # Sort by time
            df = df.sort_index()
            
            # Technical indicators
            df = self._add_technical_indicators(df)
            
            # Market microstructure
            df = self._add_microstructure_features(df)
            
            # Time features
            df = self._add_time_features(df)
            
            # News features (if provided)
            if news_data:
                df = self._add_news_features(df, news_data)
            
            # Filing features (if provided)
            if filing_data:
                df = self._add_filing_features(df, filing_data)
            
            return df
            
        except Exception as e:
            logger.error(f"Error computing features: {e}")
            return ohlcv_data
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to the dataframe."""
        try:
            # Simple Moving Averages
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['sma_200'] = df['close'].rolling(window=200).mean()
            
            # Exponential Moving Averages
            df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
            df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
            
            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']
            
            # RSI (Relative Strength Index)
            df['rsi'] = self._calculate_rsi(df['close'], period=14)
            
            # Bollinger Bands
            bb_period = 20
            bb_std = 2
            df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
            bb_std_dev = df['close'].rolling(window=bb_period).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * bb_std_dev)
            df['bb_lower'] = df['bb_middle'] - (bb_std * bb_std_dev)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
            
            # ATR (Average True Range)
            df['atr'] = self._calculate_atr(df, period=14)
            
            # VWAP (Volume Weighted Average Price)
            df['vwap'] = self._calculate_vwap(df)
            
            # Price momentum
            df['momentum_5'] = df['close'].pct_change(periods=5)
            df['momentum_10'] = df['close'].pct_change(periods=10)
            df['momentum_20'] = df['close'].pct_change(periods=20)
            
            # Volume indicators
            df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma_20']
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding technical indicators: {e}")
            return df
    
    def _add_microstructure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market microstructure features."""
        try:
            # Spread estimate (using high-low)
            df['spread_estimate'] = (df['high'] - df['low']) / df['close']
            
            # Price range
            df['price_range'] = df['high'] - df['low']
            df['price_range_pct'] = df['price_range'] / df['close']
            
            # Volatility (rolling standard deviation of returns)
            df['returns'] = df['close'].pct_change()
            df['volatility_10'] = df['returns'].rolling(window=10).std()
            df['volatility_20'] = df['returns'].rolling(window=20).std()
            
            # Volume profile
            df['volume_at_close'] = df['volume']
            df['avg_trade_size'] = df['volume'] / df['price_range'].replace(0, np.nan)
            
            # Price efficiency (close-to-close vs high-low range)
            df['price_efficiency'] = abs(df['close'] - df['open']) / df['price_range'].replace(0, np.nan)
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding microstructure features: {e}")
            return df
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features."""
        try:
            # Day of week (0 = Monday, 4 = Friday)
            df['day_of_week'] = df.index.dayofweek
            
            # Hour of day (market hours)
            df['hour'] = df.index.hour
            df['minute'] = df.index.minute
            
            # Market session indicators
            # Market open: 9:30 AM, close: 4:00 PM ET
            df['time_minutes'] = df['hour'] * 60 + df['minute']
            df['is_market_open'] = (df['time_minutes'] >= 570) & (df['time_minutes'] <= 960)  # 9:30 AM - 4:00 PM
            df['minutes_since_open'] = df['time_minutes'] - 570
            df['minutes_to_close'] = 960 - df['time_minutes']
            
            # Session indicators
            df['is_first_hour'] = df['minutes_since_open'] <= 60
            df['is_last_hour'] = df['minutes_to_close'] <= 60
            df['is_mid_day'] = (df['minutes_since_open'] > 120) & (df['minutes_to_close'] > 120)
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding time features: {e}")
            return df
    
    def _add_news_features(self, df: pd.DataFrame, news_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Add news-derived features."""
        try:
            # Initialize news features
            df['news_count_1h'] = 0
            df['news_sentiment_1h'] = 0.0
            df['news_count_24h'] = 0
            df['news_sentiment_24h'] = 0.0
            df['has_recent_news'] = False
            
            if not news_data:
                return df
            
            # Convert news to DataFrame for easier processing
            news_df = pd.DataFrame(news_data)
            if 'timestamp_utc' not in news_df.columns:
                return df
            
            news_df['timestamp_utc'] = pd.to_datetime(news_df['timestamp_utc'])
            news_df = news_df.sort_values('timestamp_utc')
            
            # For each timestamp in OHLCV data, count news and aggregate sentiment
            for idx in df.index:
                # News in last 1 hour
                one_hour_ago = idx - pd.Timedelta(hours=1)
                recent_news_1h = news_df[
                    (news_df['timestamp_utc'] > one_hour_ago) & 
                    (news_df['timestamp_utc'] <= idx)
                ]
                
                if not recent_news_1h.empty:
                    df.loc[idx, 'news_count_1h'] = len(recent_news_1h)
                    if 'sentiment_score' in recent_news_1h.columns:
                        df.loc[idx, 'news_sentiment_1h'] = recent_news_1h['sentiment_score'].mean()
                    df.loc[idx, 'has_recent_news'] = True
                
                # News in last 24 hours
                one_day_ago = idx - pd.Timedelta(hours=24)
                recent_news_24h = news_df[
                    (news_df['timestamp_utc'] > one_day_ago) & 
                    (news_df['timestamp_utc'] <= idx)
                ]
                
                if not recent_news_24h.empty:
                    df.loc[idx, 'news_count_24h'] = len(recent_news_24h)
                    if 'sentiment_score' in recent_news_24h.columns:
                        df.loc[idx, 'news_sentiment_24h'] = recent_news_24h['sentiment_score'].mean()
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding news features: {e}")
            return df
    
    def _add_filing_features(self, df: pd.DataFrame, filing_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Add SEC filing features."""
        try:
            # Initialize filing features
            df['has_recent_filing'] = False
            df['filing_type'] = None
            df['days_since_filing'] = np.nan
            
            if not filing_data:
                return df
            
            # Convert filings to DataFrame
            filing_df = pd.DataFrame(filing_data)
            if 'filing_date' not in filing_df.columns:
                return df
            
            filing_df['filing_date'] = pd.to_datetime(filing_df['filing_date'])
            filing_df = filing_df.sort_values('filing_date', ascending=False)
            
            # For each timestamp, find most recent filing
            for idx in df.index:
                recent_filings = filing_df[filing_df['filing_date'] <= idx]
                
                if not recent_filings.empty:
                    most_recent = recent_filings.iloc[0]
                    days_diff = (idx - most_recent['filing_date']).days
                    
                    # Mark if filing is within last 7 days
                    if days_diff <= 7:
                        df.loc[idx, 'has_recent_filing'] = True
                        df.loc[idx, 'filing_type'] = most_recent.get('filing_type', None)
                    
                    df.loc[idx, 'days_since_filing'] = days_diff
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding filing features: {e}")
            return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index.
        
        Args:
            prices: Series of prices
            period: RSI period (default 14)
            
        Returns:
            Series of RSI values
        """
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return pd.Series(index=prices.index, dtype=float)
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range.
        
        Args:
            df: DataFrame with OHLCV data
            period: ATR period (default 14)
            
        Returns:
            Series of ATR values
        """
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = true_range.rolling(window=period).mean()
            
            return atr
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Volume Weighted Average Price (daily).
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Series of VWAP values
        """
        try:
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
            
            return vwap
            
        except Exception as e:
            logger.error(f"Error calculating VWAP: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def get_latest_features(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recently computed features for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary of latest features, or None if not available
        """
        if symbol in self.cache:
            return self.cache[symbol]
        return None
    
    def clear_cache(self):
        """Clear the feature cache."""
        self.cache.clear()
        logger.info("Feature cache cleared")

