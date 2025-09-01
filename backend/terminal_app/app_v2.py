"""Enhanced terminal trading application with trading grid."""

import asyncio
import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Optional
import logging

from rich.live import Live
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from dotenv import load_dotenv

from .components.layout import AppLayout
from .components.trading_grid import TradingGrid
from .components.bet_modal import BetModal, BetConfirmation
from .stores.match_store import MatchDataStore
from .stores.position_store import PositionStore
from .stores.trade_store import TradeStore
from .websocket_client import WebSocketClient
from .models import RiskMetrics, OrderSide


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('terminal_app.log')]
)
logger = logging.getLogger(__name__)


class TradingTerminalApp:
    """Enhanced terminal trading application with grid interface."""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize console and layout
        self.console = Console()
        self.layout = AppLayout()
        
        # Initialize data stores
        self.match_store = MatchDataStore()
        self.position_store = PositionStore()
        self.trade_store = TradeStore()
        
        # Initialize components
        self.trading_grid = TradingGrid(self.match_store, self.position_store)
        self.bet_modal = BetModal()
        self.bet_confirmation = BetConfirmation()
        
        # Initialize WebSocket client
        ws_url = os.getenv('WS_URL', 'ws://localhost:8000/api/ws/monitor')
        self.ws_client = WebSocketClient(
            ws_url,
            self.match_store,
            self.position_store,
            self.trade_store
        )
        
        # Application state
        self.running = False
        self.live_display: Optional[Live] = None
        self.feed_messages = []
        self.risk_metrics = RiskMetrics()
        
        # Keyboard bindings
        self.kb = KeyBindings()
        self._setup_keybindings()
        
        # Register observers
        self._register_observers()
    
    def _setup_keybindings(self):
        """Set up keyboard bindings."""
        
        @self.kb.add('q')
        @self.kb.add('c-c')
        async def quit_app(event):
            """Quit the application."""
            if self.bet_modal.is_open:
                self.bet_modal.close()
            else:
                self.running = False
                if self.live_display:
                    self.live_display.stop()
                await self.shutdown()
                sys.exit(0)
        
        @self.kb.add('r')
        async def refresh(event):
            """Refresh all data."""
            await self.refresh_data()
        
        # Navigation
        @self.kb.add(Keys.Up)
        @self.kb.add('k')
        async def move_up(event):
            """Move selection up."""
            if not self.bet_modal.is_open:
                self.trading_grid.move_selection_up()
                await self.update_display()
        
        @self.kb.add(Keys.Down)
        @self.kb.add('j')
        async def move_down(event):
            """Move selection down."""
            if not self.bet_modal.is_open:
                self.trading_grid.move_selection_down()
                await self.update_display()
        
        # Betting
        @self.kb.add('b')
        async def back_bet(event):
            """Place a back bet."""
            if not self.bet_modal.is_open:
                await self._open_bet_modal(OrderSide.BACK)
        
        @self.kb.add('l')
        async def lay_bet(event):
            """Place a lay bet."""
            if not self.bet_modal.is_open:
                await self._open_bet_modal(OrderSide.LAY)
        
        # Quick stakes (1-5)
        for i in range(1, 6):
            @self.kb.add(str(i))
            async def quick_stake(event, stake_index=i-1):
                """Set quick stake."""
                if self.bet_modal.is_open:
                    # Update stake in modal
                    stake = self.trading_grid.quick_stakes[stake_index]
                    self.bet_modal.update_stake(str(stake))
                else:
                    # Set default stake
                    self.trading_grid.selected_stake_index = stake_index
                    self.add_feed_message(
                        f"Stake set to £{self.trading_grid.get_selected_stake()}", 
                        "yellow"
                    )
                await self.update_display()
        
        # Modal controls
        @self.kb.add('y')
        @self.kb.add('Y')
        async def confirm_bet(event):
            """Confirm bet placement."""
            if self.bet_modal.is_open:
                await self._place_bet()
        
        @self.kb.add('n')
        @self.kb.add('N')
        @self.kb.add(Keys.Escape)
        async def cancel_bet(event):
            """Cancel bet placement."""
            if self.bet_modal.is_open:
                self.bet_modal.close()
                self.add_feed_message("Bet cancelled", "yellow")
                await self.update_display()
        
        # Price adjustment in modal
        @self.kb.add('+')
        async def increase_price(event):
            """Increase price."""
            if self.bet_modal.is_open and self.bet_modal.price:
                new_price = self.bet_modal.price + Decimal("0.01")
                self.bet_modal.update_price(str(new_price))
                await self.update_display()
        
        @self.kb.add('-')
        async def decrease_price(event):
            """Decrease price."""
            if self.bet_modal.is_open and self.bet_modal.price:
                new_price = max(Decimal("1.01"), self.bet_modal.price - Decimal("0.01"))
                self.bet_modal.update_price(str(new_price))
                await self.update_display()
        
        # Help
        @self.kb.add('?')
        @self.kb.add('h')
        async def show_help(event):
            """Show help menu."""
            if not self.bet_modal.is_open:
                self.add_feed_message(
                    "Keys: ↑↓/jk=navigate, b=back, l=lay, 1-5=stake, r=refresh, q=quit", 
                    "cyan"
                )
    
    def _register_observers(self):
        """Register observers for data changes."""
        # WebSocket connection observer
        self.ws_client.add_connection_observer(self._on_connection_change)
        
        # Data store observers
        self.match_store.add_observer(self._on_data_update)
        self.position_store.add_observer(self._on_data_update)
        self.trade_store.add_observer(self._on_data_update)
    
    def _on_connection_change(self, connected: bool):
        """Handle WebSocket connection changes."""
        status = "Connected" if connected else "Disconnected"
        self.add_feed_message(
            f"WebSocket {status}",
            "green" if connected else "red"
        )
        asyncio.create_task(self.update_display())
    
    def _on_data_update(self):
        """Handle data updates from stores."""
        asyncio.create_task(self.update_display())
    
    async def _open_bet_modal(self, side: OrderSide):
        """Open bet placement modal."""
        match_id, selection_id, selection_name = self.trading_grid.get_selected_market()
        
        if not selection_id:
            self.add_feed_message("No selection", "red")
            return
        
        # Get current price
        prices = self.match_store.get_prices(match_id)
        price_data = prices.get(selection_id) if prices else None
        
        if not price_data:
            self.add_feed_message("No price available", "red")
            return
        
        # Get appropriate price
        if side == OrderSide.BACK:
            price = price_data.back_price
        else:
            price = price_data.lay_price
        
        if not price:
            self.add_feed_message(f"No {side.value.lower()} price available", "red")
            return
        
        # Open modal
        self.bet_modal.open(
            selection_name,
            side,
            price,
            self.trading_grid.get_selected_stake()
        )
        
        await self.update_display()
    
    async def _place_bet(self):
        """Place the bet from modal."""
        bet_details = self.bet_modal.get_bet_details()
        
        if not bet_details:
            self.add_feed_message("Invalid bet details", "red")
            return
        
        side, stake, price = bet_details
        match_id, selection_id, selection_name = self.trading_grid.get_selected_market()
        
        # Close modal
        self.bet_modal.close()
        
        # Show confirmation
        self.bet_confirmation.show_pending(
            f"Placing {side.value} £{stake} @ {price} on {selection_name}"
        )
        await self.update_display()
        
        # Send bet via WebSocket
        await self.ws_client.send_message({
            'type': 'place_bet',
            'data': {
                'match_id': match_id,
                'selection_id': selection_id,
                'selection_name': selection_name,
                'side': side.value,
                'stake': str(stake),
                'price': str(price)
            }
        })
        
        # Add to feed
        self.add_feed_message(
            f"✓ {side.value} {selection_name} £{stake} @ {price}",
            "green"
        )
        
        # Close confirmation after delay
        await asyncio.sleep(2)
        self.bet_confirmation.close()
        await self.update_display()
    
    def add_feed_message(self, text: str, style: str = "white"):
        """Add a message to the feed."""
        self.feed_messages.append({
            'time': datetime.now(),
            'text': text,
            'style': style
        })
        # Keep only last 100 messages
        if len(self.feed_messages) > 100:
            self.feed_messages = self.feed_messages[-100:]
    
    async def update_display(self):
        """Update the display with current data."""
        if not self.live_display:
            return
        
        # Update header
        conn_status = "Connected" if self.ws_client.is_connected else "Disconnected"
        total_pnl = self.position_store.get_total_pnl()
        self.layout.update_header(conn_status, total_pnl)
        
        # Update main content with trading grid
        grid = self.trading_grid.create_grid()
        
        # Add bet modal if open
        if self.bet_modal.is_open:
            modal = self.bet_modal.create_panel()
            # Overlay modal on grid
            combined = Layout()
            combined.split_column(
                Layout(grid, ratio=1),
                Layout(Align.center(modal, vertical="middle"), size=15)
            )
            self.layout.update_main(combined)
        elif self.bet_confirmation.is_open:
            confirmation = self.bet_confirmation.create_panel()
            combined = Layout()
            combined.split_column(
                Layout(grid, ratio=1),
                Layout(Align.center(confirmation, vertical="bottom"), size=5)
            )
            self.layout.update_main(combined)
        else:
            self.layout.update_main(Panel(grid, border_style="green"))
        
        # Update feed
        self.layout.update_feed(self.feed_messages)
        
        # Update status bar
        self.layout.update_status(self.risk_metrics)
        
        # Refresh display
        self.live_display.refresh()
    
    async def refresh_data(self):
        """Refresh all data from server."""
        self.add_feed_message("Refreshing data...", "yellow")
        await self.update_display()
    
    async def run(self):
        """Run the main application loop."""
        self.running = True
        
        # Start WebSocket connection
        ws_task = asyncio.create_task(self.ws_client.connect())
        
        # Initial display update
        await self.update_display()
        
        # Start Rich Live display
        with Live(
            self.layout.get_layout(),
            console=self.console,
            screen=True,
            refresh_per_second=4
        ) as live:
            self.live_display = live
            
            # Welcome message
            self.add_feed_message("🎾 Tennis Trading Terminal v2.0", "green")
            self.add_feed_message("Keys: ↑↓=navigate, b=back, l=lay, 1-5=stake", "cyan")
            self.add_feed_message("Press ? for help, q to quit", "yellow")
            
            # Run keyboard input handler in background
            kb_task = asyncio.create_task(self._handle_keyboard())
            
            try:
                # Keep the app running
                while self.running:
                    await self.update_display()
                    await asyncio.sleep(0.25)  # Update 4 times per second
                    
            except KeyboardInterrupt:
                pass
            finally:
                self.running = False
                kb_task.cancel()
                ws_task.cancel()
    
    async def _handle_keyboard(self):
        """Handle keyboard input asynchronously."""
        while self.running:
            await asyncio.sleep(0.1)
    
    async def shutdown(self):
        """Shutdown the application gracefully."""
        logger.info("Shutting down terminal app")
        self.running = False
        await self.ws_client.disconnect()
        self.add_feed_message("Shutting down...", "yellow")


async def main():
    """Main entry point."""
    app = TradingTerminalApp()
    try:
        await app.run()
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())