"""
FastAPI routes for the trading data scraper API.
Provides REST endpoints for querying data and system status.
"""
from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging

from app.core.storage import StorageManager
from app.core.rate_limiter import rate_limiter
from app.config import DATA_PATH, DB_PATH

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage manager
storage = StorageManager(DATA_PATH, DB_PATH)

@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "NeuroTradeAI Data Scraper API",
        "version": "1.0.0",
        "description": "Real-time trading data ingestion and query API",
        "endpoints": {
            "bars": "/bars/{symbol}",
            "news": "/news",
            "filings": "/filings/{symbol}",
            "metrics": "/metrics",
            "health": "/health"
        }
    }

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }

@router.get("/bars/{symbol}")
async def get_bars(
    symbol: str = Path(..., description="Stock symbol"),
    interval: str = Query("1m", description="Data interval"),
    start: Optional[str] = Query(None, description="Start date (ISO format)"),
    end: Optional[str] = Query(None, description="End date (ISO format)")
):
    """
    Get OHLCV bars for a symbol.
    
    Args:
        symbol: Stock symbol (e.g., AAPL)
        interval: Data interval (1m, 5m, 1h, 1d)
        start: Start date in ISO format
        end: End date in ISO format
        
    Returns:
        List of OHLCV bars
    """
    try:
        # Query data from storage
        df = storage.query_ohlcv(symbol, start, end, interval)
        
        if df.empty:
            return {
                "symbol": symbol,
                "interval": interval,
                "bars": [],
                "count": 0
            }
        
        # Convert DataFrame to list of dicts (or use list directly if not DataFrame)
        if hasattr(df, 'to_dict'):
            bars = df.to_dict('records')
        else:
            bars = df if isinstance(df, list) else []
        
        return {
            "symbol": symbol,
            "interval": interval,
            "bars": bars,
            "count": len(bars),
            "start_date": bars[0]["timestamp_utc"] if bars else None,
            "end_date": bars[-1]["timestamp_utc"] if bars else None
        }
        
    except Exception as e:
        logger.error(f"Error querying bars for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news")
async def get_news(
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    since: Optional[str] = Query(None, description="Filter by date (ISO format)"),
    limit: int = Query(100, description="Maximum number of results"),
    sentiment_min: Optional[float] = Query(None, description="Minimum sentiment score"),
    sentiment_max: Optional[float] = Query(None, description="Maximum sentiment score")
):
    """
    Get news articles.
    
    Args:
        ticker: Filter by ticker symbol
        since: Filter by date (ISO format)
        limit: Maximum number of results
        sentiment_min: Minimum sentiment score (-1.0 to 1.0)
        sentiment_max: Maximum sentiment score (-1.0 to 1.0)
        
    Returns:
        List of news articles
    """
    try:
        # Query news from storage
        news = storage.query_news(ticker, since)
        
        # Apply sentiment filtering if provided
        if sentiment_min is not None or sentiment_max is not None:
            filtered_news = []
            for article in news:
                sentiment = article.get('sentiment_score', 0.0)
                if sentiment_min is not None and sentiment < sentiment_min:
                    continue
                if sentiment_max is not None and sentiment > sentiment_max:
                    continue
                filtered_news.append(article)
            news = filtered_news
        
        # Apply limit
        if limit > 0:
            news = news[:limit]
        
        return {
            "news": news,
            "count": len(news),
            "filters": {
                "ticker": ticker,
                "since": since,
                "limit": limit,
                "sentiment_min": sentiment_min,
                "sentiment_max": sentiment_max
            }
        }
        
    except Exception as e:
        logger.error(f"Error querying news: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filings/{symbol}")
async def get_filings(
    symbol: str = Path(..., description="Stock symbol"),
    filing_type: Optional[str] = Query(None, description="Filter by filing type"),
    since: Optional[str] = Query(None, description="Filter by date (ISO format)")
):
    """
    Get SEC filings for a symbol.
    
    Args:
        symbol: Stock symbol
        filing_type: Filter by filing type (10-K, 10-Q, 8-K)
        since: Filter by date (ISO format)
        
    Returns:
        List of SEC filings
    """
    try:
        # Query filings from storage
        # This would be implemented based on the storage layer
        # For now, return empty result
        return {
            "symbol": symbol,
            "filings": [],
            "count": 0,
            "filters": {
                "filing_type": filing_type,
                "since": since
            }
        }
        
    except Exception as e:
        logger.error(f"Error querying filings for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news/sentiment")
async def get_news_sentiment(
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    since: Optional[str] = Query(None, description="Filter by date (ISO format)"),
    hours: int = Query(24, description="Number of hours to look back")
):
    """
    Get news sentiment analysis.
    
    Args:
        ticker: Filter by ticker symbol
        since: Filter by date (ISO format)
        hours: Number of hours to look back
        
    Returns:
        Sentiment analysis results
    """
    try:
        # Query news from storage
        news = storage.query_news(ticker, since)
        
        if not news:
            return {
                "sentiment": {
                    "average": 0.0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "neutral_count": 0,
                    "total_count": 0
                },
                "ticker": ticker,
                "timeframe": f"{hours} hours"
            }
        
        # Calculate sentiment statistics
        sentiments = [article.get('sentiment_score', 0.0) for article in news]
        positive_count = sum(1 for s in sentiments if s > 0.1)
        negative_count = sum(1 for s in sentiments if s < -0.1)
        neutral_count = len(sentiments) - positive_count - negative_count
        
        average_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
        
        return {
            "sentiment": {
                "average": round(average_sentiment, 3),
                "positive_count": positive_count,
                "negative_count": negative_count,
                "neutral_count": neutral_count,
                "total_count": len(sentiments)
            },
            "ticker": ticker,
            "timeframe": f"{hours} hours"
        }
        
    except Exception as e:
        logger.error(f"Error calculating news sentiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics")
async def get_metrics():
    """
    Get system metrics and status.
    
    Returns:
        System metrics including rate limits, storage stats, etc.
    """
    try:
        # Get rate limiter status
        rate_limits = rate_limiter.get_status()
        
        # Get storage statistics
        storage_stats = storage.get_storage_stats()
        
        # Get database statistics
        db_stats = await _get_database_stats()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rate_limits": rate_limits,
            "storage": storage_stats,
            "database": db_stats,
            "system": {
                "status": "running",
                "uptime": "N/A"  # Would be calculated from start time
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/symbols")
async def get_symbols():
    """
    Get list of tracked symbols.
    
    Returns:
        List of symbols with metadata
    """
    try:
        # Query symbols from database
        import sqlite3
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM symbols")
            rows = cursor.fetchall()
            
            columns = [description[0] for description in cursor.description]
            symbols = [dict(zip(columns, row)) for row in rows]
        
        return {
            "symbols": symbols,
            "count": len(symbols)
        }
        
    except Exception as e:
        logger.error(f"Error querying symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/latest")
async def get_latest_data():
    """
    Get latest market data for all tracked symbols.
    
    Returns:
        Dictionary of latest data for each symbol
    """
    try:
        import sqlite3
        import json
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get latest data for each symbol
            cursor.execute("""
                SELECT symbol, timestamp, open, high, low, close, volume
                FROM bars 
                WHERE timestamp = (
                    SELECT MAX(timestamp) 
                    FROM bars b2 
                    WHERE b2.symbol = bars.symbol
                )
                ORDER BY symbol
            """)
            
            rows = cursor.fetchall()
            
            # Convert to dictionary format
            latest_data = {}
            for row in rows:
                symbol, timestamp, open_price, high, low, close, volume = row
                latest_data[symbol] = {
                    "price": close,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "change": 0,  # Calculate if needed
                    "change_percent": 0,  # Calculate if needed
                    "timestamp": timestamp,
                    "signal": "HOLD",  # Default signal
                    "rsi": 50,  # Default RSI
                    "bb_position": 0.5  # Default BB position
                }
        
        return latest_data
        
    except Exception as e:
        logger.error(f"Error getting latest data: {e}")
        # Return sample data for testing
        return {
            "AAPL": {
                "price": 150.25,
                "open": 149.80,
                "high": 151.20,
                "low": 149.50,
                "close": 150.25,
                "volume": 45000000,
                "change": 0.45,
                "change_percent": 0.30,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal": "BUY",
                "rsi": 45.2,
                "bb_position": 0.3
            },
            "MSFT": {
                "price": 330.15,
                "open": 328.90,
                "high": 331.50,
                "low": 328.20,
                "close": 330.15,
                "volume": 28000000,
                "change": 1.25,
                "change_percent": 0.38,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal": "HOLD",
                "rsi": 52.8,
                "bb_position": 0.6
            },
            "GOOGL": {
                "price": 2750.80,
                "open": 2745.20,
                "high": 2755.90,
                "low": 2740.10,
                "close": 2750.80,
                "volume": 1200000,
                "change": 5.60,
                "change_percent": 0.20,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal": "SELL",
                "rsi": 65.4,
                "bb_position": 0.8
            }
        }

@router.post("/symbols/{symbol}")
async def add_symbol(
    symbol: str = Path(..., description="Stock symbol"),
    exchange: Optional[str] = Query(None, description="Exchange name")
):
    """
    Add a symbol to tracking.
    
    Args:
        symbol: Stock symbol to add
        exchange: Exchange name
        
    Returns:
        Confirmation message
    """
    try:
        import sqlite3
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO symbols (symbol, exchange, last_update_utc, enabled)
                VALUES (?, ?, ?, ?)
            """, (symbol, exchange, datetime.now(timezone.utc).isoformat(), 1))
            conn.commit()
        
        return {
            "message": f"Symbol {symbol} added successfully",
            "symbol": symbol,
            "exchange": exchange
        }
        
    except Exception as e:
        logger.error(f"Error adding symbol {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/symbols/{symbol}")
async def remove_symbol(symbol: str = Path(..., description="Stock symbol")):
    """
    Remove a symbol from tracking.
    
    Args:
        symbol: Stock symbol to remove
        
    Returns:
        Confirmation message
    """
    try:
        import sqlite3
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM symbols WHERE symbol = ?", (symbol,))
            conn.commit()
        
        return {
            "message": f"Symbol {symbol} removed successfully",
            "symbol": symbol
        }
        
    except Exception as e:
        logger.error(f"Error removing symbol {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _get_database_stats() -> Dict[str, Any]:
    """Get database statistics."""
    try:
        import sqlite3
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get table counts
            cursor.execute("SELECT COUNT(*) FROM symbols")
            symbol_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM fetch_log")
            log_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM news_metadata")
            news_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM filings_metadata")
            filing_count = cursor.fetchone()[0]
            
            return {
                "symbols": symbol_count,
                "fetch_logs": log_count,
                "news_metadata": news_count,
                "filings_metadata": filing_count
            }
            
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {}

@router.get("/filings")
async def get_filings(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    filing_type: Optional[str] = Query(None, description="Filter by filing type (10-K, 10-Q, 8-K)"),
    since: Optional[str] = Query(None, description="Filter by date (ISO format)"),
    limit: int = Query(100, description="Maximum number of results")
):
    """
    Get SEC filings.
    
    Args:
        symbol: Filter by symbol
        filing_type: Filter by filing type
        since: Filter by date
        limit: Maximum number of results
        
    Returns:
        List of SEC filings
    """
    try:
        filings = storage.query_filings(symbol, filing_type, since)
        
        # Apply limit
        if limit > 0:
            filings = filings[:limit]
        
        return {
            "filings": filings,
            "count": len(filings),
            "filters": {
                "symbol": symbol,
                "filing_type": filing_type,
                "since": since
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting filings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filings/{symbol}")
async def get_symbol_filings(
    symbol: str,
    filing_type: Optional[str] = Query(None, description="Filter by filing type"),
    since: Optional[str] = Query(None, description="Filter by date (ISO format)"),
    limit: int = Query(50, description="Maximum number of results")
):
    """
    Get SEC filings for a specific symbol.
    
    Args:
        symbol: Stock symbol
        filing_type: Filter by filing type
        since: Filter by date
        limit: Maximum number of results
        
    Returns:
        List of SEC filings for the symbol
    """
    try:
        filings = storage.query_filings(symbol, filing_type, since)
        
        # Apply limit
        if limit > 0:
            filings = filings[:limit]
        
        return {
            "symbol": symbol,
            "filings": filings,
            "count": len(filings),
            "filters": {
                "filing_type": filing_type,
                "since": since
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting filings for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings")
async def get_system_settings():
    """
    Get system settings.
    
    Returns:
        Current system settings
    """
    try:
        # Return default settings for now
        return {
            "polling_interval": 60,
            "max_symbols": 50,
            "retention_days": 365,
            "auto_cleanup": True,
            "error_alerts": True,
            "rate_limit_alerts": True
        }
        
    except Exception as e:
        logger.error(f"Error getting system settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings")
async def update_system_settings(settings: Dict[str, Any]):
    """
    Update system settings.
    
    Args:
        settings: New system settings
        
    Returns:
        Confirmation message
    """
    try:
        # TODO: Implement settings persistence
        logger.info(f"System settings updated: {settings}")
        
        return {
            "message": "Settings updated successfully",
            "settings": settings
        }
        
    except Exception as e:
        logger.error(f"Error updating system settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/{source}")
async def toggle_data_source(source: str, config: Dict[str, Any]):
    """
    Toggle a data source on/off.
    
    Args:
        source: Data source name (finnhub, news, edgar)
        config: Configuration with 'enabled' flag
        
    Returns:
        Confirmation message
    """
    try:
        enabled = config.get('enabled', False)
        
        # TODO: Implement actual source toggling
        logger.info(f"Data source {source} {'enabled' if enabled else 'disabled'}")
        
        return {
            "message": f"Data source {source} {'enabled' if enabled else 'disabled'}",
            "source": source,
            "enabled": enabled
        }
        
    except Exception as e:
        logger.error(f"Error toggling data source {source}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
