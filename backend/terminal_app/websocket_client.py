"""WebSocket client with auto-reconnection for terminal app."""

import asyncio
import json
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import websockets
from websockets.exceptions import WebSocketException
from decimal import Decimal

from .models import MessageType
from .stores.match_store import MatchDataStore
from .stores.position_store import PositionStore
from .stores.trade_store import TradeStore


logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client with automatic reconnection and message handling."""
    
    def __init__(
        self,
        url: str,
        match_store: MatchDataStore,
        position_store: PositionStore,
        trade_store: TradeStore
    ):
        self.url = url
        self.match_store = match_store
        self.position_store = position_store
        self.trade_store = trade_store
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.reconnect_delay = 1  # Start with 1 second
        self.max_reconnect_delay = 60  # Max 60 seconds
        self.reconnect_attempts = 0
        
        self._stop_event = asyncio.Event()
        self._message_handlers: Dict[MessageType, Callable] = {}
        self._connection_observers: list[Callable] = []
        
        # Register default message handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register default message handlers."""
        self._message_handlers[MessageType.PRICE_UPDATE] = self._handle_price_update
        self._message_handlers[MessageType.POSITION_UPDATE] = self._handle_position_update
        self._message_handlers[MessageType.TRADE_UPDATE] = self._handle_trade_update
        self._message_handlers[MessageType.MATCH_UPDATE] = self._handle_match_update
        self._message_handlers[MessageType.SCORE_UPDATE] = self._handle_score_update
    
    async def connect(self) -> None:
        """Connect to WebSocket with automatic reconnection."""
        while not self._stop_event.is_set():
            try:
                logger.info(f"Connecting to WebSocket: {self.url}")
                self.websocket = await websockets.connect(self.url)
                self.is_connected = True
                self.reconnect_delay = 1  # Reset delay on successful connection
                self.reconnect_attempts = 0
                
                # Notify observers of connection
                await self._notify_connection_change(True)
                
                logger.info("WebSocket connected successfully")
                
                # Start message handler
                await self._handle_messages()
                
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                self.is_connected = False
                await self._notify_connection_change(False)
                
                if not self._stop_event.is_set():
                    # Exponential backoff for reconnection
                    self.reconnect_attempts += 1
                    wait_time = min(self.reconnect_delay * (2 ** self.reconnect_attempts), 
                                  self.max_reconnect_delay)
                    logger.info(f"Reconnecting in {wait_time} seconds... (attempt {self.reconnect_attempts})")
                    await asyncio.sleep(wait_time)
    
    async def _handle_messages(self) -> None:
        """Handle incoming WebSocket messages."""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
            self.is_connected = False
            await self._notify_connection_change(False)
    
    async def _process_message(self, data: Dict[str, Any]) -> None:
        """Process a WebSocket message."""
        msg_type_str = data.get('type', '')
        
        try:
            msg_type = MessageType(msg_type_str)
            handler = self._message_handlers.get(msg_type)
            
            if handler:
                await handler(data.get('data', {}))
            else:
                logger.warning(f"No handler for message type: {msg_type}")
                
        except ValueError:
            logger.warning(f"Unknown message type: {msg_type_str}")
    
    async def _handle_price_update(self, data: Dict) -> None:
        """Handle price update message."""
        match_id = data.get('match_id')
        selection_id = data.get('selection_id')
        
        if match_id and selection_id:
            price_data = {
                'back_price': Decimal(str(data['back_price'])) if 'back_price' in data else None,
                'back_volume': Decimal(str(data['back_volume'])) if 'back_volume' in data else None,
                'lay_price': Decimal(str(data['lay_price'])) if 'lay_price' in data else None,
                'lay_volume': Decimal(str(data['lay_volume'])) if 'lay_volume' in data else None,
                'last_traded': Decimal(str(data['last_traded'])) if 'last_traded' in data else None,
            }
            await self.match_store.update_prices(match_id, selection_id, price_data)
    
    async def _handle_position_update(self, data: Dict) -> None:
        """Handle position update message."""
        position_id = data.get('position_id')
        
        if position_id:
            # Update existing position
            await self.position_store.update_position(position_id, data)
        elif 'match_id' in data and 'selection_id' in data:
            # New position
            await self.position_store.add_position(data)
    
    async def _handle_trade_update(self, data: Dict) -> None:
        """Handle trade update message."""
        trade_id = data.get('trade_id')
        
        if trade_id and 'status' in data:
            # Update existing trade
            await self.trade_store.update_trade_status(
                trade_id, 
                data['status'],
                pnl=data.get('pnl'),
                commission=data.get('commission')
            )
        elif 'match_id' in data and 'selection_id' in data:
            # New trade
            await self.trade_store.add_trade(data)
    
    async def _handle_match_update(self, data: Dict) -> None:
        """Handle match update message."""
        match_id = data.get('match_id')
        if match_id:
            await self.match_store.update_match(match_id, data)
    
    async def _handle_score_update(self, data: Dict) -> None:
        """Handle score update message."""
        match_id = data.get('match_id')
        if match_id:
            await self.match_store.update_match(match_id, {
                'score': data.get('score'),
                'serving': data.get('serving')
            })
    
    async def send_message(self, message: Dict) -> None:
        """Send a message to the server."""
        if self.websocket and self.is_connected:
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                self.is_connected = False
                await self._notify_connection_change(False)
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._stop_event.set()
        if self.websocket:
            await self.websocket.close()
        self.is_connected = False
        await self._notify_connection_change(False)
    
    def add_connection_observer(self, callback: Callable[[bool], None]) -> None:
        """Add observer for connection status changes."""
        self._connection_observers.append(callback)
    
    async def _notify_connection_change(self, connected: bool) -> None:
        """Notify observers of connection status change."""
        for observer in self._connection_observers:
            if asyncio.iscoroutinefunction(observer):
                await observer(connected)
            else:
                observer(connected)