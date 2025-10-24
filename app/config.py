"""
Configuration management for the trading data scraper.
"""
import os
from typing import List, Dict, Any

# Default watchlist (50 symbols for MVP)
WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX", "AMD", "INTC",
    "CRM", "ORCL", "ADBE", "PYPL", "UBER", "LYFT", "SQ", "ROKU", "ZM", "PTON",
    "SPOT", "TWTR", "SNAP", "PINS", "SHOP", "SNOW", "PLTR", "CRWD", "OKTA", "ZM",
    "SPY", "QQQ", "IWM", "VTI", "VOO", "ARKK", "TQQQ", "SQQQ", "UPRO", "TMF",
    "GLD", "SLV", "TLT", "HYG", "LQD", "EFA", "EEM", "VEA", "VWO", "BND"
]

# Rate limits (requests per minute)
RATE_LIMITS = {
    "finnhub": 60,
    "twelvedata": 8,
    "alphavantage": 5,
    "edgar": 10,
    "fmp": 5,
}

# Retention policy (days)
RETENTION = {
    "1m_bars": 730,      # 2 years
    "tick_data": 7,      # 7 days
    "news": 365,         # 1 year
    "filings": 1095,     # 3 years
}

# Storage paths (use current directory for development, D:\NeuroTradeAI for production)
if os.path.exists("D:\\NeuroTradeAI"):
    # Production mode - use D:\NeuroTradeAI
    BASE_PATH = "D:\\NeuroTradeAI"
else:
    # Development mode - use current directory
    BASE_PATH = os.getcwd()

DATA_PATH = os.path.join(BASE_PATH, "data")
DB_PATH = os.path.join(BASE_PATH, "db", "metadata.sqlite")
LOG_PATH = os.path.join(BASE_PATH, "logs")
KEYS_PATH = os.path.join(BASE_PATH, "keys")

# API Configuration
API_HOST = "localhost"
API_PORT = 8000
API_URL = f"http://{API_HOST}:{API_PORT}"

# Trading Configuration
TRADING_CONFIG = {
    "mode": "paper",  # paper or live
    "broker": "simulator",  # simulator or alpaca
    "default_strategy": "mean_reversion",
    "polling_interval": 60,  # seconds
    "risk_limits": {
        "max_position_size_pct": 1.0,
        "max_total_exposure_pct": 5.0,
        "daily_loss_limit_pct": 3.0,
        "max_positions": 3,
        "min_avg_volume": 1_000_000,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 3.0,
        "circuit_breaker_losses": 3
    },
    "execution": {
        "default_order_type": "limit",
        "limit_offset_pct": 0.1,  # offset from mid for limit orders
        "max_order_retry": 3,
        "order_timeout_seconds": 300
    }
}

# WebSocket Configuration
WS_URL = f"ws://{API_HOST}:{API_PORT}/stream"

# Database Configuration
DB_CONFIG = {
    "timeout": 30,
    "check_same_thread": False,
}

# Logging Configuration
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "max_bytes": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5,
}

# Security Configuration
ENCRYPTION_KEY_LENGTH = 32
VAULT_FILENAME = "vault.enc"

# Data Schema Configuration
CANONICAL_SCHEMAS = {
    "ohlcv": [
        "symbol", "exchange", "timestamp_utc", "interval", 
        "open", "high", "low", "close", "volume", "source", "recv_ts"
    ],
    "news": [
        "id", "timestamp_utc", "source", "headline", "url", 
        "tickers", "sentiment_score", "raw_payload"
    ],
    "filings": [
        "symbol", "filing_type", "filing_date", "url", "summary", "raw_xbrl"
    ]
}

# User Agent for HTTP requests
USER_AGENT = "NeuroTradeAI-Scraper/1.0 (Educational Research Tool)"

# Default polling intervals (seconds)
POLLING_INTERVALS = {
    "realtime": 1,      # WebSocket updates
    "bars": 60,          # 1-minute bars
    "news": 300,         # 5 minutes
    "filings": 3600,     # 1 hour
}

# Error handling configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
EXPONENTIAL_BACKOFF = True
MAX_BACKOFF_DELAY = 300  # 5 minutes
