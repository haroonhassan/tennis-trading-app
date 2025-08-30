#!/usr/bin/env python3
"""Test streaming functionality with live tennis market."""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import signal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.providers import DataProviderFactory
from app.providers.models import StreamMessage, MessageType, StreamConfig


class StreamingConsole:
    """Console display for streaming prices."""
    
    def __init__(self):
        """Initialize console display."""
        self.market_data = {}
        self.last_update = {}
        self.message_count = 0
        self.start_time = datetime.now()
        
    def handle_stream_message(self, message: StreamMessage):
        """Handle incoming stream message."""
        self.message_count += 1
        
        if message.type == MessageType.CONNECTION:
            self._print_status(f"✅ Stream connected: {message.data}")
            
        elif message.type == MessageType.HEARTBEAT:
            # Don't print heartbeats to avoid clutter
            pass
            
        elif message.type == MessageType.MARKET_CHANGE:
            self._handle_market_change(message)
            
        elif message.type == MessageType.ERROR:
            self._print_status(f"❌ Error: {message.error}")
            
        elif message.type == MessageType.STATUS:
            self._print_status(f"ℹ️  Status: {message.data}")
    
    def _handle_market_change(self, message: StreamMessage):
        """Handle market price changes."""
        market_prices = message.data
        market_id = market_prices.market_id
        
        # Store market data
        self.market_data[market_id] = market_prices
        self.last_update[market_id] = datetime.now()
        
        # Display update
        self._display_market(market_prices)
    
    def _display_market(self, market_prices):
        """Display market prices in console."""
        # Clear screen (works on Unix/Mac)
        print("\033[2J\033[H", end="")
        
        # Header
        print("=" * 80)
        print("🎾 TENNIS TRADING - LIVE STREAMING PRICES")
        print("=" * 80)
        
        # Connection info
        runtime = datetime.now() - self.start_time
        print(f"Runtime: {runtime} | Messages: {self.message_count}")
        print("-" * 80)
        
        # Market info
        print(f"\n📊 Market: {market_prices.market_id}")
        if market_prices.event_name:
            print(f"   Event: {market_prices.event_name}")
        if market_prices.market_name:
            print(f"   Type: {market_prices.market_name}")
        print(f"   In-Play: {'🔴 YES' if market_prices.in_play else '⚪ NO'}")
        if market_prices.total_matched:
            print(f"   Total Matched: £{market_prices.total_matched:,.2f}")
        print(f"   Last Update: {market_prices.timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        
        # Price display
        print("\n" + "=" * 80)
        print(f"{'Runner':<30} {'Back':<20} {'Lay':<20} {'Last Traded':<10}")
        print("-" * 80)
        
        for runner_id, runner_prices in market_prices.runners.items():
            runner_name = runner_prices.runner_name or f"Runner {runner_id}"
            
            # Format back price
            if runner_prices.best_back:
                back = f"{runner_prices.best_back.price:.2f} @ £{runner_prices.best_back.volume:.0f}"
            else:
                back = "---"
            
            # Format lay price
            if runner_prices.best_lay:
                lay = f"{runner_prices.best_lay.price:.2f} @ £{runner_prices.best_lay.volume:.0f}"
            else:
                lay = "---"
            
            # Format last traded
            if runner_prices.last_traded_price:
                last = f"{runner_prices.last_traded_price:.2f}"
            else:
                last = "---"
            
            print(f"{runner_name[:30]:<30} {back:<20} {lay:<20} {last:<10}")
            
            # Show price depth if available
            if len(runner_prices.back_prices) > 1 or len(runner_prices.lay_prices) > 1:
                self._display_price_depth(runner_prices)
        
        print("=" * 80)
        print("\nPress Ctrl+C to stop streaming...")
    
    def _display_price_depth(self, runner_prices):
        """Display price depth for a runner."""
        # Show up to 3 levels of prices
        depth_str = "   Depth: "
        
        # Back prices
        if len(runner_prices.back_prices) > 1:
            back_depth = " | ".join([f"{p.price:.2f}" for p in runner_prices.back_prices[:3]])
            depth_str += f"Back [{back_depth}]"
        
        # Lay prices
        if len(runner_prices.lay_prices) > 1:
            if len(runner_prices.back_prices) > 1:
                depth_str += " / "
            lay_depth = " | ".join([f"{p.price:.2f}" for p in runner_prices.lay_prices[:3]])
            depth_str += f"Lay [{lay_depth}]"
        
        if len(depth_str) > 11:  # More than just "   Depth: "
            print(depth_str)
    
    def _print_status(self, message: str):
        """Print a status message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")


def find_tennis_market(provider) -> Optional[str]:
    """Find a suitable tennis market for streaming."""
    print("\n🔍 Looking for live tennis markets...")
    
    # Get live matches
    matches = provider.get_live_matches("tennis")
    
    if not matches:
        print("No live matches found. Looking for upcoming matches...")
        
        # Get upcoming matches
        from betfairlightweight import filters
        
        market_filter = filters.market_filter(
            event_type_ids=[provider.TENNIS_EVENT_TYPE_ID],
            market_type_codes=["MATCH_ODDS"],
            market_start_time={
                "from": datetime.now().isoformat(),
                "to": datetime.now().replace(hour=23, minute=59).isoformat()
            }
        )
        
        markets = provider.client.betting.list_market_catalogue(
            filter=market_filter,
            market_projection=["EVENT", "MARKET_START_TIME", "RUNNER_DESCRIPTION"],
            max_results=10,
            sort="FIRST_TO_START"
        )
        
        if markets:
            # Use first available market
            market = markets[0]
            event = market.get('event', {})
            print(f"\n✅ Found upcoming match: {event.get('name', 'Unknown')}")
            print(f"   Market ID: {market.get('marketId')}")
            print(f"   Start Time: {market.get('marketStartTime')}")
            return market.get('marketId')
    else:
        # Use first live match
        match = matches[0]
        print(f"\n✅ Found live match: {match.event_name}")
        print(f"   Competition: {match.competition}")
        print(f"   Market ID: {match.id}")
        return match.id
    
    return None


def main():
    """Main streaming test function."""
    print("=" * 80)
    print("🚀 BETFAIR STREAMING TEST")
    print("=" * 80)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("streaming_test")
    
    # Create provider
    print("\n📦 Creating Betfair provider...")
    provider = DataProviderFactory.create_provider("betfair", logger)
    
    # Authenticate
    print("🔐 Authenticating...")
    if not provider.authenticate():
        print("❌ Authentication failed!")
        return 1
    
    print("✅ Authentication successful!")
    
    # Find a market to stream
    market_id = find_tennis_market(provider)
    
    if not market_id:
        print("\n❌ No suitable markets found for streaming")
        
        # Let user provide a market ID
        print("\n💡 You can provide a specific market ID to stream:")
        print("   Example: python test_streaming.py 1.247201095")
        
        if len(sys.argv) > 1:
            market_id = sys.argv[1]
            print(f"\n📊 Using provided market ID: {market_id}")
        else:
            return 1
    
    # Configure streaming
    stream_config = StreamConfig(
        conflate_ms=500,  # Update every 500ms
        heartbeat_ms=10000,  # Heartbeat every 10 seconds
        auto_reconnect=True,
        max_reconnect_attempts=5
    )
    
    print(f"\n🔌 Connecting to stream...")
    if not provider.connect_stream(stream_config):
        print("❌ Failed to connect to stream!")
        return 1
    
    print("✅ Stream connected!")
    
    # Create console display
    console = StreamingConsole()
    
    # Subscribe to market
    print(f"\n📡 Subscribing to market {market_id}...")
    
    if not provider.subscribe_market_stream(
        [market_id],
        console.handle_stream_message,
        {"conflate_ms": 500}
    ):
        print("❌ Failed to subscribe to market!")
        return 1
    
    print("✅ Subscribed! Streaming live prices...")
    print("\n" + "=" * 80)
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\n🛑 Stopping stream...")
        provider.disconnect_stream()
        provider.disconnect()
        print("✅ Disconnected successfully")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Keep running
    try:
        while True:
            time.sleep(1)
            
            # Check stream status
            if not provider.is_stream_connected():
                print("\n⚠️  Stream disconnected. Attempting to reconnect...")
                if not provider.connect_stream(stream_config):
                    print("❌ Reconnection failed")
                    break
                    
    except KeyboardInterrupt:
        pass
    finally:
        print("\n🛑 Cleaning up...")
        provider.disconnect_stream()
        provider.disconnect()
        print("✅ Done!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())