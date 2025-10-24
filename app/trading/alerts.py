"""
Multi-channel alert system for trading events.
Provides desktop notifications, log alerts, and WebSocket push notifications.
"""
import asyncio
import logging
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum
import os
import platform

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of trading alerts."""
    RISK_LIMIT_BREACH = "risk_limit_breach"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    ORDER_REJECTED = "order_rejected"
    CONNECTION_LOST = "connection_lost"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    SIGNAL_GENERATED = "signal_generated"
    TRADING_STARTED = "trading_started"
    TRADING_STOPPED = "trading_stopped"
    EMERGENCY_STOP = "emergency_stop"
    SYSTEM_ERROR = "system_error"


class Alert:
    """Alert data structure."""
    
    def __init__(
        self,
        alert_type: AlertType,
        level: AlertLevel,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        self.alert_type = alert_type
        self.level = level
        self.title = title
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.now(timezone.utc)
        self.id = f"{alert_type.value}_{int(self.timestamp.timestamp())}"
        self.hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate hash for integrity verification."""
        content = {
            "id": self.id,
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "type": self.alert_type.value,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "hash": self.hash
        }
    
    def to_json(self) -> str:
        """Convert alert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class AlertManager:
    """
    Multi-channel alert manager for trading system.
    
    Channels:
    - Desktop notifications (cross-platform)
    - Log file alerts
    - WebSocket push to dashboard
    - Console output
    """
    
    def __init__(self, log_file: str = "logs/trading_alerts.log"):
        """Initialize alert manager."""
        self.log_file = log_file
        self.websocket_clients = set()
        self.alert_history = []
        self.max_history = 1000
        
        # Setup log file
        self._setup_logging()
        
        # Setup desktop notifications
        self._setup_desktop_notifications()
    
    def _setup_logging(self):
        """Setup alert logging to file."""
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            
            # Create file handler for alerts
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            
            # Create alert logger
            self.alert_logger = logging.getLogger('trading_alerts')
            self.alert_logger.setLevel(logging.INFO)
            self.alert_logger.addHandler(file_handler)
            self.alert_logger.propagate = False
            
        except Exception as e:
            logger.error(f"Failed to setup alert logging: {e}")
            self.alert_logger = None
    
    def _setup_desktop_notifications(self):
        """Setup desktop notification system."""
        self.desktop_notifications = False
        
        try:
            if platform.system() == "Windows":
                import win10toast
                self.toaster = win10toast.ToastNotifier()
                self.desktop_notifications = True
            elif platform.system() == "Darwin":  # macOS
                # Use osascript for macOS notifications
                self.desktop_notifications = True
            elif platform.system() == "Linux":
                # Try to use notify-send
                import subprocess
                subprocess.run(["which", "notify-send"], check=True)
                self.desktop_notifications = True
        except Exception as e:
            logger.warning(f"Desktop notifications not available: {e}")
            self.desktop_notifications = False
    
    async def send_alert(
        self,
        alert_type: AlertType,
        level: AlertLevel,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send alert through all available channels.
        
        Args:
            alert_type: Type of alert
            level: Severity level
            title: Alert title
            message: Alert message
            data: Additional data
            
        Returns:
            True if alert was sent successfully
        """
        try:
            # Create alert
            alert = Alert(alert_type, level, title, message, data)
            
            # Add to history
            self.alert_history.append(alert)
            if len(self.alert_history) > self.max_history:
                self.alert_history.pop(0)
            
            # Send through all channels
            success = True
            
            # 1. Log to file
            success &= await self._log_alert(alert)
            
            # 2. Desktop notification
            success &= await self._send_desktop_notification(alert)
            
            # 3. WebSocket broadcast
            success &= await self._broadcast_websocket(alert)
            
            # 4. Console output for critical alerts
            if level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
                print(f"🚨 {level.value.upper()}: {title} - {message}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
    
    async def _log_alert(self, alert: Alert) -> bool:
        """Log alert to file."""
        try:
            if self.alert_logger:
                log_message = f"{alert.title}: {alert.message}"
                if alert.data:
                    log_message += f" | Data: {json.dumps(alert.data)}"
                
                self.alert_logger.info(log_message)
            return True
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")
            return False
    
    async def _send_desktop_notification(self, alert: Alert) -> bool:
        """Send desktop notification."""
        try:
            if not self.desktop_notifications:
                return True
            
            if platform.system() == "Windows" and hasattr(self, 'toaster'):
                self.toaster.show_toast(
                    alert.title,
                    alert.message,
                    duration=10,
                    threaded=True
                )
            elif platform.system() == "Darwin":
                # macOS notification
                import subprocess
                subprocess.run([
                    "osascript", "-e",
                    f'display notification "{alert.message}" with title "{alert.title}"'
                ])
            elif platform.system() == "Linux":
                # Linux notification
                import subprocess
                subprocess.run([
                    "notify-send",
                    "-t", "10000",
                    alert.title,
                    alert.message
                ])
            
            return True
        except Exception as e:
            logger.error(f"Failed to send desktop notification: {e}")
            return False
    
    async def _broadcast_websocket(self, alert: Alert) -> bool:
        """Broadcast alert via WebSocket."""
        try:
            if not self.websocket_clients:
                return True
            
            message = {
                "type": "alert",
                "data": alert.to_dict()
            }
            
            # Broadcast to all connected clients
            disconnected_clients = set()
            for client in self.websocket_clients:
                try:
                    await client.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"Failed to send WebSocket alert: {e}")
                    disconnected_clients.add(client)
            
            # Remove disconnected clients
            self.websocket_clients -= disconnected_clients
            
            return True
        except Exception as e:
            logger.error(f"Failed to broadcast WebSocket alert: {e}")
            return False
    
    def add_websocket_client(self, client):
        """Add WebSocket client for real-time alerts."""
        self.websocket_clients.add(client)
    
    def remove_websocket_client(self, client):
        """Remove WebSocket client."""
        self.websocket_clients.discard(client)
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        recent = self.alert_history[-limit:] if self.alert_history else []
        return [alert.to_dict() for alert in recent]
    
    def get_alerts_by_type(self, alert_type: AlertType) -> List[Dict[str, Any]]:
        """Get alerts by type."""
        filtered = [alert for alert in self.alert_history if alert.alert_type == alert_type]
        return [alert.to_dict() for alert in filtered]
    
    def get_alerts_by_level(self, level: AlertLevel) -> List[Dict[str, Any]]:
        """Get alerts by severity level."""
        filtered = [alert for alert in self.alert_history if alert.level == level]
        return [alert.to_dict() for alert in filtered]
    
    async def send_risk_alert(
        self,
        risk_type: str,
        current_value: float,
        limit_value: float,
        symbol: Optional[str] = None
    ):
        """Send risk limit breach alert."""
        title = f"Risk Limit Breach: {risk_type}"
        message = f"Current: {current_value:.2f}, Limit: {limit_value:.2f}"
        if symbol:
            message += f" (Symbol: {symbol})"
        
        await self.send_alert(
            AlertType.RISK_LIMIT_BREACH,
            AlertLevel.WARNING,
            title,
            message,
            {
                "risk_type": risk_type,
                "current_value": current_value,
                "limit_value": limit_value,
                "symbol": symbol
            }
        )
    
    async def send_daily_loss_alert(
        self,
        current_loss: float,
        loss_limit: float,
        loss_pct: float
    ):
        """Send daily loss limit alert."""
        title = "Daily Loss Limit Reached"
        message = f"Daily loss: ${current_loss:.2f} ({loss_pct:.1f}%) - Limit: ${loss_limit:.2f}"
        
        await self.send_alert(
            AlertType.DAILY_LOSS_LIMIT,
            AlertLevel.CRITICAL,
            title,
            message,
            {
                "current_loss": current_loss,
                "loss_limit": loss_limit,
                "loss_pct": loss_pct
            }
        )
    
    async def send_order_alert(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        status: str,
        reason: Optional[str] = None
    ):
        """Send order-related alert."""
        if status == "rejected":
            alert_type = AlertType.ORDER_REJECTED
            level = AlertLevel.WARNING
            title = f"Order Rejected: {symbol}"
            message = f"{side.upper()} {quantity} {symbol} - Reason: {reason or 'Unknown'}"
        else:
            alert_type = AlertType.POSITION_OPENED if side == "buy" else AlertType.POSITION_CLOSED
            level = AlertLevel.INFO
            title = f"Order {status.title()}: {symbol}"
            message = f"{side.upper()} {quantity} {symbol} - Status: {status}"
        
        await self.send_alert(
            alert_type,
            level,
            title,
            message,
            {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "status": status,
                "reason": reason
            }
        )
    
    async def send_system_alert(
        self,
        component: str,
        error: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Send system error alert."""
        title = f"System Error: {component}"
        message = f"Error in {component}: {error}"
        
        alert_data = {
            "component": component,
            "error": error
        }
        if data:
            alert_data.update(data)
        
        await self.send_alert(
            AlertType.SYSTEM_ERROR,
            AlertLevel.ERROR,
            title,
            message,
            alert_data
        )
    
    async def send_emergency_stop_alert(self, reason: str):
        """Send emergency stop alert."""
        title = "EMERGENCY STOP ACTIVATED"
        message = f"Trading stopped immediately: {reason}"
        
        await self.send_alert(
            AlertType.EMERGENCY_STOP,
            AlertLevel.CRITICAL,
            title,
            message,
            {"reason": reason}
        )