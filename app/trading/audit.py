"""
Immutable audit logging system for trading decisions.
Provides append-only logging with session replay capability.
"""
import asyncio
import json
import gzip
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import hashlib
import uuid

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_REJECTED = "signal_rejected"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    RISK_CHECK = "risk_check"
    FEATURE_COMPUTED = "feature_computed"
    STRATEGY_CHANGED = "strategy_changed"
    TRADING_STARTED = "trading_started"
    TRADING_STOPPED = "trading_stopped"
    EMERGENCY_STOP = "emergency_stop"
    SYSTEM_ERROR = "system_error"


class AuditEvent:
    """Immutable audit event."""
    
    def __init__(
        self,
        event_type: AuditEventType,
        session_id: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ):
        self.id = str(uuid.uuid4())
        self.event_type = event_type
        self.session_id = session_id
        self.data = data.copy()  # Make a copy to prevent modification
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate hash for integrity verification."""
        content = {
            "id": self.id,
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "hash": self.hash
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def verify_integrity(self) -> bool:
        """Verify event integrity using hash."""
        return self.hash == self._calculate_hash()


class AuditLogger:
    """
    Immutable audit logging system.
    
    Features:
    - Append-only logging (no modifications)
    - Compressed daily log files
    - Hash-based integrity verification
    - Session replay capability
    - Event filtering and search
    """
    
    def __init__(self, log_dir: str = "logs/audit"):
        """Initialize audit logger."""
        self.log_dir = log_dir
        self.current_session_id = None
        self.daily_logs = {}
        
        # Create log directory
        os.makedirs(log_dir, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup audit logging."""
        try:
            # Create audit logger
            self.audit_logger = logging.getLogger('trading_audit')
            self.audit_logger.setLevel(logging.INFO)
            self.audit_logger.propagate = False
            
            # Create formatter
            formatter = logging.Formatter('%(message)s')
            
            # Add console handler for debugging
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.audit_logger.addHandler(console_handler)
            
        except Exception as e:
            logger.error(f"Failed to setup audit logging: {e}")
            self.audit_logger = None
    
    def set_session_id(self, session_id: str):
        """Set current trading session ID."""
        self.current_session_id = session_id
    
    async def log_event(
        self,
        event_type: AuditEventType,
        data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> str:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            data: Event data
            session_id: Trading session ID
            
        Returns:
            Event ID
        """
        try:
            session_id = session_id or self.current_session_id
            if not session_id:
                raise ValueError("No session ID provided")
            
            # Create audit event
            event = AuditEvent(event_type, session_id, data)
            
            # Write to daily log file
            await self._write_to_daily_log(event)
            
            # Log to console for debugging
            if self.audit_logger:
                self.audit_logger.info(f"AUDIT: {event_type.value} - {event.id}")
            
            return event.id
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            raise
    
    async def _write_to_daily_log(self, event: AuditEvent):
        """Write event to daily compressed log file."""
        try:
            date_str = event.timestamp.strftime("%Y%m%d")
            log_file = os.path.join(self.log_dir, f"trading_audit_{date_str}.jsonl.gz")
            
            # Create event line
            event_line = json.dumps(event.to_dict()) + "\n"
            
            # Append to compressed file
            with gzip.open(log_file, 'at', encoding='utf-8') as f:
                f.write(event_line)
                
        except Exception as e:
            logger.error(f"Failed to write to daily log: {e}")
            raise
    
    async def log_signal(self, signal: Dict[str, Any]):
        """Log signal generation."""
        await self.log_event(
            AuditEventType.SIGNAL_GENERATED,
            {
                "signal": signal,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_signal_rejection(self, signal: Dict[str, Any], reason: str):
        """Log signal rejection."""
        await self.log_event(
            AuditEventType.SIGNAL_REJECTED,
            {
                "signal": signal,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_order(self, order: Dict[str, Any]):
        """Log order placement."""
        await self.log_event(
            AuditEventType.ORDER_PLACED,
            {
                "order": order,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_order_fill(self, order_id: str, fill_data: Dict[str, Any]):
        """Log order fill."""
        await self.log_event(
            AuditEventType.ORDER_FILLED,
            {
                "order_id": order_id,
                "fill_data": fill_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_order_cancellation(self, order_id: str, reason: str):
        """Log order cancellation."""
        await self.log_event(
            AuditEventType.ORDER_CANCELLED,
            {
                "order_id": order_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_order_rejection(self, order_id: str, reason: str):
        """Log order rejection."""
        await self.log_event(
            AuditEventType.ORDER_REJECTED,
            {
                "order_id": order_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_position_opened(self, position: Dict[str, Any]):
        """Log position opening."""
        await self.log_event(
            AuditEventType.POSITION_OPENED,
            {
                "position": position,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_position_closed(self, position: Dict[str, Any], reason: str):
        """Log position closing."""
        await self.log_event(
            AuditEventType.POSITION_CLOSED,
            {
                "position": position,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_risk_check(
        self,
        check_type: str,
        result: bool,
        details: Dict[str, Any]
    ):
        """Log risk check."""
        await self.log_event(
            AuditEventType.RISK_CHECK,
            {
                "check_type": check_type,
                "result": result,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_feature_computation(
        self,
        symbol: str,
        features: Dict[str, Any],
        computation_time: float
    ):
        """Log feature computation."""
        await self.log_event(
            AuditEventType.FEATURE_COMPUTED,
            {
                "symbol": symbol,
                "features": features,
                "computation_time": computation_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_strategy_change(self, old_strategy: str, new_strategy: str):
        """Log strategy change."""
        await self.log_event(
            AuditEventType.STRATEGY_CHANGED,
            {
                "old_strategy": old_strategy,
                "new_strategy": new_strategy,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_trading_start(self, mode: str, strategy: str):
        """Log trading start."""
        await self.log_event(
            AuditEventType.TRADING_STARTED,
            {
                "mode": mode,
                "strategy": strategy,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_trading_stop(self, reason: str):
        """Log trading stop."""
        await self.log_event(
            AuditEventType.TRADING_STOPPED,
            {
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_emergency_stop(self, reason: str):
        """Log emergency stop."""
        await self.log_event(
            AuditEventType.EMERGENCY_STOP,
            {
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def log_system_error(self, component: str, error: str, data: Dict[str, Any]):
        """Log system error."""
        await self.log_event(
            AuditEventType.SYSTEM_ERROR,
            {
                "component": component,
                "error": error,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    def get_session_events(
        self,
        session_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get all events for a session."""
        events = []
        
        try:
            # Get date range
            if start_date:
                start_str = start_date.strftime("%Y%m%d")
            else:
                start_str = "00000000"
            
            if end_date:
                end_str = end_date.strftime("%Y%m%d")
            else:
                end_str = "99999999"
            
            # Read daily log files
            for filename in os.listdir(self.log_dir):
                if filename.startswith("trading_audit_") and filename.endswith(".jsonl.gz"):
                    date_str = filename[14:22]  # Extract date from filename
                    if start_str <= date_str <= end_str:
                        file_path = os.path.join(self.log_dir, filename)
                        events.extend(self._read_log_file(file_path, session_id))
            
            # Sort by timestamp
            events.sort(key=lambda x: x['timestamp'])
            return events
            
        except Exception as e:
            logger.error(f"Failed to get session events: {e}")
            return []
    
    def _read_log_file(self, file_path: str, session_id: str) -> List[Dict[str, Any]]:
        """Read events from a log file."""
        events = []
        
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        event = json.loads(line)
                        if event.get('session_id') == session_id:
                            events.append(event)
        except Exception as e:
            logger.error(f"Failed to read log file {file_path}: {e}")
        
        return events
    
    def get_events_by_type(
        self,
        event_type: AuditEventType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get events by type."""
        events = []
        
        try:
            # Get date range
            if start_date:
                start_str = start_date.strftime("%Y%m%d")
            else:
                start_str = "00000000"
            
            if end_date:
                end_str = end_date.strftime("%Y%m%d")
            else:
                end_str = "99999999"
            
            # Read daily log files
            for filename in os.listdir(self.log_dir):
                if filename.startswith("trading_audit_") and filename.endswith(".jsonl.gz"):
                    date_str = filename[14:22]  # Extract date from filename
                    if start_str <= date_str <= end_str:
                        file_path = os.path.join(self.log_dir, filename)
                        events.extend(self._read_log_file_by_type(file_path, event_type))
            
            # Sort by timestamp
            events.sort(key=lambda x: x['timestamp'])
            return events
            
        except Exception as e:
            logger.error(f"Failed to get events by type: {e}")
            return []
    
    def _read_log_file_by_type(
        self,
        file_path: str,
        event_type: AuditEventType
    ) -> List[Dict[str, Any]]:
        """Read events of specific type from a log file."""
        events = []
        
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        event = json.loads(line)
                        if event.get('event_type') == event_type.value:
                            events.append(event)
        except Exception as e:
            logger.error(f"Failed to read log file {file_path}: {e}")
        
        return events
    
    def verify_session_integrity(self, session_id: str) -> Dict[str, Any]:
        """Verify integrity of all events in a session."""
        events = self.get_session_events(session_id)
        
        integrity_report = {
            "session_id": session_id,
            "total_events": len(events),
            "valid_events": 0,
            "invalid_events": 0,
            "invalid_event_ids": [],
            "timestamp_range": {
                "start": None,
                "end": None
            }
        }
        
        if not events:
            return integrity_report
        
        # Check timestamp range
        timestamps = [event['timestamp'] for event in events]
        integrity_report['timestamp_range']['start'] = min(timestamps)
        integrity_report['timestamp_range']['end'] = max(timestamps)
        
        # Verify each event
        for event in events:
            try:
                # Recreate event object for verification
                audit_event = AuditEvent(
                    AuditEventType(event['event_type']),
                    event['session_id'],
                    event['data'],
                    datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                )
                audit_event.id = event['id']
                audit_event.hash = event['hash']
                
                if audit_event.verify_integrity():
                    integrity_report['valid_events'] += 1
                else:
                    integrity_report['invalid_events'] += 1
                    integrity_report['invalid_event_ids'].append(event['id'])
                    
            except Exception as e:
                logger.error(f"Failed to verify event {event.get('id', 'unknown')}: {e}")
                integrity_report['invalid_events'] += 1
                integrity_report['invalid_event_ids'].append(event.get('id', 'unknown'))
        
        return integrity_report