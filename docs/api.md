# API Reference

Complete API documentation for NeuroTradeAI endpoints.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, the API does not require authentication for local access. In production deployments, consider implementing API key authentication.

## Endpoints

### Market Data

#### Get OHLCV Data
```http
GET /ohlcv/{symbol}
```

**Parameters:**
- `symbol` (path): Stock symbol (e.g., AAPL, MSFT)
- `interval` (query): Data interval (1m, 5m, 15m, 1h, 1d)
- `start` (query): Start date (ISO format)
- `end` (query): End date (ISO format)
- `limit` (query): Maximum number of records

**Response:**
```json
{
  "symbol": "AAPL",
  "data": [
    {
      "timestamp_utc": "2025-10-23T14:31:00Z",
      "open": 171.34,
      "high": 171.52,
      "low": 171.12,
      "close": 171.49,
      "volume": 123456,
      "source": "finnhub"
    }
  ],
  "count": 1,
  "filters": {
    "interval": "1m",
    "start": "2025-10-23T00:00:00Z",
    "end": "2025-10-23T23:59:59Z"
  }
}
```

#### Get All OHLCV Data
```http
GET /ohlcv
```

**Parameters:**
- `symbol` (query): Filter by symbol
- `interval` (query): Filter by interval
- `start` (query): Start date filter
- `end` (query): End date filter
- `limit` (query): Maximum number of records

### News Data

#### Get News
```http
GET /news
```

**Parameters:**
- `ticker` (query): Filter by ticker symbol
- `since` (query): Filter by date (ISO format)
- `limit` (query): Maximum number of records

**Response:**
```json
{
  "news": [
    {
      "id": "news_123",
      "timestamp_utc": "2025-10-23T14:31:00Z",
      "source": "finnhub",
      "headline": "Apple reports strong earnings",
      "url": "https://example.com/news",
      "tickers": ["AAPL"],
      "sentiment_score": 0.8,
      "raw_payload": {}
    }
  ],
  "count": 1,
  "filters": {
    "ticker": "AAPL",
    "since": "2025-10-23T00:00:00Z"
  }
}
```

### SEC Filings

#### Get Filings
```http
GET /filings
```

**Parameters:**
- `symbol` (query): Filter by symbol
- `filing_type` (query): Filter by filing type (10-K, 10-Q, 8-K)
- `since` (query): Filter by date (ISO format)
- `limit` (query): Maximum number of records

**Response:**
```json
{
  "filings": [
    {
      "symbol": "AAPL",
      "filing_type": "10-K",
      "filing_date": "2025-10-20T00:00:00Z",
      "entity_name": "Apple Inc.",
      "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000123/aapl-20250930.htm",
      "summary": "Annual report for fiscal year ended September 30, 2025",
      "source": "edgar"
    }
  ],
  "count": 1,
  "filters": {
    "symbol": "AAPL",
    "filing_type": "10-K"
  }
}
```

#### Get Filings for Symbol
```http
GET /filings/{symbol}
```

**Parameters:**
- `symbol` (path): Stock symbol
- `filing_type` (query): Filter by filing type
- `since` (query): Filter by date
- `limit` (query): Maximum number of records

### System Information

#### Get Metrics
```http
GET /metrics
```

**Response:**
```json
{
  "system": {
    "uptime": "2h 15m 30s",
    "version": "1.0.0",
    "status": "healthy"
  },
  "storage": {
    "total_files": 1250,
    "total_size_mb": 45.2,
    "ohlcv_files": 800,
    "news_files": 300,
    "filings_files": 150
  },
  "database": {
    "symbols": 50,
    "last_update": "2025-10-23T14:31:00Z"
  },
  "rate_limits": {
    "finnhub": {
      "requests_per_minute": 60,
      "current_usage": 45,
      "reset_time": "2025-10-23T14:32:00Z"
    }
  }
}
```

#### Get System Settings
```http
GET /settings
```

**Response:**
```json
{
  "polling_interval": 60,
  "max_symbols": 50,
  "retention_days": 365,
  "auto_cleanup": true,
  "error_alerts": true,
  "rate_limit_alerts": true
}
```

#### Update System Settings
```http
POST /settings
```

**Request Body:**
```json
{
  "polling_interval": 120,
  "max_symbols": 100,
  "retention_days": 730,
  "auto_cleanup": true,
  "error_alerts": true,
  "rate_limit_alerts": true
}
```

### Data Source Management

#### Toggle Data Source
```http
POST /sources/{source}
```

**Parameters:**
- `source` (path): Data source name (finnhub, news, edgar)

**Request Body:**
```json
{
  "enabled": true
}
```

### API Key Management

#### Get Key Status
```http
GET /keys/status
```

**Response:**
```json
{
  "vault_unlocked": true,
  "keys": {
    "finnhub": {
      "configured": true,
      "last_tested": "2025-10-23T14:31:00Z",
      "status": "valid"
    },
    "twelvedata": {
      "configured": false,
      "last_tested": null,
      "status": "not_configured"
    }
  }
}
```

#### Add API Key
```http
POST /keys/{service}
```

**Parameters:**
- `service` (path): Service name (finnhub, twelvedata, alphavantage)

**Request Body:**
```json
{
  "api_key": "your_api_key_here"
}
```

#### Remove API Key
```http
DELETE /keys/{service}
```

**Parameters:**
- `service` (path): Service name

#### Test API Key
```http
GET /keys/test/{service}
```

**Parameters:**
- `service` (path): Service name

**Response:**
```json
{
  "service": "finnhub",
  "status": "valid",
  "message": "API key is working correctly",
  "tested_at": "2025-10-23T14:31:00Z"
}
```

## WebSocket Streaming

### Connect to Stream
```javascript
const ws = new WebSocket('ws://localhost:8000/stream');
```

### Message Types

#### OHLCV Update
```json
{
  "type": "ohlcv_update",
  "symbol": "AAPL",
  "data": {
    "timestamp_utc": "2025-10-23T14:31:00Z",
    "open": 171.34,
    "high": 171.52,
    "low": 171.12,
    "close": 171.49,
    "volume": 123456,
    "source": "finnhub"
  },
  "timestamp": "2025-10-23T14:31:01Z"
}
```

#### News Update
```json
{
  "type": "news_update",
  "data": {
    "id": "news_123",
    "timestamp_utc": "2025-10-23T14:31:00Z",
    "source": "finnhub",
    "headline": "Apple reports strong earnings",
    "url": "https://example.com/news",
    "tickers": ["AAPL"],
    "sentiment_score": 0.8
  },
  "timestamp": "2025-10-23T14:31:01Z"
}
```

#### Filing Update
```json
{
  "type": "filing_update",
  "data": {
    "symbol": "AAPL",
    "filing_type": "10-K",
    "filing_date": "2025-10-20T00:00:00Z",
    "entity_name": "Apple Inc.",
    "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000123/aapl-20250930.htm",
    "summary": "Annual report for fiscal year ended September 30, 2025",
    "source": "edgar"
  },
  "timestamp": "2025-10-23T14:31:01Z"
}
```

#### System Status
```json
{
  "type": "system_status",
  "data": {
    "system": {
      "uptime": "2h 15m 30s",
      "status": "healthy"
    },
    "storage": {
      "total_files": 1250,
      "total_size_mb": 45.2
    }
  },
  "timestamp": "2025-10-23T14:31:01Z"
}
```

## Error Responses

### Standard Error Format
```json
{
  "detail": "Error message",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-10-23T14:31:00Z"
}
```

### Common Error Codes
- `VALIDATION_ERROR`: Invalid request parameters
- `NOT_FOUND`: Resource not found
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded
- `INTERNAL_ERROR`: Server internal error
- `UNAUTHORIZED`: Authentication required
- `FORBIDDEN`: Access denied

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **Finnhub**: 60 requests per minute
- **News**: 60 requests per minute
- **EDGAR**: 10 requests per minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 2025-10-23T14:32:00Z
```

## Data Formats

### Timestamps
All timestamps are in ISO 8601 format with UTC timezone:
```
2025-10-23T14:31:00Z
```

### Symbols
Stock symbols are case-insensitive and should be provided in uppercase:
```
AAPL, MSFT, GOOGL, AMZN, TSLA
```

### Intervals
Supported data intervals:
- `1m`: 1 minute
- `5m`: 5 minutes
- `15m`: 15 minutes
- `1h`: 1 hour
- `1d`: 1 day

## Examples

### Python Client
```python
import requests
import json

# Get OHLCV data
response = requests.get('http://localhost:8000/api/v1/ohlcv/AAPL')
data = response.json()

# Get news
response = requests.get('http://localhost:8000/api/v1/news?ticker=AAPL&limit=10')
news = response.json()

# Get filings
response = requests.get('http://localhost:8000/api/v1/filings/AAPL')
filings = response.json()
```

### JavaScript Client
```javascript
// REST API
fetch('http://localhost:8000/api/v1/ohlcv/AAPL')
  .then(response => response.json())
  .then(data => console.log(data));

// WebSocket
const ws = new WebSocket('ws://localhost:8000/stream');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

---

*For more information, see the [Installation Guide](installation.md) and [Troubleshooting Guide](troubleshooting.md).*
