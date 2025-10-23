"""
Base adapter interface for all data source connectors.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncio
import logging

logger = logging.getLogger(__name__)

class BaseAdapter(ABC):
    """Abstract base class for all data source adapters."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    @abstractmethod
    async def start(self) -> bool:
        """Start the adapter and begin data collection."""
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """Stop the adapter and clean up resources."""
        pass
    
    @abstractmethod
    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw data to canonical schema."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the adapter is healthy and can fetch data."""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the adapter."""
        return {
            "name": self.name,
            "is_running": self.is_running,
            "config": self.config,
            "task_running": self._task is not None and not self._task.done()
        }
    
    async def _run_forever(self):
        """Internal method to run adapter in background."""
        try:
            self.is_running = True
            logger.info(f"Started adapter: {self.name}")
            
            while not self._stop_event.is_set():
                try:
                    await self._fetch_data()
                    # Add a small delay to prevent overwhelming the WebSocket
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error in adapter {self.name}: {e}")
                    # Longer pause on error to prevent infinite loops
                    await asyncio.sleep(5)
                
                # Check if we should stop
                if self._stop_event.is_set():
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"Adapter {self.name} was cancelled")
        except Exception as e:
            logger.error(f"Fatal error in adapter {self.name}: {e}")
        finally:
            self.is_running = False
            logger.info(f"Stopped adapter: {self.name}")
    
    @abstractmethod
    async def _fetch_data(self):
        """Internal method to fetch data from the source."""
        pass
    
    async def _start_background_task(self):
        """Start the background data fetching task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_forever())
    
    async def _stop_background_task(self):
        """Stop the background data fetching task."""
        if self._task and not self._task.done():
            self._stop_event.set()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


class WebSocketAdapter(BaseAdapter):
    """Base class for WebSocket-based adapters."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.websocket = None
        self.connection_url = config.get('websocket_url')
        
    async def start(self) -> bool:
        """Start WebSocket connection."""
        try:
            import websockets
            self.websocket = await websockets.connect(self.connection_url)
            await self._start_background_task()
            return True
        except Exception as e:
            logger.error(f"Failed to start WebSocket adapter {self.name}: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop WebSocket connection."""
        try:
            await self._stop_background_task()
            if self.websocket:
                await self.websocket.close()
            return True
        except Exception as e:
            logger.error(f"Error stopping WebSocket adapter {self.name}: {e}")
            return False
    
    async def _fetch_data(self):
        """Fetch data from WebSocket."""
        if self.websocket:
            try:
                # Use a timeout to prevent hanging
                message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                data = await self._process_websocket_message(message)
                if data:
                    await self._handle_data(data)
            except asyncio.TimeoutError:
                # Timeout is normal, just continue
                pass
            except Exception as e:
                if "ConnectionClosed" in str(type(e)) or "ConnectionClosed" in str(e):
                    logger.warning(f"WebSocket connection closed for {self.name}")
                    self._stop_event.set()
                elif "cannot call recv while another coroutine is already running" in str(e):
                    # This is the specific error we're seeing - stop the adapter
                    logger.error(f"WebSocket concurrency error in {self.name}, stopping adapter")
                    self._stop_event.set()
                else:
                    logger.error(f"Error processing WebSocket message: {e}")
    
    @abstractmethod
    async def _process_websocket_message(self, message: str) -> Optional[Dict[str, Any]]:
        """Process incoming WebSocket message."""
        pass
    
    @abstractmethod
    async def _handle_data(self, data: Dict[str, Any]):
        """Handle processed data."""
        pass


class RESTAdapter(BaseAdapter):
    """Base class for REST API-based adapters."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.base_url = config.get('base_url')
        self.api_key = config.get('api_key')
        self.session = None
        
    async def start(self) -> bool:
        """Start REST adapter."""
        try:
            import aiohttp
            self.session = aiohttp.ClientSession()
            await self._start_background_task()
            return True
        except Exception as e:
            logger.error(f"Failed to start REST adapter {self.name}: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop REST adapter."""
        try:
            await self._stop_background_task()
            if self.session:
                await self.session.close()
            return True
        except Exception as e:
            logger.error(f"Error stopping REST adapter {self.name}: {e}")
            return False
    
    async def _fetch_data(self):
        """Fetch data from REST API."""
        # This will be implemented by subclasses
        pass
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Make HTTP request to API endpoint."""
        if not self.session:
            return None
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if params is None:
            params = {}
        
        if self.api_key:
            params['token'] = self.api_key
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"HTTP {response.status} from {url}")
                    return None
        except Exception as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
