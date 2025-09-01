"""Bet placement modal component."""

from decimal import Decimal
from typing import Optional, Tuple

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.console import Group
from rich.layout import Layout

from ..models import OrderSide


class BetModal:
    """Modal dialog for bet placement and confirmation."""
    
    def __init__(self):
        self.is_open = False
        self.selection_name: Optional[str] = None
        self.side: Optional[OrderSide] = None
        self.price: Optional[Decimal] = None
        self.stake: Optional[Decimal] = None
        self.liability: Optional[Decimal] = None
        self.potential_profit: Optional[Decimal] = None
        self.error_message: Optional[str] = None
        
        # Input state
        self.stake_input = ""
        self.price_input = ""
        self.confirm_required = True
    
    def open(
        self,
        selection_name: str,
        side: OrderSide,
        price: Decimal,
        default_stake: Decimal
    ):
        """Open the modal with bet details."""
        self.is_open = True
        self.selection_name = selection_name
        self.side = side
        self.price = price
        self.stake = default_stake
        self.stake_input = str(default_stake)
        self.price_input = str(price)
        self.error_message = None
        
        self._calculate_liability_and_profit()
    
    def close(self):
        """Close the modal."""
        self.is_open = False
        self.error_message = None
    
    def _calculate_liability_and_profit(self):
        """Calculate liability and potential profit."""
        if not self.stake or not self.price:
            return
        
        if self.side == OrderSide.BACK:
            # Back bet: liability = stake, profit = stake * (odds - 1)
            self.liability = self.stake
            self.potential_profit = self.stake * (self.price - 1)
        else:
            # Lay bet: liability = stake * (odds - 1), profit = stake
            self.liability = self.stake * (self.price - 1)
            self.potential_profit = self.stake
    
    def update_stake(self, new_stake: str):
        """Update stake amount."""
        try:
            self.stake = Decimal(new_stake)
            self.stake_input = new_stake
            self._calculate_liability_and_profit()
            self.error_message = None
        except (ValueError, ArithmeticError):
            self.error_message = "Invalid stake amount"
    
    def update_price(self, new_price: str):
        """Update price/odds."""
        try:
            price = Decimal(new_price)
            if price < Decimal("1.01") or price > Decimal("1000"):
                self.error_message = "Price must be between 1.01 and 1000"
            else:
                self.price = price
                self.price_input = new_price
                self._calculate_liability_and_profit()
                self.error_message = None
        except (ValueError, ArithmeticError):
            self.error_message = "Invalid price"
    
    def create_panel(self) -> Panel:
        """Create the modal panel."""
        if not self.is_open:
            return Panel("", height=1, style="hidden")
        
        # Create content
        content = []
        
        # Title
        side_color = "green" if self.side == OrderSide.BACK else "red"
        title = Text(f"{self.side.value} {self.selection_name}", style=f"bold {side_color}")
        content.append(Align.center(title))
        content.append(Text(""))
        
        # Create details table
        details = Table.grid(padding=1)
        details.add_column(justify="right", style="cyan")
        details.add_column(justify="left")
        
        # Price row
        price_text = Text(self.price_input, style="bold white")
        details.add_row("Price:", price_text)
        
        # Stake row with input indication
        stake_text = Text(f"£{self.stake_input}", style="bold yellow")
        details.add_row("Stake:", stake_text)
        
        # Liability row
        if self.liability:
            liab_text = Text(f"£{self.liability:.2f}", style="bold red")
            details.add_row("Liability:", liab_text)
        
        # Potential profit row
        if self.potential_profit:
            profit_text = Text(f"£{self.potential_profit:.2f}", style="bold green")
            details.add_row("Profit:", profit_text)
        
        content.append(Align.center(details))
        
        # Error message
        if self.error_message:
            content.append(Text(""))
            error = Text(f"⚠️  {self.error_message}", style="bold red")
            content.append(Align.center(error))
        
        # Instructions
        content.append(Text(""))
        
        if self.confirm_required:
            instructions = Table.grid()
            instructions.add_column(justify="center")
            instructions.add_row(
                Text("Press [Y] to confirm, [N] to cancel", style="dim")
            )
            instructions.add_row(
                Text("Use number keys to edit stake", style="dim")
            )
            instructions.add_row(
                Text("Press [+/-] to adjust price", style="dim")
            )
            content.append(Align.center(instructions))
        
        # Create panel
        panel_content = Group(*content)
        
        return Panel(
            panel_content,
            title="🎰 Place Bet",
            border_style=side_color,
            padding=(1, 2),
            expand=False
        )
    
    def get_bet_details(self) -> Optional[Tuple[OrderSide, Decimal, Decimal]]:
        """Get bet details if valid."""
        if self.is_open and self.stake and self.price and not self.error_message:
            return (self.side, self.stake, self.price)
        return None


class BetConfirmation:
    """Simple confirmation for quick bets."""
    
    def __init__(self):
        self.is_open = False
        self.message = ""
        self.style = "green"
    
    def show_success(self, message: str):
        """Show success confirmation."""
        self.is_open = True
        self.message = f"✅ {message}"
        self.style = "green"
    
    def show_error(self, message: str):
        """Show error message."""
        self.is_open = True
        self.message = f"❌ {message}"
        self.style = "red"
    
    def show_pending(self, message: str):
        """Show pending message."""
        self.is_open = True
        self.message = f"⏳ {message}"
        self.style = "yellow"
    
    def close(self):
        """Close the confirmation."""
        self.is_open = False
    
    def create_panel(self) -> Optional[Panel]:
        """Create confirmation panel."""
        if not self.is_open:
            return None
        
        return Panel(
            Align.center(Text(self.message, style=f"bold {self.style}")),
            border_style=self.style,
            padding=(0, 2),
            height=3
        )