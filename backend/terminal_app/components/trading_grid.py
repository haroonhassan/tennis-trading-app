"""Trading grid component with betting interface."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED
from rich.align import Align

from ..models import Match, PriceData, Position, OrderSide
from ..stores import MatchDataStore, PositionStore


@dataclass
class GridSelection:
    """Current grid selection state."""
    match_id: Optional[str] = None
    selection_id: Optional[str] = None
    selection_name: Optional[str] = None
    row_index: int = 0
    total_rows: int = 0


@dataclass
class PriceFlash:
    """Track price flash effects."""
    selection_id: str
    field: str  # 'back' or 'lay'
    direction: str  # 'up' or 'down'
    timestamp: datetime = field(default_factory=datetime.now)
    
    def is_active(self, duration_ms: int = 500) -> bool:
        """Check if flash is still active."""
        elapsed = (datetime.now() - self.timestamp).total_seconds() * 1000
        return elapsed < duration_ms


class TradingGrid:
    """Trading grid with real-time updates and betting interface."""
    
    def __init__(self, match_store: MatchDataStore, position_store: PositionStore):
        self.match_store = match_store
        self.position_store = position_store
        self.selection = GridSelection()
        self.price_flashes: List[PriceFlash] = []
        self.stale_threshold = timedelta(seconds=5)
        
        # Quick stake amounts
        self.quick_stakes = [
            Decimal("10"),
            Decimal("25"),
            Decimal("50"),
            Decimal("100"),
            Decimal("250")
        ]
        self.selected_stake_index = 2  # Default to £50
    
    def create_grid(self) -> Table:
        """Create the trading grid table."""
        table = Table(
            title="🎾 Trading Markets",
            box=ROUNDED,
            show_header=True,
            header_style="bold cyan",
            title_style="bold blue",
            expand=True,
            row_styles=["", "dim"]  # Alternate row styling
        )
        
        # Define columns
        table.add_column("Match", style="white", width=35)
        table.add_column("Score", style="yellow", width=10)
        table.add_column("Back", style="green", width=12, justify="right")
        table.add_column("Vol", style="dim green", width=8, justify="right")
        table.add_column("Lay", style="red", width=12, justify="right")
        table.add_column("Vol", style="dim red", width=8, justify="right")
        table.add_column("Pos", width=8, justify="center")
        table.add_column("P&L", width=12, justify="right")
        
        # Get all matches and their data
        matches = self.match_store.get_all_matches()
        row_index = 0
        
        for match in matches:
            # Get prices for this match
            prices = self.match_store.get_prices(match.match_id)
            
            # Get positions for this match
            positions = self.position_store.get_positions_by_match(match.match_id)
            positions_by_selection = {p.selection_id: p for p in positions}
            
            # Add row for each selection (player)
            for player_name, selection_id in [
                (match.home_player, f"{match.match_id}_home"),
                (match.away_player, f"{match.match_id}_away")
            ]:
                # Get price data
                price_data = prices.get(selection_id)
                position = positions_by_selection.get(selection_id)
                
                # Build row data
                row_data = self._build_row_data(
                    match, player_name, selection_id, 
                    price_data, position, row_index
                )
                
                # Apply selection highlighting
                if row_index == self.selection.row_index:
                    # Highlight selected row
                    row_data = [self._highlight_cell(cell) for cell in row_data]
                    self.selection.match_id = match.match_id
                    self.selection.selection_id = selection_id
                    self.selection.selection_name = player_name
                
                table.add_row(*row_data)
                row_index += 1
        
        self.selection.total_rows = row_index
        return table
    
    def _build_row_data(
        self, 
        match: Match,
        player_name: str,
        selection_id: str,
        price_data: Optional[PriceData],
        position: Optional[Position],
        row_index: int
    ) -> List:
        """Build a row of data for the grid."""
        row = []
        
        # Match column with serving indicator
        match_text = Text(player_name)
        if match.serving == player_name:
            match_text = Text("• ", style="bright_yellow") + match_text
        else:
            match_text = Text("  ") + match_text
        row.append(match_text)
        
        # Score column
        score_text = Text(match.score or "0-0", style="yellow")
        row.append(score_text)
        
        # Price columns with formatting
        if price_data:
            # Back price with flash effect
            back_text = self._format_price(
                price_data.back_price,
                selection_id,
                'back',
                price_data.last_update
            )
            row.append(back_text)
            
            # Back volume
            back_vol = self._format_volume(price_data.back_volume)
            row.append(back_vol)
            
            # Lay price with flash effect
            lay_text = self._format_price(
                price_data.lay_price,
                selection_id,
                'lay',
                price_data.last_update
            )
            row.append(lay_text)
            
            # Lay volume
            lay_vol = self._format_volume(price_data.lay_volume)
            row.append(lay_vol)
        else:
            # No price data
            row.extend([
                Text("-", style="dim"),
                Text("", style="dim"),
                Text("-", style="dim"),
                Text("", style="dim")
            ])
        
        # Position indicator
        if position and position.status.value == "OPEN":
            pos_text = Text("€", style="bold cyan")
            row.append(pos_text)
            
            # P&L with color
            pnl = position.pnl
            if pnl > 0:
                pnl_text = Text(f"+£{pnl:.2f}", style="bold green")
            elif pnl < 0:
                pnl_text = Text(f"-£{abs(pnl):.2f}", style="bold red")
            else:
                pnl_text = Text(f"£{pnl:.2f}", style="white")
            row.append(pnl_text)
        else:
            row.extend([Text(""), Text("")])
        
        return row
    
    def _format_price(
        self,
        price: Optional[Decimal],
        selection_id: str,
        field: str,
        last_update: datetime
    ) -> Text:
        """Format price with flash effects and staleness."""
        if not price:
            return Text("-", style="dim")
        
        # Check if price is stale
        is_stale = (datetime.now() - last_update) > self.stale_threshold
        
        # Check for active flash
        flash = self._get_active_flash(selection_id, field)
        
        # Determine style
        if flash:
            if flash.direction == 'up':
                style = "bold green on dark_green"
            else:
                style = "bold red on dark_red"
        elif is_stale:
            style = "dim"
        elif field == 'back':
            style = "green"
        else:
            style = "red"
        
        return Text(f"{price:.2f}", style=style)
    
    def _format_volume(self, volume: Optional[Decimal]) -> Text:
        """Format volume for display."""
        if not volume:
            return Text("")
        
        if volume >= 1000:
            vol_str = f"{volume/1000:.0f}k"
        else:
            vol_str = f"{volume:.0f}"
        
        return Text(vol_str, style="dim")
    
    def _highlight_cell(self, cell) -> Text:
        """Highlight a cell for selection."""
        if isinstance(cell, Text):
            # Add cyan background to existing text
            new_style = cell.style or ""
            if "on " not in new_style:
                new_style += " on dark_cyan"
            return Text(cell.plain, style=new_style)
        else:
            return Text(str(cell), style="on dark_cyan")
    
    def _get_active_flash(self, selection_id: str, field: str) -> Optional[PriceFlash]:
        """Get active flash effect for a price."""
        # Clean old flashes
        self.price_flashes = [
            f for f in self.price_flashes 
            if f.is_active()
        ]
        
        # Find active flash
        for flash in self.price_flashes:
            if flash.selection_id == selection_id and flash.field == field:
                return flash
        return None
    
    def add_price_flash(self, selection_id: str, field: str, direction: str):
        """Add a price flash effect."""
        self.price_flashes.append(
            PriceFlash(selection_id, field, direction)
        )
    
    def move_selection_up(self):
        """Move selection up in the grid."""
        if self.selection.row_index > 0:
            self.selection.row_index -= 1
    
    def move_selection_down(self):
        """Move selection down in the grid."""
        if self.selection.row_index < self.selection.total_rows - 1:
            self.selection.row_index += 1
    
    def get_selected_market(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get currently selected market details."""
        return (
            self.selection.match_id,
            self.selection.selection_id,
            self.selection.selection_name
        )
    
    def get_selected_stake(self) -> Decimal:
        """Get currently selected stake amount."""
        return self.quick_stakes[self.selected_stake_index]
    
    def cycle_stake(self, direction: int = 1):
        """Cycle through stake amounts."""
        self.selected_stake_index = (
            self.selected_stake_index + direction
        ) % len(self.quick_stakes)