# NeuroTradeAI - Real-Time Trading Data Scraper

A comprehensive, real-time trading data collection and analysis system built with Python, FastAPI, and modern web technologies. Collects market data, news, and SEC filings from multiple sources with professional-grade rate limiting, encryption, and storage.

## 🚀 Features

### **Real-Time Data Collection**
- **Market Data**: Live OHLCV data from Finnhub with WebSocket streaming
- **News Feed**: Real-time news with sentiment analysis and ticker extraction
- **SEC Filings**: Automated collection of 10-K, 10-Q, and 8-K filings
- **Multi-Source**: Extensible adapter system for multiple data providers

### **Professional Dashboard**
- **Live Updates**: Real-time price updates with WebSocket streaming
- **News Display**: Recent news with sentiment indicators and ticker filtering
- **Filing Tracker**: SEC filings with color-coded filing types
- **System Metrics**: Comprehensive monitoring and health indicators
- **Control Panel**: Enable/disable data sources and system configuration

### **Enterprise-Grade Security**
- **Credential Encryption**: AES-256 encryption for all API keys
- **Rate Limiting**: Token bucket algorithm with burst capacity
- **Input Validation**: Comprehensive data sanitization and validation
- **Audit Logging**: Complete request tracking and error monitoring

### **High-Performance Storage**
- **Parquet Files**: Efficient columnar storage for time-series data
- **SQLite Metadata**: Fast querying and relationship management
- **JSONL Archives**: Compressed news and filing storage
- **Retention Policies**: Automated data cleanup and management

## 📊 System Architecture

```
NeuroTradeAI/
├── app/                    # Core application
│   ├── main.py            # FastAPI server & orchestrator
│   ├── config.py          # Configuration management
│   ├── adapters/          # Data source adapters
│   │   ├── finnhub.py     # Market data & news
│   │   ├── edgar.py       # SEC filings
│   │   └── base.py        # Adapter interface
│   ├── core/              # Core components
│   │   ├── storage.py     # Data persistence
│   │   ├── rate_limiter.py # Rate limiting
│   │   └── normalizer.py  # Data normalization
│   ├── security/          # Security components
│   │   └── vault.py       # Credential encryption
│   └── api/               # API endpoints
│       ├── routes.py      # REST API
│       └── websocket.py   # Real-time streaming
├── web/                   # Dashboard interface
│   ├── index.html         # Main dashboard
│   └── static/            # CSS/JS assets
├── tests/                 # Comprehensive test suite
├── data/                  # Data storage
├── logs/                  # Application logs
└── keys/                  # Encrypted credentials
```

## 🛠️ Installation

### **Prerequisites**
- Python 3.8+ (tested with Python 3.14)
- Windows 10/11 (primary support)
- 1TB+ storage recommended for production data

### **Quick Start**

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/NeuroTradeAI.git
   cd NeuroTradeAI
   ```

2. **Run the launcher**
   ```bash
   launcher.bat
   ```

3. **Access the dashboard**
   - Open `http://localhost:8000` in your browser
   - Configure API keys in the dashboard
   - Start collecting data!

### **Manual Installation**

1. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize the system**
   ```bash
   python -m app.main
   ```

## 🔧 Configuration

### **API Keys Setup**

The system supports multiple data sources. Configure your API keys through the dashboard:

1. **Finnhub** (Required for market data)
   - Get free API key at [finnhub.io](https://finnhub.io)
   - Rate limit: 60 requests/minute
   - Provides: Real-time quotes, news, company data

2. **Optional Sources**
   - **TwelveData**: Additional market data
   - **Alpha Vantage**: Backup data source
   - **Financial Modeling Prep**: Enhanced fundamentals

### **System Configuration**

Access system settings through the dashboard:
- **Polling Intervals**: Adjust data collection frequency
- **Symbol Limits**: Control maximum symbols tracked
- **Retention Policies**: Set data cleanup schedules
- **Alert Settings**: Configure error notifications

## 📈 Usage

### **Dashboard Features**

- **Live Prices**: Real-time price updates for tracked symbols
- **News Feed**: Recent news with sentiment analysis
- **SEC Filings**: Regulatory filings with direct links
- **System Metrics**: Performance monitoring and health status
- **Control Panel**: Manage data sources and system settings

### **API Endpoints**

- `GET /api/v1/ohlcv/{symbol}` - Historical price data
- `GET /api/v1/news` - News articles with filtering
- `GET /api/v1/filings` - SEC filings by symbol/type
- `GET /api/v1/metrics` - System health and statistics
- `WS /stream` - Real-time data streaming

### **Data Schemas**

All data is normalized to canonical schemas:

**OHLCV Data**
```json
{
  "symbol": "AAPL",
  "timestamp_utc": "2025-10-23T14:31:00Z",
  "open": 171.34,
  "high": 171.52,
  "low": 171.12,
  "close": 171.49,
  "volume": 123456,
  "source": "finnhub"
}
```

**News Data**
```json
{
  "id": "news_123",
  "timestamp_utc": "2025-10-23T14:31:00Z",
  "headline": "Apple reports strong earnings",
  "url": "https://example.com/news",
  "tickers": ["AAPL"],
  "sentiment_score": 0.8
}
```

## 🧪 Testing

### **Run Test Suite**
```bash
# Run all tests
python run_tests.py

# Run specific test categories
python run_tests.py --type unit
python run_tests.py --type integration
python run_tests.py --type load
python run_tests.py --type security

# Run with coverage
python run_tests.py --coverage
```

### **Test Coverage**
- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow validation
- **Load Tests**: Performance under high load
- **Security Tests**: Credential protection and input validation

## 📊 Performance

### **Benchmarks**
- **Storage**: 1000+ records per second
- **Rate Limiting**: 100+ concurrent requests
- **Memory Usage**: <100MB for 10,000 records
- **Query Performance**: <2 seconds for 5000 records

### **Scalability**
- **Symbols**: Tested with 100+ concurrent symbols
- **Data Volume**: Handles millions of records efficiently
- **Concurrent Users**: Supports multiple dashboard connections
- **Storage**: Optimized for long-term data retention

## 🔒 Security

### **Credential Protection**
- **AES-256 Encryption**: All API keys encrypted at rest
- **Secure Vault**: Password-protected credential storage
- **No Plaintext**: Never stores unencrypted credentials
- **Audit Trail**: Complete access logging

### **Data Validation**
- **Input Sanitization**: All data validated and cleaned
- **SQL Injection Protection**: Parameterized queries only
- **Path Traversal Prevention**: Secure file handling
- **XSS Protection**: Output encoding for web interface

## 📚 Documentation

- **[API Documentation](docs/api.md)** - Complete API reference
- **[Configuration Guide](docs/configuration.md)** - System setup
- **[Deployment Guide](docs/deployment.md)** - Production deployment
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### **Development Setup**
```bash
git clone https://github.com/yourusername/NeuroTradeAI.git
cd NeuroTradeAI
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-test.txt
python run_tests.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/NeuroTradeAI/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/NeuroTradeAI/discussions)
- **Documentation**: [Wiki](https://github.com/yourusername/NeuroTradeAI/wiki)

## 🎯 Roadmap

- [ ] **M7**: Advanced Analytics Dashboard
- [ ] **M8**: Machine Learning Integration
- [ ] **M9**: Mobile App Interface
- [ ] **M10**: Cloud Deployment Options

## 📈 Changelog

### **v1.0.0** - Initial Release
- ✅ Real-time market data collection
- ✅ News feed with sentiment analysis
- ✅ SEC filings integration
- ✅ Professional web dashboard
- ✅ Comprehensive test suite
- ✅ Enterprise security features

---

**Built with ❤️ for the trading community**