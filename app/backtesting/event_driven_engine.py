"""
Event-driven backtesting engine.
Simulates realistic trading with event-driven execution.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta
import logging
import json
import uuid
from collections import deque

from .data_loader import BacktestDataLoader
from app.trading.signals import Signal, SignalAction
from app.trading.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class EventDrivenBacktestEngine:
    """
    Event-driven backtesting engine.
    
    Features:
    - Realistic order execution simulation
    - Event-driven signal processing
    - Portfolio state management
    - Trade execution with slippage and commission
    - Detailed trade logging
    """
    
    def __init__(self, data_loader: BacktestDataLoader):
        """
        Initialize event-driven backtesting engine.
        
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
        Run event-driven backtest.
        
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
        self.logger.info(f"Starting event-driven backtest for {strategy.name}")
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
        
        # Create event queue
        events = self._create_event_queue(data)
        
        # Initialize portfolio
        portfolio = Portfolio(initial_balance)
        
        # Process events
        results = self._process_events(
            events=events,
            strategy=strategy,
            portfolio=portfolio,
            commission=commission,
            slippage=slippage
        )
        
        # Add metadata
        results['metadata'] = {
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
        
        self.logger.info("Event-driven backtest completed successfully")
        return results
    
    def _create_event_queue(self, data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """Create event queue from data."""
        events = []
        
        for symbol, df in data.items():
            for timestamp, row in df.iterrows():
                event = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'type': 'market_data',
                    'data': row.to_dict()
                }
                events.append(event)
        
        # Sort events by timestamp
        events.sort(key=lambda x: x['timestamp'])
        
        self.logger.info(f"Created {len(events)} events")
        return events
    
    def _process_events(
        self,
        events: List[Dict[str, Any]],
        strategy: BaseStrategy,
        portfolio: 'Portfolio',
        commission: float,
        slippage: float
    ) -> Dict[str, Any]:
        """Process events and generate trades."""
        try:
            trades = []
            portfolio_history = []
            
            for event in events:
                timestamp = event['timestamp']
                symbol = event['symbol']
                data = event['data']
                
                # Update portfolio with current prices
                portfolio.update_prices({symbol: data['close']})
                
                # Generate signals
                try:
                    signals = strategy.generate_signals(
                        symbol=symbol,
                        features=data,
                        current_positions=portfolio.get_positions()
                    )
                    
                    # Process signals
                    for signal in signals:
                        trade = self._execute_signal(
                            signal=signal,
                            portfolio=portfolio,
                            commission=commission,
                            slippage=slippage
                        )
                        
                        if trade:
                            trades.append(trade)
                
                except Exception as e:
                    self.logger.debug(f"Error processing signal for {symbol} at {timestamp}: {e}")
                    continue
                
                # Record portfolio state
                portfolio_state = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'balance': portfolio.balance,
                    'total_value': portfolio.get_total_value(),
                    'positions': portfolio.get_positions().copy(),
                    'pnl': portfolio.get_total_pnl(),
                    'pnl_pct': portfolio.get_total_pnl_pct()
                }
                portfolio_history.append(portfolio_state)
            
            # Calculate performance metrics
            metrics = self._calculate_metrics(portfolio_history, trades)
            
            # Analyze trades
            trade_analysis = self._analyze_trades(trades)
            
            return {
                'portfolio_history': portfolio_history,
                'trades': trades,
                'metrics': metrics,
                'trade_analysis': trade_analysis,
                'final_portfolio': portfolio.get_state()
            }
            
        except Exception as e:
            self.logger.error(f"Error processing events: {e}")
            return {'error': str(e)}
    
    def _execute_signal(
        self,
        signal: Signal,
        portfolio: 'Portfolio',
        commission: float,
        slippage: float
    ) -> Optional[Dict[str, Any]]:
        """Execute a trading signal."""
        try:
            symbol = signal.symbol
            action = signal.action
            size_pct = signal.size_pct
            entry_price = signal.entry_price or portfolio.get_price(symbol)
            
            if not entry_price:
                return None
            
            # Apply slippage
            if action == SignalAction.BUY:
                execution_price = entry_price * (1 + slippage)
            else:
                execution_price = entry_price * (1 - slippage)
            
            # Calculate position size
            position_value = portfolio.balance * size_pct
            shares = position_value / execution_price
            
            # Check if we have enough balance
            if action == SignalAction.BUY and position_value > portfolio.balance:
                return None
            
            # Execute trade
            if action == SignalAction.BUY:
                # Buy shares
                cost = shares * execution_price
                commission_cost = cost * commission
                total_cost = cost + commission_cost
                
                if total_cost <= portfolio.balance:
                    portfolio.balance -= total_cost
                    portfolio.add_position(symbol, shares, execution_price)
                    
                    return {
                        'timestamp': datetime.now(timezone.utc),
                        'symbol': symbol,
                        'action': 'buy',
                        'shares': shares,
                        'price': execution_price,
                        'cost': cost,
                        'commission': commission_cost,
                        'total_cost': total_cost,
                        'confidence': signal.confidence,
                        'reasoning': signal.reasoning
                    }
            
            elif action == SignalAction.SELL:
                # Sell shares
                current_position = portfolio.get_position(symbol)
                if current_position and current_position['shares'] > 0:
                    shares_to_sell = min(shares, current_position['shares'])
                    proceeds = shares_to_sell * execution_price
                    commission_cost = proceeds * commission
                    net_proceeds = proceeds - commission_cost
                    
                    portfolio.balance += net_proceeds
                    portfolio.remove_position(symbol, shares_to_sell)
                    
                    return {
                        'timestamp': datetime.now(timezone.utc),
                        'symbol': symbol,
                        'action': 'sell',
                        'shares': shares_to_sell,
                        'price': execution_price,
                        'proceeds': proceeds,
                        'commission': commission_cost,
                        'net_proceeds': net_proceeds,
                        'confidence': signal.confidence,
                        'reasoning': signal.reasoning
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            return None
    
    def _calculate_metrics(self, portfolio_history: List[Dict], trades: List[Dict]) -> Dict[str, float]:
        """Calculate performance metrics."""
        try:
            if not portfolio_history:
                return {}
            
            # Extract values
            total_values = [p['total_value'] for p in portfolio_history]
            pnls = [p['pnl'] for p in portfolio_history]
            pnl_pcts = [p['pnl_pct'] for p in portfolio_history]
            
            # Basic metrics
            initial_value = total_values[0]
            final_value = total_values[-1]
            total_return = final_value - initial_value
            total_return_pct = total_return / initial_value if initial_value > 0 else 0
            
            # Calculate returns
            returns = pd.Series(total_values).pct_change().dropna()
            
            # Risk metrics
            volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
            
            # Drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min() if len(drawdown) > 0 else 0
            
            # Win rate
            positive_returns = returns[returns > 0]
            win_rate = len(positive_returns) / len(returns) if len(returns) > 0 else 0
            
            # Trade statistics
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t.get('net_proceeds', 0) > 0])
            win_rate_trades = winning_trades / total_trades if total_trades > 0 else 0
            
            return {
                'total_return': total_return,
                'total_return_pct': total_return_pct,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'max_drawdown_pct': max_drawdown * 100,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'win_rate_trades': win_rate_trades,
                'final_value': final_value,
                'max_value': max(total_values),
                'min_value': min(total_values)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {e}")
            return {}
    
    def _analyze_trades(self, trades: List[Dict]) -> Dict[str, Any]:
        """Analyze individual trades."""
        try:
            if not trades:
                return {}
            
            # Calculate trade returns
            trade_returns = []
            for trade in trades:
                if trade['action'] == 'sell':
                    # Calculate return for this trade
                    entry_price = trade.get('entry_price', 0)
                    exit_price = trade['price']
                    if entry_price > 0:
                        return_pct = (exit_price - entry_price) / entry_price
                        trade_returns.append(return_pct)
            
            if not trade_returns:
                return {}
            
            trade_returns = pd.Series(trade_returns)
            
            return {
                'total_trades': len(trades),
                'avg_return': trade_returns.mean(),
                'median_return': trade_returns.median(),
                'best_trade': trade_returns.max(),
                'worst_trade': trade_returns.min(),
                'return_std': trade_returns.std(),
                'positive_trades': len(trade_returns[trade_returns > 0]),
                'negative_trades': len(trade_returns[trade_returns < 0])
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing trades: {e}")
            return {}


class Portfolio:
    """Portfolio state management for event-driven backtesting."""
    
    def __init__(self, initial_balance: float):
        """Initialize portfolio."""
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions = {}  # symbol -> {'shares': float, 'avg_price': float}
        self.prices = {}  # symbol -> current_price
    
    def update_prices(self, prices: Dict[str, float]):
        """Update current prices."""
        self.prices.update(prices)
    
    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol."""
        return self.prices.get(symbol)
    
    def add_position(self, symbol: str, shares: float, price: float):
        """Add to position."""
        if symbol in self.positions:
            # Average price calculation
            current_shares = self.positions[symbol]['shares']
            current_avg_price = self.positions[symbol]['avg_price']
            total_shares = current_shares + shares
            total_cost = (current_shares * current_avg_price) + (shares * price)
            new_avg_price = total_cost / total_shares if total_shares > 0 else price
            
            self.positions[symbol] = {
                'shares': total_shares,
                'avg_price': new_avg_price
            }
        else:
            self.positions[symbol] = {
                'shares': shares,
                'avg_price': price
            }
    
    def remove_position(self, symbol: str, shares: float):
        """Remove from position."""
        if symbol in self.positions:
            self.positions[symbol]['shares'] -= shares
            if self.positions[symbol]['shares'] <= 0:
                del self.positions[symbol]
    
    def get_position(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get position for symbol."""
        return self.positions.get(symbol)
    
    def get_positions(self) -> Dict[str, Dict[str, float]]:
        """Get all positions."""
        return self.positions.copy()
    
    def get_total_value(self) -> float:
        """Get total portfolio value."""
        total = self.balance
        for symbol, position in self.positions.items():
            if symbol in self.prices:
                total += position['shares'] * self.prices[symbol]
        return total
    
    def get_total_pnl(self) -> float:
        """Get total P&L."""
        pnl = 0
        for symbol, position in self.positions.items():
            if symbol in self.prices:
                current_value = position['shares'] * self.prices[symbol]
                cost_basis = position['shares'] * position['avg_price']
                pnl += current_value - cost_basis
        return pnl
    
    def get_total_pnl_pct(self) -> float:
        """Get total P&L percentage."""
        total_value = self.get_total_value()
        return (total_value - self.initial_balance) / self.initial_balance if self.initial_balance > 0 else 0
    
    def get_state(self) -> Dict[str, Any]:
        """Get current portfolio state."""
        return {
            'balance': self.balance,
            'positions': self.positions.copy(),
            'prices': self.prices.copy(),
            'total_value': self.get_total_value(),
            'total_pnl': self.get_total_pnl(),
            'total_pnl_pct': self.get_total_pnl_pct()
        }
