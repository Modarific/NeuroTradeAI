# Installation Guide

This guide will help you install and set up NeuroTradeAI on your system.

## 📋 Prerequisites

### **System Requirements**
- **Operating System**: Windows 10/11 (primary support)
- **Python**: Version 3.8 or higher (tested with Python 3.14)
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 1TB+ recommended for production data
- **Network**: Stable internet connection for data collection

### **Python Installation**
If you don't have Python installed:

1. **Download Python**: Visit [python.org](https://python.org/downloads/)
2. **Install Python**: Run the installer with "Add to PATH" checked
3. **Verify Installation**: Open Command Prompt and run:
   ```bash
   python --version
   ```

## 🚀 Quick Installation

### **Method 1: Launcher Script (Recommended)**

1. **Download NeuroTradeAI**
   ```bash
   git clone https://github.com/yourusername/NeuroTradeAI.git
   cd NeuroTradeAI
   ```

2. **Run the launcher**
   ```bash
   launcher.bat
   ```

3. **Follow the setup wizard**
   - The launcher will create a virtual environment
   - Install all dependencies automatically
   - Set up directory structure
   - Guide you through API key configuration

### **Method 2: Manual Installation**

1. **Create project directory**
   ```bash
   mkdir NeuroTradeAI
   cd NeuroTradeAI
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create directories**
   ```bash
   mkdir logs db data keys
   mkdir data\ohlcv data\news data\filings
   mkdir web\static
   ```

5. **Start the application**
   ```bash
   python -m app.main
   ```

## 🔧 Configuration

### **API Keys Setup**

NeuroTradeAI requires API keys for data collection:

#### **Required: Finnhub API Key**
1. Visit [finnhub.io](https://finnhub.io)
2. Sign up for a free account
3. Get your API key from the dashboard
4. Add it to NeuroTradeAI through the web interface

#### **Optional: Additional Sources**
- **TwelveData**: Enhanced market data
- **Alpha Vantage**: Backup data source
- **Financial Modeling Prep**: Advanced fundamentals

### **System Configuration**

Access configuration through the web dashboard at `http://localhost:8000`:

- **Data Sources**: Enable/disable data collection
- **Symbols**: Configure watchlist symbols
- **Polling**: Set collection intervals
- **Storage**: Configure retention policies
- **Alerts**: Set up notifications

## 🧪 Verification

### **Test Installation**

1. **Run the test suite**
   ```bash
   python run_tests.py
   ```

2. **Check system health**
   - Open `http://localhost:8000`
   - Navigate to System Metrics
   - Verify all components are green

3. **Test data collection**
   - Add a test symbol (e.g., AAPL)
   - Enable data collection
   - Verify data appears in the dashboard

## 🔧 Troubleshooting

### **Common Issues**

#### **Python Not Found**
```bash
# Add Python to PATH or use full path
C:\Python314\python.exe -m venv venv
```

#### **Permission Errors**
```bash
# Run Command Prompt as Administrator
# Or change directory permissions
```

#### **Dependency Installation Fails**
```bash
# Try minimal requirements
pip install -r requirements-minimal.txt

# Or use conda
conda install -c conda-forge pyarrow pandas
```

#### **Port Already in Use**
```bash
# Change port in app/config.py
API_PORT = 8001
```

### **Getting Help**

- **Check Logs**: Look in `logs/` directory for error messages
- **GitHub Issues**: [Report problems](https://github.com/yourusername/NeuroTradeAI/issues)
- **Documentation**: See [troubleshooting.md](troubleshooting.md)

## 📦 Production Deployment

### **Production Considerations**

1. **Dedicated Server**: Use a dedicated machine for production
2. **Storage**: Ensure adequate storage space (1TB+)
3. **Backup**: Set up regular backups of data and configuration
4. **Monitoring**: Configure system monitoring and alerts
5. **Security**: Use strong passwords and secure network access

### **Performance Optimization**

- **SSD Storage**: Use SSD for better I/O performance
- **Memory**: 8GB+ RAM for large datasets
- **Network**: Stable, high-speed internet connection
- **CPU**: Multi-core processor for concurrent operations

## 🎯 Next Steps

After successful installation:

1. **Configure API Keys**: Set up your data source credentials
2. **Add Symbols**: Configure your watchlist
3. **Start Collection**: Begin data collection
4. **Monitor Dashboard**: Watch real-time data flow
5. **Explore Features**: Discover all system capabilities

---

*For more detailed information, see the [Configuration Guide](configuration.md) and [API Reference](api.md).*
