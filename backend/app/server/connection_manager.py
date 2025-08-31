"""WebSocket connection manager."""

import json
import asyncio
import logging
from typing import Dict, Set, List, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

from .models import WebSocketMessage, MessageType


class ClientConnection:
    """Represents a WebSocket client connection."""
    
    def __init__(self, websocket: WebSocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.connected_at = datetime.now()
        self.subscriptions: Set[str] = set()  # Match IDs subscribed to
        self.last_ping = datetime.now()
        
    async def send_json(self, data: dict):
        """Send JSON data to client."""
        try:
            await self.websocket.send_json(data)
        except Exception as e:
            logging.error(f"Error sending to client {self.client_id}: {e}")
            raise


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize connection manager.
        
        Args:
            logger: Optional logger
        """
        self.logger = logger or logging.getLogger(__name__)
        self.active_connections: Dict[str, ClientConnection] = {}
        self._lock = asyncio.Lock()
        self._ping_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def connect(self, websocket: WebSocket, client_id: str) -> ClientConnection:
        """
        Accept new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            client_id: Unique client identifier
            
        Returns:
            ClientConnection instance
        """
        await websocket.accept()
        
        async with self._lock:
            connection = ClientConnection(websocket, client_id)
            self.active_connections[client_id] = connection
            
        self.logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")
        
        # Send welcome message
        await self.send_personal_message(
            client_id,
            WebSocketMessage(
                type=MessageType.PROVIDER_STATUS,
                data={"message": "Connected to tennis trading server", "client_id": client_id},
                timestamp=datetime.now()
            )
        )
        
        return connection
    
    async def disconnect(self, client_id: str):
        """
        Handle client disconnection.
        
        Args:
            client_id: Client to disconnect
        """
        async with self._lock:
            if client_id in self.active_connections:
                del self.active_connections[client_id]
                
        self.logger.info(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, client_id: str, message: WebSocketMessage):
        """
        Send message to specific client.
        
        Args:
            client_id: Target client
            message: Message to send
        """
        if client_id not in self.active_connections:
            return
        
        connection = self.active_connections[client_id]
        try:
            await connection.send_json(message.model_dump(mode='json'))
        except Exception as e:
            self.logger.error(f"Error sending message to {client_id}: {e}")
            await self.disconnect(client_id)
    
    async def broadcast(self, message: WebSocketMessage, exclude: Optional[Set[str]] = None):
        """
        Broadcast message to all connected clients.
        
        Args:
            message: Message to broadcast
            exclude: Set of client IDs to exclude
        """
        exclude = exclude or set()
        
        # Prepare message once
        if isinstance(message, dict):
            message_dict = message
        elif hasattr(message, 'model_dump'):
            message_dict = message.model_dump(mode='json')
        else:
            message_dict = {"data": str(message)}
        
        # Send to all clients
        disconnected = []
        for client_id, connection in self.active_connections.items():
            if client_id in exclude:
                continue
            
            try:
                await connection.send_json(message_dict)
            except Exception as e:
                self.logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            await self.disconnect(client_id)
    
    async def broadcast_to_subscribers(self, match_id: str, message: WebSocketMessage):
        """
        Broadcast message to clients subscribed to a specific match.
        
        Args:
            match_id: Match ID
            message: Message to broadcast
        """
        message_dict = message.model_dump(mode='json')
        disconnected = []
        
        for client_id, connection in self.active_connections.items():
            if match_id not in connection.subscriptions:
                continue
            
            try:
                await connection.send_json(message_dict)
            except Exception as e:
                self.logger.error(f"Error broadcasting to subscriber {client_id}: {e}")
                disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            await self.disconnect(client_id)
    
    async def handle_subscription(self, client_id: str, match_ids: List[str]):
        """
        Handle match subscription request.
        
        Args:
            client_id: Client making request
            match_ids: Match IDs to subscribe to
        """
        if client_id not in self.active_connections:
            return
        
        connection = self.active_connections[client_id]
        connection.subscriptions.update(match_ids)
        
        await self.send_personal_message(
            client_id,
            WebSocketMessage(
                type=MessageType.SUBSCRIPTION,
                data={"subscribed": list(connection.subscriptions)},
                timestamp=datetime.now()
            )
        )
        
        self.logger.info(f"Client {client_id} subscribed to {len(match_ids)} matches")
    
    async def handle_unsubscription(self, client_id: str, match_ids: List[str]):
        """
        Handle match unsubscription request.
        
        Args:
            client_id: Client making request
            match_ids: Match IDs to unsubscribe from
        """
        if client_id not in self.active_connections:
            return
        
        connection = self.active_connections[client_id]
        for match_id in match_ids:
            connection.subscriptions.discard(match_id)
        
        await self.send_personal_message(
            client_id,
            WebSocketMessage(
                type=MessageType.UNSUBSCRIPTION,
                data={"subscribed": list(connection.subscriptions)},
                timestamp=datetime.now()
            )
        )
        
        self.logger.info(f"Client {client_id} unsubscribed from {len(match_ids)} matches")
    
    async def handle_client_message(self, client_id: str, data: dict) -> Any:
        """
        Handle incoming message from client.
        
        Args:
            client_id: Client sending message
            data: Message data
            
        Returns:
            Response data if any
        """
        try:
            message_type = data.get("type")
            
            if message_type == "ping":
                # Update last ping time
                if client_id in self.active_connections:
                    self.active_connections[client_id].last_ping = datetime.now()
                
                # Send pong response
                await self.send_personal_message(
                    client_id,
                    WebSocketMessage(
                        type=MessageType.PONG,
                        data={"timestamp": datetime.now().isoformat()},
                        timestamp=datetime.now()
                    )
                )
                
            elif message_type == "subscribe":
                match_ids = data.get("match_ids", [])
                await self.handle_subscription(client_id, match_ids)
                
            elif message_type == "unsubscribe":
                match_ids = data.get("match_ids", [])
                await self.handle_unsubscription(client_id, match_ids)
                
            else:
                self.logger.warning(f"Unknown message type from {client_id}: {message_type}")
                
        except Exception as e:
            self.logger.error(f"Error handling message from {client_id}: {e}")
            await self.send_personal_message(
                client_id,
                WebSocketMessage(
                    type=MessageType.ERROR,
                    data={"error": str(e)},
                    timestamp=datetime.now()
                )
            )
    
    async def start_ping_interval(self, interval: int = 30):
        """
        Start periodic ping to keep connections alive.
        
        Args:
            interval: Ping interval in seconds
        """
        if self._running:
            return
        
        self._running = True
        self._ping_task = asyncio.create_task(self._ping_loop(interval))
        self.logger.info(f"Started ping interval ({interval}s)")
    
    async def stop_ping_interval(self):
        """Stop periodic ping."""
        self._running = False
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped ping interval")
    
    async def _ping_loop(self, interval: int):
        """
        Ping loop to keep connections alive.
        
        Args:
            interval: Ping interval in seconds
        """
        while self._running:
            try:
                # Send ping to all clients
                await self.broadcast(
                    WebSocketMessage(
                        type=MessageType.PING,
                        data={"timestamp": datetime.now().isoformat()},
                        timestamp=datetime.now()
                    )
                )
                
                # Check for stale connections
                now = datetime.now()
                stale_clients = []
                
                for client_id, connection in self.active_connections.items():
                    time_since_ping = (now - connection.last_ping).total_seconds()
                    if time_since_ping > interval * 3:  # 3 missed pings
                        stale_clients.append(client_id)
                
                # Disconnect stale clients
                for client_id in stale_clients:
                    self.logger.warning(f"Disconnecting stale client: {client_id}")
                    await self.disconnect(client_id)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in ping loop: {e}")
                await asyncio.sleep(interval)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.
        
        Returns:
            Dictionary with connection stats
        """
        total_subscriptions = sum(
            len(conn.subscriptions) for conn in self.active_connections.values()
        )
        
        return {
            "total_connections": len(self.active_connections),
            "total_subscriptions": total_subscriptions,
            "clients": [
                {
                    "client_id": client_id,
                    "connected_at": conn.connected_at.isoformat(),
                    "subscriptions": list(conn.subscriptions),
                    "last_ping": conn.last_ping.isoformat()
                }
                for client_id, conn in self.active_connections.items()
            ]
        }