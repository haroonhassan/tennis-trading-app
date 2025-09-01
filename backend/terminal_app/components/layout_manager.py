"""Layout manager for multi-window support."""

from enum import Enum
from typing import Optional

from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.console import Group
from rich.columns import Columns

from .trading_grid import TradingGrid
from .positions_panel import PositionsPanel
from .layout import AppLayout


class ViewMode(Enum):
    """Available view modes."""
    TRADING = "trading"  # F1 - Full trading grid
    POSITIONS = "positions"  # F2 - Full positions view
    SPLIT = "split"  # F3 - Split screen (grid + positions)
    RISK = "risk"  # F4 - Risk dashboard


class LayoutManager:
    """Manages different layout configurations."""
    
    def __init__(
        self,
        app_layout: AppLayout,
        trading_grid: TradingGrid,
        positions_panel: PositionsPanel
    ):
        self.app_layout = app_layout
        self.trading_grid = trading_grid
        self.positions_panel = positions_panel
        self.current_mode = ViewMode.TRADING
        self.active_pane = 0  # 0 = left/top, 1 = right/bottom
    
    def create_layout(self) -> Layout:
        """Create layout based on current mode."""
        if self.current_mode == ViewMode.TRADING:
            return self._create_trading_layout()
        elif self.current_mode == ViewMode.POSITIONS:
            return self._create_positions_layout()
        elif self.current_mode == ViewMode.SPLIT:
            return self._create_split_layout()
        elif self.current_mode == ViewMode.RISK:
            return self._create_risk_layout()
        else:
            return self._create_trading_layout()
    
    def _create_trading_layout(self) -> Layout:
        """Create full trading grid layout."""
        grid = self.trading_grid.create_grid()
        return Panel(
            grid,
            title="[F1] Trading View",
            border_style="green" if self.active_pane == 0 else "dim"
        )
    
    def _create_positions_layout(self) -> Layout:
        """Create full positions view layout."""
        # Main positions table
        positions_table = self.positions_panel.create_positions_table()
        
        # Get selected position for ladder
        selected_pos = self.positions_panel.get_selected_position()
        
        # Create layout with positions and ladder
        layout = Layout()
        layout.split_row(
            Layout(positions_table, name="positions", ratio=2),
            Layout(name="sidebar", ratio=1)
        )
        
        # Add ladder and summary to sidebar
        sidebar_content = []
        if selected_pos:
            ladder = self.positions_panel.create_pnl_ladder(selected_pos)
            sidebar_content.append(ladder)
        
        summary = self.positions_panel.create_summary_panel()
        sidebar_content.append(summary)
        
        if sidebar_content:
            layout["sidebar"].update(Group(*sidebar_content))
        
        return Panel(
            layout,
            title="[F2] Positions View",
            border_style="green"
        )
    
    def _create_split_layout(self) -> Layout:
        """Create split screen layout."""
        # Get both components
        grid = self.trading_grid.create_grid()
        positions_table = self.positions_panel.create_positions_table()
        
        # Create split layout
        layout = Layout()
        layout.split_column(
            Layout(
                Panel(
                    grid,
                    title="Trading Grid",
                    border_style="green" if self.active_pane == 0 else "dim"
                ),
                name="top",
                ratio=1
            ),
            Layout(
                Panel(
                    positions_table,
                    title="Positions",
                    border_style="green" if self.active_pane == 1 else "dim"
                ),
                name="bottom",
                ratio=1
            )
        )
        
        return Panel(
            layout,
            title="[F3] Split View",
            border_style="blue"
        )
    
    def _create_risk_layout(self) -> Layout:
        """Create risk dashboard layout."""
        from rich.table import Table
        from rich.text import Text
        from rich.progress import Progress, BarColumn, TextColumn
        
        # Create risk overview
        risk_table = Table.grid(padding=1, expand=True)
        risk_table.add_column(justify="right", style="cyan")
        risk_table.add_column(justify="left")
        
        # Mock risk data for now
        risk_table.add_row("Risk Score:", Text("35/100", style="green"))
        risk_table.add_row("Daily P&L:", Text("+£45.50", style="green"))
        risk_table.add_row("Exposure:", Text("£250/£1000", style="yellow"))
        risk_table.add_row("Positions:", Text("3/20", style="white"))
        
        # Create exposure bars
        exposure_bars = Table(title="Exposure by Market", box=None)
        exposure_bars.add_column("Market", style="cyan")
        exposure_bars.add_column("Exposure", width=30)
        exposure_bars.add_column("Amount", justify="right")
        
        # Add sample bars
        markets = [
            ("Djokovic vs Federer", 0.3, "£30"),
            ("Nadal vs Murray", 0.5, "£50"),
            ("Alcaraz vs Sinner", 0.2, "£20")
        ]
        
        for market, pct, amount in markets:
            bar_len = int(pct * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            color = "red" if pct > 0.7 else "yellow" if pct > 0.4 else "green"
            exposure_bars.add_row(
                market,
                Text(bar, style=color),
                Text(amount, style=color)
            )
        
        # Create P&L chart (ASCII)
        pnl_chart = Panel(
            Text(
                "     £\n"
                "  50 │     ╭─╮\n"
                "  40 │    ╱  ╰╮\n"
                "  30 │   ╱    ╰─╮\n"
                "  20 │  ╱       ╰╮\n"
                "  10 │ ╱         ╰─╮\n"
                "   0 ├─────────────╯─\n"
                " -10 │\n"
                "     └────────────────\n"
                "      9am  12pm  3pm  6pm",
                style="cyan"
            ),
            title="Daily P&L",
            border_style="blue"
        )
        
        # Combine into layout
        layout = Layout()
        layout.split_row(
            Layout(
                Panel(risk_table, title="Risk Overview", border_style="yellow"),
                name="overview",
                ratio=1
            ),
            Layout(name="middle", ratio=1),
            Layout(pnl_chart, name="chart", ratio=1)
        )
        
        layout["middle"].update(
            Panel(exposure_bars, title="Market Exposure", border_style="yellow")
        )
        
        return Panel(
            layout,
            title="[F4] Risk Dashboard",
            border_style="green"
        )
    
    def switch_mode(self, mode: ViewMode):
        """Switch to a different view mode."""
        self.current_mode = mode
        self.active_pane = 0  # Reset to first pane
    
    def toggle_active_pane(self):
        """Toggle active pane in split view."""
        if self.current_mode == ViewMode.SPLIT:
            self.active_pane = 1 - self.active_pane
    
    def get_mode_indicator(self) -> str:
        """Get current mode indicator for status bar."""
        indicators = {
            ViewMode.TRADING: "[F1] Trading",
            ViewMode.POSITIONS: "[F2] Positions",
            ViewMode.SPLIT: "[F3] Split",
            ViewMode.RISK: "[F4] Risk"
        }
        return indicators.get(self.current_mode, "Unknown")