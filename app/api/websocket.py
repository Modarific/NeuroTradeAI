"""
WebSocket handler for real-time data streaming.
Provides live updates to connected clients.
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time data streaming."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, List[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return
        
        # Create a copy of the list to avoid modification during iteration
        connections = self.active_connections.copy()
        
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                self.disconnect(connection)
    
    async def broadcast_to_subscribers(self, data_type: str, message: str):
        """Broadcast a message to clients subscribed to a specific data type."""
        if not self.active_connections:
            return
        
        connections = self.active_connections.copy()
        
        for connection in connections:
            try:
                # Check if client is subscribed to this data type
                if connection in self.subscriptions and data_type in self.subscriptions[connection]:
                    await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to subscriber: {e}")
                self.disconnect(connection)
    
    def subscribe(self, websocket: WebSocket, data_type: str):
        """Subscribe a client to a specific data type."""
        if websocket in self.subscriptions:
            if data_type not in self.subscriptions[websocket]:
                self.subscriptions[websocket].append(data_type)
                logger.info(f"Client subscribed to {data_type}")
    
    def unsubscribe(self, websocket: WebSocket, data_type: str):
        """Unsubscribe a client from a specific data type."""
        if websocket in self.subscriptions:
            if data_type in self.subscriptions[websocket]:
                self.subscriptions[websocket].remove(data_type)
                logger.info(f"Client unsubscribed from {data_type}")
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)
    
    def get_subscription_stats(self) -> Dict[str, int]:
        """Get subscription statistics."""
        stats = {}
        for subscriptions in self.subscriptions.values():
            for data_type in subscriptions:
                stats[data_type] = stats.get(data_type, 0) + 1
        return stats

# Global connection manager
manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time data streaming.
    
    Expected message format:
    {
        "action": "subscribe|unsubscribe|ping",
        "data_type": "ohlcv|news|filings",
        "symbol": "AAPL" (optional, for symbol-specific subscriptions)
    }
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for message from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                action = message.get("action")
                data_type = message.get("data_type")
                symbol = message.get("symbol")
                
                if action == "subscribe":
                    if data_type:
                        manager.subscribe(websocket, data_type)
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "subscription_confirmed",
                                "data_type": data_type,
                                "symbol": symbol
                            }), 
                            websocket
                        )
                
                elif action == "unsubscribe":
                    if data_type:
                        manager.unsubscribe(websocket, data_type)
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "unsubscription_confirmed",
                                "data_type": data_type,
                                "symbol": symbol
                            }), 
                            websocket
                        )
                
                elif action == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong", "timestamp": "N/A"}), 
                        websocket
                    )
                
                else:
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": f"Unknown action: {action}"
                        }), 
                        websocket
                    )
                    
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }), 
                    websocket
                )
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def broadcast_ohlcv_update(symbol: str, data: Dict[str, Any]):
    """Broadcast OHLCV update to subscribed clients."""
    from datetime import datetime, timezone
    
    message = json.dumps({
        "type": "ohlcv_update",
        "symbol": symbol,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    await manager.broadcast_to_subscribers("ohlcv", message)
    logger.info(f"Broadcasted OHLCV update for {symbol}")

async def broadcast_news_update(news: Dict[str, Any]):
    """Broadcast news update to subscribed clients."""
    from datetime import datetime, timezone
    
    message = json.dumps({
        "type": "news_update",
        "data": news,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    await manager.broadcast_to_subscribers("news", message)
    logger.info(f"Broadcasted news update: {news.get('headline', 'Unknown')[:50]}...")

async def broadcast_filing_update(symbol: str, filing: Dict[str, Any]):
    """Broadcast filing update to subscribed clients."""
    message = json.dumps({
        "type": "filing_update",
        "symbol": symbol,
        "data": filing,
        "timestamp": "N/A"  # Would be current timestamp
    })
    
    await manager.broadcast_to_subscribers("filings", message)

async def broadcast_system_status(status: Dict[str, Any]):
    """Broadcast system status update to all clients."""
    message = json.dumps({
        "type": "system_status",
        "data": status,
        "timestamp": "N/A"  # Would be current timestamp
    })
    
    await manager.broadcast(message)

def get_connection_stats() -> Dict[str, Any]:
    """Get WebSocket connection statistics."""
    return {
        "active_connections": manager.get_connection_count(),
        "subscriptions": manager.get_subscription_stats()
    }
