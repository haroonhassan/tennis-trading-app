"""Position management modals."""

from decimal import Decimal
from typing import Optional, Tuple

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.console import Group

from ..models import Position, OrderSide


class ClosePositionModal:
    """Modal for closing a position."""
    
    def __init__(self):
        self.is_open = False
        self.position: Optional[Position] = None
        self.close_price: Optional[Decimal] = None
        self.pnl: Optional[Decimal] = None
    
    def open(self, position: Position, current_price: Decimal):
        """Open the modal."""
        self.is_open = True
        self.position = position
        self.close_price = current_price
        self.pnl = self._calculate_close_pnl(position, current_price)
    
    def _calculate_close_pnl(self, position: Position, price: Decimal) -> Decimal:
        """Calculate P&L if closed at given price."""
        if position.side == OrderSide.BACK:
            # Close back position by laying
            return position.stake * (position.odds - price) / price
        else:
            # Close lay position by backing
            return position.stake * (price - position.odds) / position.odds
    
    def create_panel(self) -> Panel:
        """Create the modal panel."""
        if not self.is_open or not self.position:
            return Panel("", height=1, style="hidden")
        
        content = []
        
        # Title
        title = Text(f"Close Position: {self.position.selection_name}", style="bold yellow")
        content.append(Align.center(title))
        content.append(Text(""))
        
        # Details table
        details = Table.grid(padding=1)
        details.add_column(justify="right", style="cyan")
        details.add_column(justify="left")
        
        # Position details
        side_color = "green" if self.position.side == OrderSide.BACK else "red"
        details.add_row("Side:", Text(self.position.side.value, style=side_color))
        details.add_row("Stake:", Text(f"£{self.position.stake:.2f}", style="white"))
        details.add_row("Entry:", Text(f"{self.position.odds:.2f}", style="white"))
        details.add_row("Current:", Text(f"{self.close_price:.2f}", style="yellow"))
        
        # P&L
        pnl_color = "bold green" if self.pnl >= 0 else "bold red"
        pnl_text = f"+£{self.pnl:.2f}" if self.pnl >= 0 else f"-£{abs(self.pnl):.2f}"
        details.add_row("P&L:", Text(pnl_text, style=pnl_color))
        
        content.append(Align.center(details))
        content.append(Text(""))
        
        # Instructions
        instructions = Text("Press [Y] to close position, [N] to cancel", style="dim")
        content.append(Align.center(instructions))
        
        return Panel(
            Group(*content),
            title="💰 Close Position",
            border_style="yellow",
            padding=(1, 2)
        )


class HedgePositionModal:
    """Modal for hedging/greening up a position."""
    
    def __init__(self):
        self.is_open = False
        self.position: Optional[Position] = None
        self.hedge_stake: Optional[Decimal] = None
        self.hedge_price: Optional[Decimal] = None
        self.guaranteed_profit: Optional[Decimal] = None
    
    def open(self, position: Position, current_price: Decimal):
        """Open the modal."""
        self.is_open = True
        self.position = position
        self.hedge_price = current_price
        
        # Calculate hedge stake for equal profit
        if position.side == OrderSide.BACK:
            # Need to lay to hedge a back bet
            self.hedge_stake = position.stake * position.odds / current_price
        else:
            # Need to back to hedge a lay bet
            self.hedge_stake = position.stake * position.odds / current_price
        
        # Calculate guaranteed profit
        self._calculate_guaranteed_profit()
    
    def _calculate_guaranteed_profit(self):
        """Calculate guaranteed profit after hedging."""
        if not self.position or not self.hedge_stake:
            return
        
        if self.position.side == OrderSide.BACK:
            # Original back bet hedged with lay
            win_profit = self.position.stake * (self.position.odds - 1) - self.hedge_stake * (self.hedge_price - 1)
            lose_profit = -self.position.stake + self.hedge_stake
        else:
            # Original lay bet hedged with back
            win_profit = self.position.stake - self.hedge_stake * (self.hedge_price - 1)
            lose_profit = -self.position.stake * (self.position.odds - 1) + self.hedge_stake
        
        # Equal profit regardless of outcome
        self.guaranteed_profit = min(win_profit, lose_profit)
    
    def create_panel(self) -> Panel:
        """Create the modal panel."""
        if not self.is_open or not self.position:
            return Panel("", height=1, style="hidden")
        
        content = []
        
        # Title
        title = Text(f"Hedge Position: {self.position.selection_name}", style="bold green")
        content.append(Align.center(title))
        content.append(Text(""))
        
        # Details table
        details = Table.grid(padding=1)
        details.add_column(justify="right", style="cyan")
        details.add_column(justify="left")
        
        # Original position
        details.add_row("Original:", Text(
            f"{self.position.side.value} £{self.position.stake:.2f} @ {self.position.odds:.2f}",
            style="white"
        ))
        
        # Hedge bet
        hedge_side = OrderSide.LAY if self.position.side == OrderSide.BACK else OrderSide.BACK
        hedge_color = "red" if hedge_side == OrderSide.LAY else "green"
        details.add_row("Hedge:", Text(
            f"{hedge_side.value} £{self.hedge_stake:.2f} @ {self.hedge_price:.2f}",
            style=hedge_color
        ))
        
        # Guaranteed profit
        profit_color = "bold green" if self.guaranteed_profit >= 0 else "bold red"
        profit_text = f"+£{self.guaranteed_profit:.2f}" if self.guaranteed_profit >= 0 else f"-£{abs(self.guaranteed_profit):.2f}"
        details.add_row("Guaranteed:", Text(profit_text, style=profit_color))
        
        content.append(Align.center(details))
        content.append(Text(""))
        
        # Instructions
        instructions = Text("Press [Y] to hedge position, [N] to cancel", style="dim")
        content.append(Align.center(instructions))
        
        return Panel(
            Group(*content),
            title="🌿 Hedge Position (Green Up)",
            border_style="green",
            padding=(1, 2)
        )


class StopLossModal:
    """Modal for setting stop loss."""
    
    def __init__(self):
        self.is_open = False
        self.position: Optional[Position] = None
        self.stop_price: Optional[Decimal] = None
        self.stop_loss_input = ""
        self.max_loss: Optional[Decimal] = None
    
    def open(self, position: Position):
        """Open the modal."""
        self.is_open = True
        self.position = position
        
        # Default stop loss price
        if position.side == OrderSide.BACK:
            # Stop loss at 10% below entry
            self.stop_price = position.odds * Decimal("0.9")
        else:
            # Stop loss at 10% above entry
            self.stop_price = position.odds * Decimal("1.1")
        
        self.stop_loss_input = str(self.stop_price)
        self._calculate_max_loss()
    
    def update_stop_price(self, new_price: str):
        """Update stop price."""
        try:
            price = Decimal(new_price)
            if price >= Decimal("1.01"):
                self.stop_price = price
                self.stop_loss_input = new_price
                self._calculate_max_loss()
        except (ValueError, ArithmeticError):
            pass
    
    def _calculate_max_loss(self):
        """Calculate maximum loss at stop price."""
        if not self.position or not self.stop_price:
            return
        
        if self.position.side == OrderSide.BACK:
            # Loss if we have to lay at higher price
            if self.stop_price > self.position.odds:
                self.max_loss = self.position.stake * (self.stop_price - self.position.odds) / self.stop_price
            else:
                self.max_loss = Decimal("0")  # Would be profitable
        else:
            # Loss if we have to back at lower price
            if self.stop_price < self.position.odds:
                self.max_loss = self.position.stake * (self.position.odds - self.stop_price) / self.position.odds
            else:
                self.max_loss = Decimal("0")  # Would be profitable
    
    def create_panel(self) -> Panel:
        """Create the modal panel."""
        if not self.is_open or not self.position:
            return Panel("", height=1, style="hidden")
        
        content = []
        
        # Title
        title = Text(f"Set Stop Loss: {self.position.selection_name}", style="bold red")
        content.append(Align.center(title))
        content.append(Text(""))
        
        # Details table
        details = Table.grid(padding=1)
        details.add_column(justify="right", style="cyan")
        details.add_column(justify="left")
        
        # Position details
        side_color = "green" if self.position.side == OrderSide.BACK else "red"
        details.add_row("Position:", Text(
            f"{self.position.side.value} £{self.position.stake:.2f} @ {self.position.odds:.2f}",
            style=side_color
        ))
        
        # Stop price
        details.add_row("Stop Price:", Text(self.stop_loss_input, style="yellow"))
        
        # Max loss
        if self.max_loss and self.max_loss > 0:
            details.add_row("Max Loss:", Text(f"-£{self.max_loss:.2f}", style="bold red"))
        else:
            details.add_row("Max Loss:", Text("£0.00", style="green"))
        
        content.append(Align.center(details))
        content.append(Text(""))
        
        # Instructions
        instructions = Table.grid()
        instructions.add_column(justify="center")
        instructions.add_row(Text("Press [Y] to set stop loss, [N] to cancel", style="dim"))
        instructions.add_row(Text("Use number keys to edit stop price", style="dim"))
        content.append(Align.center(instructions))
        
        return Panel(
            Group(*content),
            title="🛑 Set Stop Loss",
            border_style="red",
            padding=(1, 2)
        )