"""
Vectorized backtesting engine.
Fast vectorized backtesting using pandas and numpy operations.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
import logging
import json
import uuid

from .data_loader import BacktestDataLoader
from app.trading.signals import Signal, SignalAction
from app.trading.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class VectorizedBacktestEngine:
    """
    Fast vectorized backtesting engine.
    
    Features:
    - Vectorized signal generation
    - Portfolio simulation
    - Performance metrics calculation
    - Trade analysis
    - Equity curve generation
    """
    
    def __init__(self, data_loader: BacktestDataLoader):
        """
        Initialize backtesting engine.
        
        Args:
            data_loader: Data loader instance
        """
        self.data_loader = data_loader
        self.logger = logging.getLogger(__name__)
    
    def run_backtest(
        self,
        strategy: BaseStrategy,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        initial_balance: float = 100000.0,
        commission: float = 0.0,
        slippage: float = 0.001,
        include_news: bool = True,
        include_filings: bool = True
    ) -> Dict[str, Any]:
        """
        Run vectorized backtest.
        
        Args:
            strategy: Trading strategy to test
            symbols: List of symbols to trade
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_balance: Starting balance
            commission: Commission per trade
            slippage: Slippage factor
            include_news: Whether to include news data
            include_filings: Whether to include filings data
            
        Returns:
            Backtest results dictionary
        """
        self.logger.info(f"Starting vectorized backtest for {strategy.name}")
        self.logger.info(f"Symbols: {symbols}")
        self.logger.info(f"Period: {start_date} to {end_date}")
        
        # Load data
        data = self.data_loader.create_unified_dataset(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            include_news=include_news,
            include_filings=include_filings
        )
        
        if not data:
            raise ValueError("No data loaded for backtesting")
        
        # Run backtest for each symbol
        results = {}
        for symbol, df in data.items():
            self.logger.info(f"Running backtest for {symbol}")
            symbol_results = self._run_symbol_backtest(
                strategy=strategy,
                symbol=symbol,
                data=df,
                initial_balance=initial_balance,
                commission=commission,
                slippage=slippage
            )
            results[symbol] = symbol_results
        
        # Combine results
        combined_results = self._combine_results(results, initial_balance)
        
        # Add metadata
        combined_results['metadata'] = {
            'strategy_name': strategy.name,
            'symbols': symbols,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'initial_balance': initial_balance,
            'commission': commission,
            'slippage': slippage,
            'backtest_id': str(uuid.uuid4()),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        self.logger.info("Backtest completed successfully")
        return combined_results
    
    def _run_symbol_backtest(
        self,
        strategy: BaseStrategy,
        symbol: str,
        data: pd.DataFrame,
        initial_balance: float,
        commission: float,
        slippage: float
    ) -> Dict[str, Any]:
        """Run backtest for a single symbol."""
        try:
            # Generate signals
            signals = self._generate_signals_vectorized(strategy, symbol, data)
            
            # Simulate portfolio
            portfolio_results = self._simulate_portfolio(
                data=data,
                signals=signals,
                initial_balance=initial_balance,
                commission=commission,
                slippage=slippage
            )
            
            # Calculate performance metrics
            metrics = self._calculate_performance_metrics(portfolio_results)
            
            # Add trade analysis
            trade_analysis = self._analyze_trades(portfolio_results)
            
            return {
                'symbol': symbol,
                'signals': signals,
                'portfolio': portfolio_results,
                'metrics': metrics,
                'trade_analysis': trade_analysis
            }
            
        except Exception as e:
            self.logger.error(f"Error running backtest for {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'signals': pd.DataFrame(),
                'portfolio': pd.DataFrame(),
                'metrics': {},
                'trade_analysis': {}
            }
    
    def _generate_signals_vectorized(
        self,
        strategy: BaseStrategy,
        symbol: str,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate signals using vectorized operations."""
        try:
            signals_list = []
            
            # Process data in chunks to avoid memory issues
            chunk_size = 1000
            for i in range(0, len(data), chunk_size):
                chunk = data.iloc[i:i+chunk_size]
                
                for idx, row in chunk.iterrows():
                    try:
                        # Convert row to features dictionary
                        features = row.to_dict()
                        
                        # Generate signals
                        symbol_signals = strategy.generate_signals(
                            symbol=symbol,
                            features=features,
                            current_positions={}
                        )
                        
                        # Add to signals list
                        for signal in symbol_signals:
                            signals_list.append({
                                'timestamp': idx,
                                'symbol': signal.symbol,
                                'action': signal.action.value,
                                'confidence': signal.confidence,
                                'size_pct': signal.size_pct,
                                'reasoning': signal.reasoning,
                                'entry_price': signal.entry_price,
                                'stop_loss': signal.stop_loss,
                                'take_profit': signal.take_profit,
                                'strategy_name': signal.strategy_name
                            })
                    
                    except Exception as e:
                        self.logger.debug(f"Error generating signal for {symbol} at {idx}: {e}")
                        continue
            
            # Convert to DataFrame
            if signals_list:
                signals_df = pd.DataFrame(signals_list)
                signals_df = signals_df.set_index('timestamp')
                signals_df = signals_df.sort_index()
            else:
                signals_df = pd.DataFrame()
            
            self.logger.info(f"Generated {len(signals_df)} signals for {symbol}")
            return signals_df
            
        except Exception as e:
            self.logger.error(f"Error generating signals for {symbol}: {e}")
            return pd.DataFrame()
    
    def _simulate_portfolio(
        self,
        data: pd.DataFrame,
        signals: pd.DataFrame,
        initial_balance: float,
        commission: float,
        slippage: float
    ) -> pd.DataFrame:
        """Simulate portfolio performance."""
        try:
            # Initialize portfolio tracking
            portfolio = pd.DataFrame(index=data.index)
            portfolio['price'] = data['close']
            portfolio['balance'] = initial_balance
            portfolio['position'] = 0.0
            portfolio['position_value'] = 0.0
            portfolio['total_value'] = initial_balance
            portfolio['pnl'] = 0.0
            portfolio['pnl_pct'] = 0.0
            portfolio['trade_count'] = 0
            portfolio['commission_paid'] = 0.0
            
            # Track trades
            trades = []
            current_position = 0.0
            current_balance = initial_balance
            trade_count = 0
            
            # Process signals
            for timestamp, signal in signals.iterrows():
                if timestamp not in data.index:
                    continue
                
                current_price = data.loc[timestamp, 'close']
                action = signal['action']
                size_pct = signal['size_pct']
                confidence = signal['confidence']
                
                # Calculate position size
                position_value = current_balance * size_pct
                shares = position_value / current_price
                
                # Apply slippage
                if action == 'buy':
                    execution_price = current_price * (1 + slippage)
                else:
                    execution_price = current_price * (1 - slippage)
                
                # Calculate commission
                trade_commission = position_value * commission
                
                # Execute trade
                if action == 'buy' and current_position == 0:
                    # Open long position
                    current_position = shares
                    current_balance -= (shares * execution_price + trade_commission)
                    trade_count += 1
                    
                    trades.append({
                        'timestamp': timestamp,
                        'action': 'buy',
                        'shares': shares,
                        'price': execution_price,
                        'commission': trade_commission,
                        'confidence': confidence
                    })
                
                elif action == 'sell' and current_position > 0:
                    # Close long position
                    proceeds = current_position * execution_price - trade_commission
                    current_balance += proceeds
                    current_position = 0.0
                    trade_count += 1
                    
                    trades.append({
                        'timestamp': timestamp,
                        'action': 'sell',
                        'shares': current_position,
                        'price': execution_price,
                        'commission': trade_commission,
                        'confidence': confidence
                    })
                
                # Update portfolio values
                position_value = current_position * current_price
                total_value = current_balance + position_value
                pnl = total_value - initial_balance
                pnl_pct = pnl / initial_balance
                
                # Update portfolio DataFrame
                portfolio.loc[timestamp, 'balance'] = current_balance
                portfolio.loc[timestamp, 'position'] = current_position
                portfolio.loc[timestamp, 'position_value'] = position_value
                portfolio.loc[timestamp, 'total_value'] = total_value
                portfolio.loc[timestamp, 'pnl'] = pnl
                portfolio.loc[timestamp, 'pnl_pct'] = pnl_pct
                portfolio.loc[timestamp, 'trade_count'] = trade_count
                portfolio.loc[timestamp, 'commission_paid'] = trade_commission
            
            # Forward-fill portfolio values
            portfolio = portfolio.ffill()
            
            # Add trades to portfolio
            portfolio['trades'] = len(trades)
            
            return portfolio
            
        except Exception as e:
            self.logger.error(f"Error simulating portfolio: {e}")
            return pd.DataFrame()
    
    def _calculate_performance_metrics(self, portfolio: pd.DataFrame) -> Dict[str, float]:
        """Calculate performance metrics."""
        try:
            if portfolio.empty:
                return {}
            
            # Basic metrics
            total_return = portfolio['total_value'].iloc[-1] - portfolio['total_value'].iloc[0]
            total_return_pct = total_return / portfolio['total_value'].iloc[0]
            
            # Calculate returns
            returns = portfolio['total_value'].pct_change().dropna()
            
            # Risk metrics
            volatility = returns.std() * np.sqrt(252)  # Annualized
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
            
            # Drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()
            
            # Win rate
            positive_returns = returns[returns > 0]
            win_rate = len(positive_returns) / len(returns) if len(returns) > 0 else 0
            
            # Profit factor
            gross_profit = positive_returns.sum()
            gross_loss = abs(returns[returns < 0].sum())
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            # Trade statistics
            total_trades = portfolio.get('trade_count', pd.Series([0])).iloc[-1] if 'trade_count' in portfolio.columns else 0
            avg_trade_duration = len(portfolio) / total_trades if total_trades > 0 else 0
            
            return {
                'total_return': total_return,
                'total_return_pct': total_return_pct,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'max_drawdown_pct': max_drawdown * 100,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'total_trades': total_trades,
                'avg_trade_duration': avg_trade_duration,
                'final_balance': portfolio['total_value'].iloc[-1],
                'max_balance': portfolio['total_value'].max(),
                'min_balance': portfolio['total_value'].min()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def _analyze_trades(self, portfolio: pd.DataFrame) -> Dict[str, Any]:
        """Analyze individual trades."""
        try:
            if portfolio.empty:
                return {}
            
            # Calculate trade returns
            returns = portfolio['total_value'].pct_change().dropna()
            
            # Best and worst trades
            best_trade = returns.max()
            worst_trade = returns.min()
            
            # Consecutive wins/losses
            consecutive_wins = 0
            consecutive_losses = 0
            max_consecutive_wins = 0
            max_consecutive_losses = 0
            
            current_wins = 0
            current_losses = 0
            
            for ret in returns:
                if ret > 0:
                    current_wins += 1
                    current_losses = 0
                    max_consecutive_wins = max(max_consecutive_wins, current_wins)
                elif ret < 0:
                    current_losses += 1
                    current_wins = 0
                    max_consecutive_losses = max(max_consecutive_losses, current_losses)
            
            return {
                'best_trade': best_trade,
                'worst_trade': worst_trade,
                'max_consecutive_wins': max_consecutive_wins,
                'max_consecutive_losses': max_consecutive_losses,
                'avg_return': returns.mean(),
                'median_return': returns.median(),
                'return_std': returns.std()
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing trades: {e}")
            return {}
    
    def _combine_results(self, results: Dict[str, Any], initial_balance: float) -> Dict[str, Any]:
        """Combine results from multiple symbols."""
        try:
            combined = {
                'symbols': list(results.keys()),
                'total_symbols': len(results),
                'initial_balance': initial_balance,
                'symbol_results': results
            }
            
            # Calculate combined metrics
            total_return = 0
            total_trades = 0
            total_commission = 0
            
            for symbol, result in results.items():
                if 'metrics' in result:
                    metrics = result['metrics']
                    total_return += metrics.get('total_return', 0)
                    total_trades += metrics.get('total_trades', 0)
                    total_commission += metrics.get('commission_paid', 0)
            
            combined['combined_metrics'] = {
                'total_return': total_return,
                'total_return_pct': total_return / initial_balance if initial_balance > 0 else 0,
                'total_trades': total_trades,
                'total_commission': total_commission,
                'avg_return_per_symbol': total_return / len(results) if results else 0
            }
            
            return combined
            
        except Exception as e:
            self.logger.error(f"Error combining results: {e}")
            return {'error': str(e)}
    
    def export_results(self, results: Dict[str, Any], format: str = 'json') -> str:
        """
        Export backtest results.
        
        Args:
            results: Backtest results
            format: Export format ('json', 'csv')
            
        Returns:
            Exported data as string
        """
        try:
            if format == 'json':
                return json.dumps(results, indent=2, default=str)
            elif format == 'csv':
                # Export portfolio data as CSV
                csv_data = []
                for symbol, result in results.get('symbol_results', {}).items():
                    if 'portfolio' in result and not result['portfolio'].empty:
                        portfolio_df = result['portfolio']
                        portfolio_df['symbol'] = symbol
                        csv_data.append(portfolio_df)
                
                if csv_data:
                    combined_df = pd.concat(csv_data, ignore_index=True)
                    return combined_df.to_csv(index=False)
                else:
                    return "No portfolio data to export"
            else:
                raise ValueError(f"Unsupported format: {format}")
                
        except Exception as e:
            self.logger.error(f"Error exporting results: {e}")
            return f"Error exporting results: {e}"
