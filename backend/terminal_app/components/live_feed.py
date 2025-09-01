"""Live data feed component for real-time updates."""

from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import deque
from enum import Enum

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group
from rich.layout import Layout
from rich.align import Align
from rich.live import Live
from rich.syntax import Syntax

from ..models import Trade, Position, MessageType


class FeedEventType(Enum):
    """Types of feed events."""
    TRADE = "trade"
    POSITION = "position"
    PRICE = "price"
    MATCH = "match"
    SCORE = "score"
    ALERT = "alert"
    SYSTEM = "system"
    ERROR = "error"
    INFO = "info"


class FeedEvent:
    """Represents a single feed event."""
    
    def __init__(
        self,
        event_type: FeedEventType,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        priority: int = 0
    ):
        self.event_type = event_type
        self.message = message
        self.data = data or {}
        self.timestamp = timestamp or datetime.now()
        self.priority = priority
    
    def format(self) -> Text:
        """Format the event for display."""
        # Time stamp
        time_str = self.timestamp.strftime("%H:%M:%S")
        
        # Icon and color based on event type
        icons = {
            FeedEventType.TRADE: ("💰", "green"),
            FeedEventType.POSITION: ("📊", "cyan"),
            FeedEventType.PRICE: ("📈", "yellow"),
            FeedEventType.MATCH: ("🎾", "magenta"),
            FeedEventType.SCORE: ("🏆", "blue"),
            FeedEventType.ALERT: ("⚠️", "red"),
            FeedEventType.SYSTEM: ("⚙️", "dim"),
            FeedEventType.ERROR: ("❌", "red"),
            FeedEventType.INFO: ("ℹ️", "white")
        }
        
        icon, color = icons.get(self.event_type, ("•", "white"))
        
        # Build formatted text
        text = Text()
        text.append(f"[{time_str}] ", style="dim")
        text.append(f"{icon} ", style=color)
        text.append(self.message, style=color)
        
        return text


class LiveFeedPanel:
    """Live feed panel for real-time updates."""
    
    def __init__(self, max_events: int = 100):
        self.events: deque = deque(maxlen=max_events)
        self.filters = set(FeedEventType)
        self.paused = False
        self.auto_scroll = True
        self.highlight_keywords = []
        self.event_counts = {event_type: 0 for event_type in FeedEventType}
    
    def add_event(self, event: FeedEvent):
        """Add a new event to the feed."""
        if not self.paused:
            self.events.append(event)
            self.event_counts[event.event_type] += 1
    
    def create_panel(self, height: Optional[int] = None) -> Panel:
        """Create the live feed panel."""
        # Filter events
        filtered_events = [
            e for e in self.events 
            if e.event_type in self.filters
        ]
        
        # Sort by priority and time
        filtered_events.sort(key=lambda e: (-e.priority, e.timestamp))
        
        # Limit to display height
        if height:
            filtered_events = filtered_events[-height:]
        
        # Create display
        if not filtered_events:
            content = Text("No events to display", style="dim italic")
        else:
            lines = []
            for event in filtered_events:
                formatted = event.format()
                
                # Highlight keywords
                for keyword in self.highlight_keywords:
                    if keyword.lower() in event.message.lower():
                        formatted.stylize("bold yellow on red")
                
                lines.append(formatted)
            
            content = Group(*lines)
        
        # Status line
        status = self._create_status_line()
        
        return Panel(
            content,
            title="📡 Live Feed",
            subtitle=status,
            border_style="cyan" if not self.paused else "yellow"
        )
    
    def _create_status_line(self) -> str:
        """Create status line for the panel."""
        status_parts = []
        
        if self.paused:
            status_parts.append("⏸️  PAUSED")
        else:
            status_parts.append("▶️  LIVE")
        
        if self.auto_scroll:
            status_parts.append("📜 Auto")
        
        # Event count
        total = len(self.events)
        status_parts.append(f"Events: {total}")
        
        return " | ".join(status_parts)
    
    def toggle_pause(self):
        """Toggle feed pause."""
        self.paused = not self.paused
    
    def toggle_auto_scroll(self):
        """Toggle auto-scroll."""
        self.auto_scroll = not self.auto_scroll
    
    def clear(self):
        """Clear all events."""
        self.events.clear()
        self.event_counts = {event_type: 0 for event_type in FeedEventType}
    
    def set_filter(self, event_types: List[FeedEventType]):
        """Set event type filters."""
        self.filters = set(event_types)
    
    def add_filter(self, event_type: FeedEventType):
        """Add an event type to filters."""
        self.filters.add(event_type)
    
    def remove_filter(self, event_type: FeedEventType):
        """Remove an event type from filters."""
        self.filters.discard(event_type)
    
    def set_highlight(self, keywords: List[str]):
        """Set keywords to highlight."""
        self.highlight_keywords = keywords


class TradeFeed:
    """Specialized feed for trade events."""
    
    def __init__(self):
        self.trades: deque = deque(maxlen=50)
        self.total_volume = Decimal("0")
        self.trade_count = 0
    
    def add_trade(self, trade: Trade):
        """Add a trade to the feed."""
        self.trades.append(trade)
        self.total_volume += trade.stake
        self.trade_count += 1
    
    def create_panel(self) -> Panel:
        """Create trade feed panel."""
        table = Table(show_header=True, box=None)
        table.add_column("Time", style="dim", width=8)
        table.add_column("Side", width=6)
        table.add_column("Selection", style="white")
        table.add_column("Odds", justify="right", style="yellow")
        table.add_column("Stake", justify="right")
        table.add_column("P&L", justify="right")
        
        for trade in list(self.trades)[-10:]:  # Last 10 trades
            time_str = trade.executed_at.strftime("%H:%M:%S")
            
            # Side with color
            side_style = "green" if trade.side.value == "BACK" else "red"
            side_text = Text(trade.side.value, style=side_style)
            
            # P&L with color
            pnl_text = ""
            if trade.pnl:
                pnl_style = "green" if trade.pnl >= 0 else "red"
                pnl_text = Text(f"£{trade.pnl:.2f}", style=pnl_style)
            
            table.add_row(
                time_str,
                side_text,
                trade.selection_name[:15],
                f"{trade.odds:.2f}",
                f"£{trade.stake:.2f}",
                pnl_text
            )
        
        # Summary
        summary = Text()
        summary.append(f"Total: {self.trade_count} trades | ", style="dim")
        summary.append(f"Volume: £{self.total_volume:.2f}", style="cyan")
        
        return Panel(
            Group(table, Text(""), summary),
            title="💰 Trade Feed",
            border_style="green"
        )


class ScoreFeed:
    """Live score updates feed."""
    
    def __init__(self):
        self.score_updates: deque = deque(maxlen=20)
        self.current_scores: Dict[str, str] = {}
    
    def update_score(self, match_id: str, score: str, server: Optional[str] = None):
        """Update match score."""
        update = {
            'match_id': match_id,
            'score': score,
            'server': server,
            'timestamp': datetime.now()
        }
        self.score_updates.append(update)
        self.current_scores[match_id] = score
    
    def create_panel(self) -> Panel:
        """Create score feed panel."""
        if not self.score_updates:
            content = Text("No score updates", style="dim italic")
        else:
            lines = []
            for update in list(self.score_updates)[-10:]:
                time_str = update['timestamp'].strftime("%H:%M:%S")
                
                text = Text()
                text.append(f"[{time_str}] ", style="dim")
                text.append("🎾 ", style="green")
                text.append(f"{update['match_id']}: ", style="cyan")
                text.append(update['score'], style="yellow")
                
                if update['server']:
                    text.append(f" • {update['server']}", style="magenta")
                
                lines.append(text)
            
            content = Group(*lines)
        
        return Panel(
            content,
            title="🏆 Score Feed",
            border_style="blue"
        )


class AlertFeed:
    """Alert and notification feed."""
    
    def __init__(self):
        self.alerts: deque = deque(maxlen=20)
        self.unread_count = 0
    
    def add_alert(self, level: str, message: str, data: Optional[Dict] = None):
        """Add an alert."""
        alert = {
            'level': level,
            'message': message,
            'data': data or {},
            'timestamp': datetime.now(),
            'read': False
        }
        self.alerts.append(alert)
        self.unread_count += 1
    
    def mark_all_read(self):
        """Mark all alerts as read."""
        for alert in self.alerts:
            alert['read'] = True
        self.unread_count = 0
    
    def create_panel(self) -> Panel:
        """Create alert feed panel."""
        if not self.alerts:
            content = Text("No alerts", style="dim italic")
        else:
            lines = []
            for alert in list(self.alerts)[-10:]:
                time_str = alert['timestamp'].strftime("%H:%M:%S")
                
                # Level icon and color
                level_icons = {
                    'critical': ("🔴", "red"),
                    'warning': ("🟡", "yellow"),
                    'info': ("🔵", "blue"),
                    'success': ("🟢", "green")
                }
                icon, color = level_icons.get(alert['level'], ("⚪", "white"))
                
                text = Text()
                text.append(f"[{time_str}] ", style="dim")
                text.append(f"{icon} ", style=color)
                text.append(alert['message'], style=color if not alert['read'] else "dim " + color)
                
                if not alert['read']:
                    text.append(" [NEW]", style="bold yellow")
                
                lines.append(text)
            
            content = Group(*lines)
        
        # Title with unread count
        title = "🚨 Alerts"
        if self.unread_count > 0:
            title += f" ({self.unread_count} new)"
        
        return Panel(
            content,
            title=title,
            border_style="red" if self.unread_count > 0 else "yellow"
        )


class LiveDataManager:
    """Manages all live data feeds."""
    
    def __init__(self):
        self.main_feed = LiveFeedPanel()
        self.trade_feed = TradeFeed()
        self.score_feed = ScoreFeed()
        self.alert_feed = AlertFeed()
        
        # Statistics
        self.stats = {
            'messages_per_second': 0,
            'total_messages': 0,
            'connection_uptime': timedelta(0),
            'last_message': None
        }
        self.message_times: deque = deque(maxlen=100)
        self.connection_start = datetime.now()
    
    def process_message(self, msg_type: MessageType, data: Dict[str, Any]):
        """Process incoming WebSocket message."""
        self.stats['total_messages'] += 1
        self.stats['last_message'] = datetime.now()
        self.message_times.append(datetime.now())
        
        # Calculate messages per second
        if len(self.message_times) > 1:
            time_diff = (self.message_times[-1] - self.message_times[0]).total_seconds()
            if time_diff > 0:
                self.stats['messages_per_second'] = len(self.message_times) / time_diff
        
        # Route to appropriate feed
        if msg_type == MessageType.TRADE_UPDATE:
            self._process_trade(data)
        elif msg_type == MessageType.POSITION_UPDATE:
            self._process_position(data)
        elif msg_type == MessageType.PRICE_UPDATE:
            self._process_price(data)
        elif msg_type == MessageType.SCORE_UPDATE:
            self._process_score(data)
        elif msg_type == MessageType.MATCH_UPDATE:
            self._process_match(data)
        elif msg_type == MessageType.RISK_UPDATE:
            self._process_risk(data)
        elif msg_type == MessageType.ERROR:
            self._process_error(data)
    
    def _process_trade(self, data: Dict):
        """Process trade update."""
        event = FeedEvent(
            FeedEventType.TRADE,
            f"Trade executed: {data.get('side', 'UNKNOWN')} {data.get('selection', '')} @ {data.get('odds', 0)}",
            data
        )
        self.main_feed.add_event(event)
    
    def _process_position(self, data: Dict):
        """Process position update."""
        event = FeedEvent(
            FeedEventType.POSITION,
            f"Position updated: {data.get('selection', '')} P&L: £{data.get('pnl', 0):.2f}",
            data
        )
        self.main_feed.add_event(event)
    
    def _process_price(self, data: Dict):
        """Process price update."""
        event = FeedEvent(
            FeedEventType.PRICE,
            f"Price update: {data.get('selection', '')} Back: {data.get('back_price', 0)} Lay: {data.get('lay_price', 0)}",
            data,
            priority=-1  # Low priority
        )
        self.main_feed.add_event(event)
    
    def _process_score(self, data: Dict):
        """Process score update."""
        self.score_feed.update_score(
            data.get('match_id', ''),
            data.get('score', ''),
            data.get('server')
        )
        
        event = FeedEvent(
            FeedEventType.SCORE,
            f"Score: {data.get('match_id', '')} - {data.get('score', '')}",
            data
        )
        self.main_feed.add_event(event)
    
    def _process_match(self, data: Dict):
        """Process match update."""
        event = FeedEvent(
            FeedEventType.MATCH,
            f"Match update: {data.get('status', '')} - {data.get('home', '')} vs {data.get('away', '')}",
            data
        )
        self.main_feed.add_event(event)
    
    def _process_risk(self, data: Dict):
        """Process risk update."""
        level = data.get('level', 'info')
        if level in ['critical', 'warning']:
            self.alert_feed.add_alert(level, data.get('message', ''), data)
        
        event = FeedEvent(
            FeedEventType.ALERT if level in ['critical', 'warning'] else FeedEventType.INFO,
            f"Risk alert: {data.get('message', '')}",
            data,
            priority=2 if level == 'critical' else 1
        )
        self.main_feed.add_event(event)
    
    def _process_error(self, data: Dict):
        """Process error message."""
        self.alert_feed.add_alert('critical', data.get('message', 'Unknown error'), data)
        
        event = FeedEvent(
            FeedEventType.ERROR,
            f"Error: {data.get('message', '')}",
            data,
            priority=3  # High priority
        )
        self.main_feed.add_event(event)
    
    def create_dashboard(self) -> Layout:
        """Create complete feed dashboard."""
        layout = Layout()
        
        # Split into main feed and side panels
        layout.split_row(
            Layout(name="main", ratio=2),
            Layout(name="side", ratio=1)
        )
        
        # Main feed
        layout["main"].update(self.main_feed.create_panel())
        
        # Side panels
        layout["side"].split_column(
            Layout(self.trade_feed.create_panel(), name="trades", ratio=1),
            Layout(self.score_feed.create_panel(), name="scores", ratio=1),
            Layout(self.alert_feed.create_panel(), name="alerts", ratio=1),
            Layout(self._create_stats_panel(), name="stats", ratio=1)
        )
        
        return layout
    
    def _create_stats_panel(self) -> Panel:
        """Create statistics panel."""
        self.stats['connection_uptime'] = datetime.now() - self.connection_start
        
        table = Table.grid(padding=0)
        table.add_column(justify="right", style="cyan")
        table.add_column(justify="left")
        
        table.add_row("Messages/sec:", f"{self.stats['messages_per_second']:.1f}")
        table.add_row("Total messages:", str(self.stats['total_messages']))
        table.add_row("Uptime:", str(self.stats['connection_uptime']).split('.')[0])
        
        if self.stats['last_message']:
            ago = (datetime.now() - self.stats['last_message']).total_seconds()
            table.add_row("Last message:", f"{ago:.1f}s ago")
        
        return Panel(
            table,
            title="📊 Stats",
            border_style="blue"
        )