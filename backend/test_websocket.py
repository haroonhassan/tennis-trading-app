#!/usr/bin/env python3
"""Test WebSocket connections."""

import asyncio
import websockets
import json


async def test_websocket():
    """Test WebSocket monitor endpoint."""
    uri = "ws://localhost:8000/api/ws/monitor"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket")
            
            # Receive initial message
            message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            data = json.loads(message)
            print(f"✅ Received initial data: {data['type']}")
            
            # Test more messages (with timeout)
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                data = json.loads(message)
                print(f"✅ Received update: {data['type']}")
            except asyncio.TimeoutError:
                print("✅ WebSocket is waiting for updates (normal behavior)")
                
            print("✅ WebSocket connection working correctly!")
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_websocket())