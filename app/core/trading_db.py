"""
Database extensions for trading system.
Adds trading-specific tables to the existing SQLite database.
"""
import sqlite3
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import json
import uuid

logger = logging.getLogger(__name__)


class TradingDatabase:
    """
    Database manager for trading system.
    
    Manages:
    - Trading sessions
    - Orders and order events
    - Positions
    - Backtest results
    - Audit trail
    """
    
    def __init__(self, db_path: str):
        """
        Initialize trading database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    def initialize_tables(self):
        """Create trading tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Trading sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trading_sessions (
                        id TEXT PRIMARY KEY,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        mode TEXT NOT NULL, -- 'paper' or 'live'
                        strategy_name TEXT,
                        initial_balance REAL NOT NULL,
                        final_balance REAL,
                        total_trades INTEGER DEFAULT 0,
                        pnl REAL DEFAULT 0.0,
                        max_drawdown REAL DEFAULT 0.0,
                        win_rate REAL DEFAULT 0.0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                # Orders table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id TEXT PRIMARY KEY,
                        session_id TEXT,
                        client_order_id TEXT,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL, -- 'buy' or 'sell'
                        order_type TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        filled_quantity REAL DEFAULT 0.0,
                        remaining_quantity REAL NOT NULL,
                        status TEXT NOT NULL,
                        time_in_force TEXT NOT NULL,
                        limit_price REAL,
                        stop_price REAL,
                        trail_price REAL,
                        trail_percent REAL,
                        average_fill_price REAL,
                        commission REAL DEFAULT 0.0,
                        submitted_at TEXT,
                        filled_at TEXT,
                        cancelled_at TEXT,
                        rejected_at TEXT,
                        cancel_reason TEXT,
                        signal_reason TEXT,
                        strategy_name TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES trading_sessions (id)
                    )
                """)
                
                # Order events table (for order lifecycle tracking)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS order_events (
                        id TEXT PRIMARY KEY,
                        order_id TEXT NOT NULL,
                        event_type TEXT NOT NULL, -- 'submitted', 'filled', 'cancelled', 'rejected'
                        event_data TEXT, -- JSON data
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (order_id) REFERENCES orders (id)
                    )
                """)
                
                # Positions table (current positions)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS positions (
                        id TEXT PRIMARY KEY,
                        session_id TEXT,
                        symbol TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        side TEXT NOT NULL, -- 'long' or 'short'
                        entry_price REAL NOT NULL,
                        current_price REAL,
                        market_value REAL,
                        cost_basis REAL,
                        unrealized_pl REAL,
                        unrealized_plpc REAL,
                        stop_loss REAL,
                        take_profit REAL,
                        entry_time TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES trading_sessions (id)
                    )
                """)
                
                # Backtest results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS backtests (
                        id TEXT PRIMARY KEY,
                        strategy_name TEXT NOT NULL,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        symbols TEXT NOT NULL, -- JSON array
                        parameters TEXT, -- JSON object
                        initial_balance REAL NOT NULL,
                        final_balance REAL NOT NULL,
                        total_return REAL NOT NULL,
                        total_return_pct REAL NOT NULL,
                        sharpe_ratio REAL,
                        max_drawdown REAL,
                        max_drawdown_pct REAL,
                        win_rate REAL,
                        profit_factor REAL,
                        total_trades INTEGER,
                        avg_trade_duration REAL,
                        created_at TEXT NOT NULL
                    )
                """)
                
                # Audit trail table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_trail (
                        id TEXT PRIMARY KEY,
                        session_id TEXT,
                        event_type TEXT NOT NULL, -- 'signal', 'order', 'position', 'risk'
                        event_data TEXT NOT NULL, -- JSON data
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES trading_sessions (id)
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_session_id ON orders (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders (symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_events_order_id ON order_events (order_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_events_timestamp ON order_events (timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_session_id ON positions (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions (symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_session_id ON audit_trail (session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_timestamp ON audit_trail (timestamp)")
                
                conn.commit()
                self.logger.info("Trading database tables initialized successfully")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing trading database: {e}")
            raise
    
    def create_session(
        self,
        mode: str,
        strategy_name: str,
        initial_balance: float
    ) -> str:
        """
        Create a new trading session.
        
        Args:
            mode: Trading mode ('paper' or 'live')
            strategy_name: Name of the strategy
            initial_balance: Starting balance
            
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO trading_sessions (
                        id, start_time, mode, strategy_name, initial_balance,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_id, now, mode, strategy_name, initial_balance, now, now))
                conn.commit()
                
            self.logger.info(f"Created trading session {session_id} ({mode}, {strategy_name})")
            return session_id
            
        except sqlite3.Error as e:
            self.logger.error(f"Error creating trading session: {e}")
            raise
    
    def end_session(
        self,
        session_id: str,
        final_balance: float,
        total_trades: int,
        pnl: float,
        max_drawdown: float,
        win_rate: float
    ) -> bool:
        """
        End a trading session.
        
        Args:
            session_id: Session ID
            final_balance: Final account balance
            total_trades: Total number of trades
            pnl: Total P&L
            max_drawdown: Maximum drawdown
            win_rate: Win rate percentage
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE trading_sessions SET
                        end_time = ?,
                        final_balance = ?,
                        total_trades = ?,
                        pnl = ?,
                        max_drawdown = ?,
                        win_rate = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    datetime.now(timezone.utc).isoformat(),
                    final_balance,
                    total_trades,
                    pnl,
                    max_drawdown,
                    win_rate,
                    datetime.now(timezone.utc).isoformat(),
                    session_id
                ))
                conn.commit()
                
            self.logger.info(f"Ended trading session {session_id}")
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Error ending trading session: {e}")
            return False
    
    def add_order(
        self,
        session_id: str,
        order_id: str,
        client_order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        time_in_force: str,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        trail_price: Optional[float] = None,
        trail_percent: Optional[float] = None,
        signal_reason: Optional[str] = None,
        strategy_name: Optional[str] = None
    ) -> bool:
        """
        Add a new order to the database.
        
        Args:
            session_id: Trading session ID
            order_id: Order ID
            client_order_id: Client order ID
            symbol: Stock symbol
            side: Order side ('buy' or 'sell')
            order_type: Order type
            quantity: Order quantity
            time_in_force: Time in force
            limit_price: Limit price (optional)
            stop_price: Stop price (optional)
            trail_price: Trail price (optional)
            trail_percent: Trail percentage (optional)
            signal_reason: Signal reasoning (optional)
            strategy_name: Strategy name (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO orders (
                        id, session_id, client_order_id, symbol, side, order_type,
                        quantity, remaining_quantity, status, time_in_force,
                        limit_price, stop_price, trail_price, trail_percent,
                        signal_reason, strategy_name, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_id, session_id, client_order_id, symbol, side, order_type,
                    quantity, quantity, 'pending', time_in_force,
                    limit_price, stop_price, trail_price, trail_percent,
                    signal_reason, strategy_name,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()
                
            self.logger.debug(f"Added order {order_id} to database")
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Error adding order: {e}")
            return False
    
    def update_order(
        self,
        order_id: str,
        status: str,
        filled_quantity: Optional[float] = None,
        remaining_quantity: Optional[float] = None,
        average_fill_price: Optional[float] = None,
        commission: Optional[float] = None,
        cancel_reason: Optional[str] = None
    ) -> bool:
        """
        Update order status and details.
        
        Args:
            order_id: Order ID
            status: New status
            filled_quantity: Filled quantity (optional)
            remaining_quantity: Remaining quantity (optional)
            average_fill_price: Average fill price (optional)
            commission: Commission (optional)
            cancel_reason: Cancel reason (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build update query dynamically
                updates = ["status = ?", "updated_at = ?"]
                values = [status, datetime.now(timezone.utc).isoformat()]
                
                if filled_quantity is not None:
                    updates.append("filled_quantity = ?")
                    values.append(filled_quantity)
                
                if remaining_quantity is not None:
                    updates.append("remaining_quantity = ?")
                    values.append(remaining_quantity)
                
                if average_fill_price is not None:
                    updates.append("average_fill_price = ?")
                    values.append(average_fill_price)
                
                if commission is not None:
                    updates.append("commission = ?")
                    values.append(commission)
                
                if cancel_reason is not None:
                    updates.append("cancel_reason = ?")
                    values.append(cancel_reason)
                
                # Add timestamp fields based on status
                if status == 'submitted':
                    updates.append("submitted_at = ?")
                    values.append(datetime.now(timezone.utc).isoformat())
                elif status == 'filled':
                    updates.append("filled_at = ?")
                    values.append(datetime.now(timezone.utc).isoformat())
                elif status == 'cancelled':
                    updates.append("cancelled_at = ?")
                    values.append(datetime.now(timezone.utc).isoformat())
                elif status == 'rejected':
                    updates.append("rejected_at = ?")
                    values.append(datetime.now(timezone.utc).isoformat())
                
                values.append(order_id)
                
                query = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, values)
                conn.commit()
                
            self.logger.debug(f"Updated order {order_id} status to {status}")
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Error updating order: {e}")
            return False
    
    def add_order_event(
        self,
        order_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> bool:
        """
        Add an order event to the audit trail.
        
        Args:
            order_id: Order ID
            event_type: Event type
            event_data: Event data dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO order_events (
                        id, order_id, event_type, event_data, timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    order_id,
                    event_type,
                    json.dumps(event_data),
                    datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()
                
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Error adding order event: {e}")
            return False
    
    def update_position(
        self,
        session_id: str,
        symbol: str,
        quantity: float,
        side: str,
        entry_price: float,
        current_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Update position in database.
        
        Args:
            session_id: Trading session ID
            symbol: Stock symbol
            quantity: Position quantity
            side: Position side ('long' or 'short')
            entry_price: Entry price
            current_price: Current price (optional)
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if position exists
                cursor.execute("""
                    SELECT id FROM positions 
                    WHERE session_id = ? AND symbol = ?
                """, (session_id, symbol))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing position
                    cursor.execute("""
                        UPDATE positions SET
                            quantity = ?,
                            side = ?,
                            entry_price = ?,
                            current_price = ?,
                            stop_loss = ?,
                            take_profit = ?,
                            updated_at = ?
                        WHERE session_id = ? AND symbol = ?
                    """, (
                        quantity, side, entry_price, current_price,
                        stop_loss, take_profit,
                        datetime.now(timezone.utc).isoformat(),
                        session_id, symbol
                    ))
                else:
                    # Create new position
                    cursor.execute("""
                        INSERT INTO positions (
                            id, session_id, symbol, quantity, side, entry_price,
                            current_price, stop_loss, take_profit, entry_time, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()),
                        session_id, symbol, quantity, side, entry_price,
                        current_price, stop_loss, take_profit,
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat()
                    ))
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Error updating position: {e}")
            return False
    
    def get_session_orders(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all orders for a session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM orders WHERE session_id = ?
                    ORDER BY created_at DESC
                """, (session_id,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting session orders: {e}")
            return []
    
    def get_session_positions(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all positions for a session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM positions WHERE session_id = ?
                    ORDER BY updated_at DESC
                """, (session_id,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting session positions: {e}")
            return []
    
    def add_audit_event(
        self,
        session_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> bool:
        """
        Add audit event to trail.
        
        Args:
            session_id: Trading session ID
            event_type: Event type
            event_data: Event data dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_trail (
                        id, session_id, event_type, event_data, timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    session_id,
                    event_type,
                    json.dumps(event_data),
                    datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()
                
            return True
            
        except sqlite3.Error as e:
            self.logger.error(f"Error adding audit event: {e}")
            return False
    
    def get_audit_trail(
        self,
        session_id: str,
        event_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for a session.
        
        Args:
            session_id: Trading session ID
            event_type: Filter by event type (optional)
            limit: Maximum number of events (optional)
            
        Returns:
            List of audit events
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = "SELECT * FROM audit_trail WHERE session_id = ?"
                params = [session_id]
                
                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type)
                
                query += " ORDER BY timestamp DESC"
                
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting audit trail: {e}")
            return []
    
    def get_current_session_id(self) -> Optional[str]:
        """
        Get the current active session ID.
        
        Returns:
            Current session ID or None if no active session
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id FROM trading_sessions 
                    WHERE end_time IS NULL 
                    ORDER BY start_time DESC 
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                return result[0] if result else None
                
        except Exception as e:
            self.logger.error(f"Error getting current session ID: {e}")
            return None
    
    def update_order_status(self, order_id: str, status: str, filled_price: Optional[float] = None, filled_quantity: Optional[float] = None) -> bool:
        """
        Update order status.
        
        Args:
            order_id: Order ID
            status: New status
            filled_price: Filled price if filled
            filled_quantity: Filled quantity if filled
            
        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update order
                cursor.execute("""
                    UPDATE orders 
                    SET status = ?, average_fill_price = ?, filled_quantity = ?
                    WHERE id = ?
                """, (status, filled_price, filled_quantity, order_id))
                
                # Add order event
                self.add_order_event(
                    order_id,
                    status,
                    {"filled_price": filled_price, "filled_quantity": filled_quantity}
                )
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating order status: {e}")
            return False
