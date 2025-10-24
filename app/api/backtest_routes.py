"""
Backtesting API routes.
REST endpoints for running and managing backtests.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging
import uuid

from app.backtesting.data_loader import BacktestDataLoader
from app.backtesting.vectorized_engine import VectorizedBacktestEngine
from app.backtesting.event_driven_engine import EventDrivenBacktestEngine
from app.core.storage import StorageManager
from app.trading.strategies.base import BaseStrategy
from app.trading.strategies.mean_reversion import MeanReversionStrategy
from app.trading.strategies.momentum import MomentumStrategy
from app.trading.strategies.news_driven import NewsDrivenStrategy

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/backtest", tags=["backtesting"])

# Global backtest storage (in production, use database)
backtest_results = {}
running_backtests = {}


class BacktestRequest(BaseModel):
    """Backtest request model."""
    strategy_name: str = Field(..., description="Strategy name")
    symbols: List[str] = Field(..., description="List of symbols to trade")
    start_date: str = Field(..., description="Start date (ISO format)")
    end_date: str = Field(..., description="End date (ISO format)")
    initial_balance: float = Field(100000.0, description="Initial balance")
    commission: float = Field(0.0, description="Commission per trade")
    slippage: float = Field(0.001, description="Slippage factor")
    engine_type: str = Field("vectorized", description="Engine type: vectorized or event_driven")
    include_news: bool = Field(True, description="Include news data")
    include_filings: bool = Field(True, description="Include filings data")
    strategy_params: Optional[Dict[str, Any]] = Field(None, description="Strategy parameters")


class BacktestResponse(BaseModel):
    """Backtest response model."""
    backtest_id: str
    status: str
    message: str
    results: Optional[Dict[str, Any]] = None


class BacktestStatus(BaseModel):
    """Backtest status model."""
    backtest_id: str
    status: str
    progress: float
    message: str
    created_at: str
    completed_at: Optional[str] = None


def get_strategy(strategy_name: str, params: Optional[Dict[str, Any]] = None) -> BaseStrategy:
    """Get strategy instance by name."""
    try:
        if strategy_name == "mean_reversion":
            return MeanReversionStrategy(params or {})
        elif strategy_name == "momentum":
            return MomentumStrategy(params or {})
        elif strategy_name == "news_driven":
            return NewsDrivenStrategy(params or {})
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
    except Exception as e:
        logger.error(f"Error creating strategy {strategy_name}: {e}")
        raise HTTPException(status_code=400, detail=f"Error creating strategy: {e}")


def get_storage_manager() -> StorageManager:
    """Get storage manager instance."""
    try:
        return StorageManager("data", "data/trading.db")
    except Exception as e:
        logger.error(f"Error creating storage manager: {e}")
        raise HTTPException(status_code=500, detail="Error initializing storage manager")


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    storage_manager: StorageManager = Depends(get_storage_manager)
):
    """
    Run a new backtest.
    
    Args:
        request: Backtest configuration
        background_tasks: FastAPI background tasks
        storage_manager: Storage manager instance
        
    Returns:
        Backtest response with ID and status
    """
    try:
        # Generate backtest ID
        backtest_id = str(uuid.uuid4())
        
        # Parse dates
        start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        
        # Validate dates
        if start_date >= end_date:
            raise HTTPException(status_code=400, detail="Start date must be before end date")
        
        # Create strategy
        strategy = get_strategy(request.strategy_name, request.strategy_params)
        
        # Initialize backtest status
        backtest_status = BacktestStatus(
            backtest_id=backtest_id,
            status="queued",
            progress=0.0,
            message="Backtest queued for execution",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Store status
        backtest_results[backtest_id] = backtest_status
        running_backtests[backtest_id] = True
        
        # Start background task
        background_tasks.add_task(
            execute_backtest,
            backtest_id=backtest_id,
            request=request,
            start_date=start_date,
            end_date=end_date,
            strategy=strategy,
            storage_manager=storage_manager
        )
        
        logger.info(f"Started backtest {backtest_id} for strategy {request.strategy_name}")
        
        return BacktestResponse(
            backtest_id=backtest_id,
            status="queued",
            message="Backtest started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting backtest: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting backtest: {e}")


async def execute_backtest(
    backtest_id: str,
    request: BacktestRequest,
    start_date: datetime,
    end_date: datetime,
    strategy: BaseStrategy,
    storage_manager: StorageManager
):
    """Execute backtest in background."""
    try:
        # Update status
        backtest_results[backtest_id].status = "running"
        backtest_results[backtest_id].progress = 10.0
        backtest_results[backtest_id].message = "Loading data..."
        
        # Create data loader
        data_loader = BacktestDataLoader(storage_manager)
        
        # Update progress
        backtest_results[backtest_id].progress = 30.0
        backtest_results[backtest_id].message = "Running backtest..."
        
        # Run backtest
        if request.engine_type == "vectorized":
            engine = VectorizedBacktestEngine(data_loader)
        else:
            engine = EventDrivenBacktestEngine(data_loader)
        
        results = engine.run_backtest(
            strategy=strategy,
            symbols=request.symbols,
            start_date=start_date,
            end_date=end_date,
            initial_balance=request.initial_balance,
            commission=request.commission,
            slippage=request.slippage,
            include_news=request.include_news,
            include_filings=request.include_filings
        )
        
        # Update status
        backtest_results[backtest_id].status = "completed"
        backtest_results[backtest_id].progress = 100.0
        backtest_results[backtest_id].message = "Backtest completed successfully"
        backtest_results[backtest_id].completed_at = datetime.now(timezone.utc).isoformat()
        backtest_results[backtest_id].results = results
        
        # Remove from running
        if backtest_id in running_backtests:
            del running_backtests[backtest_id]
        
        logger.info(f"Backtest {backtest_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error executing backtest {backtest_id}: {e}")
        
        # Update status with error
        backtest_results[backtest_id].status = "failed"
        backtest_results[backtest_id].message = f"Backtest failed: {str(e)}"
        backtest_results[backtest_id].completed_at = datetime.now(timezone.utc).isoformat()
        
        # Remove from running
        if backtest_id in running_backtests:
            del running_backtests[backtest_id]


@router.get("/status/{backtest_id}", response_model=BacktestStatus)
async def get_backtest_status(backtest_id: str):
    """
    Get backtest status.
    
    Args:
        backtest_id: Backtest ID
        
    Returns:
        Backtest status
    """
    if backtest_id not in backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    return backtest_results[backtest_id]


@router.get("/results/{backtest_id}")
async def get_backtest_results(backtest_id: str):
    """
    Get backtest results.
    
    Args:
        backtest_id: Backtest ID
        
    Returns:
        Backtest results
    """
    if backtest_id not in backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    backtest = backtest_results[backtest_id]
    
    if backtest.status != "completed":
        raise HTTPException(status_code=400, detail="Backtest not completed")
    
    if not backtest.results:
        raise HTTPException(status_code=500, detail="No results available")
    
    return backtest.results


@router.get("/list")
async def list_backtests(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None
):
    """
    List backtests.
    
    Args:
        limit: Maximum number of backtests to return
        offset: Number of backtests to skip
        status: Filter by status
        
    Returns:
        List of backtests
    """
    try:
        # Filter backtests
        filtered_backtests = list(backtest_results.values())
        
        if status:
            filtered_backtests = [bt for bt in filtered_backtests if bt.status == status]
        
        # Sort by creation date (newest first)
        filtered_backtests.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        start = offset
        end = offset + limit
        paginated_backtests = filtered_backtests[start:end]
        
        return {
            "backtests": paginated_backtests,
            "total": len(filtered_backtests),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error listing backtests: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing backtests: {e}")


@router.delete("/{backtest_id}")
async def delete_backtest(backtest_id: str):
    """
    Delete a backtest.
    
    Args:
        backtest_id: Backtest ID
        
    Returns:
        Success message
    """
    if backtest_id not in backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    # Check if running
    if backtest_id in running_backtests:
        raise HTTPException(status_code=400, detail="Cannot delete running backtest")
    
    # Delete backtest
    del backtest_results[backtest_id]
    
    logger.info(f"Deleted backtest {backtest_id}")
    
    return {"message": "Backtest deleted successfully"}


@router.get("/strategies")
async def get_available_strategies():
    """
    Get available strategies.
    
    Returns:
        List of available strategies
    """
    strategies = [
        {
            "name": "mean_reversion",
            "display_name": "Mean Reversion",
            "description": "Trades on price reversals using RSI and Bollinger Bands",
            "parameters": {
                "rsi_oversold": {"type": "float", "default": 30, "min": 10, "max": 50},
                "rsi_overbought": {"type": "float", "default": 70, "min": 50, "max": 90},
                "bb_touch_threshold": {"type": "float", "default": 0.02, "min": 0.01, "max": 0.1}
            }
        },
        {
            "name": "momentum",
            "display_name": "Momentum Breakout",
            "description": "Trades on momentum breakouts using moving averages",
            "parameters": {
                "sma_period": {"type": "int", "default": 20, "min": 5, "max": 100},
                "volume_threshold": {"type": "float", "default": 1.5, "min": 1.0, "max": 5.0}
            }
        },
        {
            "name": "news_driven",
            "display_name": "News Driven",
            "description": "Trades based on news sentiment and price movement",
            "parameters": {
                "sentiment_threshold": {"type": "float", "default": 0.7, "min": 0.5, "max": 1.0},
                "price_change_threshold": {"type": "float", "default": 0.02, "min": 0.01, "max": 0.1}
            }
        }
    ]
    
    return {"strategies": strategies}


@router.get("/metrics/{backtest_id}")
async def get_backtest_metrics(backtest_id: str):
    """
    Get backtest performance metrics.
    
    Args:
        backtest_id: Backtest ID
        
    Returns:
        Performance metrics
    """
    if backtest_id not in backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    backtest = backtest_results[backtest_id]
    
    if backtest.status != "completed" or not backtest.results:
        raise HTTPException(status_code=400, detail="Backtest not completed or no results")
    
    try:
        results = backtest.results
        
        # Extract metrics
        metrics = {}
        
        if 'combined_metrics' in results:
            metrics.update(results['combined_metrics'])
        
        # Add symbol-specific metrics
        if 'symbol_results' in results:
            symbol_metrics = {}
            for symbol, symbol_result in results['symbol_results'].items():
                if 'metrics' in symbol_result:
                    symbol_metrics[symbol] = symbol_result['metrics']
            metrics['symbol_metrics'] = symbol_metrics
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting metrics for backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting metrics: {e}")


@router.post("/export/{backtest_id}")
async def export_backtest_results(
    backtest_id: str,
    format: str = "json"
):
    """
    Export backtest results.
    
    Args:
        backtest_id: Backtest ID
        format: Export format (json, csv)
        
    Returns:
        Exported data
    """
    if backtest_id not in backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    backtest = backtest_results[backtest_id]
    
    if backtest.status != "completed" or not backtest.results:
        raise HTTPException(status_code=400, detail="Backtest not completed or no results")
    
    try:
        # Create appropriate engine for export
        storage_manager = StorageManager()
        data_loader = BacktestDataLoader(storage_manager)
        
        if format == "json":
            import json
            return json.dumps(backtest.results, indent=2, default=str)
        elif format == "csv":
            # Export portfolio data as CSV
            import pandas as pd
            
            csv_data = []
            if 'symbol_results' in backtest.results:
                for symbol, symbol_result in backtest.results['symbol_results'].items():
                    if 'portfolio' in symbol_result and not symbol_result['portfolio'].empty:
                        portfolio_df = symbol_result['portfolio']
                        portfolio_df['symbol'] = symbol
                        csv_data.append(portfolio_df)
            
            if csv_data:
                combined_df = pd.concat(csv_data, ignore_index=True)
                return combined_df.to_csv(index=False)
            else:
                return "No portfolio data to export"
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
            
    except Exception as e:
        logger.error(f"Error exporting backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting results: {e}")
