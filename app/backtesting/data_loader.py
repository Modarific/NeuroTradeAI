"""
Data loader for backtesting framework.
Loads historical data from the storage manager for backtesting.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta
import logging

from app.core.storage import StorageManager

logger = logging.getLogger(__name__)


class BacktestDataLoader:
    """
    Loads and prepares historical data for backtesting.
    
    Features:
    - Load OHLCV data from storage manager
    - Load news and filing events
    - Handle missing data and forward-fill
    - Combine into unified DataFrame
    - Support for multiple symbols
    """
    
    def __init__(self, storage_manager: StorageManager):
        """
        Initialize data loader.
        
        Args:
            storage_manager: Storage manager instance
        """
        self.storage = storage_manager
        self.logger = logging.getLogger(__name__)
    
    def load_ohlcv_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1min"
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV data for multiple symbols.
        
        Args:
            symbols: List of symbols to load
            start_date: Start date for data
            end_date: End date for data
            timeframe: Data timeframe (1min, 5min, 1hour, 1day)
            
        Returns:
            Dictionary mapping symbols to DataFrames
        """
        data = {}
        
        for symbol in symbols:
            try:
                df = self.storage.query_ohlcv(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df.empty:
                    self.logger.warning(f"No data found for {symbol}")
                    continue
                
                # Ensure proper datetime index
                if 'timestamp_utc' in df.columns:
                    df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
                    df = df.set_index('timestamp_utc')
                
                # Sort by timestamp
                df = df.sort_index()
                
                # Forward-fill missing values
                df = df.ffill()
                
                # Remove any remaining NaN values
                df = df.dropna()
                
                if not df.empty:
                    data[symbol] = df
                    self.logger.info(f"Loaded {len(df)} records for {symbol}")
                else:
                    self.logger.warning(f"No valid data after cleaning for {symbol}")
                    
            except Exception as e:
                self.logger.error(f"Error loading data for {symbol}: {e}")
                continue
        
        return data
    
    def load_news_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Load news data for symbols.
        
        Args:
            symbols: List of symbols to load news for
            start_date: Start date for news
            end_date: End date for news
            
        Returns:
            DataFrame with news data
        """
        try:
            news_data = self.storage.query_news(
                ticker=None,  # Get all news
                start_date=start_date,
                end_date=end_date,
                limit=10000
            )
            
            if not news_data:
                self.logger.warning("No news data found")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(news_data)
            
            # Filter by symbols if provided
            if symbols:
                df = df[df['ticker'].isin(symbols)]
            
            # Convert timestamp
            df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
            df = df.set_index('timestamp_utc')
            
            # Sort by timestamp
            df = df.sort_index()
            
            self.logger.info(f"Loaded {len(df)} news records")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading news data: {e}")
            return pd.DataFrame()
    
    def load_filings_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Load SEC filings data for symbols.
        
        Args:
            symbols: List of symbols to load filings for
            start_date: Start date for filings
            end_date: End date for filings
            
        Returns:
            DataFrame with filings data
        """
        try:
            filings_data = []
            
            for symbol in symbols:
                filings = self.storage.query_filings(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date
                )
                filings_data.extend(filings)
            
            if not filings_data:
                self.logger.warning("No filings data found")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(filings_data)
            
            # Convert timestamp
            df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
            df = df.set_index('timestamp_utc')
            
            # Sort by timestamp
            df = df.sort_index()
            
            self.logger.info(f"Loaded {len(df)} filings records")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading filings data: {e}")
            return pd.DataFrame()
    
    def create_unified_dataset(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        include_news: bool = True,
        include_filings: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Create unified dataset with OHLCV, news, and filings data.
        
        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            include_news: Whether to include news data
            include_filings: Whether to include filings data
            
        Returns:
            Dictionary with unified datasets for each symbol
        """
        self.logger.info(f"Creating unified dataset for {symbols}")
        
        # Load OHLCV data
        ohlcv_data = self.load_ohlcv_data(symbols, start_date, end_date)
        
        # Load news data if requested
        news_data = pd.DataFrame()
        if include_news:
            news_data = self.load_news_data(symbols, start_date, end_date)
        
        # Load filings data if requested
        filings_data = pd.DataFrame()
        if include_filings:
            filings_data = self.load_filings_data(symbols, start_date, end_date)
        
        # Create unified dataset for each symbol
        unified_data = {}
        
        for symbol in symbols:
            if symbol not in ohlcv_data:
                self.logger.warning(f"No OHLCV data for {symbol}, skipping")
                continue
            
            df = ohlcv_data[symbol].copy()
            
            # Add news features
            if not news_data.empty:
                symbol_news = news_data[news_data['ticker'] == symbol]
                if not symbol_news.empty:
                    # Add news sentiment features
                    df = self._add_news_features(df, symbol_news)
            
            # Add filings features
            if not filings_data.empty:
                symbol_filings = filings_data[filings_data['ticker'] == symbol]
                if not symbol_filings.empty:
                    # Add filings features
                    df = self._add_filings_features(df, symbol_filings)
            
            # Add time-based features
            df = self._add_time_features(df)
            
            # Add basic technical indicators
            df = self._add_basic_indicators(df)
            
            unified_data[symbol] = df
            self.logger.info(f"Created unified dataset for {symbol} with {len(df)} records")
        
        return unified_data
    
    def _add_news_features(self, df: pd.DataFrame, news_data: pd.DataFrame) -> pd.DataFrame:
        """Add news sentiment features to DataFrame."""
        try:
            # Calculate news sentiment over time windows
            for window in ['1h', '4h', '1d']:
                # Count news articles
                news_count = news_data.resample(window).size()
                news_count = news_count.reindex(df.index, fill_value=0)
                df[f'news_count_{window}'] = news_count
                
                # Average sentiment
                if 'sentiment_score' in news_data.columns:
                    sentiment = news_data['sentiment_score'].resample(window).mean()
                    sentiment = sentiment.reindex(df.index, fill_value=0)
                    df[f'news_sentiment_{window}'] = sentiment
                
                # Recent news flag
                recent_news = news_count > 0
                df[f'has_recent_news_{window}'] = recent_news.astype(int)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding news features: {e}")
            return df
    
    def _add_filings_features(self, df: pd.DataFrame, filings_data: pd.DataFrame) -> pd.DataFrame:
        """Add SEC filings features to DataFrame."""
        try:
            # Count filings over time windows
            for window in ['1d', '1w', '1M']:
                filings_count = filings_data.resample(window).size()
                filings_count = filings_count.reindex(df.index, fill_value=0)
                df[f'filings_count_{window}'] = filings_count
                
                # Recent filings flag
                recent_filings = filings_count > 0
                df[f'has_recent_filings_{window}'] = recent_filings.astype(int)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding filings features: {e}")
            return df
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features to DataFrame."""
        try:
            # Market hours
            df['hour'] = df.index.hour
            df['day_of_week'] = df.index.dayofweek
            df['is_market_open'] = ((df['hour'] >= 9) & (df['hour'] < 16) & (df['day_of_week'] < 5)).astype(int)
            
            # Time since market open/close
            market_open = df.index.normalize() + pd.Timedelta(hours=9, minutes=30)
            market_close = df.index.normalize() + pd.Timedelta(hours=16)
            
            df['minutes_since_open'] = (df.index - market_open).dt.total_seconds() / 60
            df['minutes_until_close'] = (market_close - df.index).dt.total_seconds() / 60
            
            # Clamp negative values
            df['minutes_since_open'] = df['minutes_since_open'].clip(lower=0)
            df['minutes_until_close'] = df['minutes_until_close'].clip(lower=0)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding time features: {e}")
            return df
    
    def _add_basic_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add basic technical indicators to DataFrame."""
        try:
            # Simple Moving Averages
            for period in [20, 50, 200]:
                df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
            
            # Exponential Moving Averages
            for period in [12, 26]:
                df[f'ema_{period}'] = df['close'].ewm(span=period).mean()
            
            # RSI
            df['rsi'] = self._calculate_rsi(df['close'], 14)
            
            # Bollinger Bands
            bb_period = 20
            bb_std = 2
            sma = df['close'].rolling(window=bb_period).mean()
            std = df['close'].rolling(window=bb_period).std()
            df['bb_upper'] = sma + (std * bb_std)
            df['bb_lower'] = sma - (std * bb_std)
            df['bb_middle'] = sma
            df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
            
            # ATR
            df['atr'] = self._calculate_atr(df, 14)
            
            # Volume indicators
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding basic indicators: {e}")
            return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator."""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except Exception:
            return pd.Series(index=prices.index, dtype=float)
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range indicator."""
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            
            return atr
        except Exception:
            return pd.Series(index=df.index, dtype=float)
    
    def get_data_summary(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Get summary statistics for loaded data.
        
        Args:
            data: Dictionary of DataFrames
            
        Returns:
            Summary statistics
        """
        summary = {}
        
        for symbol, df in data.items():
            summary[symbol] = {
                'records': len(df),
                'start_date': df.index.min().isoformat() if not df.empty else None,
                'end_date': df.index.max().isoformat() if not df.empty else None,
                'columns': list(df.columns),
                'missing_data': df.isnull().sum().to_dict(),
                'price_range': {
                    'min': df['close'].min() if 'close' in df.columns else None,
                    'max': df['close'].max() if 'close' in df.columns else None,
                    'mean': df['close'].mean() if 'close' in df.columns else None
                }
            }
        
        return summary
