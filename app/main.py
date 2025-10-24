"""
Main application entry point for the trading data scraper.
Starts FastAPI server and background data ingestion workers.
"""
import asyncio
import logging
import signal
import sys
import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from app.config import API_HOST, API_PORT, LOG_PATH, KEYS_PATH, RATE_LIMITS, DATA_PATH, DB_PATH
from app.api.routes import router
from app.api.websocket import websocket_endpoint, manager
from app.api.key_management import router as key_router, set_vault
from app.core.rate_limiter import setup_rate_limiters
from app.security.vault import setup_vault_interactive
from app.adapters.finnhub import FinnhubAdapter
from app.adapters.news import NewsAdapter
from app.adapters.edgar import EdgarAdapter

# Configure logging
# Ensure log directory exists
os.makedirs(LOG_PATH, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{LOG_PATH}/scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Global variables for background tasks
background_tasks = []
adapters = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting NeuroTradeAI Data Scraper...")
    
    # Setup credential vault
    # Skip vault setup in test environment
    if os.getenv("TESTING") == "true":
        vault = None
        logger.info("Skipping vault setup in test environment")
    else:
        vault = setup_vault_interactive(KEYS_PATH)
        if not vault:
            logger.error("Failed to setup credential vault")
            sys.exit(1)
    
    # Set vault for key management API
    set_vault(vault)
    
    # Setup rate limiters
    setup_rate_limiters(RATE_LIMITS)
    logger.info("Rate limiters configured")
    
    # Initialize storage and database
    from app.core.storage import StorageManager
    storage = StorageManager(DATA_PATH, DB_PATH)
    logger.info("Storage manager initialized")
    
    # Initialize adapters
    await initialize_adapters(vault)
    
    # Start background tasks
    await start_background_tasks()
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Stop background tasks
    await stop_background_tasks()
    
    # Stop adapters
    await stop_adapters()
    
    logger.info("Application shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="NeuroTradeAI Data Scraper",
    description="Real-time trading data ingestion and query API",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(router, prefix="/api/v1")
app.include_router(key_router, prefix="/api/v1")

# Include trading and backtesting routes
from app.api.trading_routes import router as trading_router
from app.api.backtest_routes import router as backtest_router
app.include_router(trading_router, prefix="")
app.include_router(backtest_router, prefix="")

# Add WebSocket endpoint
app.add_api_websocket_route("/stream", websocket_endpoint)

# Serve static files (create directory if it doesn't exist)
import os
static_dir = "web/static"
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
    # Create a simple index file if directory is empty
    if not os.listdir(static_dir):
        with open(os.path.join(static_dir, "index.html"), "w") as f:
            f.write("<!-- Static files directory -->")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard."""
    return FileResponse("web/index.html")

async def initialize_adapters(vault):
    """Initialize data source adapters."""
    try:
        # Get API keys from vault
        finnhub_key = vault.get_api_key("finnhub")
        
        if finnhub_key:
            # Initialize Finnhub adapter
            finnhub_config = {
                "api_key": finnhub_key,
                "websocket_url": f"wss://ws.finnhub.io?token={finnhub_key}",
                "base_url": "https://finnhub.io/api/v1",
                "watchlist": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]  # Default watchlist
            }
            
            adapters["finnhub"] = FinnhubAdapter("finnhub", finnhub_config)
            logger.info("Finnhub adapter initialized")
            
            # Initialize News adapter (uses same Finnhub API key)
            news_config = {
                "api_key": finnhub_key,
                "base_url": "https://finnhub.io/api/v1",
                "watchlist": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
                "polling_interval": 300  # 5 minutes
            }
            
            adapters["news"] = NewsAdapter("news", news_config)
            logger.info("News adapter initialized")
            
            # Initialize EDGAR adapter (no API key required)
            edgar_config = {
                "storage": storage,
                "rate_limiter": rate_limiter,
                "watchlist": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
                "polling_interval": 21600  # 6 hours
            }
            
            adapters["edgar"] = EdgarAdapter("edgar", edgar_config)
            logger.info("EDGAR adapter initialized")
        else:
            logger.warning("No Finnhub API key found in vault")
        
        # Add other adapters here as they are implemented
        
    except Exception as e:
        logger.error(f"Error initializing adapters: {e}")

async def start_background_tasks():
    """Start background data ingestion tasks."""
    try:
        # Start adapters
        for name, adapter in adapters.items():
            if await adapter.start():
                logger.info(f"Started adapter: {name}")
                background_tasks.append(asyncio.create_task(adapter._run_forever()))
            else:
                logger.error(f"Failed to start adapter: {name}")
        
        # Start other background tasks here
        
    except Exception as e:
        logger.error(f"Error starting background tasks: {e}")

async def stop_background_tasks():
    """Stop background tasks."""
    try:
        # Cancel all background tasks
        for task in background_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        
        background_tasks.clear()
        logger.info("Background tasks stopped")
        
    except Exception as e:
        logger.error(f"Error stopping background tasks: {e}")

async def stop_adapters():
    """Stop all adapters."""
    try:
        for name, adapter in adapters.items():
            await adapter.stop()
            logger.info(f"Stopped adapter: {name}")
        
        adapters.clear()
        
    except Exception as e:
        logger.error(f"Error stopping adapters: {e}")

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Main entry point."""
    # Setup signal handlers
    setup_signal_handlers()
    
    # Start the server
    logger.info(f"Starting server on {API_HOST}:{API_PORT}")
    
    uvicorn.run(
        "app.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
