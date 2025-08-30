#!/usr/bin/env python3
"""Test WebSocket connection to FastAPI server."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import websockets
import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class WebSocketTestClient:
    """Test client for WebSocket connection."""
    
    def __init__(self, server_url: str = "localhost:8000"):
        """
        Initialize test client.
        
        Args:
            server_url: Server URL (without protocol)
        """
        self.server_url = server_url
        self.api_url = f"http://{server_url}"
        self.ws_url = f"ws://{server_url}/ws"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        
    async def test_api_endpoints(self):
        """Test REST API endpoints."""
        print("\n" + "=" * 60)
        print("TESTING REST API ENDPOINTS")
        print("=" * 60)
        
        async with httpx.AsyncClient() as client:
            # Test health endpoint
            print("\n1. Testing /health endpoint...")
            response = await client.get(f"{self.api_url}/health")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
            
            # Test providers endpoint
            print("\n2. Testing /api/providers endpoint...")
            response = await client.get(f"{self.api_url}/api/providers")
            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Providers: {len(data.get('providers', []))}")
            for provider in data.get('providers', []):
                print(f"      - {provider['name']}: {provider['status']}")
            
            # Test matches endpoint
            print("\n3. Testing /api/matches endpoint...")
            response = await client.get(f"{self.api_url}/api/matches")
            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Total matches: {data.get('total', 0)}")
            
            # Show first few matches
            for match in data.get('matches', [])[:5]:
                print(f"      - {match['player1']} vs {match['player2']} ({match['status']})")
            
            # Test WebSocket stats
            print("\n4. Testing /api/websocket/stats endpoint...")
            response = await client.get(f"{self.api_url}/api/websocket/stats")
            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Active connections: {data.get('total_connections', 0)}")
            print(f"   Total subscriptions: {data.get('total_subscriptions', 0)}")
    
    async def connect(self):
        """Connect to WebSocket server."""
        print(f"\nConnecting to WebSocket at {self.ws_url}...")
        
        try:
            self.websocket = await websockets.connect(self.ws_url)
            print("✅ Connected successfully!")
            self.running = True
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket server."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            print("\n✅ Disconnected from server")
    
    async def send_message(self, message: dict):
        """Send message to server."""
        if not self.websocket:
            print("❌ Not connected to server")
            return
        
        try:
            await self.websocket.send(json.dumps(message))
            print(f"📤 Sent: {message}")
        except Exception as e:
            print(f"❌ Send error: {e}")
    
    async def receive_messages(self):
        """Receive messages from server."""
        if not self.websocket:
            return
        
        try:
            while self.running:
                message = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=60
                )
                
                data = json.loads(message)
                self.handle_message(data)
                
        except asyncio.TimeoutError:
            print("⏱️  No messages received (timeout)")
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Connection closed by server")
            self.running = False
        except Exception as e:
            print(f"❌ Receive error: {e}")
            self.running = False
    
    def handle_message(self, data: dict):
        """Handle received message."""
        msg_type = data.get("type")
        timestamp = data.get("timestamp", "")
        
        if msg_type == "ping":
            print(f"🏓 PING received at {timestamp}")
            # Send pong response
            asyncio.create_task(self.send_message({"type": "ping"}))
            
        elif msg_type == "pong":
            print(f"🏓 PONG received at {timestamp}")
            
        elif msg_type == "match_update":
            matches = data.get("data", {}).get("matches", [])
            print(f"🎾 MATCH UPDATE: {len(matches)} matches")
            for match in matches[:3]:  # Show first 3
                if isinstance(match, dict):
                    print(f"   - {match.get('player1')} vs {match.get('player2')}")
                else:
                    print(f"   - Match ID: {match}")
                    
        elif msg_type == "score_update":
            print(f"📊 SCORE UPDATE: {data.get('data')}")
            
        elif msg_type == "provider_status":
            print(f"🔌 PROVIDER STATUS: {data.get('data')}")
            
        elif msg_type == "subscription":
            subscribed = data.get("data", {}).get("subscribed", [])
            print(f"✅ SUBSCRIBED to {len(subscribed)} matches")
            
        elif msg_type == "error":
            print(f"❌ ERROR: {data.get('data')}")
            
        else:
            print(f"📨 {msg_type}: {data.get('data')}")
    
    async def test_subscriptions(self):
        """Test match subscriptions."""
        print("\n" + "=" * 60)
        print("TESTING SUBSCRIPTIONS")
        print("=" * 60)
        
        # Get available matches
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.api_url}/api/matches?status=live")
            data = response.json()
            matches = data.get("matches", [])
            
            if not matches:
                print("No live matches available for subscription")
                return
            
            # Subscribe to first 3 matches
            match_ids = [m["id"] for m in matches[:3]]
            print(f"\nSubscribing to {len(match_ids)} matches...")
            
            await self.send_message({
                "type": "subscribe",
                "match_ids": match_ids
            })
            
            # Wait for subscription confirmation
            await asyncio.sleep(2)
            
            # Unsubscribe from one match
            print(f"\nUnsubscribing from 1 match...")
            await self.send_message({
                "type": "unsubscribe",
                "match_ids": [match_ids[0]]
            })
    
    async def run_interactive(self):
        """Run interactive test session."""
        print("\n" + "=" * 60)
        print("INTERACTIVE MODE")
        print("=" * 60)
        print("\nCommands:")
        print("  1. Send ping")
        print("  2. Subscribe to matches")
        print("  3. Get match list")
        print("  4. Test API endpoints")
        print("  q. Quit")
        print("=" * 60)
        
        # Start receive task
        receive_task = asyncio.create_task(self.receive_messages())
        
        while self.running:
            try:
                # Get user input with timeout
                command = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, 
                        input, 
                        "\n> Enter command: "
                    ),
                    timeout=30
                )
                
                if command.lower() == 'q':
                    break
                elif command == '1':
                    await self.send_message({"type": "ping"})
                elif command == '2':
                    await self.test_subscriptions()
                elif command == '3':
                    async with httpx.AsyncClient() as client:
                        response = await client.get(f"{self.api_url}/api/matches")
                        data = response.json()
                        print(f"Found {data.get('total', 0)} matches")
                elif command == '4':
                    await self.test_api_endpoints()
                else:
                    print("Invalid command")
                    
            except asyncio.TimeoutError:
                # Just continue - allows receiving messages
                continue
            except KeyboardInterrupt:
                break
        
        # Cancel receive task
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass


async def main():
    """Main test function."""
    print("=" * 60)
    print("WEBSOCKET TEST CLIENT FOR TENNIS TRADING API")
    print("=" * 60)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create test client
    client = WebSocketTestClient("localhost:8000")
    
    # Test API endpoints first
    await client.test_api_endpoints()
    
    # Connect to WebSocket
    if await client.connect():
        try:
            # Run interactive session
            await client.run_interactive()
        finally:
            # Disconnect
            await client.disconnect()
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")