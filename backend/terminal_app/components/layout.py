"""Base layout components for the terminal app."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.live import Live

from ..models import RiskMetrics


class AppLayout:
    """Main application layout using Rich."""
    
    def __init__(self):
        self.layout = Layout()
        self.console = Console()
        self._setup_layout()
        
        # Status data
        self.connection_status = "Disconnected"
        self.total_pnl = Decimal("0")
        self.risk_metrics = RiskMetrics()
        self.last_update = datetime.now()
    
    def _setup_layout(self):
        """Set up the main layout structure."""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="feed", size=10),
            Layout(name="status", size=1)
        )
    
    def update_header(self, connection_status: str, total_pnl: Decimal) -> None:
        """Update header panel."""
        self.connection_status = connection_status
        self.total_pnl = total_pnl
        
        # Create header content
        header_table = Table.grid(expand=True)
        header_table.add_column(justify="left", ratio=1)
        header_table.add_column(justify="center", ratio=1)
        header_table.add_column(justify="right", ratio=1)
        
        # Connection status with color
        conn_color = "green" if connection_status == "Connected" else "red"
        conn_text = Text(f"● {connection_status}", style=conn_color)
        
        # P&L with color
        pnl_color = "green" if total_pnl >= 0 else "red"
        pnl_text = Text(f"P&L: £{total_pnl:.2f}", style=f"bold {pnl_color}")
        
        # Time
        time_text = Text(datetime.now().strftime("%H:%M:%S"), style="cyan")
        
        header_table.add_row(conn_text, pnl_text, time_text)
        
        self.layout["header"].update(
            Panel(header_table, title="[bold blue]Tennis Trading Terminal", border_style="blue")
        )
    
    def update_main(self, content) -> None:
        """Update main content area."""
        self.layout["main"].update(content)
    
    def update_feed(self, messages: list) -> None:
        """Update live feed panel."""
        feed_table = Table(show_header=False, box=None, expand=True)
        feed_table.add_column("Time", width=8)
        feed_table.add_column("Message", ratio=1)
        
        # Show last 8 messages
        for msg in messages[-8:]:
            time_str = msg.get('time', '').strftime("%H:%M:%S") if 'time' in msg else ""
            text = msg.get('text', '')
            style = msg.get('style', 'white')
            feed_table.add_row(
                Text(time_str, style="dim"),
                Text(text, style=style)
            )
        
        self.layout["feed"].update(
            Panel(feed_table, title="Live Feed", border_style="yellow")
        )
    
    def update_status(self, risk_metrics: RiskMetrics) -> None:
        """Update status bar."""
        self.risk_metrics = risk_metrics
        
        # Create status bar content
        status_parts = []
        
        # Risk score with color
        risk_color = "green"
        if risk_metrics.risk_score > 70:
            risk_color = "red"
        elif risk_metrics.risk_score > 40:
            risk_color = "yellow"
        status_parts.append(f"[{risk_color}]Risk: {risk_metrics.risk_score}%[/]")
        
        # Exposure
        exp_pct = risk_metrics.exposure_used
        exp_color = "red" if exp_pct > 80 else "yellow" if exp_pct > 60 else "green"
        status_parts.append(f"[{exp_color}]Exposure: {exp_pct:.0f}%[/]")
        
        # Positions
        pos_color = "red" if risk_metrics.open_positions >= risk_metrics.max_positions else "white"
        status_parts.append(f"[{pos_color}]Positions: {risk_metrics.open_positions}/{risk_metrics.max_positions}[/]")
        
        # Daily P&L
        daily_color = "green" if risk_metrics.daily_pnl >= 0 else "red"
        status_parts.append(f"[{daily_color}]Daily: £{risk_metrics.daily_pnl:.2f}[/]")
        
        # Trading status
        if not risk_metrics.trading_enabled:
            status_parts.append("[red bold]TRADING DISABLED[/]")
        
        status_text = " | ".join(status_parts)
        
        self.layout["status"].update(
            Panel(status_text, height=1, style="on grey23")
        )
    
    def create_placeholder_grid(self) -> Panel:
        """Create a placeholder trading grid."""
        table = Table(title="Markets", expand=True)
        table.add_column("Match", style="cyan", width=30)
        table.add_column("Score", width=8)
        table.add_column("Back", style="green", width=8)
        table.add_column("Lay", style="red", width=8)
        table.add_column("Position", width=10)
        table.add_column("P&L", width=10)
        
        # Add sample data
        table.add_row(
            "Djokovic vs Federer",
            "6-4 2-1*",
            "1.85",
            "1.87",
            "",
            ""
        )
        table.add_row(
            "Nadal vs Murray",
            "3-6 5-4",
            "2.10",
            "2.12",
            "€ +25.50",
            "[green]+£12.30[/]"
        )
        
        return Panel(table, title="Trading Grid", border_style="green")
    
    def get_layout(self) -> Layout:
        """Get the layout object."""
        return self.layout