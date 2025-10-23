@echo off
REM NeuroTradeAI - Real-Time Trading Data Scraper
REM Professional launcher script for Windows

title NeuroTradeAI Data Scraper

echo.
echo ========================================
echo    NeuroTradeAI Data Scraper v1.0.0
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    echo.
    pause
    exit /b 1
)

echo Python version:
python --version
echo.

REM Check if we're in the right directory
if not exist "app\main.py" (
    echo ERROR: app\main.py not found
    echo Please run this script from the NeuroTradeAI directory
    echo.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
echo.

REM Try minimal requirements first (avoids compilation issues)
echo Trying minimal requirements first (avoids compilation issues)...
pip install -r requirements-minimal.txt
if errorlevel 1 (
    echo WARNING: Minimal requirements failed, trying standard version...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo WARNING: Standard requirements failed, trying Windows-optimized version...
        pip install -r requirements-windows.txt
        if errorlevel 1 (
            echo ERROR: Failed to install dependencies
            echo.
            echo TROUBLESHOOTING:
            echo 1. Make sure you have Visual Studio Build Tools installed
            echo 2. Try: pip install --upgrade pip setuptools wheel
            echo 3. Try: conda install -c conda-forge pyarrow pandas
            echo 4. Check Python version (3.8+ required)
            echo 5. The app will work with minimal requirements (JSON storage)
            echo.
            pause
            exit /b 1
        )
    )
)

echo Dependencies installed successfully
echo.

REM Create necessary directories
echo Creating directories...
if not exist "logs" mkdir logs
if not exist "db" mkdir db
if not exist "data" mkdir data
if not exist "keys" mkdir keys
if not exist "data\ohlcv" mkdir data\ohlcv
if not exist "data\news" mkdir data\news
if not exist "data\filings" mkdir data\filings
if not exist "data\ohlcv\1m" mkdir data\ohlcv\1m
if not exist "web\static" mkdir web\static

echo Directories created successfully
echo.

REM Check if this is first run
if not exist "keys\vault.enc" (
    echo ========================================
    echo    FIRST TIME SETUP
    echo ========================================
    echo.
    echo This appears to be your first time running NeuroTradeAI.
    echo You'll need to set up your API keys.
    echo.
    echo Required API Keys:
    echo - Finnhub: Get free key at https://finnhub.io
    echo - Others: Optional for enhanced features
    echo.
    echo You can add API keys through the web dashboard.
    echo.
    pause
)

REM Start the application
echo ========================================
echo    STARTING NEUROTRADEAI
echo ========================================
echo.
echo Dashboard will be available at: http://localhost:8000
echo API will be available at: http://localhost:8000/api/v1
echo.
echo Press Ctrl+C to stop the application
echo.

REM Start the application
python -m app.main

REM If we get here, the application has stopped
echo.
echo ========================================
echo    APPLICATION STOPPED
echo ========================================
echo.
echo Thank you for using NeuroTradeAI!
echo.
pause