"""
Tests for Phase 3: Backtesting Framework
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import tempfile
import os

from app.backtesting.data_loader import BacktestDataLoader
from app.backtesting.vectorized_engine import VectorizedBacktestEngine
from app.backtesting.event_driven_engine import EventDrivenBacktestEngine, Portfolio
from app.trading.strategies.mean_reversion import MeanReversionStrategy
from app.trading.signals import Signal, SignalAction


class TestBacktestDataLoader:
    """Test data loader functionality."""
    
    def test_data_loader_initialization(self):
        """Test data loader initialization."""
        storage_manager = Mock()
        loader = BacktestDataLoader(storage_manager)
        assert loader.storage == storage_manager
    
    def test_load_ohlcv_data(self):
        """Test loading OHLCV data."""
        # Mock storage manager
        storage_manager = Mock()
        mock_data = pd.DataFrame({
            'timestamp_utc': pd.date_range('2023-01-01', periods=100, freq='1min'),
            'open': np.random.randn(100) + 100,
            'high': np.random.randn(100) + 101,
            'low': np.random.randn(100) + 99,
            'close': np.random.randn(100) + 100,
            'volume': np.random.randint(1000, 10000, 100)
        })
        storage_manager.query_ohlcv.return_value = mock_data
        
        loader = BacktestDataLoader(storage_manager)
        
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        result = loader.load_ohlcv_data(['AAPL'], start_date, end_date)
        
        assert 'AAPL' in result
        assert len(result['AAPL']) > 0
        assert 'close' in result['AAPL'].columns
    
    def test_load_news_data(self):
        """Test loading news data."""
        storage_manager = Mock()
        mock_news = [
            {
                'timestamp_utc': datetime(2023, 1, 1, tzinfo=timezone.utc),
                'ticker': 'AAPL',
                'headline': 'Test news',
                'sentiment_score': 0.5
            }
        ]
        storage_manager.query_news.return_value = mock_news
        
        loader = BacktestDataLoader(storage_manager)
        
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        result = loader.load_news_data(['AAPL'], start_date, end_date)
        
        assert not result.empty
        assert 'ticker' in result.columns
    
    def test_create_unified_dataset(self):
        """Test creating unified dataset."""
        storage_manager = Mock()
        
        # Mock OHLCV data
        mock_ohlcv = pd.DataFrame({
            'timestamp_utc': pd.date_range('2023-01-01', periods=100, freq='1min'),
            'open': np.random.randn(100) + 100,
            'high': np.random.randn(100) + 101,
            'low': np.random.randn(100) + 99,
            'close': np.random.randn(100) + 100,
            'volume': np.random.randint(1000, 10000, 100)
        })
        storage_manager.query_ohlcv.return_value = mock_ohlcv
        storage_manager.query_news.return_value = []
        storage_manager.query_filings.return_value = []
        
        loader = BacktestDataLoader(storage_manager)
        
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        result = loader.create_unified_dataset(['AAPL'], start_date, end_date)
        
        assert 'AAPL' in result
        assert len(result['AAPL']) > 0
        assert 'close' in result['AAPL'].columns
        assert 'sma_20' in result['AAPL'].columns  # Basic indicators added
    
    def test_add_basic_indicators(self):
        """Test adding basic technical indicators."""
        storage_manager = Mock()
        loader = BacktestDataLoader(storage_manager)
        
        # Create test data
        data = pd.DataFrame({
            'close': [100, 101, 102, 101, 100, 99, 98, 99, 100, 101] * 10,
            'high': [101, 102, 103, 102, 101, 100, 99, 100, 101, 102] * 10,
            'low': [99, 100, 101, 100, 99, 98, 97, 98, 99, 100] * 10,
            'volume': [1000] * 100
        })
        
        result = loader._add_basic_indicators(data)
        
        assert 'sma_20' in result.columns
        assert 'rsi' in result.columns
        assert 'bb_upper' in result.columns
        assert 'bb_lower' in result.columns
        assert 'atr' in result.columns


class TestVectorizedBacktestEngine:
    """Test vectorized backtesting engine."""
    
    def test_engine_initialization(self):
        """Test engine initialization."""
        data_loader = Mock()
        engine = VectorizedBacktestEngine(data_loader)
        assert engine.data_loader == data_loader
    
    def test_run_backtest(self):
        """Test running a backtest."""
        # Mock data loader
        data_loader = Mock()
        mock_data = {
            'AAPL': pd.DataFrame({
                'close': [100, 101, 102, 101, 100, 99, 98, 99, 100, 101] * 10,
                'volume': [1000] * 100,
                'sma_20': [100] * 100,
                'rsi': [50] * 100
            })
        }
        data_loader.create_unified_dataset.return_value = mock_data
        
        # Mock strategy
        strategy = Mock()
        strategy.name = "test_strategy"
        strategy.generate_signals.return_value = []
        
        engine = VectorizedBacktestEngine(data_loader)
        
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        result = engine.run_backtest(
            strategy=strategy,
            symbols=['AAPL'],
            start_date=start_date,
            end_date=end_date,
            initial_balance=100000.0
        )
        
        assert 'metadata' in result
        assert 'symbol_results' in result
        assert 'AAPL' in result['symbol_results']
    
    def test_calculate_performance_metrics(self):
        """Test performance metrics calculation."""
        data_loader = Mock()
        engine = VectorizedBacktestEngine(data_loader)
        
        # Create mock portfolio data
        portfolio = pd.DataFrame({
            'total_value': [100000, 101000, 102000, 101500, 100500],
            'pnl': [0, 1000, 2000, 1500, 500],
            'pnl_pct': [0, 0.01, 0.02, 0.015, 0.005]
        })
        
        metrics = engine._calculate_performance_metrics(portfolio)
        
        assert 'total_return' in metrics
        assert 'total_return_pct' in metrics
        assert 'volatility' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics
        assert 'win_rate' in metrics
    
    def test_analyze_trades(self):
        """Test trade analysis."""
        data_loader = Mock()
        engine = VectorizedBacktestEngine(data_loader)
        
        # Create mock portfolio data
        portfolio = pd.DataFrame({
            'total_value': [100000, 101000, 102000, 101500, 100500],
            'pnl': [0, 1000, 2000, 1500, 500],
            'pnl_pct': [0, 0.01, 0.02, 0.015, 0.005]
        })
        
        trade_analysis = engine._analyze_trades(portfolio)
        
        assert 'best_trade' in trade_analysis
        assert 'worst_trade' in trade_analysis
        assert 'avg_return' in trade_analysis


class TestEventDrivenBacktestEngine:
    """Test event-driven backtesting engine."""
    
    def test_engine_initialization(self):
        """Test engine initialization."""
        data_loader = Mock()
        engine = EventDrivenBacktestEngine(data_loader)
        assert engine.data_loader == data_loader
    
    def test_create_event_queue(self):
        """Test creating event queue."""
        data_loader = Mock()
        engine = EventDrivenBacktestEngine(data_loader)
        
        # Create mock data
        data = {
            'AAPL': pd.DataFrame({
                'close': [100, 101, 102],
                'volume': [1000, 1100, 1200]
            })
        }
        
        events = engine._create_event_queue(data)
        
        assert len(events) == 3
        assert events[0]['symbol'] == 'AAPL'
        assert events[0]['type'] == 'market_data'
        assert 'close' in events[0]['data']
    
    def test_process_events(self):
        """Test processing events."""
        data_loader = Mock()
        engine = EventDrivenBacktestEngine(data_loader)
        
        # Create mock events
        events = [
            {
                'timestamp': datetime(2023, 1, 1, tzinfo=timezone.utc),
                'symbol': 'AAPL',
                'type': 'market_data',
                'data': {'close': 100, 'volume': 1000}
            }
        ]
        
        # Mock strategy
        strategy = Mock()
        strategy.generate_signals.return_value = []
        
        portfolio = Portfolio(100000.0)
        
        result = engine._process_events(events, strategy, portfolio, 0.0, 0.001)
        
        assert 'portfolio_history' in result
        assert 'trades' in result
        assert 'metrics' in result
        assert 'trade_analysis' in result


class TestPortfolio:
    """Test portfolio state management."""
    
    def test_portfolio_initialization(self):
        """Test portfolio initialization."""
        portfolio = Portfolio(100000.0)
        assert portfolio.balance == 100000.0
        assert portfolio.positions == {}
        assert portfolio.prices == {}
    
    def test_add_position(self):
        """Test adding position."""
        portfolio = Portfolio(100000.0)
        portfolio.add_position('AAPL', 100, 150.0)
        
        assert 'AAPL' in portfolio.positions
        assert portfolio.positions['AAPL']['shares'] == 100
        assert portfolio.positions['AAPL']['avg_price'] == 150.0
    
    def test_remove_position(self):
        """Test removing position."""
        portfolio = Portfolio(100000.0)
        portfolio.add_position('AAPL', 100, 150.0)
        portfolio.remove_position('AAPL', 50)
        
        assert portfolio.positions['AAPL']['shares'] == 50
    
    def test_get_total_value(self):
        """Test getting total value."""
        portfolio = Portfolio(100000.0)
        portfolio.add_position('AAPL', 100, 150.0)
        portfolio.update_prices({'AAPL': 160.0})
        
        total_value = portfolio.get_total_value()
        assert total_value == 100000.0 + (100 * 160.0)
    
    def test_get_total_pnl(self):
        """Test getting total P&L."""
        portfolio = Portfolio(100000.0)
        portfolio.add_position('AAPL', 100, 150.0)
        portfolio.update_prices({'AAPL': 160.0})
        
        pnl = portfolio.get_total_pnl()
        assert pnl == 100 * (160.0 - 150.0)  # 1000
    
    def test_get_total_pnl_pct(self):
        """Test getting total P&L percentage."""
        portfolio = Portfolio(100000.0)
        portfolio.add_position('AAPL', 100, 150.0)
        portfolio.update_prices({'AAPL': 160.0})
        
        pnl_pct = portfolio.get_total_pnl_pct()
        # P&L percentage should be based on total portfolio value vs initial balance
        total_value = portfolio.get_total_value()
        expected_pct = (total_value - 100000.0) / 100000.0
        assert abs(pnl_pct - expected_pct) < 0.001


class TestIntegration:
    """Integration tests for backtesting framework."""
    
    def test_complete_backtest_flow(self):
        """Test complete backtesting flow."""
        # Mock storage manager
        storage_manager = Mock()
        mock_data = pd.DataFrame({
            'timestamp_utc': pd.date_range('2023-01-01', periods=100, freq='1min'),
            'open': np.random.randn(100) + 100,
            'high': np.random.randn(100) + 101,
            'low': np.random.randn(100) + 99,
            'close': np.random.randn(100) + 100,
            'volume': np.random.randint(1000, 10000, 100)
        })
        storage_manager.query_ohlcv.return_value = mock_data
        storage_manager.query_news.return_value = []
        storage_manager.query_filings.return_value = []
        
        # Create data loader
        data_loader = BacktestDataLoader(storage_manager)
        
        # Create strategy
        strategy = MeanReversionStrategy()
        
        # Create engine
        engine = VectorizedBacktestEngine(data_loader)
        
        # Run backtest
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        result = engine.run_backtest(
            strategy=strategy,
            symbols=['AAPL'],
            start_date=start_date,
            end_date=end_date,
            initial_balance=100000.0
        )
        
        # Verify results
        assert 'metadata' in result
        assert 'symbol_results' in result
        assert 'AAPL' in result['symbol_results']
        
        symbol_result = result['symbol_results']['AAPL']
        assert 'signals' in symbol_result
        assert 'portfolio' in symbol_result
        assert 'metrics' in symbol_result
        assert 'trade_analysis' in symbol_result
    
    def test_event_driven_backtest(self):
        """Test event-driven backtesting."""
        # Mock storage manager
        storage_manager = Mock()
        mock_data = pd.DataFrame({
            'timestamp_utc': pd.date_range('2023-01-01', periods=100, freq='1min'),
            'open': np.random.randn(100) + 100,
            'high': np.random.randn(100) + 101,
            'low': np.random.randn(100) + 99,
            'close': np.random.randn(100) + 100,
            'volume': np.random.randint(1000, 10000, 100)
        })
        storage_manager.query_ohlcv.return_value = mock_data
        storage_manager.query_news.return_value = []
        storage_manager.query_filings.return_value = []
        
        # Create data loader
        data_loader = BacktestDataLoader(storage_manager)
        
        # Create strategy
        strategy = MeanReversionStrategy()
        
        # Create engine
        engine = EventDrivenBacktestEngine(data_loader)
        
        # Run backtest
        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        result = engine.run_backtest(
            strategy=strategy,
            symbols=['AAPL'],
            start_date=start_date,
            end_date=end_date,
            initial_balance=100000.0
        )
        
        # Verify results
        assert 'metadata' in result
        assert 'portfolio_history' in result
        assert 'trades' in result
        assert 'metrics' in result
        assert 'trade_analysis' in result
    
    def test_export_results(self):
        """Test exporting results."""
        data_loader = Mock()
        engine = VectorizedBacktestEngine(data_loader)
        
        # Mock results
        results = {
            'metadata': {'strategy_name': 'test'},
            'symbol_results': {
                'AAPL': {
                    'portfolio': pd.DataFrame({
                        'total_value': [100000, 101000, 102000],
                        'pnl': [0, 1000, 2000]
                    })
                }
            }
        }
        
        # Test JSON export
        json_result = engine.export_results(results, 'json')
        assert isinstance(json_result, str)
        assert 'strategy_name' in json_result
        
        # Test CSV export
        csv_result = engine.export_results(results, 'csv')
        assert isinstance(csv_result, str)
        assert 'total_value' in csv_result


class TestBacktestAPI:
    """Test backtesting API routes."""
    
    def test_backtest_request_validation(self):
        """Test backtest request validation."""
        from app.api.backtest_routes import BacktestRequest
        
        # Valid request
        request = BacktestRequest(
            strategy_name="mean_reversion",
            symbols=["AAPL"],
            start_date="2023-01-01T00:00:00Z",
            end_date="2023-01-02T00:00:00Z"
        )
        
        assert request.strategy_name == "mean_reversion"
        assert request.symbols == ["AAPL"]
        assert request.initial_balance == 100000.0
        assert request.commission == 0.0
        assert request.slippage == 0.001
    
    def test_get_strategy(self):
        """Test getting strategy instance."""
        from app.api.backtest_routes import get_strategy
        
        # Test mean reversion strategy
        strategy = get_strategy("mean_reversion")
        assert strategy.name == "mean_reversion"
        
        # Test with parameters
        strategy = get_strategy("mean_reversion", {"rsi_oversold": 25})
        assert strategy.name == "mean_reversion"
        
        # Test unknown strategy
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            get_strategy("unknown_strategy")


if __name__ == "__main__":
    pytest.main([__file__])
