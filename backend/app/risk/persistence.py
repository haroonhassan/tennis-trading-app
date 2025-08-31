"""Position persistence layer using SQLite."""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import logging

from app.risk.models import (
    Position, PositionStatus, PositionSide,
    RiskAlert, PositionUpdate
)

logger = logging.getLogger(__name__)


class PositionDatabase:
    """SQLite database for position persistence."""
    
    def __init__(self, db_path: str = "positions.db"):
        """Initialize database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        
        # Ensure database directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
    def connect(self):
        """Connect to database and create tables if needed."""
        try:
            self.conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            
            # Register adapters for Decimal
            sqlite3.register_adapter(Decimal, str)
            sqlite3.register_converter("DECIMAL", lambda v: Decimal(v.decode()))
            
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
            
            # Create tables
            self._create_tables()
            
            logger.info(f"Connected to position database: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
            
    def disconnect(self):
        """Disconnect from database."""
        if self.conn:
            self.conn.close()
            self.conn = None
            
    def _create_tables(self):
        """Create database tables."""
        # Positions table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                selection_id TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price DECIMAL NOT NULL,
                entry_size DECIMAL NOT NULL,
                entry_time TIMESTAMP NOT NULL,
                current_size DECIMAL NOT NULL,
                exit_price DECIMAL,
                exit_size DECIMAL DEFAULT 0,
                last_update TIMESTAMP NOT NULL,
                realized_pnl DECIMAL DEFAULT 0,
                unrealized_pnl DECIMAL DEFAULT 0,
                commission DECIMAL DEFAULT 0,
                status TEXT NOT NULL,
                provider TEXT NOT NULL,
                strategy TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_market ON positions(market_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_selection ON positions(market_id, selection_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON positions(status)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_time ON positions(entry_time)")
        
        # Position updates table (audit trail)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS position_updates (
                update_id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                update_type TEXT NOT NULL,
                size_change DECIMAL,
                price DECIMAL,
                pnl_impact DECIMAL,
                new_size DECIMAL NOT NULL,
                new_avg_price DECIMAL NOT NULL,
                new_pnl DECIMAL NOT NULL,
                source TEXT NOT NULL,
                order_id TEXT,
                FOREIGN KEY (position_id) REFERENCES positions(position_id)
            )
        """)
        
        # Risk alerts table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_alerts (
                alert_id TEXT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                market_id TEXT,
                position_id TEXT,
                metric_name TEXT,
                metric_value DECIMAL,
                threshold DECIMAL,
                suggested_action TEXT,
                auto_action_taken TEXT,
                requires_confirmation BOOLEAN,
                acknowledged BOOLEAN DEFAULT FALSE,
                acknowledged_at TIMESTAMP,
                acknowledged_by TEXT
            )
        """)
        
        # Create indexes for risk_alerts
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_timestamp ON risk_alerts(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_severity ON risk_alerts(severity)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_category ON risk_alerts(category)")
        
        # Daily P&L table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_pnl (
                date DATE PRIMARY KEY,
                gross_pnl DECIMAL NOT NULL,
                commission DECIMAL NOT NULL,
                net_pnl DECIMAL NOT NULL,
                num_trades INTEGER NOT NULL,
                win_rate DECIMAL,
                avg_win DECIMAL,
                avg_loss DECIMAL,
                total_volume DECIMAL,
                max_drawdown DECIMAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Market exposures snapshot table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS exposure_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                market_id TEXT NOT NULL,
                net_back_exposure DECIMAL NOT NULL,
                net_lay_liability DECIMAL NOT NULL,
                max_loss DECIMAL NOT NULL,
                open_positions INTEGER NOT NULL,
                total_stake DECIMAL NOT NULL,
                hedge_required BOOLEAN,
                hedge_amount DECIMAL,
                hedge_selection TEXT,
                hedge_price DECIMAL
            )
        """)
        
        # Create index for exposure_snapshots
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_exposure_timestamp_market ON exposure_snapshots(timestamp, market_id)")
        
        self.conn.commit()
        
    # Position methods
    
    def save_position(self, position: Position):
        """Save or update a position.
        
        Args:
            position: Position to save
        """
        try:
            tags_json = json.dumps(position.tags) if position.tags else None
            
            self.conn.execute("""
                INSERT OR REPLACE INTO positions (
                    position_id, market_id, selection_id, side,
                    entry_price, entry_size, entry_time,
                    current_size, exit_price, exit_size, last_update,
                    realized_pnl, unrealized_pnl, commission,
                    status, provider, strategy, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.position_id,
                position.market_id,
                position.selection_id,
                position.side,
                str(position.entry_price),
                str(position.entry_size),
                position.entry_time,
                str(position.current_size),
                str(position.exit_price) if position.exit_price else None,
                str(position.exit_size),
                position.last_update,
                str(position.realized_pnl),
                str(position.unrealized_pnl),
                str(position.commission),
                position.status,
                position.provider,
                position.strategy,
                tags_json
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to save position {position.position_id}: {e}")
            self.conn.rollback()
            raise
            
    def load_position(self, position_id: str) -> Optional[Position]:
        """Load a position by ID.
        
        Args:
            position_id: Position ID
            
        Returns:
            Position if found
        """
        try:
            cursor = self.conn.execute("""
                SELECT * FROM positions WHERE position_id = ?
            """, (position_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            return self._row_to_position(row)
            
        except Exception as e:
            logger.error(f"Failed to load position {position_id}: {e}")
            return None
            
    def load_open_positions(self) -> List[Position]:
        """Load all open positions.
        
        Returns:
            List of open positions
        """
        try:
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.execute("""
                SELECT * FROM positions 
                WHERE status != ?
                ORDER BY entry_time DESC
            """, (PositionStatus.CLOSED,))
            
            positions = []
            for row in cursor.fetchall():
                position = self._row_to_position(row)
                if position:
                    positions.append(position)
                    
            return positions
            
        except Exception as e:
            logger.error(f"Failed to load open positions: {e}")
            return []
            
    def load_positions_by_market(self, market_id: str) -> List[Position]:
        """Load all positions for a market.
        
        Args:
            market_id: Market ID
            
        Returns:
            List of positions
        """
        try:
            cursor = self.conn.execute("""
                SELECT * FROM positions 
                WHERE market_id = ?
                ORDER BY entry_time DESC
            """, (market_id,))
            
            positions = []
            for row in cursor.fetchall():
                position = self._row_to_position(row)
                if position:
                    positions.append(position)
                    
            return positions
            
        except Exception as e:
            logger.error(f"Failed to load positions for market {market_id}: {e}")
            return []
            
    def _row_to_position(self, row: sqlite3.Row) -> Optional[Position]:
        """Convert database row to Position object.
        
        Args:
            row: Database row
            
        Returns:
            Position object
        """
        try:
            return Position(
                position_id=row["position_id"],
                market_id=row["market_id"],
                selection_id=row["selection_id"],
                side=PositionSide(row["side"]),
                entry_price=Decimal(row["entry_price"]),
                entry_size=Decimal(row["entry_size"]),
                entry_time=row["entry_time"],
                current_size=Decimal(row["current_size"]),
                exit_price=Decimal(row["exit_price"]) if row["exit_price"] else None,
                exit_size=Decimal(row["exit_size"]),
                last_update=row["last_update"],
                realized_pnl=Decimal(row["realized_pnl"]),
                unrealized_pnl=Decimal(row["unrealized_pnl"]),
                commission=Decimal(row["commission"]),
                status=PositionStatus(row["status"]),
                provider=row["provider"],
                strategy=row["strategy"],
                tags=json.loads(row["tags"]) if row["tags"] else []
            )
        except Exception as e:
            logger.error(f"Failed to convert row to position: {e}")
            return None
            
    # Position update methods
    
    def save_position_update(self, update: PositionUpdate):
        """Save position update for audit trail.
        
        Args:
            update: Position update to save
        """
        try:
            self.conn.execute("""
                INSERT INTO position_updates (
                    position_id, timestamp, update_type,
                    size_change, price, pnl_impact,
                    new_size, new_avg_price, new_pnl,
                    source, order_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                update.position_id,
                update.timestamp,
                update.update_type,
                str(update.size_change) if update.size_change else None,
                str(update.price) if update.price else None,
                str(update.pnl_impact) if update.pnl_impact else None,
                str(update.new_size),
                str(update.new_avg_price),
                str(update.new_pnl),
                update.source,
                update.order_id
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to save position update: {e}")
            self.conn.rollback()
            
    def load_position_updates(
        self,
        position_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Load position updates for audit trail.
        
        Args:
            position_id: Position ID
            limit: Maximum number of updates
            
        Returns:
            List of position updates
        """
        try:
            cursor = self.conn.execute("""
                SELECT * FROM position_updates
                WHERE position_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (position_id, limit))
            
            updates = []
            for row in cursor.fetchall():
                updates.append(dict(row))
                
            return updates
            
        except Exception as e:
            logger.error(f"Failed to load position updates: {e}")
            return []
            
    # Risk alert methods
    
    def save_alert(self, alert: RiskAlert):
        """Save risk alert.
        
        Args:
            alert: Alert to save
        """
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO risk_alerts (
                    alert_id, timestamp, severity, category, message,
                    market_id, position_id, metric_name, metric_value,
                    threshold, suggested_action, auto_action_taken,
                    requires_confirmation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id,
                alert.timestamp,
                alert.severity,
                alert.category,
                alert.message,
                alert.market_id,
                alert.position_id,
                alert.metric_name,
                str(alert.metric_value) if alert.metric_value else None,
                str(alert.threshold) if alert.threshold else None,
                alert.suggested_action,
                alert.auto_action_taken,
                alert.requires_confirmation
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
            self.conn.rollback()
            
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Acknowledge a risk alert.
        
        Args:
            alert_id: Alert ID
            acknowledged_by: User who acknowledged
        """
        try:
            self.conn.execute("""
                UPDATE risk_alerts
                SET acknowledged = TRUE,
                    acknowledged_at = CURRENT_TIMESTAMP,
                    acknowledged_by = ?
                WHERE alert_id = ?
            """, (acknowledged_by, alert_id))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
            self.conn.rollback()
            
    def load_unacknowledged_alerts(self) -> List[Dict[str, Any]]:
        """Load unacknowledged alerts.
        
        Returns:
            List of unacknowledged alerts
        """
        try:
            cursor = self.conn.execute("""
                SELECT * FROM risk_alerts
                WHERE acknowledged = FALSE
                ORDER BY timestamp DESC
            """)
            
            alerts = []
            for row in cursor.fetchall():
                alerts.append(dict(row))
                
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to load unacknowledged alerts: {e}")
            return []
            
    # P&L methods
    
    def save_daily_pnl(self, date: datetime, pnl_data: Dict[str, Any]):
        """Save daily P&L summary.
        
        Args:
            date: Date
            pnl_data: P&L data dictionary
        """
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO daily_pnl (
                    date, gross_pnl, commission, net_pnl,
                    num_trades, win_rate, avg_win, avg_loss,
                    total_volume, max_drawdown
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date.date(),
                str(pnl_data["gross_pnl"]),
                str(pnl_data["commission"]),
                str(pnl_data["net_pnl"]),
                pnl_data["num_trades"],
                str(pnl_data.get("win_rate", 0)),
                str(pnl_data.get("avg_win", 0)),
                str(pnl_data.get("avg_loss", 0)),
                str(pnl_data.get("total_volume", 0)),
                str(pnl_data.get("max_drawdown", 0))
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to save daily P&L: {e}")
            self.conn.rollback()
            
    def load_daily_pnl(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Load daily P&L for a date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of daily P&L records
        """
        try:
            cursor = self.conn.execute("""
                SELECT * FROM daily_pnl
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
            """, (start_date.date(), end_date.date()))
            
            records = []
            for row in cursor.fetchall():
                records.append(dict(row))
                
            return records
            
        except Exception as e:
            logger.error(f"Failed to load daily P&L: {e}")
            return []
            
    # Exposure methods
    
    def save_exposure_snapshot(self, exposure_data: Dict[str, Any]):
        """Save market exposure snapshot.
        
        Args:
            exposure_data: Exposure data dictionary
        """
        try:
            self.conn.execute("""
                INSERT INTO exposure_snapshots (
                    timestamp, market_id, net_back_exposure,
                    net_lay_liability, max_loss, open_positions,
                    total_stake, hedge_required, hedge_amount,
                    hedge_selection, hedge_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(),
                exposure_data["market_id"],
                str(exposure_data["net_back_exposure"]),
                str(exposure_data["net_lay_liability"]),
                str(exposure_data["max_loss"]),
                exposure_data["open_positions"],
                str(exposure_data["total_stake"]),
                exposure_data.get("hedge_required", False),
                str(exposure_data.get("hedge_amount", 0)),
                exposure_data.get("hedge_selection"),
                str(exposure_data.get("hedge_price", 0))
            ))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to save exposure snapshot: {e}")
            self.conn.rollback()
            
    # Cleanup methods
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data.
        
        Args:
            days_to_keep: Number of days of data to keep
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Clean up old closed positions
            self.conn.execute("""
                DELETE FROM positions
                WHERE status = ? AND last_update < ?
            """, (PositionStatus.CLOSED, cutoff_date))
            
            # Clean up old position updates
            self.conn.execute("""
                DELETE FROM position_updates
                WHERE timestamp < ?
            """, (cutoff_date,))
            
            # Clean up old acknowledged alerts
            self.conn.execute("""
                DELETE FROM risk_alerts
                WHERE acknowledged = TRUE AND timestamp < ?
            """, (cutoff_date,))
            
            # Clean up old exposure snapshots
            self.conn.execute("""
                DELETE FROM exposure_snapshots
                WHERE timestamp < ?
            """, (cutoff_date,))
            
            self.conn.commit()
            
            logger.info(f"Cleaned up data older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Failed to clean up old data: {e}")
            self.conn.rollback()