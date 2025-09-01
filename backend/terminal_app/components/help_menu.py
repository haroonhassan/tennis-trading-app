"""Help menu component showing all keyboard shortcuts."""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.console import Group


class HelpMenu:
    """Help menu showing all keyboard shortcuts."""
    
    def __init__(self):
        self.is_visible = False
    
    def create_panel(self) -> Panel:
        """Create the help menu panel."""
        # Create tables for different categories
        navigation_table = self._create_navigation_table()
        trading_table = self._create_trading_table()
        position_table = self._create_position_table()
        view_table = self._create_view_table()
        advanced_table = self._create_advanced_table()
        system_table = self._create_system_table()
        
        # Arrange in columns
        left_column = Group(
            navigation_table,
            Text(""),
            trading_table,
            Text(""),
            position_table
        )
        
        right_column = Group(
            view_table,
            Text(""),
            advanced_table,
            Text(""),
            system_table
        )
        
        # Create main content
        content = Columns([left_column, right_column], padding=2, expand=True)
        
        # Create panel
        return Panel(
            content,
            title="⌨️  Keyboard Shortcuts",
            subtitle="Press any key to close",
            border_style="bright_blue",
            padding=(1, 2)
        )
    
    def _create_navigation_table(self) -> Panel:
        """Create navigation shortcuts table."""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Key", style="bold cyan", width=15)
        table.add_column("Action", style="white")
        
        table.add_row("↑/↓, j/k", "Navigate up/down")
        table.add_row("←/→, h/l", "Navigate left/right")
        table.add_row("Page Up/Down", "Fast scroll")
        table.add_row("Home/End", "Jump to top/bottom")
        table.add_row("Tab", "Cycle panels")
        table.add_row("/", "Search/filter")
        
        return Panel(table, title="Navigation", border_style="cyan", expand=False)
    
    def _create_trading_table(self) -> Panel:
        """Create trading shortcuts table."""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Key", style="bold green", width=15)
        table.add_column("Action", style="white")
        
        table.add_row("b", "Place back bet")
        table.add_row("l", "Place lay bet")
        table.add_row("1-5", "Quick stake select")
        table.add_row("+/-", "Adjust stake/price")
        table.add_row("Enter", "Confirm action")
        table.add_row("Esc", "Cancel/close modal")
        table.add_row("Y/N", "Yes/No in modals")
        
        return Panel(table, title="Trading", border_style="green", expand=False)
    
    def _create_position_table(self) -> Panel:
        """Create position management shortcuts table."""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Key", style="bold yellow", width=15)
        table.add_column("Action", style="white")
        
        table.add_row("c", "Close position")
        table.add_row("h", "Hedge (green up)")
        table.add_row("x", "Set stop loss")
        table.add_row("t", "Set take profit")
        table.add_row("s", "Sort positions")
        table.add_row("Shift+S", "Sort direction")
        
        return Panel(table, title="Position Management", border_style="yellow", expand=False)
    
    def _create_view_table(self) -> Panel:
        """Create view control shortcuts table."""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Key", style="bold magenta", width=15)
        table.add_column("Action", style="white")
        
        table.add_row("F1", "Trading grid")
        table.add_row("F2", "Positions view")
        table.add_row("F3", "Split screen")
        table.add_row("F4", "Risk dashboard")
        table.add_row("F5", "Live feed")
        table.add_row("F6", "Charts view")
        table.add_row("o", "Toggle odds format")
        table.add_row("p", "Positions only")
        
        return Panel(table, title="View Controls", border_style="magenta", expand=False)
    
    def _create_advanced_table(self) -> Panel:
        """Create advanced shortcuts table."""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Key", style="bold red", width=15)
        table.add_column("Action", style="white")
        
        table.add_row("Shift+C", "Close ALL positions")
        table.add_row("Shift+H", "Hedge ALL positions")
        table.add_row("Shift+S", "KILL SWITCH")
        table.add_row("Ctrl+Z", "Undo last action")
        
        return Panel(table, title="⚠️  Advanced", border_style="red", expand=False)
    
    def _create_system_table(self) -> Panel:
        """Create system shortcuts table."""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Key", style="bold blue", width=15)
        table.add_column("Action", style="white")
        
        table.add_row("r", "Refresh data")
        table.add_row("?", "Show this help")
        table.add_row("q", "Quit application")
        table.add_row("Ctrl+C", "Force quit")
        
        return Panel(table, title="System", border_style="blue", expand=False)
    
    def show(self):
        """Show the help menu."""
        self.is_visible = True
    
    def hide(self):
        """Hide the help menu."""
        self.is_visible = False
    
    def toggle(self):
        """Toggle help menu visibility."""
        self.is_visible = not self.is_visible


class QuickReferenceBar:
    """Quick reference bar showing current mode and available actions."""
    
    def __init__(self):
        self.mode = "Normal"
        self.context_actions = []
    
    def create_bar(self) -> Text:
        """Create the quick reference bar."""
        parts = []
        
        # Mode indicator
        if self.mode != "Normal":
            parts.append(f"[{self.mode}]")
        
        # Context actions
        if self.context_actions:
            actions = " | ".join(self.context_actions)
            parts.append(actions)
        else:
            # Default actions based on mode
            if self.mode == "Trading":
                parts.append("b=Back l=Lay 1-5=Stake ↑↓=Navigate")
            elif self.mode == "Positions":
                parts.append("c=Close h=Hedge x=Stop ↑↓=Select")
            elif self.mode == "Confirm":
                parts.append("Y=Yes N=No ESC=Cancel")
            else:
                parts.append("F1-F4=Views b=Back l=Lay ?=Help q=Quit")
        
        return Text(" | ".join(parts), style="dim")
    
    def set_mode(self, mode: str):
        """Set the current mode."""
        self.mode = mode
    
    def set_context(self, actions: list):
        """Set context-specific actions."""
        self.context_actions = actions