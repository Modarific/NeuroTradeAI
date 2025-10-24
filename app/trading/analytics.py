"""
Performance analytics and reporting system.
Provides post-trade analysis, performance metrics, and report generation.
"""
import asyncio
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import statistics
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Report output formats."""
    JSON = "json"
    HTML = "html"
    CSV = "csv"


@dataclass
class TradeMetrics:
    """Trade performance metrics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_winner: float
    avg_loser: float
    profit_factor: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    avg_holding_time: float
    best_trade: float
    worst_trade: float


@dataclass
class PerformanceReport:
    """Performance report data."""
    session_id: str
    start_date: datetime
    end_date: datetime
    strategy: str
    mode: str
    initial_balance: float
    final_balance: float
    total_return: float
    total_return_pct: float
    trade_metrics: TradeMetrics
    daily_returns: List[float]
    equity_curve: List[Dict[str, Any]]
    trade_log: List[Dict[str, Any]]


class PerformanceAnalytics:
    """
    Performance analytics and reporting system.
    
    Features:
    - Trade analysis and metrics
    - Performance reporting
    - Risk analysis
    - Strategy comparison
    - Report generation (JSON, HTML, CSV)
    """
    
    def __init__(self, data_dir: str = "data/analytics"):
        """Initialize performance analytics."""
        self.data_dir = data_dir
        self.reports_dir = os.path.join(data_dir, "reports")
        
        # Create directories
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
    
    async def analyze_session(
        self,
        session_id: str,
        trades: List[Dict[str, Any]],
        positions: List[Dict[str, Any]],
        initial_balance: float,
        final_balance: float,
        start_date: datetime,
        end_date: datetime,
        strategy: str,
        mode: str
    ) -> PerformanceReport:
        """
        Analyze trading session performance.
        
        Args:
            session_id: Trading session ID
            trades: List of completed trades
            positions: List of current positions
            initial_balance: Starting balance
            final_balance: Ending balance
            start_date: Session start date
            end_date: Session end date
            strategy: Strategy used
            mode: Trading mode (paper/live)
            
        Returns:
            Performance report
        """
        try:
            # Calculate basic metrics
            total_return = final_balance - initial_balance
            total_return_pct = (total_return / initial_balance) * 100 if initial_balance > 0 else 0
            
            # Analyze trades
            trade_metrics = self._calculate_trade_metrics(trades)
            
            # Calculate daily returns
            daily_returns = self._calculate_daily_returns(trades, start_date, end_date)
            
            # Generate equity curve
            equity_curve = self._generate_equity_curve(trades, initial_balance, start_date, end_date)
            
            # Create performance report
            report = PerformanceReport(
                session_id=session_id,
                start_date=start_date,
                end_date=end_date,
                strategy=strategy,
                mode=mode,
                initial_balance=initial_balance,
                final_balance=final_balance,
                total_return=total_return,
                total_return_pct=total_return_pct,
                trade_metrics=trade_metrics,
                daily_returns=daily_returns,
                equity_curve=equity_curve,
                trade_log=trades
            )
            
            # Save report
            await self._save_report(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to analyze session: {e}")
            raise
    
    def _calculate_trade_metrics(self, trades: List[Dict[str, Any]]) -> TradeMetrics:
        """Calculate trade performance metrics."""
        if not trades:
            return TradeMetrics(
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0.0, avg_winner=0.0, avg_loser=0.0, profit_factor=0.0,
                total_pnl=0.0, max_drawdown=0.0, max_drawdown_pct=0.0,
                sharpe_ratio=0.0, avg_holding_time=0.0, best_trade=0.0, worst_trade=0.0
            )
        
        # Separate winning and losing trades
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
        
        total_trades = len(trades)
        winning_count = len(winning_trades)
        losing_count = len(losing_trades)
        win_rate = (winning_count / total_trades) * 100 if total_trades > 0 else 0
        
        # Calculate average winner/loser
        avg_winner = statistics.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loser = statistics.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # Calculate profit factor
        total_wins = sum(t['pnl'] for t in winning_trades)
        total_losses = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Calculate total P&L
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        
        # Calculate max drawdown
        max_drawdown, max_drawdown_pct = self._calculate_max_drawdown(trades)
        
        # Calculate Sharpe ratio
        returns = [t.get('pnl', 0) for t in trades]
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        
        # Calculate average holding time
        holding_times = []
        for trade in trades:
            if 'entry_time' in trade and 'exit_time' in trade:
                entry = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))
                exit = datetime.fromisoformat(trade['exit_time'].replace('Z', '+00:00'))
                holding_time = (exit - entry).total_seconds() / 3600  # hours
                holding_times.append(holding_time)
        
        avg_holding_time = statistics.mean(holding_times) if holding_times else 0
        
        # Best and worst trades
        pnls = [t.get('pnl', 0) for t in trades]
        best_trade = max(pnls) if pnls else 0
        worst_trade = min(pnls) if pnls else 0
        
        return TradeMetrics(
            total_trades=total_trades,
            winning_trades=winning_count,
            losing_trades=losing_count,
            win_rate=win_rate,
            avg_winner=avg_winner,
            avg_loser=avg_loser,
            profit_factor=profit_factor,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            avg_holding_time=avg_holding_time,
            best_trade=best_trade,
            worst_trade=worst_trade
        )
    
    def _calculate_max_drawdown(self, trades: List[Dict[str, Any]]) -> Tuple[float, float]:
        """Calculate maximum drawdown."""
        if not trades:
            return 0.0, 0.0
        
        # Calculate running balance
        running_balance = 0
        peak_balance = 0
        max_dd = 0
        max_dd_pct = 0
        
        for trade in trades:
            running_balance += trade.get('pnl', 0)
            if running_balance > peak_balance:
                peak_balance = running_balance
            
            drawdown = peak_balance - running_balance
            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_pct = (drawdown / peak_balance) * 100 if peak_balance > 0 else 0
        
        return max_dd, max_dd_pct
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        
        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        
        if std_return == 0:
            return 0.0
        
        # Assume risk-free rate of 0 for simplicity
        sharpe_ratio = mean_return / std_return
        return sharpe_ratio
    
    def _calculate_daily_returns(
        self,
        trades: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime
    ) -> List[float]:
        """Calculate daily returns."""
        daily_returns = []
        
        # Group trades by date
        trades_by_date = {}
        for trade in trades:
            if 'exit_time' in trade:
                trade_date = datetime.fromisoformat(
                    trade['exit_time'].replace('Z', '+00:00')
                ).date()
                if trade_date not in trades_by_date:
                    trades_by_date[trade_date] = []
                trades_by_date[trade_date].append(trade.get('pnl', 0))
        
        # Calculate daily returns
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            daily_pnl = sum(trades_by_date.get(current_date, []))
            daily_returns.append(daily_pnl)
            current_date += timedelta(days=1)
        
        return daily_returns
    
    def _generate_equity_curve(
        self,
        trades: List[Dict[str, Any]],
        initial_balance: float,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Generate equity curve data."""
        equity_curve = []
        running_balance = initial_balance
        
        # Sort trades by exit time
        sorted_trades = sorted(
            trades,
            key=lambda t: t.get('exit_time', ''),
            reverse=False
        )
        
        for trade in sorted_trades:
            if 'exit_time' in trade:
                running_balance += trade.get('pnl', 0)
                equity_curve.append({
                    'timestamp': trade['exit_time'],
                    'balance': running_balance,
                    'pnl': trade.get('pnl', 0)
                })
        
        return equity_curve
    
    async def _save_report(self, report: PerformanceReport):
        """Save performance report."""
        try:
            report_file = os.path.join(
                self.reports_dir,
                f"performance_report_{report.session_id}.json"
            )
            
            # Convert report to dictionary
            report_dict = {
                'session_id': report.session_id,
                'start_date': report.start_date.isoformat(),
                'end_date': report.end_date.isoformat(),
                'strategy': report.strategy,
                'mode': report.mode,
                'initial_balance': report.initial_balance,
                'final_balance': report.final_balance,
                'total_return': report.total_return,
                'total_return_pct': report.total_return_pct,
                'trade_metrics': {
                    'total_trades': report.trade_metrics.total_trades,
                    'winning_trades': report.trade_metrics.winning_trades,
                    'losing_trades': report.trade_metrics.losing_trades,
                    'win_rate': report.trade_metrics.win_rate,
                    'avg_winner': report.trade_metrics.avg_winner,
                    'avg_loser': report.trade_metrics.avg_loser,
                    'profit_factor': report.trade_metrics.profit_factor,
                    'total_pnl': report.trade_metrics.total_pnl,
                    'max_drawdown': report.trade_metrics.max_drawdown,
                    'max_drawdown_pct': report.trade_metrics.max_drawdown_pct,
                    'sharpe_ratio': report.trade_metrics.sharpe_ratio,
                    'avg_holding_time': report.trade_metrics.avg_holding_time,
                    'best_trade': report.trade_metrics.best_trade,
                    'worst_trade': report.trade_metrics.worst_trade
                },
                'daily_returns': report.daily_returns,
                'equity_curve': report.equity_curve,
                'trade_log': report.trade_log
            }
            
            with open(report_file, 'w') as f:
                json.dump(report_dict, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            raise
    
    async def generate_html_report(self, report: PerformanceReport) -> str:
        """Generate HTML performance report."""
        try:
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Trading Performance Report</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                    .metric-card {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; }}
                    .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
                    .metric-label {{ font-size: 14px; color: #666; }}
                    .positive {{ color: #28a745; }}
                    .negative {{ color: #dc3545; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                    th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                    th {{ background-color: #f0f0f0; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Trading Performance Report</h1>
                    <p><strong>Session ID:</strong> {session_id}</p>
                    <p><strong>Strategy:</strong> {strategy}</p>
                    <p><strong>Mode:</strong> {mode}</p>
                    <p><strong>Period:</strong> {start_date} to {end_date}</p>
                </div>
                
                <div class="metrics">
                    <div class="metric-card">
                        <div class="metric-value {return_class}">{total_return_pct:.2f}%</div>
                        <div class="metric-label">Total Return</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{total_trades}</div>
                        <div class="metric-label">Total Trades</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{win_rate:.1f}%</div>
                        <div class="metric-label">Win Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{profit_factor:.2f}</div>
                        <div class="metric-label">Profit Factor</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value {sharpe_class}">{sharpe_ratio:.2f}</div>
                        <div class="metric-label">Sharpe Ratio</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value negative">{max_drawdown_pct:.2f}%</div>
                        <div class="metric-label">Max Drawdown</div>
                    </div>
                </div>
                
                <h2>Trade Summary</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Initial Balance</td><td>${initial_balance:,.2f}</td></tr>
                    <tr><td>Final Balance</td><td>${final_balance:,.2f}</td></tr>
                    <tr><td>Total P&L</td><td class="{return_class}">${total_return:,.2f}</td></tr>
                    <tr><td>Winning Trades</td><td>{winning_trades}</td></tr>
                    <tr><td>Losing Trades</td><td>{losing_trades}</td></tr>
                    <tr><td>Average Winner</td><td>${avg_winner:,.2f}</td></tr>
                    <tr><td>Average Loser</td><td>${avg_loser:,.2f}</td></tr>
                    <tr><td>Best Trade</td><td class="positive">${best_trade:,.2f}</td></tr>
                    <tr><td>Worst Trade</td><td class="negative">${worst_trade:,.2f}</td></tr>
                    <tr><td>Avg Holding Time</td><td>{avg_holding_time:.1f} hours</td></tr>
                </table>
            </body>
            </html>
            """
            
            # Determine CSS classes
            return_class = "positive" if report.total_return_pct > 0 else "negative"
            sharpe_class = "positive" if report.trade_metrics.sharpe_ratio > 1 else "negative"
            
            html_content = html_template.format(
                session_id=report.session_id,
                strategy=report.strategy,
                mode=report.mode,
                start_date=report.start_date.strftime("%Y-%m-%d %H:%M:%S"),
                end_date=report.end_date.strftime("%Y-%m-%d %H:%M:%S"),
                total_return_pct=report.total_return_pct,
                return_class=return_class,
                total_trades=report.trade_metrics.total_trades,
                win_rate=report.trade_metrics.win_rate,
                profit_factor=report.trade_metrics.profit_factor,
                sharpe_ratio=report.trade_metrics.sharpe_ratio,
                sharpe_class=sharpe_class,
                max_drawdown_pct=report.trade_metrics.max_drawdown_pct,
                initial_balance=report.initial_balance,
                final_balance=report.final_balance,
                total_return=report.total_return,
                winning_trades=report.trade_metrics.winning_trades,
                losing_trades=report.trade_metrics.losing_trades,
                avg_winner=report.trade_metrics.avg_winner,
                avg_loser=report.trade_metrics.avg_loser,
                best_trade=report.trade_metrics.best_trade,
                worst_trade=report.trade_metrics.worst_trade,
                avg_holding_time=report.trade_metrics.avg_holding_time
            )
            
            return html_content
            
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {e}")
            raise
    
    async def generate_csv_report(self, report: PerformanceReport) -> str:
        """Generate CSV performance report."""
        try:
            csv_content = f"""Session ID,{report.session_id}
Strategy,{report.strategy}
Mode,{report.mode}
Start Date,{report.start_date.isoformat()}
End Date,{report.end_date.isoformat()}
Initial Balance,{report.initial_balance}
Final Balance,{report.final_balance}
Total Return,{report.total_return}
Total Return %,{report.total_return_pct}
Total Trades,{report.trade_metrics.total_trades}
Winning Trades,{report.trade_metrics.winning_trades}
Losing Trades,{report.trade_metrics.losing_trades}
Win Rate,{report.trade_metrics.win_rate}
Average Winner,{report.trade_metrics.avg_winner}
Average Loser,{report.trade_metrics.avg_loser}
Profit Factor,{report.trade_metrics.profit_factor}
Total P&L,{report.trade_metrics.total_pnl}
Max Drawdown,{report.trade_metrics.max_drawdown}
Max Drawdown %,{report.trade_metrics.max_drawdown_pct}
Sharpe Ratio,{report.trade_metrics.sharpe_ratio}
Average Holding Time,{report.trade_metrics.avg_holding_time}
Best Trade,{report.trade_metrics.best_trade}
Worst Trade,{report.trade_metrics.worst_trade}
"""
            return csv_content
            
        except Exception as e:
            logger.error(f"Failed to generate CSV report: {e}")
            raise
    
    async def compare_strategies(
        self,
        strategy_reports: List[PerformanceReport]
    ) -> Dict[str, Any]:
        """Compare multiple strategy performances."""
        try:
            comparison = {
                'strategies': [],
                'best_performer': None,
                'worst_performer': None,
                'summary': {}
            }
            
            for report in strategy_reports:
                strategy_data = {
                    'strategy': report.strategy,
                    'total_return_pct': report.total_return_pct,
                    'sharpe_ratio': report.trade_metrics.sharpe_ratio,
                    'max_drawdown_pct': report.trade_metrics.max_drawdown_pct,
                    'win_rate': report.trade_metrics.win_rate,
                    'profit_factor': report.trade_metrics.profit_factor,
                    'total_trades': report.trade_metrics.total_trades
                }
                comparison['strategies'].append(strategy_data)
            
            # Find best and worst performers
            if strategy_reports:
                best = max(strategy_reports, key=lambda r: r.total_return_pct)
                worst = min(strategy_reports, key=lambda r: r.total_return_pct)
                
                comparison['best_performer'] = best.strategy
                comparison['worst_performer'] = worst.strategy
                
                # Calculate summary statistics
                returns = [r.total_return_pct for r in strategy_reports]
                comparison['summary'] = {
                    'avg_return': statistics.mean(returns),
                    'median_return': statistics.median(returns),
                    'std_return': statistics.stdev(returns) if len(returns) > 1 else 0,
                    'min_return': min(returns),
                    'max_return': max(returns)
                }
            
            return comparison
            
        except Exception as e:
            logger.error(f"Failed to compare strategies: {e}")
            raise
