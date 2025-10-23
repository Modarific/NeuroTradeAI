"""
Storage layer for time-series data using Parquet and SQLite.
Handles data persistence, retrieval, and metadata management.
"""
import os
import sqlite3
import json
import gzip
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import logging

# Try to import pandas and pyarrow, fall back to simple storage if not available
try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    # Import simple storage as fallback
    try:
        from .storage_simple import SimpleStorageManager
    except ImportError:
        # If relative import fails, try absolute import
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        from storage_simple import SimpleStorageManager

logger = logging.getLogger(__name__)

class StorageManager:
    """Manages data storage using Parquet files and SQLite metadata."""
    
    def __init__(self, data_path: str, db_path: str):
        self.data_path = data_path
        self.db_path = db_path
        
        # Use simple storage if pandas/pyarrow not available
        if not PANDAS_AVAILABLE:
            logger.warning("Pandas/PyArrow not available, using simple JSON storage")
            self.simple_storage = SimpleStorageManager(data_path, db_path)
            return
        
        self._init_directories()
        self._init_database()
    
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
    
    def _init_database(self):
        """Initialize SQLite database with required tables."""
        try:
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
        """
        Store OHLCV data in Parquet format.
        
        Args:
            data: List of OHLCV records
            
        Returns:
            True if successful, False otherwise
        """
        if not data:
            return True
        
        # Use simple storage if pandas not available
        if not PANDAS_AVAILABLE:
            return self.simple_storage.store_ohlcv(data)
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Ensure timestamp is datetime
            df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
            df['recv_ts'] = pd.to_datetime(df['recv_ts'])
            
            # Group by symbol and year for partitioning
            for symbol in df['symbol'].unique():
                symbol_data = df[df['symbol'] == symbol]
                
                for year in symbol_data['timestamp_utc'].dt.year.unique():
                    year_data = symbol_data[symbol_data['timestamp_utc'].dt.year == year]
                    
                    # Create file path
                    file_path = os.path.join(
                        self.data_path, "ohlcv", "1m", symbol, f"{year}.parquet"
                    )
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    # Convert to Arrow table
                    table = pa.Table.from_pandas(year_data)
                    
                    # Write to Parquet
                    pq.write_table(table, file_path)
                    
                    # Update file manifest
                    self._update_file_manifest(
                        file_path, 
                        len(year_data),
                        year_data['timestamp_utc'].min(),
                        year_data['timestamp_utc'].max()
                    )
            
            logger.info(f"Stored {len(data)} OHLCV records")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store OHLCV data: {e}")
            return False
    
    def store_news(self, data: List[Dict[str, Any]]) -> bool:
        """
        Store news data in compressed JSONL format.
        
        Args:
            data: List of news records
            
        Returns:
            True if successful, False otherwise
        """
        if not data:
            return True
        
        # Use simple storage if pandas not available
        if not PANDAS_AVAILABLE:
            return self.simple_storage.store_news(data)
        
        try:
            # Group by month for partitioning
            for record in data:
                timestamp = pd.to_datetime(record['timestamp_utc'])
                month_key = timestamp.strftime('%Y-%m')
                
                file_path = os.path.join(
                    self.data_path, "news", f"{month_key}.jsonl.gz"
                )
                
                # Append to compressed file
                with gzip.open(file_path, 'at', encoding='utf-8') as f:
                    f.write(json.dumps(record) + '\n')
                
                # Update metadata
                self._store_news_metadata(record, file_path)
            
            logger.info(f"Stored {len(data)} news records")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store news data: {e}")
            return False
    
    def store_filings(self, data: List[Dict[str, Any]]) -> bool:
        """
        Store filings data.
        
        Args:
            data: List of filing records
            
        Returns:
            True if successful, False otherwise
        """
        if not data:
            return True
        
        try:
            for record in data:
                # Store raw data
                symbol = record['symbol']
                filing_date = record['filing_date']
                filing_type = record['filing_type']
                
                file_path = os.path.join(
                    self.data_path, "filings", symbol, f"{filing_date}_{filing_type}.json"
                )
                
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'w') as f:
                    json.dump(record, f, indent=2)
                
                # Update metadata
                self._store_filing_metadata(record, file_path)
            
            logger.info(f"Stored {len(data)} filing records")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store filings data: {e}")
            return False
    
    def query_ohlcv(self, symbol: str, start_date: Optional[str] = None, 
                    end_date: Optional[str] = None, interval: str = "1m"):
        """
        Query OHLCV data for a symbol.
        
        Args:
            symbol: Stock symbol
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            interval: Data interval (default: 1m)
            
        Returns:
            DataFrame with OHLCV data (or list if pandas not available)
        """
        # Use simple storage if pandas not available
        if not PANDAS_AVAILABLE:
            return self.simple_storage.query_ohlcv(symbol, start_date, end_date, interval)
        
        try:
            # Find relevant Parquet files
            symbol_path = os.path.join(self.data_path, "ohlcv", interval, symbol)
            
            if not os.path.exists(symbol_path):
                return pd.DataFrame()
            
            # Read all Parquet files for the symbol
            files = [f for f in os.listdir(symbol_path) if f.endswith('.parquet')]
            
            if not files:
                return pd.DataFrame()
            
            # Load and concatenate data
            dfs = []
            for file in files:
                file_path = os.path.join(symbol_path, file)
                df = pd.read_parquet(file_path)
                dfs.append(df)
            
            if not dfs:
                return pd.DataFrame()
            
            result_df = pd.concat(dfs, ignore_index=True)
            
            # Filter by date range if specified
            if start_date:
                start_ts = pd.to_datetime(start_date)
                result_df = result_df[result_df['timestamp_utc'] >= start_ts]
            
            if end_date:
                end_ts = pd.to_datetime(end_date)
                result_df = result_df[result_df['timestamp_utc'] <= end_ts]
            
            # Sort by timestamp
            result_df = result_df.sort_values('timestamp_utc')
            
            return result_df
            
        except Exception as e:
            logger.error(f"Failed to query OHLCV data for {symbol}: {e}")
            return pd.DataFrame() if PANDAS_AVAILABLE else []
    
    def query_news(self, ticker: Optional[str] = None, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query news data.
        
        Args:
            ticker: Filter by ticker symbol
            since: Filter by date (ISO format)
            
        Returns:
            List of news records
        """
        # Use simple storage if pandas not available
        if not PANDAS_AVAILABLE:
            return self.simple_storage.query_news(ticker, since)
        
        try:
            # Query metadata first
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM news_metadata WHERE 1=1"
                params = []
                
                if ticker:
                    query += " AND tickers LIKE ?"
                    params.append(f"%{ticker}%")
                
                if since:
                    query += " AND timestamp_utc >= ?"
                    params.append(since)
                
                query += " ORDER BY timestamp_utc DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Get column names
                columns = [description[0] for description in cursor.description]
                
                # Convert to list of dicts
                results = []
                for row in rows:
                    record = dict(zip(columns, row))
                    
                    # Load full record from file
                    if record['file_path'] and os.path.exists(record['file_path']):
                        with gzip.open(record['file_path'], 'rt') as f:
                            for line in f:
                                news_record = json.loads(line)
                                if news_record['id'] == record['id']:
                                    results.append(news_record)
                                    break
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to query news data: {e}")
            return []
    
    def _update_file_manifest(self, file_path: str, record_count: int, 
                            start_ts: pd.Timestamp, end_ts: pd.Timestamp):
        """Update file manifest in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO file_manifest 
                    (path, record_count, start_ts, end_ts, created_utc)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    file_path,
                    record_count,
                    start_ts.isoformat(),
                    end_ts.isoformat(),
                    datetime.now(timezone.utc).isoformat()
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update file manifest: {e}")
    
    def _store_news_metadata(self, record: Dict[str, Any], file_path: str):
        """Store news metadata in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO news_metadata 
                    (id, timestamp_utc, source, headline, url, tickers, sentiment_score, file_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record['id'],
                    record['timestamp_utc'],
                    record['source'],
                    record['headline'],
                    record.get('url', ''),
                    json.dumps(record.get('tickers', [])),
                    record.get('sentiment_score', 0.0),
                    file_path
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store news metadata: {e}")
    
    def _store_filing_metadata(self, record: Dict[str, Any], file_path: str):
        """Store filing metadata in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO filings_metadata 
                    (symbol, filing_type, filing_date, url, summary, file_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    record['symbol'],
                    record['filing_type'],
                    record['filing_date'],
                    record.get('url', ''),
                    record.get('summary', ''),
                    file_path
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store filing metadata: {e}")
    
    def store_filings(self, data: List[Dict[str, Any]]) -> bool:
        """Store filing data."""
        if not PANDAS_AVAILABLE:
            return self.simple_storage.store_filings(data)
        
        # TODO: Implement Parquet storage for filings
        logger.warning("Parquet filing storage not yet implemented, using simple storage")
        return self.simple_storage.store_filings(data)
    
    def query_filings(self, symbol: Optional[str] = None, 
                     filing_type: Optional[str] = None,
                     since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query filing data."""
        if not PANDAS_AVAILABLE:
            return self.simple_storage.query_filings(symbol, filing_type, since)
        
        # TODO: Implement Parquet query for filings
        logger.warning("Parquet filing query not yet implemented, using simple storage")
        return self.simple_storage.query_filings(symbol, filing_type, since)
    
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
