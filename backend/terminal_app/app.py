"""Main terminal trading application."""

import asyncio
import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Optional
import logging

from rich.live import Live
from rich.console import Console
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from dotenv import load_dotenv

from .components.layout import AppLayout
from .stores.match_store import MatchDataStore
from .stores.position_store import PositionStore
from .stores.trade_store import TradeStore
from .websocket_client import WebSocketClient
from .models import RiskMetrics


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('terminal_app.log')]
)
logger = logging.getLogger(__name__)


class TradingTerminalApp:
    """Main terminal trading application."""
    
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
            self.running = False
            if self.live_display:
                self.live_display.stop()
            await self.shutdown()
            sys.exit(0)
        
        @self.kb.add('r')
        async def refresh(event):
            """Refresh all data."""
            await self.refresh_data()
        
        @self.kb.add('b')
        async def back_bet(event):
            """Place a back bet."""
            self.add_feed_message("Back bet placeholder", "green")
        
        @self.kb.add('l')
        async def lay_bet(event):
            """Place a lay bet."""
            self.add_feed_message("Lay bet placeholder", "red")
        
        @self.kb.add(Keys.Up)
        @self.kb.add('k')
        async def move_up(event):
            """Move selection up."""
            self.add_feed_message("Move up", "dim")
        
        @self.kb.add(Keys.Down)
        @self.kb.add('j')
        async def move_down(event):
            """Move selection down."""
            self.add_feed_message("Move down", "dim")
        
        @self.kb.add('?')
        @self.kb.add('h')
        async def show_help(event):
            """Show help menu."""
            self.add_feed_message("Help: q=quit, r=refresh, b=back, l=lay, arrows=navigate", "yellow")
    
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
        
        # Update main content (placeholder for now)
        self.layout.update_main(self.layout.create_placeholder_grid())
        
        # Update feed
        self.layout.update_feed(self.feed_messages)
        
        # Update status bar
        self.layout.update_status(self.risk_metrics)
        
        # Refresh display
        self.live_display.refresh()
    
    async def refresh_data(self):
        """Refresh all data from server."""
        self.add_feed_message("Refreshing data...", "yellow")
        # In a real implementation, this would request fresh data
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
            self.add_feed_message("Tennis Trading Terminal started", "green")
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
        # Note: In a real implementation, we'd use prompt_toolkit's async input
        # For now, this is a placeholder
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