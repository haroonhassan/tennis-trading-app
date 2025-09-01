#!/usr/bin/env python3
"""Final integrated terminal trading application."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

# Add components
from models import Match, Position, Trade, OrderSide, PositionStatus, MessageType
from websocket_client import WebSocketClient
from config import ConfigManager, ConfigSection
from stores.match_store import MatchStore
from stores.position_store import PositionStore
from stores.trade_store import TradeStore

# UI Components
from components.layout import AppLayout
from components.trading_grid import TradingGrid
from components.bet_modal import BetModal
from components.positions_panel import PositionsPanel
from components.position_modals import ClosePositionModal, HedgePositionModal, StopLossModal
from components.layout_manager import LayoutManager, ViewMode
from components.risk_dashboard import RiskDashboard, PerformanceMetrics
from components.automated_trading import AutomatedTradingManager
from components.live_feed import LiveDataManager
from components.charts import ChartDashboard
from components.settings_ui import SettingsPanel
from components.help_menu import HelpMenu, QuickReferenceBar
from keyboard_handler_fixed import KeyboardHandler, InputMode


class TennisTradingTerminal:
    """Complete integrated terminal trading application."""
    
    def __init__(self):
        """Initialize the application."""
        self.console = Console()
        self.running = False
        
        # Configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        
        # Data stores
        self.match_store = MatchStore()
        self.position_store = PositionStore()
        self.trade_store = TradeStore()
        
        # WebSocket client
        self.ws_client = WebSocketClient(
            url=self.config.connection.websocket_url,
            on_message=self.handle_ws_message,
            reconnect_interval=self.config.connection.reconnect_interval
        )
        
        # UI Components
        self.app_layout = AppLayout()
        self.trading_grid = TradingGrid(self.match_store)
        self.positions_panel = PositionsPanel(self.position_store)
        self.risk_dashboard = RiskDashboard()
        self.layout_manager = LayoutManager(
            self.app_layout,
            self.trading_grid,
            self.positions_panel,
            self.risk_dashboard
        )
        
        # Additional components
        self.auto_trader = AutomatedTradingManager()
        self.live_feed = LiveDataManager()
        self.chart_dashboard = ChartDashboard()
        self.settings_panel = SettingsPanel(self.config_manager)
        self.help_menu = HelpMenu()
        self.quick_ref = QuickReferenceBar()
        
        # Keyboard handler
        self.keyboard = KeyboardHandler()
        self._setup_keyboard_handlers()
        
        # Modals
        self.bet_modal: Optional[BetModal] = None
        self.position_modal = None
        
        # State
        self.current_view = ViewMode.TRADING
        self.show_help = False
        self.show_settings = False
        self.last_update = datetime.now()
        
        # Statistics
        self.stats = {
            'session_pnl': Decimal('0'),
            'trades_count': 0,
            'win_rate': 0.0,
            'connection_status': 'Disconnected'
        }
    
    def _setup_keyboard_handlers(self):
        """Setup keyboard event handlers."""
        # Navigation
        self.keyboard.register_callback('navigate_up', self._handle_navigate_up)
        self.keyboard.register_callback('navigate_down', self._handle_navigate_down)
        self.keyboard.register_callback('navigate_left', self._handle_navigate_left)
        self.keyboard.register_callback('navigate_right', self._handle_navigate_right)
        self.keyboard.register_callback('page_up', self._handle_page_up)
        self.keyboard.register_callback('page_down', self._handle_page_down)
        self.keyboard.register_callback('home', self._handle_home)
        self.keyboard.register_callback('end', self._handle_end)
        self.keyboard.register_callback('tab_next', self._handle_tab)
        
        # Trading
        self.keyboard.register_callback('place_back', self._handle_place_back)
        self.keyboard.register_callback('place_lay', self._handle_place_lay)
        self.keyboard.register_callback('quick_stake', self._handle_quick_stake)
        self.keyboard.register_callback('adjust_stake', self._handle_adjust_stake)
        
        # Positions
        self.keyboard.register_callback('close_position', self._handle_close_position)
        self.keyboard.register_callback('hedge_position', self._handle_hedge_position)
        self.keyboard.register_callback('set_stop_loss', self._handle_stop_loss)
        self.keyboard.register_callback('set_take_profit', self._handle_take_profit)
        
        # Advanced
        self.keyboard.register_callback('close_all', self._handle_close_all)
        self.keyboard.register_callback('hedge_all', self._handle_hedge_all)
        self.keyboard.register_callback('emergency_stop', self._handle_kill_switch)
        self.keyboard.register_callback('undo', self._handle_undo)
        
        # Views
        self.keyboard.register_callback('switch_view', self._handle_switch_view)
        self.keyboard.register_callback('toggle_odds_format', self._handle_toggle_odds)
        self.keyboard.register_callback('toggle_positions_only', self._handle_toggle_positions)
        
        # System
        self.keyboard.register_callback('refresh', self._handle_refresh)
        self.keyboard.register_callback('show_help', self._handle_help)
        self.keyboard.register_callback('quit', self._handle_quit)
        
        # Confirmations
        self.keyboard.register_callback('confirm', self._handle_confirm)
        self.keyboard.register_callback('cancel', self._handle_cancel)
    
    async def handle_ws_message(self, message: Dict[str, Any]):
        """Handle WebSocket message."""
        msg_type = MessageType(message.get('type', 'unknown'))
        data = message.get('data', {})
        
        # Update stores
        if msg_type == MessageType.MATCH_UPDATE:
            self.match_store.update_match(data)
        elif msg_type == MessageType.PRICE_UPDATE:
            self.match_store.update_price(data)
        elif msg_type == MessageType.POSITION_UPDATE:
            self.position_store.update_position(data)
        elif msg_type == MessageType.TRADE_UPDATE:
            self.trade_store.add_trade(data)
        elif msg_type == MessageType.SCORE_UPDATE:
            self.match_store.update_score(data)
        
        # Process in live feed
        self.live_feed.process_message(msg_type, data)
        
        # Check automated orders
        if msg_type == MessageType.PRICE_UPDATE:
            positions = self.position_store.get_all_positions()
            current_prices = {data.get('selection'): Decimal(str(data.get('price', 0)))}
            triggered = self.auto_trader.check_triggers(positions, current_prices)
            
            for order in triggered:
                await self._execute_automated_order(order)
        
        # Update statistics
        self._update_statistics()
    
    def create_display(self) -> Layout:
        """Create the main display layout."""
        # Main layout based on current view
        if self.show_help:
            return Layout(self.help_menu.create_panel())
        
        if self.show_settings:
            return Layout(self.settings_panel.create_panel())
        
        # Update layout manager data
        self.layout_manager.update_data(
            self.position_store.get_all_positions(),
            self.trade_store.get_all_trades()
        )
        
        # Get appropriate view
        if self.current_view == ViewMode.TRADING:
            main_content = self.layout_manager._create_trading_layout()
        elif self.current_view == ViewMode.POSITIONS:
            main_content = self.layout_manager._create_positions_layout()
        elif self.current_view == ViewMode.SPLIT:
            main_content = self.layout_manager._create_split_layout()
        elif self.current_view == ViewMode.RISK:
            main_content = self.layout_manager._create_risk_layout()
        elif self.current_view.value == "feed":  # F5
            main_content = Panel(self.live_feed.create_dashboard(), title="[F5] Live Feed")
        elif self.current_view.value == "charts":  # F6
            main_content = self._create_charts_layout()
        else:
            main_content = self.layout_manager._create_trading_layout()
        
        # Create full layout
        layout = Layout()
        layout.split_column(
            Layout(self._create_header(), name="header", size=3),
            Layout(main_content, name="body"),
            Layout(self._create_footer(), name="footer", size=3)
        )
        
        # Add modal if active
        if self.bet_modal and self.bet_modal.is_active:
            layout["body"].update(self.bet_modal.create_modal())
        elif self.position_modal:
            layout["body"].update(self.position_modal.create_modal())
        
        return layout
    
    def _create_header(self) -> Panel:
        """Create header panel."""
        # Title and status
        title = Text()
        title.append("🎾 TENNIS TRADING TERMINAL ", style="bold white on blue")
        title.append(" | ", style="dim")
        
        # Connection status
        if self.stats['connection_status'] == 'Connected':
            title.append("● Connected", style="green")
        else:
            title.append("● Disconnected", style="red")
        
        title.append(" | ", style="dim")
        
        # Session P&L
        pnl = self.stats['session_pnl']
        if pnl >= 0:
            title.append(f"P&L: +£{pnl:.2f}", style="green")
        else:
            title.append(f"P&L: -£{abs(pnl):.2f}", style="red")
        
        title.append(" | ", style="dim")
        title.append(f"Trades: {self.stats['trades_count']}", style="cyan")
        
        # Mode indicator
        mode_text = self.keyboard.get_mode_indicator()
        if mode_text:
            title.append(" | ", style="dim")
            title.append(mode_text, style="yellow on black")
        
        return Panel(Align.center(title), style="bold", box=None)
    
    def _create_footer(self) -> Panel:
        """Create footer panel."""
        # Quick reference or status
        if self.keyboard.current_mode == InputMode.NORMAL:
            self.quick_ref.set_mode(self.current_view.value.title())
            content = self.quick_ref.create_bar()
        else:
            content = Text(self.keyboard.get_mode_indicator(), style="yellow")
        
        return Panel(content, style="dim", box=None)
    
    def _create_charts_layout(self) -> Panel:
        """Create charts layout."""
        layout = Layout()
        
        # Get data
        trades = self.trade_store.get_all_trades()
        positions = self.position_store.get_all_positions()
        
        # Create charts
        layout.split_column(
            Layout(self.chart_dashboard.create_pnl_chart(trades), size=15),
            Layout(name="middle", size=12),
            Layout(self.chart_dashboard.create_mini_charts(positions), size=8)
        )
        
        layout["middle"].split_row(
            Layout(self.chart_dashboard.create_volume_chart(trades)),
            Layout(self.chart_dashboard.create_position_heatmap(positions))
        )
        
        return Panel(layout, title="[F6] Charts", border_style="magenta")
    
    def _update_statistics(self):
        """Update session statistics."""
        trades = self.trade_store.get_all_trades()
        
        if trades:
            # Calculate P&L
            self.stats['session_pnl'] = sum(t.pnl for t in trades if t.pnl)
            self.stats['trades_count'] = len(trades)
            
            # Win rate
            winning = len([t for t in trades if t.pnl and t.pnl > 0])
            if self.stats['trades_count'] > 0:
                self.stats['win_rate'] = winning / self.stats['trades_count'] * 100
        
        # Connection status
        self.stats['connection_status'] = 'Connected' if self.ws_client.connected else 'Disconnected'
    
    # Navigation handlers
    async def _handle_navigate_up(self, data: Dict):
        """Handle up navigation."""
        if self.current_view == ViewMode.TRADING:
            self.trading_grid.move_selection(-1)
        elif self.current_view == ViewMode.POSITIONS:
            self.positions_panel.selected_index = max(0, self.positions_panel.selected_index - 1)
    
    async def _handle_navigate_down(self, data: Dict):
        """Handle down navigation."""
        if self.current_view == ViewMode.TRADING:
            self.trading_grid.move_selection(1)
        elif self.current_view == ViewMode.POSITIONS:
            positions = self.position_store.get_all_positions()
            self.positions_panel.selected_index = min(
                len(positions) - 1,
                self.positions_panel.selected_index + 1
            )
    
    async def _handle_navigate_left(self, data: Dict):
        """Handle left navigation."""
        pass  # Implement as needed
    
    async def _handle_navigate_right(self, data: Dict):
        """Handle right navigation."""
        pass  # Implement as needed
    
    async def _handle_page_up(self, data: Dict):
        """Handle page up."""
        if self.current_view == ViewMode.TRADING:
            self.trading_grid.move_selection(-5)
    
    async def _handle_page_down(self, data: Dict):
        """Handle page down."""
        if self.current_view == ViewMode.TRADING:
            self.trading_grid.move_selection(5)
    
    async def _handle_home(self, data: Dict):
        """Handle home key."""
        if self.current_view == ViewMode.TRADING:
            self.trading_grid.selected_index = 0
        elif self.current_view == ViewMode.POSITIONS:
            self.positions_panel.selected_index = 0
    
    async def _handle_end(self, data: Dict):
        """Handle end key."""
        if self.current_view == ViewMode.TRADING:
            selections = self.trading_grid.get_all_selections()
            self.trading_grid.selected_index = len(selections) - 1
        elif self.current_view == ViewMode.POSITIONS:
            positions = self.position_store.get_all_positions()
            self.positions_panel.selected_index = len(positions) - 1
    
    async def _handle_tab(self, data: Dict):
        """Handle tab key."""
        self.layout_manager.toggle_active_pane()
    
    # Trading handlers
    async def _handle_place_back(self, data: Dict):
        """Handle place back bet."""
        selection = self.trading_grid.get_selected_selection()
        if selection:
            self.bet_modal = BetModal(
                selection=selection,
                side=OrderSide.BACK,
                default_stake=self.config.trading.default_stake,
                quick_stakes=self.config.trading.quick_stakes
            )
            self.keyboard.set_mode(InputMode.CONFIRM)
    
    async def _handle_place_lay(self, data: Dict):
        """Handle place lay bet."""
        selection = self.trading_grid.get_selected_selection()
        if selection:
            self.bet_modal = BetModal(
                selection=selection,
                side=OrderSide.LAY,
                default_stake=self.config.trading.default_stake,
                quick_stakes=self.config.trading.quick_stakes
            )
            self.keyboard.set_mode(InputMode.CONFIRM)
    
    async def _handle_quick_stake(self, data: Dict):
        """Handle quick stake selection."""
        if self.bet_modal:
            index = data.get('index', 0)
            if index < len(self.config.trading.quick_stakes):
                self.bet_modal.stake = self.config.trading.quick_stakes[index]
    
    async def _handle_adjust_stake(self, data: Dict):
        """Handle stake adjustment."""
        if self.bet_modal:
            direction = data.get('direction', 1)
            self.bet_modal.stake += self.config.trading.stake_increment * direction
            self.bet_modal.stake = max(Decimal('1'), self.bet_modal.stake)
    
    # Position handlers
    async def _handle_close_position(self, data: Dict):
        """Handle close position."""
        if self.current_view == ViewMode.POSITIONS:
            position = self.positions_panel.get_selected_position()
            if position:
                self.position_modal = ClosePositionModal(position)
                self.keyboard.set_mode(InputMode.CONFIRM)
    
    async def _handle_hedge_position(self, data: Dict):
        """Handle hedge position."""
        if self.current_view == ViewMode.POSITIONS:
            position = self.positions_panel.get_selected_position()
            if position:
                self.position_modal = HedgePositionModal(position)
                self.keyboard.set_mode(InputMode.CONFIRM)
    
    async def _handle_stop_loss(self, data: Dict):
        """Handle set stop loss."""
        if self.current_view == ViewMode.POSITIONS:
            position = self.positions_panel.get_selected_position()
            if position:
                self.position_modal = StopLossModal(position)
                self.keyboard.set_mode(InputMode.CONFIRM)
    
    async def _handle_take_profit(self, data: Dict):
        """Handle set take profit."""
        if self.current_view == ViewMode.POSITIONS:
            position = self.positions_panel.get_selected_position()
            if position:
                # Create take profit order
                self.auto_trader.create_take_profit(position)
                self.live_feed.alert_feed.add_alert('success', f'Take profit set for {position.selection_name}')
    
    # Advanced handlers
    async def _handle_close_all(self, data: Dict):
        """Handle close all positions."""
        positions = self.position_store.get_open_positions()
        if positions:
            self.live_feed.alert_feed.add_alert('warning', f'Close all {len(positions)} positions?')
            self.keyboard.set_mode(InputMode.CONFIRM)
    
    async def _handle_hedge_all(self, data: Dict):
        """Handle hedge all positions."""
        positions = self.position_store.get_open_positions()
        if positions:
            self.live_feed.alert_feed.add_alert('warning', f'Hedge all {len(positions)} positions?')
            self.keyboard.set_mode(InputMode.CONFIRM)
    
    async def _handle_kill_switch(self, data: Dict):
        """Handle emergency kill switch."""
        self.risk_dashboard.activate_kill_switch()
        self.live_feed.alert_feed.add_alert('critical', 'KILL SWITCH ACTIVATED - All trading stopped')
        await self._close_all_positions()
    
    async def _handle_undo(self, data: Dict):
        """Handle undo last action."""
        action = data.get('action')
        if action:
            self.live_feed.alert_feed.add_alert('info', f'Undoing: {action[0]}')
    
    # View handlers
    async def _handle_switch_view(self, data: Dict):
        """Handle view switching."""
        view = data.get('view', 'trading')
        
        view_map = {
            'trading': ViewMode.TRADING,
            'positions': ViewMode.POSITIONS,
            'split': ViewMode.SPLIT,
            'risk': ViewMode.RISK,
            'feed': ViewMode('feed'),
            'charts': ViewMode('charts')
        }
        
        if view in view_map:
            self.current_view = view_map[view]
            self.layout_manager.switch_mode(self.current_view)
    
    async def _handle_toggle_odds(self, data: Dict):
        """Toggle odds format."""
        formats = ['decimal', 'fractional', 'american']
        current = self.config.display.odds_format
        idx = formats.index(current)
        self.config.display.odds_format = formats[(idx + 1) % len(formats)]
        self.config_manager.save()
    
    async def _handle_toggle_positions(self, data: Dict):
        """Toggle positions only view."""
        # Implementation depends on specific requirements
        pass
    
    # System handlers
    async def _handle_refresh(self, data: Dict):
        """Handle refresh."""
        await self.ws_client.reconnect()
        self.live_feed.alert_feed.add_alert('info', 'Refreshing data...')
    
    async def _handle_help(self, data: Dict):
        """Handle help display."""
        action = data.get('action')
        if action == 'close':
            self.show_help = False
        else:
            self.show_help = not self.show_help
    
    async def _handle_quit(self, data: Dict):
        """Handle quit."""
        self.running = False
    
    # Confirmation handlers
    async def _handle_confirm(self, data: Dict):
        """Handle confirmation."""
        if self.bet_modal:
            await self._place_bet()
            self.bet_modal = None
        elif self.position_modal:
            await self._execute_position_action()
            self.position_modal = None
        
        self.keyboard.set_mode(InputMode.NORMAL)
    
    async def _handle_cancel(self, data: Dict):
        """Handle cancellation."""
        self.bet_modal = None
        self.position_modal = None
        self.keyboard.set_mode(InputMode.NORMAL)
    
    # Actions
    async def _place_bet(self):
        """Place a bet."""
        if not self.bet_modal:
            return
        
        # Check risk limits
        positions = self.position_store.get_all_positions()
        can_trade, message = self.risk_dashboard.check_risk_limits(
            positions,
            self.bet_modal.stake
        )
        
        if not can_trade:
            self.live_feed.alert_feed.add_alert('critical', message)
            return
        
        # Create trade
        trade = Trade(
            trade_id=f"TRD_{datetime.now().timestamp()}",
            match_id=self.bet_modal.selection['match_id'],
            selection_id=self.bet_modal.selection['id'],
            selection_name=self.bet_modal.selection['name'],
            side=self.bet_modal.side,
            odds=self.bet_modal.price,
            stake=self.bet_modal.stake,
            status="PENDING",
            executed_at=datetime.now()
        )
        
        # Add to store
        self.trade_store.add_trade(trade)
        
        # Create position
        position = Position(
            position_id=f"POS_{datetime.now().timestamp()}",
            match_id=trade.match_id,
            selection_id=trade.selection_id,
            selection_name=trade.selection_name,
            side=trade.side,
            odds=trade.odds,
            stake=trade.stake,
            status=PositionStatus.OPEN,
            current_odds=trade.odds
        )
        
        self.position_store.add_position(position)
        
        # Auto stop loss
        if self.config.risk.stop_loss_enabled:
            self.auto_trader.create_stop_loss(position)
        
        # Log
        self.live_feed.alert_feed.add_alert(
            'success',
            f'Bet placed: {trade.side.value} {trade.selection_name} @ {trade.odds} for £{trade.stake}'
        )
    
    async def _execute_position_action(self):
        """Execute position action."""
        if not self.position_modal:
            return
        
        # Different actions based on modal type
        if isinstance(self.position_modal, ClosePositionModal):
            await self._close_position(self.position_modal.position)
        elif isinstance(self.position_modal, HedgePositionModal):
            await self._hedge_position(self.position_modal.position)
        elif isinstance(self.position_modal, StopLossModal):
            self.auto_trader.create_stop_loss(
                self.position_modal.position,
                self.position_modal.stop_price
            )
    
    async def _close_position(self, position: Position):
        """Close a position."""
        position.status = PositionStatus.CLOSED
        position.closed_at = datetime.now()
        
        self.live_feed.alert_feed.add_alert(
            'info',
            f'Position closed: {position.selection_name} P&L: £{position.pnl:.2f}'
        )
    
    async def _hedge_position(self, position: Position):
        """Hedge a position."""
        # Calculate hedge stake and price
        # This is simplified - real implementation would be more complex
        hedge_stake = position.stake
        hedge_side = OrderSide.LAY if position.side == OrderSide.BACK else OrderSide.BACK
        
        # Create hedge trade
        trade = Trade(
            trade_id=f"TRD_HEDGE_{datetime.now().timestamp()}",
            match_id=position.match_id,
            selection_id=position.selection_id,
            selection_name=position.selection_name,
            side=hedge_side,
            odds=position.current_odds,
            stake=hedge_stake,
            status="MATCHED",
            executed_at=datetime.now()
        )
        
        self.trade_store.add_trade(trade)
        
        self.live_feed.alert_feed.add_alert(
            'success',
            f'Position hedged: {position.selection_name}'
        )
    
    async def _close_all_positions(self):
        """Close all open positions."""
        positions = self.position_store.get_open_positions()
        for position in positions:
            await self._close_position(position)
    
    async def _execute_automated_order(self, order):
        """Execute an automated order."""
        # Simplified execution
        self.live_feed.alert_feed.add_alert(
            'info',
            f'Automated order triggered: {order.order_type.value} for {order.position_id}'
        )
    
    async def run(self):
        """Run the application."""
        self.running = True
        
        # Connect WebSocket
        asyncio.create_task(self.ws_client.connect())
        
        # Main display loop
        with Live(
            self.create_display(),
            console=self.console,
            refresh_per_second=self.config.display.refresh_rate,
            screen=True
        ) as live:
            while self.running:
                try:
                    # Update display
                    live.update(self.create_display())
                    
                    # Process keyboard input (simplified)
                    await asyncio.sleep(0.1)
                    
                    # Auto-save
                    if self.config.general.auto_save:
                        now = datetime.now()
                        if (now - self.last_update).seconds > self.config.general.auto_save_interval:
                            self.config_manager.save()
                            self.last_update = now
                    
                except KeyboardInterrupt:
                    self.running = False
                except Exception as e:
                    self.console.print(f"[red]Error: {e}[/red]")
        
        # Cleanup
        await self.ws_client.disconnect()
        self.console.print("[green]Application terminated[/green]")


def main():
    """Main entry point."""
    app = TennisTradingTerminal()
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\nApplication interrupted")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()