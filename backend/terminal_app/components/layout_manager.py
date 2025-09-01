"""Layout manager for multi-window support."""

from enum import Enum
from typing import Optional, List

from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.console import Group
from rich.columns import Columns

from .trading_grid import TradingGrid
from .positions_panel import PositionsPanel
from .layout import AppLayout
from .risk_dashboard import RiskDashboard
from ..models import Position, Trade


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
        positions_panel: PositionsPanel,
        risk_dashboard: Optional[RiskDashboard] = None
    ):
        self.app_layout = app_layout
        self.trading_grid = trading_grid
        self.positions_panel = positions_panel
        self.risk_dashboard = risk_dashboard or RiskDashboard()
        self.current_mode = ViewMode.TRADING
        self.active_pane = 0  # 0 = left/top, 1 = right/bottom
        
        # Data for risk dashboard
        self._positions: List[Position] = []
        self._trades: List[Trade] = []
    
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
        # Use the actual risk dashboard component
        return self.risk_dashboard.create_dashboard(self._positions, self._trades)
    
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
    
    def update_data(self, positions: List[Position] = None, trades: List[Trade] = None):
        """Update positions and trades data for risk dashboard."""
        if positions is not None:
            self._positions = positions
        if trades is not None:
            self._trades = trades