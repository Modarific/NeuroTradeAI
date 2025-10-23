"""
Simplified storage layer using JSON files instead of Parquet.
This avoids pandas/pyarrow compilation issues on Windows.
"""
import os
import json
import gzip
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SimpleStorageManager:
    """Simplified storage manager using JSON files."""
    
    def __init__(self, data_path: str, db_path: str):
        self.data_path = data_path
        self.db_path = db_path
        self._init_directories()
    
    def _init_directories(self):
        """Create necessary directories."""
        directories = [
            os.path.join(self.data_path, "ohlcv", "1m"),
            os.path.join(self.data_path, "news"),
            os.path.join(self.data_path, "filings"),
            os.path.dirname(self.db_path)
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables."""
        try:
            import sqlite3
            
            # Ensure database directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Symbols table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS symbols (
                        symbol TEXT PRIMARY KEY,
                        exchange TEXT,
                        last_update_utc TEXT,
                        enabled INTEGER DEFAULT 1
                    )
                """)
                
                # Fetch log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fetch_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT,
                        endpoint TEXT,
                        status_code INTEGER,
                        timestamp_utc TEXT,
                        error TEXT
                    )
                """)
                
                # File manifest table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_manifest (
                        path TEXT PRIMARY KEY,
                        record_count INTEGER,
                        start_ts TEXT,
                        end_ts TEXT,
                        created_utc TEXT
                    )
                """)
                
                # News table for metadata
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS news_metadata (
                        id TEXT PRIMARY KEY,
                        timestamp_utc TEXT,
                        source TEXT,
                        headline TEXT,
                        url TEXT,
                        tickers TEXT,
                        sentiment_score REAL,
                        file_path TEXT
                    )
                """)
                
                # Filings table for metadata
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS filings_metadata (
                        symbol TEXT,
                        filing_type TEXT,
                        filing_date TEXT,
                        url TEXT,
                        summary TEXT,
                        file_path TEXT,
                        PRIMARY KEY (symbol, filing_date, filing_type)
                    )
                """)
                
                conn.commit()
                logger.info("Database tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            # Continue without database if it fails
    
    def store_ohlcv(self, data: List[Dict[str, Any]]) -> bool:
        """Store OHLCV data in JSON format."""
        if not data:
            return True
        
        try:
            # Group by symbol and date
            for record in data:
                symbol = record.get('symbol', 'UNKNOWN')
                timestamp = record.get('timestamp_utc', '')
                
                if timestamp:
                    # Extract date for file organization
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        date_str = dt.strftime('%Y-%m-%d')
                    except:
                        date_str = datetime.now().strftime('%Y-%m-%d')
                else:
                    date_str = datetime.now().strftime('%Y-%m-%d')
                
                # Create file path
                file_path = os.path.join(
                    self.data_path, "ohlcv", "1m", symbol, f"{date_str}.json"
                )
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Load existing data or create new
                existing_data = []
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as f:
                            existing_data = json.load(f)
                    except:
                        existing_data = []
                
                # Add new record
                existing_data.append(record)
                
                # Save updated data
                with open(file_path, 'w') as f:
                    json.dump(existing_data, f, indent=2)
                
                # Update symbol metadata in database
                self._update_symbol_metadata(symbol, timestamp)
            
            logger.info(f"Stored {len(data)} OHLCV records")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store OHLCV data: {e}")
            return False
    
    def _update_symbol_metadata(self, symbol: str, timestamp: str):
        """Update symbol metadata in database."""
        try:
            import sqlite3
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO symbols (symbol, last_update_utc, enabled)
                    VALUES (?, ?, 1)
                """, (symbol, timestamp))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating symbol metadata: {e}")
    
    def store_news(self, data: List[Dict[str, Any]]) -> bool:
        """Store news data in JSON format."""
        if not data:
            return True
        
        try:
            for record in data:
                timestamp = record.get('timestamp_utc', '')
                
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        month_key = dt.strftime('%Y-%m')
                    except:
                        month_key = datetime.now().strftime('%Y-%m')
                else:
                    month_key = datetime.now().strftime('%Y-%m')
                
                file_path = os.path.join(
                    self.data_path, "news", f"{month_key}.json"
                )
                
                # Load existing data or create new
                existing_data = []
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as f:
                            existing_data = json.load(f)
                    except:
                        existing_data = []
                
                # Add new record
                existing_data.append(record)
                
                # Save updated data
                with open(file_path, 'w') as f:
                    json.dump(existing_data, f, indent=2)
            
            logger.info(f"Stored {len(data)} news records")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store news data: {e}")
            return False
    
    def store_filings(self, data: List[Dict[str, Any]]) -> bool:
        """Store filing data in JSON format."""
        if not data:
            return True
        
        try:
            for record in data:
                timestamp = record.get('timestamp_utc', '')
                
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        month_key = dt.strftime('%Y-%m')
                    except:
                        month_key = datetime.now().strftime('%Y-%m')
                else:
                    month_key = datetime.now().strftime('%Y-%m')
                
                file_path = os.path.join(
                    self.data_path, "filings", f"{month_key}.json"
                )
                
                # Load existing data or create new
                existing_data = []
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as f:
                            existing_data = json.load(f)
                    except:
                        existing_data = []
                
                # Add new record
                existing_data.append(record)
                
                # Save updated data
                with open(file_path, 'w') as f:
                    json.dump(existing_data, f, indent=2)
            
            logger.info(f"Stored {len(data)} filing records")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store filing data: {e}")
            return False
    
    def query_ohlcv(self, symbol: str, start_date: Optional[str] = None, 
                    end_date: Optional[str] = None, interval: str = "1m") -> List[Dict[str, Any]]:
        """Query OHLCV data for a symbol."""
        try:
            symbol_path = os.path.join(self.data_path, "ohlcv", interval, symbol)
            
            if not os.path.exists(symbol_path):
                return []
            
            # Load all JSON files for the symbol
            all_data = []
            for filename in os.listdir(symbol_path):
                if filename.endswith('.json'):
                    file_path = os.path.join(symbol_path, filename)
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                all_data.extend(data)
                    except:
                        continue
            
            # Filter by date range if specified
            if start_date or end_date:
                filtered_data = []
                for record in all_data:
                    timestamp = record.get('timestamp_utc', '')
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            
                            if start_date:
                                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                                if dt < start_dt:
                                    continue
                            
                            if end_date:
                                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                if dt > end_dt:
                                    continue
                            
                            filtered_data.append(record)
                        except:
                            continue
                    else:
                        filtered_data.append(record)
                
                all_data = filtered_data
            
            # Sort by timestamp
            all_data.sort(key=lambda x: x.get('timestamp_utc', ''))
            
            return all_data
            
        except Exception as e:
            logger.error(f"Failed to query OHLCV data for {symbol}: {e}")
            return []
    
    def query_news(self, ticker: Optional[str] = None, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query news data."""
        try:
            news_path = os.path.join(self.data_path, "news")
            
            if not os.path.exists(news_path):
                return []
            
            # Load all news files
            all_news = []
            for filename in os.listdir(news_path):
                if filename.endswith('.json'):
                    file_path = os.path.join(news_path, filename)
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                all_news.extend(data)
                    except:
                        continue
            
            # Filter by ticker if specified
            if ticker:
                filtered_news = []
                for news in all_news:
                    tickers = news.get('tickers', [])
                    if ticker in tickers:
                        filtered_news.append(news)
                all_news = filtered_news
            
            # Filter by date if specified
            if since:
                filtered_news = []
                for news in all_news:
                    timestamp = news.get('timestamp_utc', '')
                    if timestamp:
                        try:
                            news_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                            if news_dt >= since_dt:
                                filtered_news.append(news)
                        except:
                            continue
                    else:
                        filtered_news.append(news)
                all_news = filtered_news
            
            # Sort by timestamp (newest first)
            all_news.sort(key=lambda x: x.get('timestamp_utc', ''), reverse=True)
            
            return all_news
            
        except Exception as e:
            logger.error(f"Failed to query news data: {e}")
            return []
    
    def query_filings(self, symbol: Optional[str] = None, 
                     filing_type: Optional[str] = None,
                     since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query filing data."""
        try:
            filings_path = os.path.join(self.data_path, "filings")
            
            if not os.path.exists(filings_path):
                return []
            
            # Load all filing files
            all_filings = []
            for filename in os.listdir(filings_path):
                if filename.endswith('.json'):
                    file_path = os.path.join(filings_path, filename)
                    with open(file_path, 'r') as f:
                        filings = json.load(f)
                        all_filings.extend(filings)
            
            # Filter by symbol if specified
            if symbol:
                all_filings = [f for f in all_filings if f.get('symbol') == symbol]
            
            # Filter by filing type if specified
            if filing_type:
                all_filings = [f for f in all_filings if f.get('filing_type') == filing_type]
            
            # Filter by date if specified
            if since:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                filtered_filings = []
                for filing in all_filings:
                    filing_date = filing.get('filing_date', '')
                    if filing_date:
                        try:
                            filing_dt = datetime.fromisoformat(filing_date.replace('Z', '+00:00'))
                            if filing_dt >= since_dt:
                                filtered_filings.append(filing)
                        except:
                            continue
                all_filings = filtered_filings
            
            # Sort by filing date (most recent first)
            all_filings.sort(key=lambda x: x.get('filing_date', ''), reverse=True)
            
            return all_filings
            
        except Exception as e:
            logger.error(f"Failed to query filing data: {e}")
            return []
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            stats = {
                "total_files": 0,
                "total_size_bytes": 0,
                "ohlcv_files": 0,
                "news_files": 0,
                "filings_files": 0
            }
            
            # Count files and sizes
            for root, dirs, files in os.walk(self.data_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    
                    stats["total_files"] += 1
                    stats["total_size_bytes"] += file_size
                    
                    if "ohlcv" in root:
                        stats["ohlcv_files"] += 1
                    elif "news" in root:
                        stats["news_files"] += 1
                    elif "filings" in root:
                        stats["filings_files"] += 1
            
            # Convert bytes to MB
            stats["total_size_mb"] = stats["total_size_bytes"] / (1024 * 1024)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}
