"""Position management panel component."""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from enum import Enum

from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.console import Group
from rich.columns import Columns
from rich.align import Align
from rich.box import ROUNDED, SIMPLE

from ..models import Position, PositionStatus, OrderSide
from ..stores import PositionStore, MatchDataStore


class SortColumn(Enum):
    """Columns available for sorting."""
    MATCH = "match"
    STAKE = "stake"
    ODDS = "odds"
    CURRENT = "current"
    PNL = "pnl"
    TIME = "time"


class PositionsPanel:
    """Panel for displaying and managing positions."""
    
    def __init__(self, position_store: PositionStore, match_store: MatchDataStore):
        self.position_store = position_store
        self.match_store = match_store
        self.selected_position_index = 0
        self.sort_column = SortColumn.TIME
        self.sort_ascending = False
        self.show_closed = False
    
    def create_positions_table(self) -> Table:
        """Create the positions table."""
        table = Table(
            title="📊 Open Positions",
            box=ROUNDED,
            show_header=True,
            header_style="bold cyan",
            title_style="bold blue",
            expand=True
        )
        
        # Define columns
        table.add_column("Match", style="white", width=25)
        table.add_column("Selection", style="yellow", width=15)
        table.add_column("Side", width=6, justify="center")
        table.add_column("Stake", style="white", width=10, justify="right")
        table.add_column("Odds", style="cyan", width=8, justify="right")
        table.add_column("Current", width=8, justify="right")
        table.add_column("P&L", width=12, justify="right")
        table.add_column("Liability", style="dim", width=10, justify="right")
        table.add_column("Time", style="dim", width=8)
        
        # Get positions
        if self.show_closed:
            positions = list(self.position_store.positions.values())
        else:
            positions = self.position_store.get_open_positions()
        
        # Sort positions
        positions = self._sort_positions(positions)
        
        # Add rows
        for idx, position in enumerate(positions):
            # Get match name
            match = self.match_store.get_match(position.match_id)
            match_name = f"{match.home_player} v {match.away_player}" if match else position.match_id
            
            # Format row data
            row_data = self._format_position_row(position, match_name)
            
            # Highlight selected row
            if idx == self.selected_position_index:
                row_data = [self._highlight_cell(cell) for cell in row_data]
            
            table.add_row(*row_data)
        
        return table
    
    def _format_position_row(self, position: Position, match_name: str) -> List:
        """Format a position row."""
        row = []
        
        # Match name
        row.append(Text(match_name, style="white"))
        
        # Selection name
        row.append(Text(position.selection_name, style="yellow"))
        
        # Side with color
        side_color = "green" if position.side == OrderSide.BACK else "red"
        row.append(Text(position.side.value, style=side_color))
        
        # Stake
        row.append(Text(f"£{position.stake:.2f}", style="white"))
        
        # Entry odds
        row.append(Text(f"{position.odds:.2f}", style="cyan"))
        
        # Current odds
        if position.current_odds:
            # Color based on favorability
            if position.side == OrderSide.BACK:
                odds_color = "green" if position.current_odds > position.odds else "red"
            else:
                odds_color = "green" if position.current_odds < position.odds else "red"
            row.append(Text(f"{position.current_odds:.2f}", style=odds_color))
        else:
            row.append(Text("-", style="dim"))
        
        # P&L with color
        if position.pnl:
            pnl_color = "bold green" if position.pnl > 0 else "bold red" if position.pnl < 0 else "white"
            pnl_text = f"+£{position.pnl:.2f}" if position.pnl > 0 else f"-£{abs(position.pnl):.2f}"
            row.append(Text(pnl_text, style=pnl_color))
        else:
            row.append(Text("£0.00", style="white"))
        
        # Liability
        if position.side == OrderSide.LAY:
            liability = position.stake * (position.odds - 1)
        else:
            liability = position.stake
        row.append(Text(f"£{liability:.2f}", style="dim"))
        
        # Time
        time_str = position.opened_at.strftime("%H:%M")
        row.append(Text(time_str, style="dim"))
        
        return row
    
    def create_pnl_ladder(self, position: Optional[Position] = None) -> Panel:
        """Create P&L ladder showing profit/loss at different prices."""
        if not position:
            positions = self.position_store.get_open_positions()
            if not positions or self.selected_position_index >= len(positions):
                return Panel("No position selected", title="P&L Ladder", border_style="yellow")
            position = positions[self.selected_position_index]
        
        # Calculate P&L at different price points
        current_price = position.current_odds or position.odds
        price_range = []
        
        # Generate price points
        for i in range(-10, 11):
            price = current_price + (Decimal("0.05") * i)
            if price >= Decimal("1.01"):
                price_range.append(price)
        
        # Build ladder content
        lines = []
        max_pnl = Decimal("0")
        min_pnl = Decimal("0")
        
        for price in price_range:
            pnl = self._calculate_pnl_at_price(position, price)
            max_pnl = max(max_pnl, pnl)
            min_pnl = min(min_pnl, pnl)
        
        # Create ASCII chart
        for price in price_range:
            pnl = self._calculate_pnl_at_price(position, price)
            
            # Create bar
            bar_width = 20
            if pnl > 0 and max_pnl > 0:
                bar_len = int((pnl / max_pnl) * bar_width)
                bar = "█" * bar_len
                bar_color = "green"
            elif pnl < 0 and min_pnl < 0:
                bar_len = int((abs(pnl) / abs(min_pnl)) * bar_width)
                bar = "█" * bar_len
                bar_color = "red"
            else:
                bar = "│"
                bar_color = "white"
            
            # Format line
            is_current = abs(price - current_price) < Decimal("0.01")
            price_str = f"{price:.2f}"
            pnl_str = f"+£{pnl:.2f}" if pnl > 0 else f"-£{abs(pnl):.2f}"
            
            if is_current:
                line = Text(f"→ {price_str:6} ", style="bold yellow")
            else:
                line = Text(f"  {price_str:6} ", style="white")
            
            line.append(Text(f"{pnl_str:>10} ", style=bar_color))
            line.append(Text(bar, style=bar_color))
            
            lines.append(line)
        
        # Group lines
        content = Group(*lines)
        
        return Panel(
            content,
            title=f"P&L Ladder - {position.selection_name}",
            subtitle=f"Break-even: {position.odds:.2f}",
            border_style="yellow",
            padding=(0, 1)
        )
    
    def _calculate_pnl_at_price(self, position: Position, price: Decimal) -> Decimal:
        """Calculate P&L at a given price."""
        if position.side == OrderSide.BACK:
            # Back bet P&L
            if price < position.odds:
                # Can lay at lower odds for profit
                return position.stake * (position.odds - price) / price
            else:
                # Would need to lay at higher odds for loss
                return -position.stake * (price - position.odds) / price
        else:
            # Lay bet P&L
            if price > position.odds:
                # Can back at higher odds for profit
                return position.stake * (price - position.odds) / position.odds
            else:
                # Would need to back at lower odds for loss
                return -position.stake * (position.odds - price) / position.odds
    
    def create_summary_panel(self) -> Panel:
        """Create position summary panel."""
        positions = self.position_store.get_open_positions()
        
        # Calculate metrics
        total_exposure = Decimal("0")
        realized_pnl = self.position_store.get_realized_pnl()
        unrealized_pnl = self.position_store.get_unrealized_pnl()
        total_pnl = realized_pnl + unrealized_pnl
        
        # Find biggest winner/loser
        biggest_winner = None
        biggest_loser = None
        biggest_win = Decimal("0")
        biggest_loss = Decimal("0")
        
        for pos in positions:
            # Calculate exposure
            if pos.side == OrderSide.LAY:
                exposure = pos.stake * (pos.odds - 1)
            else:
                exposure = pos.stake
            total_exposure += exposure
            
            # Track biggest winner/loser
            if pos.pnl > biggest_win:
                biggest_win = pos.pnl
                biggest_winner = pos.selection_name
            if pos.pnl < biggest_loss:
                biggest_loss = pos.pnl
                biggest_loser = pos.selection_name
        
        # Create summary table
        summary = Table.grid(padding=1)
        summary.add_column(justify="right", style="cyan")
        summary.add_column(justify="left")
        
        # Add rows
        summary.add_row("Open Positions:", Text(str(len(positions)), style="bold white"))
        summary.add_row("Total Exposure:", Text(f"£{total_exposure:.2f}", style="bold yellow"))
        
        # P&L rows
        real_color = "green" if realized_pnl >= 0 else "red"
        unreal_color = "green" if unrealized_pnl >= 0 else "red"
        total_color = "bold green" if total_pnl >= 0 else "bold red"
        
        summary.add_row("Realized P&L:", Text(f"£{realized_pnl:.2f}", style=real_color))
        summary.add_row("Unrealized P&L:", Text(f"£{unrealized_pnl:.2f}", style=unreal_color))
        summary.add_row("Total P&L:", Text(f"£{total_pnl:.2f}", style=total_color))
        
        # Biggest winner/loser
        if biggest_winner:
            summary.add_row("Best:", Text(f"{biggest_winner} +£{biggest_win:.2f}", style="green"))
        if biggest_loser:
            summary.add_row("Worst:", Text(f"{biggest_loser} -£{abs(biggest_loss):.2f}", style="red"))
        
        return Panel(
            summary,
            title="📈 Position Summary",
            border_style="blue",
            padding=(0, 1)
        )
    
    def _sort_positions(self, positions: List[Position]) -> List[Position]:
        """Sort positions by selected column."""
        if self.sort_column == SortColumn.MATCH:
            key = lambda p: p.match_id
        elif self.sort_column == SortColumn.STAKE:
            key = lambda p: p.stake
        elif self.sort_column == SortColumn.ODDS:
            key = lambda p: p.odds
        elif self.sort_column == SortColumn.CURRENT:
            key = lambda p: p.current_odds or Decimal("0")
        elif self.sort_column == SortColumn.PNL:
            key = lambda p: p.pnl
        else:  # TIME
            key = lambda p: p.opened_at
        
        return sorted(positions, key=key, reverse=not self.sort_ascending)
    
    def _highlight_cell(self, cell) -> Text:
        """Highlight a cell for selection."""
        if isinstance(cell, Text):
            new_style = cell.style or ""
            if "on " not in new_style:
                new_style += " on dark_cyan"
            return Text(cell.plain, style=new_style)
        else:
            return Text(str(cell), style="on dark_cyan")
    
    def cycle_sort(self):
        """Cycle through sort columns."""
        columns = list(SortColumn)
        current_idx = columns.index(self.sort_column)
        self.sort_column = columns[(current_idx + 1) % len(columns)]
    
    def toggle_sort_direction(self):
        """Toggle sort direction."""
        self.sort_ascending = not self.sort_ascending
    
    def move_selection_up(self):
        """Move selection up."""
        if self.selected_position_index > 0:
            self.selected_position_index -= 1
    
    def move_selection_down(self):
        """Move selection down."""
        positions = self.position_store.get_open_positions()
        if self.selected_position_index < len(positions) - 1:
            self.selected_position_index += 1
    
    def get_selected_position(self) -> Optional[Position]:
        """Get currently selected position."""
        positions = self.position_store.get_open_positions()
        if positions and self.selected_position_index < len(positions):
            sorted_positions = self._sort_positions(positions)
            return sorted_positions[self.selected_position_index]
        return None