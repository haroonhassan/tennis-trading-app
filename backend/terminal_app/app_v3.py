"""Terminal app v3 with comprehensive keyboard navigation."""

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
from dotenv import load_dotenv

from .components.layout import AppLayout
from .components.trading_grid import TradingGrid
from .components.positions_panel import PositionsPanel
from .components.bet_modal import BetModal, BetConfirmation
from .components.position_modals import ClosePositionModal, HedgePositionModal, StopLossModal
from .components.layout_manager import LayoutManager, ViewMode
from .components.help_menu import HelpMenu, QuickReferenceBar
from .stores.match_store import MatchDataStore
from .stores.position_store import PositionStore
from .stores.trade_store import TradeStore
from .websocket_client import WebSocketClient
from .keyboard_handler import KeyboardHandler, InputMode
from .models import RiskMetrics, OrderSide


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('terminal_app.log')]
)
logger = logging.getLogger(__name__)


class TradingTerminalV3:
    """Enhanced terminal app with full keyboard navigation."""
    
    def __init__(self):
        # Load environment
        load_dotenv()
        
        # Initialize console and layout
        self.console = Console()
        self.app_layout = AppLayout()
        
        # Initialize data stores
        self.match_store = MatchDataStore()
        self.position_store = PositionStore()
        self.trade_store = TradeStore()
        
        # Initialize components
        self.trading_grid = TradingGrid(self.match_store, self.position_store)
        self.positions_panel = PositionsPanel(self.position_store, self.match_store)
        self.layout_manager = LayoutManager(
            self.app_layout,
            self.trading_grid,
            self.positions_panel
        )
        
        # Initialize modals
        self.bet_modal = BetModal()
        self.bet_confirmation = BetConfirmation()
        self.close_modal = ClosePositionModal()
        self.hedge_modal = HedgePositionModal()
        self.stop_loss_modal = StopLossModal()
        
        # Initialize UI helpers
        self.help_menu = HelpMenu()
        self.quick_ref = QuickReferenceBar()
        
        # Initialize keyboard handler
        self.keyboard = KeyboardHandler()
        self._register_keyboard_callbacks()
        
        # Initialize WebSocket
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
        self.search_filter = ""
        self.positions_only = False
        self.odds_format = "decimal"  # or "fractional"
        
        # Register data observers
        self._register_observers()
    
    def _register_keyboard_callbacks(self):
        """Register all keyboard callbacks."""
        
        # Navigation
        self.keyboard.register_callback('navigate_up', self._handle_navigate_up)
        self.keyboard.register_callback('navigate_down', self._handle_navigate_down)
        self.keyboard.register_callback('navigate_left', self._handle_navigate_left)
        self.keyboard.register_callback('navigate_right', self._handle_navigate_right)
        self.keyboard.register_callback('page_up', self._handle_page_up)
        self.keyboard.register_callback('page_down', self._handle_page_down)
        self.keyboard.register_callback('home', self._handle_home)
        self.keyboard.register_callback('end', self._handle_end)
        self.keyboard.register_callback('tab_next', self._handle_tab_next)
        
        # Search
        self.keyboard.register_callback('search', self._handle_search)
        
        # Trading
        self.keyboard.register_callback('place_back', self._handle_place_back)
        self.keyboard.register_callback('place_lay', self._handle_place_lay)
        self.keyboard.register_callback('quick_stake', self._handle_quick_stake)
        self.keyboard.register_callback('adjust_stake', self._handle_adjust_stake)
        self.keyboard.register_callback('adjust_price', self._handle_adjust_price)
        self.keyboard.register_callback('confirm', self._handle_confirm)
        self.keyboard.register_callback('cancel', self._handle_cancel)
        
        # Position management
        self.keyboard.register_callback('close_position', self._handle_close_position)
        self.keyboard.register_callback('hedge_position', self._handle_hedge_position)
        self.keyboard.register_callback('set_stop_loss', self._handle_set_stop_loss)
        self.keyboard.register_callback('set_take_profit', self._handle_set_take_profit)
        
        # Advanced
        self.keyboard.register_callback('close_all', self._handle_close_all)
        self.keyboard.register_callback('hedge_all', self._handle_hedge_all)
        self.keyboard.register_callback('emergency_stop', self._handle_emergency_stop)
        self.keyboard.register_callback('undo', self._handle_undo)
        
        # View controls
        self.keyboard.register_callback('switch_view', self._handle_switch_view)
        self.keyboard.register_callback('toggle_odds_format', self._handle_toggle_odds)
        self.keyboard.register_callback('toggle_positions_only', self._handle_toggle_positions)
        
        # System
        self.keyboard.register_callback('refresh', self._handle_refresh)
        self.keyboard.register_callback('show_help', self._handle_show_help)
        self.keyboard.register_callback('quit', self._handle_quit)
    
    async def _handle_navigate_up(self, data):
        """Handle up navigation."""
        if self.layout_manager.current_mode == ViewMode.TRADING:
            self.trading_grid.move_selection_up()
        elif self.layout_manager.current_mode == ViewMode.POSITIONS:
            self.positions_panel.move_selection_up()
        await self.update_display()
    
    async def _handle_navigate_down(self, data):
        """Handle down navigation."""
        if self.layout_manager.current_mode == ViewMode.TRADING:
            self.trading_grid.move_selection_down()
        elif self.layout_manager.current_mode == ViewMode.POSITIONS:
            self.positions_panel.move_selection_down()
        await self.update_display()
    
    async def _handle_navigate_left(self, data):
        """Handle left navigation."""
        self.add_feed_message("Navigate left", "dim")
    
    async def _handle_navigate_right(self, data):
        """Handle right navigation."""
        self.add_feed_message("Navigate right", "dim")
    
    async def _handle_page_up(self, data):
        """Handle page up."""
        # Move selection up by 5
        for _ in range(5):
            if self.layout_manager.current_mode == ViewMode.TRADING:
                self.trading_grid.move_selection_up()
            elif self.layout_manager.current_mode == ViewMode.POSITIONS:
                self.positions_panel.move_selection_up()
        await self.update_display()
    
    async def _handle_page_down(self, data):
        """Handle page down."""
        # Move selection down by 5
        for _ in range(5):
            if self.layout_manager.current_mode == ViewMode.TRADING:
                self.trading_grid.move_selection_down()
            elif self.layout_manager.current_mode == ViewMode.POSITIONS:
                self.positions_panel.move_selection_down()
        await self.update_display()
    
    async def _handle_home(self, data):
        """Jump to top."""
        if self.layout_manager.current_mode == ViewMode.TRADING:
            self.trading_grid.selection.row_index = 0
        elif self.layout_manager.current_mode == ViewMode.POSITIONS:
            self.positions_panel.selected_position_index = 0
        await self.update_display()
    
    async def _handle_end(self, data):
        """Jump to bottom."""
        if self.layout_manager.current_mode == ViewMode.TRADING:
            self.trading_grid.selection.row_index = self.trading_grid.selection.total_rows - 1
        elif self.layout_manager.current_mode == ViewMode.POSITIONS:
            positions = self.position_store.get_open_positions()
            self.positions_panel.selected_position_index = len(positions) - 1
        await self.update_display()
    
    async def _handle_tab_next(self, data):
        """Switch to next panel."""
        self.layout_manager.toggle_active_pane()
        self.add_feed_message("Switched pane", "dim")
        await self.update_display()
    
    async def _handle_search(self, data):
        """Handle search."""
        action = data.get('action')
        if action == 'start':
            self.add_feed_message("Search mode: Type to filter", "yellow")
            self.quick_ref.set_mode("Search")
        elif action == 'execute':
            query = data.get('query', '')
            self.search_filter = query
            self.add_feed_message(f"Filter: {query}", "green")
            self.quick_ref.set_mode("Normal")
        elif action == 'cancel':
            self.search_filter = ""
            self.add_feed_message("Search cancelled", "yellow")
            self.quick_ref.set_mode("Normal")
        await self.update_display()
    
    async def _handle_place_back(self, data):
        """Place back bet."""
        if self.layout_manager.current_mode == ViewMode.TRADING:
            await self._open_bet_modal(OrderSide.BACK)
    
    async def _handle_place_lay(self, data):
        """Place lay bet."""
        if self.layout_manager.current_mode == ViewMode.TRADING:
            await self._open_bet_modal(OrderSide.LAY)
    
    async def _handle_quick_stake(self, data):
        """Set quick stake."""
        index = data.get('index', 0)
        self.trading_grid.selected_stake_index = index
        stake = self.trading_grid.get_selected_stake()
        self.add_feed_message(f"Stake: £{stake}", "yellow")
        await self.update_display()
    
    async def _handle_adjust_stake(self, data):
        """Adjust stake."""
        direction = data.get('direction', 1)
        self.trading_grid.cycle_stake(direction)
        stake = self.trading_grid.get_selected_stake()
        self.add_feed_message(f"Stake: £{stake}", "yellow")
        await self.update_display()
    
    async def _handle_adjust_price(self, data):
        """Adjust price in modal."""
        if self.bet_modal.is_open and self.bet_modal.price:
            direction = data.get('direction', 1)
            adjustment = Decimal("0.01") * direction
            new_price = max(Decimal("1.01"), self.bet_modal.price + adjustment)
            self.bet_modal.update_price(str(new_price))
            await self.update_display()
    
    async def _handle_confirm(self, data):
        """Confirm current action."""
        if self.bet_modal.is_open:
            await self._place_bet()
        elif self.close_modal.is_open:
            await self._execute_close()
        elif self.hedge_modal.is_open:
            await self._execute_hedge()
        elif self.stop_loss_modal.is_open:
            await self._execute_stop_loss()
        self.quick_ref.set_mode("Normal")
    
    async def _handle_cancel(self, data):
        """Cancel current action."""
        self.bet_modal.close()
        self.close_modal.is_open = False
        self.hedge_modal.is_open = False
        self.stop_loss_modal.is_open = False
        self.add_feed_message("Cancelled", "yellow")
        self.quick_ref.set_mode("Normal")
        await self.update_display()
    
    async def _handle_close_position(self, data):
        """Close position."""
        if self.layout_manager.current_mode == ViewMode.POSITIONS:
            position = self.positions_panel.get_selected_position()
            if position and position.current_odds:
                self.close_modal.open(position, position.current_odds)
                self.quick_ref.set_mode("Confirm")
                await self.update_display()
    
    async def _handle_hedge_position(self, data):
        """Hedge position."""
        if self.layout_manager.current_mode == ViewMode.POSITIONS:
            position = self.positions_panel.get_selected_position()
            if position and position.current_odds:
                self.hedge_modal.open(position, position.current_odds)
                self.quick_ref.set_mode("Confirm")
                await self.update_display()
    
    async def _handle_set_stop_loss(self, data):
        """Set stop loss."""
        if self.layout_manager.current_mode == ViewMode.POSITIONS:
            position = self.positions_panel.get_selected_position()
            if position:
                self.stop_loss_modal.open(position)
                self.quick_ref.set_mode("Stop Loss")
                await self.update_display()
    
    async def _handle_set_take_profit(self, data):
        """Set take profit."""
        self.add_feed_message("Take profit: Coming soon", "yellow")
    
    async def _handle_close_all(self, data):
        """Close all positions."""
        positions = self.position_store.get_open_positions()
        if positions:
            self.add_feed_message(f"⚠️ Close ALL {len(positions)} positions? Y/N", "red")
            self.keyboard.set_mode(InputMode.CONFIRM)
            self.quick_ref.set_mode("Confirm")
            # Would execute on confirm
    
    async def _handle_hedge_all(self, data):
        """Hedge all positions."""
        positions = self.position_store.get_open_positions()
        if positions:
            self.add_feed_message(f"⚠️ Hedge ALL {len(positions)} positions? Y/N", "yellow")
            self.keyboard.set_mode(InputMode.CONFIRM)
            self.quick_ref.set_mode("Confirm")
            # Would execute on confirm
    
    async def _handle_emergency_stop(self, data):
        """Emergency kill switch."""
        self.add_feed_message("🛑 KILL SWITCH ACTIVATED!", "bold red")
        self.risk_metrics.trading_enabled = False
        await self.update_display()
    
    async def _handle_undo(self, data):
        """Undo last action."""
        action = data.get('action')
        if action:
            self.add_feed_message(f"Undo: {action}", "yellow")
    
    async def _handle_switch_view(self, data):
        """Switch view mode."""
        view = data.get('view')
        if view == 'trading':
            self.layout_manager.switch_mode(ViewMode.TRADING)
        elif view == 'positions':
            self.layout_manager.switch_mode(ViewMode.POSITIONS)
        elif view == 'split':
            self.layout_manager.switch_mode(ViewMode.SPLIT)
        elif view == 'risk':
            self.layout_manager.switch_mode(ViewMode.RISK)
        
        self.add_feed_message(f"View: {self.layout_manager.get_mode_indicator()}", "cyan")
        await self.update_display()
    
    async def _handle_toggle_odds(self, data):
        """Toggle odds format."""
        self.odds_format = "fractional" if self.odds_format == "decimal" else "decimal"
        self.add_feed_message(f"Odds format: {self.odds_format}", "yellow")
        await self.update_display()
    
    async def _handle_toggle_positions(self, data):
        """Toggle positions only view."""
        self.positions_only = not self.positions_only
        self.add_feed_message(
            "Positions only: ON" if self.positions_only else "Positions only: OFF",
            "yellow"
        )
        await self.update_display()
    
    async def _handle_refresh(self, data):
        """Refresh data."""
        self.add_feed_message("Refreshing...", "yellow")
        await self.update_display()
    
    async def _handle_show_help(self, data):
        """Show/hide help menu."""
        action = data.get('action')
        if action == 'close':
            self.help_menu.hide()
        else:
            self.help_menu.toggle()
        await self.update_display()
    
    async def _handle_quit(self, data):
        """Quit application."""
        self.running = False
        if self.live_display:
            self.live_display.stop()
        await self.shutdown()
        sys.exit(0)
    
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
        
        price = price_data.back_price if side == OrderSide.BACK else price_data.lay_price
        
        if not price:
            self.add_feed_message(f"No {side.value.lower()} price", "red")
            return
        
        self.bet_modal.open(
            selection_name,
            side,
            price,
            self.trading_grid.get_selected_stake()
        )
        
        self.keyboard.set_mode(InputMode.CONFIRM)
        self.quick_ref.set_mode("Confirm")
        await self.update_display()
    
    async def _place_bet(self):
        """Execute bet placement."""
        bet_details = self.bet_modal.get_bet_details()
        if not bet_details:
            return
        
        side, stake, price = bet_details
        self.bet_modal.close()
        
        self.add_feed_message(
            f"✓ {side.value} £{stake} @ {price}",
            "green"
        )
        
        # Add to undo stack
        self.keyboard.add_to_undo_stack(('bet', bet_details))
        
        await self.update_display()
    
    async def _execute_close(self):
        """Execute position close."""
        if self.close_modal.position:
            self.add_feed_message(
                f"✓ Closed {self.close_modal.position.selection_name} P&L: £{self.close_modal.pnl:.2f}",
                "green" if self.close_modal.pnl >= 0 else "red"
            )
        self.close_modal.is_open = False
        await self.update_display()
    
    async def _execute_hedge(self):
        """Execute position hedge."""
        if self.hedge_modal.position:
            self.add_feed_message(
                f"✓ Hedged {self.hedge_modal.position.selection_name} Guaranteed: £{self.hedge_modal.guaranteed_profit:.2f}",
                "green"
            )
        self.hedge_modal.is_open = False
        await self.update_display()
    
    async def _execute_stop_loss(self):
        """Execute stop loss setup."""
        if self.stop_loss_modal.position:
            self.add_feed_message(
                f"✓ Stop loss set at {self.stop_loss_modal.stop_price}",
                "yellow"
            )
        self.stop_loss_modal.is_open = False
        await self.update_display()
    
    def _register_observers(self):
        """Register data observers."""
        self.ws_client.add_connection_observer(self._on_connection_change)
        self.match_store.add_observer(self._on_data_update)
        self.position_store.add_observer(self._on_data_update)
        self.trade_store.add_observer(self._on_data_update)
    
    def _on_connection_change(self, connected: bool):
        """Handle connection changes."""
        status = "Connected" if connected else "Disconnected"
        self.add_feed_message(f"WebSocket {status}", "green" if connected else "red")
        asyncio.create_task(self.update_display())
    
    def _on_data_update(self):
        """Handle data updates."""
        asyncio.create_task(self.update_display())
    
    def add_feed_message(self, text: str, style: str = "white"):
        """Add message to feed."""
        self.feed_messages.append({
            'time': datetime.now(),
            'text': text,
            'style': style
        })
        if len(self.feed_messages) > 100:
            self.feed_messages = self.feed_messages[-100:]
    
    async def update_display(self):
        """Update the display."""
        if not self.live_display:
            return
        
        # Update header
        conn_status = "Connected" if self.ws_client.is_connected else "Disconnected"
        total_pnl = self.position_store.get_total_pnl()
        self.app_layout.update_header(conn_status, total_pnl)
        
        # Get main content based on mode
        if self.help_menu.is_visible:
            # Show help menu overlay
            main_content = self.help_menu.create_panel()
        else:
            # Normal layout
            main_content = self.layout_manager.create_layout()
            
            # Add modals if open
            if self.bet_modal.is_open:
                modal = self.bet_modal.create_panel()
                main_content = self._overlay_modal(main_content, modal)
            elif self.close_modal.is_open:
                modal = self.close_modal.create_panel()
                main_content = self._overlay_modal(main_content, modal)
            elif self.hedge_modal.is_open:
                modal = self.hedge_modal.create_panel()
                main_content = self._overlay_modal(main_content, modal)
            elif self.stop_loss_modal.is_open:
                modal = self.stop_loss_modal.create_panel()
                main_content = self._overlay_modal(main_content, modal)
        
        self.app_layout.update_main(main_content)
        
        # Update feed
        self.app_layout.update_feed(self.feed_messages)
        
        # Update status with keyboard mode
        mode_text = self.keyboard.get_mode_indicator()
        if mode_text:
            self.risk_metrics.trading_enabled = False  # Show mode in status
        self.app_layout.update_status(self.risk_metrics)
        
        # Refresh
        self.live_display.refresh()
    
    def _overlay_modal(self, main_content, modal):
        """Overlay a modal on main content."""
        from rich.align import Align
        combined = Layout()
        combined.split_column(
            Layout(main_content, ratio=1),
            Layout(Align.center(modal, vertical="middle"), size=15)
        )
        return combined
    
    async def run(self):
        """Run the application."""
        self.running = True
        
        # Start WebSocket
        ws_task = asyncio.create_task(self.ws_client.connect())
        
        # Initial update
        await self.update_display()
        
        # Start Rich Live
        with Live(
            self.app_layout.get_layout(),
            console=self.console,
            screen=True,
            refresh_per_second=4
        ) as live:
            self.live_display = live
            
            # Welcome
            self.add_feed_message("🎾 Tennis Trading Terminal v3", "bold green")
            self.add_feed_message("Full keyboard control enabled", "cyan")
            self.add_feed_message("Press ? for help", "yellow")
            
            try:
                while self.running:
                    await self.update_display()
                    await asyncio.sleep(0.25)
            except KeyboardInterrupt:
                pass
            finally:
                self.running = False
                ws_task.cancel()
    
    async def shutdown(self):
        """Shutdown gracefully."""
        logger.info("Shutting down terminal app v3")
        self.running = False
        await self.ws_client.disconnect()


async def main():
    """Main entry point."""
    app = TradingTerminalV3()
    try:
        await app.run()
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())