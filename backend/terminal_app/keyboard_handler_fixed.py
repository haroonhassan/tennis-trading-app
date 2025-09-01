"""Comprehensive keyboard handler for terminal app (fixed version)."""

import asyncio
from typing import Optional, Callable, Dict, Any
from enum import Enum
from decimal import Decimal

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.filters import Condition

from .models import OrderSide


class InputMode(Enum):
    """Input modes for the application."""
    NORMAL = "normal"
    SEARCH = "search"
    STAKE_EDIT = "stake_edit"
    PRICE_EDIT = "price_edit"
    HELP = "help"
    CONFIRM = "confirm"


class KeyboardHandler:
    """Handles all keyboard input for the terminal app."""
    
    def __init__(self):
        self.kb = KeyBindings()
        self.current_mode = InputMode.NORMAL
        self.search_buffer = ""
        self.stake_buffer = ""
        self.price_buffer = ""
        self.undo_stack = []
        self.last_action = None
        
        # Callbacks
        self.callbacks: Dict[str, Optional[Callable]] = {
            'quit': None,
            'refresh': None,
            'navigate_up': None,
            'navigate_down': None,
            'navigate_left': None,
            'navigate_right': None,
            'page_up': None,
            'page_down': None,
            'home': None,
            'end': None,
            'tab_next': None,
            'search': None,
            'place_back': None,
            'place_lay': None,
            'quick_stake': None,
            'adjust_stake': None,
            'adjust_price': None,
            'confirm': None,
            'cancel': None,
            'close_position': None,
            'hedge_position': None,
            'set_stop_loss': None,
            'set_take_profit': None,
            'close_all': None,
            'hedge_all': None,
            'emergency_stop': None,
            'undo': None,
            'switch_view': None,
            'toggle_odds_format': None,
            'toggle_positions_only': None,
            'show_help': None,
        }
        
        self._setup_keybindings()
    
    def _setup_keybindings(self):
        """Set up all keyboard bindings."""
        
        # Create filter conditions
        is_normal = Condition(lambda: self.current_mode == InputMode.NORMAL)
        is_search = Condition(lambda: self.current_mode == InputMode.SEARCH)
        is_confirm = Condition(lambda: self.current_mode == InputMode.CONFIRM)
        is_help = Condition(lambda: self.current_mode == InputMode.HELP)
        is_not_editing = Condition(lambda: self.current_mode not in [
            InputMode.SEARCH, InputMode.STAKE_EDIT, InputMode.PRICE_EDIT
        ])
        
        # Navigation
        @self.kb.add(Keys.Up, filter=is_normal)
        @self.kb.add('k', filter=is_normal)
        async def navigate_up(event):
            await self._call_callback('navigate_up')
        
        @self.kb.add(Keys.Down, filter=is_normal)
        @self.kb.add('j', filter=is_normal)
        async def navigate_down(event):
            await self._call_callback('navigate_down')
        
        @self.kb.add(Keys.Left, filter=is_normal)
        @self.kb.add('h', filter=is_normal)
        async def navigate_left(event):
            await self._call_callback('navigate_left')
        
        @self.kb.add(Keys.Right, filter=is_normal)
        @self.kb.add('l', filter=is_normal)
        async def navigate_right(event):
            await self._call_callback('navigate_right')
        
        @self.kb.add(Keys.PageUp, filter=is_normal)
        async def page_up(event):
            await self._call_callback('page_up')
        
        @self.kb.add(Keys.PageDown, filter=is_normal)
        async def page_down(event):
            await self._call_callback('page_down')
        
        @self.kb.add(Keys.Home, filter=is_normal)
        async def go_home(event):
            await self._call_callback('home')
        
        @self.kb.add(Keys.End, filter=is_normal)
        async def go_end(event):
            await self._call_callback('end')
        
        @self.kb.add(Keys.Tab, filter=is_normal)
        async def tab_next(event):
            await self._call_callback('tab_next')
        
        # Search
        @self.kb.add('/', filter=is_normal)
        async def start_search(event):
            self.current_mode = InputMode.SEARCH
            self.search_buffer = ""
            await self._call_callback('search', {'action': 'start'})
        
        @self.kb.add(Keys.Enter, filter=is_search)
        async def execute_search(event):
            self.current_mode = InputMode.NORMAL
            await self._call_callback('search', {
                'action': 'execute',
                'query': self.search_buffer
            })
        
        @self.kb.add(Keys.Escape, filter=is_search)
        async def cancel_search(event):
            self.current_mode = InputMode.NORMAL
            self.search_buffer = ""
            await self._call_callback('search', {'action': 'cancel'})
        
        # Trading hotkeys
        @self.kb.add('b', filter=is_normal)
        async def place_back(event):
            self.last_action = ('back', None)
            await self._call_callback('place_back')
        
        # Note: 'l' conflicts with navigation right, so we check context
        # This is handled by the app logic
        
        # Quick stakes (1-5)
        for i in range(1, 6):
            @self.kb.add(str(i), filter=is_normal)
            async def quick_stake(event, stake_index=i-1):
                await self._call_callback('quick_stake', {'index': stake_index})
        
        # Stake adjustment
        @self.kb.add('+', filter=is_normal)
        @self.kb.add('=', filter=is_normal)
        async def increase_stake(event):
            await self._call_callback('adjust_stake', {'direction': 1})
        
        @self.kb.add('-', filter=is_normal)
        async def decrease_stake(event):
            await self._call_callback('adjust_stake', {'direction': -1})
        
        # Confirmation
        @self.kb.add('y', filter=is_confirm)
        @self.kb.add('Y', filter=is_confirm)
        @self.kb.add(Keys.Enter, filter=is_confirm)
        async def confirm_action(event):
            self.current_mode = InputMode.NORMAL
            await self._call_callback('confirm')
        
        @self.kb.add('n', filter=is_confirm)
        @self.kb.add('N', filter=is_confirm)
        @self.kb.add(Keys.Escape, filter=is_confirm)
        async def cancel_action(event):
            self.current_mode = InputMode.NORMAL
            await self._call_callback('cancel')
        
        # View controls (F-keys)
        @self.kb.add(Keys.F1)
        async def view_trading(event):
            await self._call_callback('switch_view', {'view': 'trading'})
        
        @self.kb.add(Keys.F2)
        async def view_positions(event):
            await self._call_callback('switch_view', {'view': 'positions'})
        
        @self.kb.add(Keys.F3)
        async def view_split(event):
            await self._call_callback('switch_view', {'view': 'split'})
        
        @self.kb.add(Keys.F4)
        async def view_risk(event):
            await self._call_callback('switch_view', {'view': 'risk'})
        
        @self.kb.add(Keys.F5)
        async def view_feed(event):
            await self._call_callback('switch_view', {'view': 'feed'})
        
        @self.kb.add(Keys.F6)
        async def view_charts(event):
            await self._call_callback('switch_view', {'view': 'charts'})
        
        # Position management
        @self.kb.add('c', filter=is_normal)
        async def close_position(event):
            self.last_action = ('close', None)
            await self._call_callback('close_position')
        
        # Note: 'h' conflicts with navigation left
        
        @self.kb.add('x', filter=is_normal)
        async def set_stop_loss(event):
            await self._call_callback('set_stop_loss')
        
        @self.kb.add('t', filter=is_normal)
        async def set_take_profit(event):
            await self._call_callback('set_take_profit')
        
        # Advanced shortcuts (using Shift combinations)
        @self.kb.add('C', filter=is_normal)
        async def close_all_positions(event):
            self.current_mode = InputMode.CONFIRM
            await self._call_callback('close_all')
        
        @self.kb.add('H', filter=is_normal)
        async def hedge_all_positions(event):
            self.current_mode = InputMode.CONFIRM
            await self._call_callback('hedge_all')
        
        @self.kb.add('S', filter=is_normal)
        async def emergency_stop(event):
            self.current_mode = InputMode.CONFIRM
            await self._call_callback('emergency_stop')
        
        @self.kb.add('c-z')
        async def undo_last(event):
            if self.undo_stack:
                last_action = self.undo_stack.pop()
                await self._call_callback('undo', {'action': last_action})
        
        # Display options
        @self.kb.add('o', filter=is_normal)
        async def toggle_odds_format(event):
            await self._call_callback('toggle_odds_format')
        
        @self.kb.add('p', filter=is_normal)
        async def toggle_positions_only(event):
            await self._call_callback('toggle_positions_only')
        
        # System
        @self.kb.add('r', filter=is_normal)
        async def refresh(event):
            await self._call_callback('refresh')
        
        @self.kb.add('?', filter=is_normal)
        async def show_help(event):
            self.current_mode = InputMode.HELP
            await self._call_callback('show_help')
        
        @self.kb.add('q', filter=is_normal)
        @self.kb.add('c-c')
        async def quit_app(event):
            await self._call_callback('quit')
        
        # Handle any key in help mode to close it
        @self.kb.add(Keys.Any, filter=is_help)
        async def close_help(event):
            self.current_mode = InputMode.NORMAL
            await self._call_callback('show_help', {'action': 'close'})
    
    def _is_normal_mode(self) -> bool:
        """Check if in normal mode."""
        return self.current_mode == InputMode.NORMAL
    
    def _is_search_mode(self) -> bool:
        """Check if in search mode."""
        return self.current_mode == InputMode.SEARCH
    
    def _is_confirm_mode(self) -> bool:
        """Check if in confirmation mode."""
        return self.current_mode == InputMode.CONFIRM
    
    def _is_help_mode(self) -> bool:
        """Check if in help mode."""
        return self.current_mode == InputMode.HELP
    
    def _is_navigating(self) -> bool:
        """Check if currently navigating (not in text input)."""
        return self.current_mode not in [InputMode.SEARCH, InputMode.STAKE_EDIT, InputMode.PRICE_EDIT]
    
    async def _call_callback(self, name: str, data: Optional[Dict[str, Any]] = None):
        """Call a registered callback."""
        callback = self.callbacks.get(name)
        if callback:
            if asyncio.iscoroutinefunction(callback):
                await callback(data or {})
            else:
                callback(data or {})
    
    def register_callback(self, name: str, callback: Callable):
        """Register a callback for a keyboard action."""
        if name in self.callbacks:
            self.callbacks[name] = callback
    
    def set_mode(self, mode: InputMode):
        """Set the current input mode."""
        self.current_mode = mode
    
    def add_to_undo_stack(self, action: Any):
        """Add an action to the undo stack."""
        self.undo_stack.append(action)
        # Keep only last 50 actions
        if len(self.undo_stack) > 50:
            self.undo_stack = self.undo_stack[-50:]
    
    def get_mode_indicator(self) -> str:
        """Get current mode indicator for display."""
        indicators = {
            InputMode.NORMAL: "",
            InputMode.SEARCH: "SEARCH: ",
            InputMode.STAKE_EDIT: "STAKE: ",
            InputMode.PRICE_EDIT: "PRICE: ",
            InputMode.HELP: "HELP",
            InputMode.CONFIRM: "CONFIRM Y/N: "
        }
        return indicators.get(self.current_mode, "")