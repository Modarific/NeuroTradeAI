@echo off
REM NeuroTradeAI - Production Deployment Script
REM Professional deployment script for production environments

title NeuroTradeAI Production Deployment

echo.
echo ========================================
echo    NeuroTradeAI Production Deployment
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if errorlevel 1 (
    echo WARNING: Not running as administrator
    echo Some operations may require elevated privileges
    echo.
)

REM Set production directory
set PROD_DIR=D:\NeuroTradeAI
set CURRENT_DIR=%~dp0

echo Production directory: %PROD_DIR%
echo Current directory: %CURRENT_DIR%
echo.

REM Check if production directory exists
if not exist "%PROD_DIR%" (
    echo Creating production directory...
    mkdir "%PROD_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create production directory
        echo Please check permissions and disk space
        pause
        exit /b 1
    )
    echo Production directory created successfully
    echo.
)

REM Copy application files
echo Copying application files...
xcopy /E /I /Y "%CURRENT_DIR%app" "%PROD_DIR%\app"
if errorlevel 1 (
    echo ERROR: Failed to copy app directory
    pause
    exit /b 1
)

xcopy /E /I /Y "%CURRENT_DIR%web" "%PROD_DIR%\web"
if errorlevel 1 (
    echo ERROR: Failed to copy web directory
    pause
    exit /b 1
)

xcopy /E /I /Y "%CURRENT_DIR%tests" "%PROD_DIR%\tests"
if errorlevel 1 (
    echo ERROR: Failed to copy tests directory
    pause
    exit /b 1
)

xcopy /E /I /Y "%CURRENT_DIR%docs" "%PROD_DIR%\docs"
if errorlevel 1 (
    echo ERROR: Failed to copy docs directory
    pause
    exit /b 1
)

echo Application files copied successfully
echo.

REM Copy configuration files
echo Copying configuration files...
copy /Y "%CURRENT_DIR%requirements.txt" "%PROD_DIR%\"
copy /Y "%CURRENT_DIR%requirements-dev.txt" "%PROD_DIR%\"
copy /Y "%CURRENT_DIR%requirements-minimal.txt" "%PROD_DIR%\"
copy /Y "%CURRENT_DIR%requirements-windows.txt" "%PROD_DIR%\"
copy /Y "%CURRENT_DIR%setup.py" "%PROD_DIR%\"
copy /Y "%CURRENT_DIR%README.md" "%PROD_DIR%\"
copy /Y "%CURRENT_DIR%LICENSE" "%PROD_DIR%\"
copy /Y "%CURRENT_DIR%CONTRIBUTING.md" "%PROD_DIR%\"
copy /Y "%CURRENT_DIR%.gitignore" "%PROD_DIR%\"

echo Configuration files copied successfully
echo.

REM Create production launcher
echo Creating production launcher...
(
echo @echo off
echo REM NeuroTradeAI - Production Launcher
echo REM Auto-generated production launcher
echo.
echo title NeuroTradeAI Production
echo.
echo echo ========================================
echo echo    NeuroTradeAI Production Mode
echo echo ========================================
echo echo.
echo.
echo REM Change to production directory
echo cd /d "%PROD_DIR%"
echo.
echo REM Check if Python is installed
echo python --version ^>nul 2^>^&1
echo if errorlevel 1 ^(
echo     echo ERROR: Python is not installed or not in PATH
echo     echo Please install Python 3.8+ from https://python.org
echo     echo.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo REM Create virtual environment if it doesn't exist
echo if not exist "venv" ^(
echo     echo Creating production virtual environment...
echo     python -m venv venv
echo     if errorlevel 1 ^(
echo         echo ERROR: Failed to create virtual environment
echo         pause
echo         exit /b 1
echo     ^)
echo     echo Virtual environment created successfully
echo     echo.
echo ^)
echo.
echo REM Activate virtual environment
echo echo Activating virtual environment...
echo call venv\Scripts\activate.bat
echo if errorlevel 1 ^(
echo     echo ERROR: Failed to activate virtual environment
echo     pause
echo     exit /b 1
echo ^)
echo.
echo REM Install dependencies
echo echo Installing production dependencies...
echo pip install -r requirements.txt
echo if errorlevel 1 ^(
echo     echo ERROR: Failed to install dependencies
echo     pause
echo     exit /b 1
echo ^)
echo.
echo REM Create production directories
echo echo Creating production directories...
echo if not exist "logs" mkdir logs
echo if not exist "db" mkdir db
echo if not exist "data" mkdir data
echo if not exist "keys" mkdir keys
echo if not exist "data\ohlcv" mkdir data\ohlcv
echo if not exist "data\news" mkdir data\news
echo if not exist "data\filings" mkdir data\filings
echo if not exist "data\ohlcv\1m" mkdir data\ohlcv\1m
echo if not exist "web\static" mkdir web\static
echo.
echo REM Start the application
echo echo ========================================
echo echo    STARTING NEUROTRADEAI PRODUCTION
echo echo ========================================
echo echo.
echo echo Dashboard: http://localhost:8000
echo echo API: http://localhost:8000/api/v1
echo echo.
echo echo Press Ctrl+C to stop the application
echo echo.
echo.
echo REM Start the application
echo python -m app.main
echo.
echo REM If we get here, the application has stopped
echo echo.
echo echo ========================================
echo echo    APPLICATION STOPPED
echo echo ========================================
echo echo.
echo echo Thank you for using NeuroTradeAI!
echo echo.
echo pause
) > "%PROD_DIR%\launcher.bat"

echo Production launcher created successfully
echo.

REM Create production directories
echo Creating production directories...
cd /d "%PROD_DIR%"
if not exist "logs" mkdir logs
if not exist "db" mkdir db
if not exist "data" mkdir data
if not exist "keys" mkdir keys
if not exist "data\ohlcv" mkdir data\ohlcv
if not exist "data\news" mkdir data\news
if not exist "data\filings" mkdir data\filings
if not exist "data\ohlcv\1m" mkdir data\ohlcv\1m
if not exist "web\static" mkdir web\static

echo Production directories created successfully
echo.

REM Set up production environment
echo Setting up production environment...
cd /d "%PROD_DIR%"

REM Create virtual environment
if not exist "venv" (
    echo Creating production virtual environment...
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
echo Installing production dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo Production dependencies installed successfully
echo.

REM Run tests
echo Running production tests...
python run_tests.py
if errorlevel 1 (
    echo WARNING: Some tests failed
    echo Please check the test output above
    echo.
)

echo.
echo ========================================
echo    DEPLOYMENT COMPLETED SUCCESSFULLY
echo ========================================
echo.
echo Production directory: %PROD_DIR%
echo Dashboard: http://localhost:8000
echo API: http://localhost:8000/api/v1
echo.
echo To start the production application:
echo 1. Navigate to: %PROD_DIR%
echo 2. Run: launcher.bat
echo.
echo To configure API keys:
echo 1. Open the dashboard
echo 2. Go to System Settings
echo 3. Add your API keys
echo.
pause
