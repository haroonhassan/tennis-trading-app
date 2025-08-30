"""Betfair Stream API client implementation."""

import ssl
import socket
import json
import threading
import time
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from collections import defaultdict

from .models import (
    StreamMessage, 
    StreamConfig, 
    StreamStatus,
    MarketPrices,
    RunnerPrices,
    PriceVolume,
    MessageType
)


class BetfairStreamClient:
    """Client for Betfair Exchange Stream API."""
    
    STREAM_HOST = "stream-api.betfair.com"
    STREAM_PORT = 443
    
    def __init__(
        self,
        session_token: str,
        app_key: str,
        cert_file: str,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize Betfair stream client.
        
        Args:
            session_token: Valid Betfair session token
            app_key: Betfair application key
            cert_file: Path to .pem certificate file
            logger: Optional logger instance
        """
        self.session_token = session_token
        self.app_key = app_key
        self.cert_file = cert_file
        self.logger = logger or logging.getLogger(__name__)
        
        # Connection state
        self.socket = None
        self.ssl_socket = None
        self.status = StreamStatus.DISCONNECTED
        self.config = StreamConfig()
        
        # Threading
        self._read_thread = None
        self._heartbeat_thread = None
        self._stop_threads = threading.Event()
        
        # Message handling
        self._message_id = 0
        self._callback = None
        self._subscribed_markets = set()
        self._market_cache = {}  # Cache for market data
        
        # Reconnection
        self._reconnect_attempts = 0
        self._last_heartbeat = None
        
    def connect(self, config: Optional[StreamConfig] = None) -> bool:
        """
        Connect to Betfair stream.
        
        Args:
            config: Optional stream configuration
            
        Returns:
            bool: True if connection successful
        """
        if config:
            self.config = config
            
        try:
            self.status = StreamStatus.CONNECTING
            self.logger.info(f"Connecting to Betfair stream at {self.STREAM_HOST}:{self.STREAM_PORT}")
            
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(30)
            
            # SSL context with certificate
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ssl_context.load_cert_chain(self.cert_file)
            
            # Wrap socket with SSL
            self.ssl_socket = ssl_context.wrap_socket(
                self.socket,
                server_hostname=self.STREAM_HOST
            )
            
            # Connect
            self.ssl_socket.connect((self.STREAM_HOST, self.STREAM_PORT))
            
            # Authenticate
            if not self._authenticate():
                self.disconnect()
                return False
            
            self.status = StreamStatus.CONNECTED
            self.logger.info("Successfully connected to Betfair stream")
            
            # Start threads
            self._start_threads()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to stream: {e}")
            self.status = StreamStatus.ERROR
            return False
    
    def _authenticate(self) -> bool:
        """Authenticate with the stream."""
        auth_message = {
            "op": "authentication",
            "id": self._get_next_id(),
            "appKey": self.app_key,
            "session": self.session_token
        }
        
        self._send_message(auth_message)
        
        # Wait for authentication response
        timeout = time.time() + 10
        while time.time() < timeout:
            response = self._read_message()
            if response:
                if response.get("op") == "status":
                    if response.get("statusCode") == "SUCCESS":
                        self.logger.info("Stream authentication successful")
                        return True
                    else:
                        self.logger.error(f"Stream authentication failed: {response}")
                        return False
            time.sleep(0.1)
            
        self.logger.error("Stream authentication timeout")
        return False
    
    def subscribe_markets(
        self,
        market_ids: List[str],
        callback: Callable[[StreamMessage], None],
        fields: Optional[List[str]] = None,
        conflate_ms: Optional[int] = None
    ) -> bool:
        """
        Subscribe to market data.
        
        Args:
            market_ids: List of market IDs
            callback: Callback for stream messages
            fields: Optional list of fields to include
            conflate_ms: Optional conflation rate
            
        Returns:
            bool: True if subscription successful
        """
        if not self.is_connected():
            self.logger.error("Not connected to stream")
            return False
            
        self._callback = callback
        
        # Default fields for price data
        if fields is None:
            fields = ["EX_BEST_OFFERS", "EX_TRADED", "EX_TRADED_VOL", "EX_LTP", "EX_MARKET_DEF"]
        
        subscription_message = {
            "op": "marketSubscription",
            "id": self._get_next_id(),
            "marketFilter": {
                "marketIds": market_ids
            },
            "marketDataFilter": {
                "fields": fields,
                "ladderLevels": 3
            }
        }
        
        if conflate_ms is not None:
            subscription_message["conflateMs"] = conflate_ms
        elif self.config.conflate_ms:
            subscription_message["conflateMs"] = self.config.conflate_ms
            
        self._send_message(subscription_message)
        self._subscribed_markets.update(market_ids)
        
        self.logger.info(f"Subscribed to markets: {market_ids}")
        return True
    
    def unsubscribe_markets(self, market_ids: List[str]) -> bool:
        """Unsubscribe from markets."""
        if not self.is_connected():
            return False
            
        unsubscribe_message = {
            "op": "marketSubscription",
            "id": self._get_next_id(),
            "marketFilter": {
                "marketIds": market_ids
            },
            "marketDataFilter": {}
        }
        
        self._send_message(unsubscribe_message)
        self._subscribed_markets.difference_update(market_ids)
        
        self.logger.info(f"Unsubscribed from markets: {market_ids}")
        return True
    
    def disconnect(self) -> bool:
        """Disconnect from stream."""
        try:
            self.status = StreamStatus.DISCONNECTED
            self._stop_threads.set()
            
            if self.ssl_socket:
                self.ssl_socket.close()
            if self.socket:
                self.socket.close()
                
            self.logger.info("Disconnected from stream")
            return True
            
        except Exception as e:
            self.logger.error(f"Error disconnecting: {e}")
            return False
    
    def _start_threads(self):
        """Start reader and heartbeat threads."""
        self._stop_threads.clear()
        
        # Start reader thread
        self._read_thread = threading.Thread(target=self._read_loop)
        self._read_thread.daemon = True
        self._read_thread.start()
        
        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()
    
    def _read_loop(self):
        """Main read loop for stream messages."""
        buffer = ""
        
        while not self._stop_threads.is_set():
            try:
                # Read data from socket
                data = self.ssl_socket.recv(self.config.buffer_size).decode('utf-8')
                
                if not data:
                    self.logger.warning("Stream closed by server")
                    self._handle_disconnect()
                    break
                
                buffer += data
                
                # Process complete messages (delimited by \r\n)
                while '\r\n' in buffer:
                    message, buffer = buffer.split('\r\n', 1)
                    if message:
                        self._process_message(message)
                        
            except socket.timeout:
                continue
            except Exception as e:
                self.logger.error(f"Read error: {e}")
                self._handle_disconnect()
                break
    
    def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while not self._stop_threads.is_set():
            try:
                # Send heartbeat
                self._send_heartbeat()
                
                # Check for missed heartbeats
                if self._last_heartbeat:
                    time_since_heartbeat = time.time() - self._last_heartbeat
                    if time_since_heartbeat > 30:  # 30 seconds timeout
                        self.logger.warning("Heartbeat timeout")
                        self._handle_disconnect()
                        break
                
                # Wait for next heartbeat interval
                self._stop_threads.wait(self.config.heartbeat_ms / 1000)
                
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
    
    def _send_heartbeat(self):
        """Send heartbeat message."""
        heartbeat = {
            "op": "heartbeat",
            "id": self._get_next_id()
        }
        self._send_message(heartbeat)
    
    def _process_message(self, message_str: str):
        """Process a stream message."""
        try:
            message = json.loads(message_str)
            op = message.get("op")
            
            if op == "connection":
                self._handle_connection_message(message)
            elif op == "status":
                self._handle_status_message(message)
            elif op == "mcm":  # Market change message
                self._handle_market_change(message)
            elif op == "heartbeat":
                self._last_heartbeat = time.time()
                if self._callback:
                    self._callback(StreamMessage.heartbeat_message("betfair"))
                    
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    def _handle_connection_message(self, message: Dict):
        """Handle connection message."""
        connection_id = message.get("connectionId")
        self.logger.info(f"Connection established: {connection_id}")
        
        if self._callback:
            self._callback(StreamMessage.connection_message(
                "betfair",
                "connected",
                connection_id=connection_id
            ))
    
    def _handle_status_message(self, message: Dict):
        """Handle status message."""
        status_code = message.get("statusCode")
        error_message = message.get("errorMessage")
        
        if status_code != "SUCCESS":
            self.logger.error(f"Status error: {status_code} - {error_message}")
            if self._callback:
                self._callback(StreamMessage.error_message(
                    "betfair",
                    error_message or status_code
                ))
    
    def _handle_market_change(self, message: Dict):
        """Handle market change message."""
        if not self._callback:
            return
            
        mc = message.get("mc", [])
        
        for market_change in mc:
            market_id = market_change.get("id")
            
            # Update cache with market definition if present
            if "marketDefinition" in market_change:
                self._update_market_definition(market_id, market_change["marketDefinition"])
            
            # Parse price data
            market_prices = self._parse_market_prices(market_change)
            
            if market_prices:
                # Send normalized message
                self._callback(StreamMessage.market_change_message(
                    "betfair",
                    market_prices,
                    raw=market_change
                ))
    
    def _parse_market_prices(self, market_change: Dict) -> Optional[MarketPrices]:
        """Parse market change into MarketPrices."""
        market_id = market_change.get("id")
        if not market_id:
            return None
            
        # Get cached market info
        market_info = self._market_cache.get(market_id, {})
        
        market_prices = MarketPrices(
            market_id=market_id,
            market_name=market_info.get("name"),
            event_name=market_info.get("eventName"),
            in_play=market_info.get("inPlay", False),
            total_matched=market_change.get("tv")  # Total volume
        )
        
        # Parse runner changes
        for runner_change in market_change.get("rc", []):
            runner_id = str(runner_change.get("id"))
            
            runner_prices = RunnerPrices(
                runner_id=runner_id,
                runner_name=self._get_runner_name(market_id, runner_id),
                last_traded_price=runner_change.get("ltp"),
                total_matched=runner_change.get("tv")
            )
            
            # Parse available to back
            if "atb" in runner_change:
                for price_vol in runner_change["atb"]:
                    if len(price_vol) >= 2:
                        runner_prices.back_prices.append(
                            PriceVolume(price_vol[0], price_vol[1])
                        )
            
            # Parse available to lay
            if "atl" in runner_change:
                for price_vol in runner_change["atl"]:
                    if len(price_vol) >= 2:
                        runner_prices.lay_prices.append(
                            PriceVolume(price_vol[0], price_vol[1])
                        )
            
            # Parse traded volumes
            if "trd" in runner_change:
                traded_volumes = runner_change["trd"]
                # Could parse detailed traded volumes if needed
            
            market_prices.runners[runner_id] = runner_prices
        
        return market_prices
    
    def _update_market_definition(self, market_id: str, market_def: Dict):
        """Update cached market definition."""
        if market_id not in self._market_cache:
            self._market_cache[market_id] = {}
            
        cache = self._market_cache[market_id]
        cache["name"] = market_def.get("name")
        cache["eventName"] = market_def.get("eventName")
        cache["inPlay"] = market_def.get("inPlay", False)
        cache["runners"] = {}
        
        for runner in market_def.get("runners", []):
            runner_id = str(runner.get("id"))
            cache["runners"][runner_id] = runner.get("name", f"Runner {runner_id}")
    
    def _get_runner_name(self, market_id: str, runner_id: str) -> str:
        """Get runner name from cache."""
        market_cache = self._market_cache.get(market_id, {})
        runners = market_cache.get("runners", {})
        return runners.get(runner_id, f"Runner {runner_id}")
    
    def _handle_disconnect(self):
        """Handle disconnection and potential reconnection."""
        self.status = StreamStatus.DISCONNECTED
        
        if self.config.auto_reconnect and self._reconnect_attempts < self.config.max_reconnect_attempts:
            self.status = StreamStatus.RECONNECTING
            self._reconnect_attempts += 1
            
            self.logger.info(f"Attempting reconnection {self._reconnect_attempts}/{self.config.max_reconnect_attempts}")
            
            time.sleep(self.config.reconnect_interval)
            
            if self.connect(self.config):
                # Resubscribe to markets
                if self._subscribed_markets and self._callback:
                    self.subscribe_markets(list(self._subscribed_markets), self._callback)
                self._reconnect_attempts = 0
            else:
                self._handle_disconnect()  # Retry
        else:
            self.logger.error("Max reconnection attempts reached or auto-reconnect disabled")
            self.status = StreamStatus.ERROR
    
    def _send_message(self, message: Dict):
        """Send a message to the stream."""
        if self.ssl_socket:
            message_str = json.dumps(message) + '\r\n'
            self.ssl_socket.send(message_str.encode('utf-8'))
    
    def _read_message(self) -> Optional[Dict]:
        """Read a single message from the stream."""
        try:
            data = self.ssl_socket.recv(self.config.buffer_size).decode('utf-8')
            if '\r\n' in data:
                message_str = data.split('\r\n')[0]
                return json.loads(message_str)
        except:
            pass
        return None
    
    def _get_next_id(self) -> int:
        """Get next message ID."""
        self._message_id += 1
        return self._message_id
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.status == StreamStatus.CONNECTED
    
    def get_status(self) -> StreamStatus:
        """Get connection status."""
        return self.status