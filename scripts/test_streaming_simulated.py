#!/usr/bin/env python3
"""Test streaming with simulated mode (polling) for demonstration."""

import os
import sys
import time
import logging
import threading
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
from app.providers.models import (
    StreamMessage, 
    MessageType, 
    StreamConfig,
    MarketPrices,
    RunnerPrices,
    PriceVolume
)


class SimulatedStreaming:
    """Simulated streaming using polling for demonstration."""
    
    def __init__(self, provider, market_id: str, interval: float = 1.0):
        """
        Initialize simulated streaming.
        
        Args:
            provider: Data provider instance
            market_id: Market ID to stream
            interval: Polling interval in seconds
        """
        self.provider = provider
        self.market_id = market_id
        self.interval = interval
        self.running = False
        self._thread = None
        self._callback = None
        self.logger = logging.getLogger("simulated_stream")
        
    def start(self, callback):
        """Start simulated streaming."""
        self._callback = callback
        self.running = True
        
        # Send connection message
        callback(StreamMessage.connection_message(
            "betfair",
            "connected",
            mode="simulated_polling"
        ))
        
        # Start polling thread
        self._thread = threading.Thread(target=self._poll_loop)
        self._thread.daemon = True
        self._thread.start()
        
    def stop(self):
        """Stop simulated streaming."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _poll_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                # Get market prices
                price_data_list = self.provider.get_market_prices(self.market_id)
                
                if price_data_list:
                    # Convert to universal format
                    market_prices = self._convert_to_market_prices(price_data_list)
                    
                    # Send market change message
                    if market_prices and self._callback:
                        self._callback(StreamMessage.market_change_message(
                            "betfair",
                            market_prices
                        ))
                
                # Wait for next poll
                time.sleep(self.interval)
                
            except Exception as e:
                self.logger.error(f"Polling error: {e}")
                if self._callback:
                    self._callback(StreamMessage.error_message(
                        "betfair",
                        str(e)
                    ))
    
    def _convert_to_market_prices(self, price_data_list) -> MarketPrices:
        """Convert provider price data to universal MarketPrices."""
        # Get market info
        market_info = self._get_market_info()
        
        market_prices = MarketPrices(
            market_id=self.market_id,
            market_name=market_info.get("name"),
            event_name=market_info.get("event_name"),
            in_play=market_info.get("in_play", False)
        )
        
        # Convert each runner
        for price_data in price_data_list:
            runner_prices = RunnerPrices(
                runner_id=price_data.selection_id,
                runner_name=price_data.selection_name,
                last_traded_price=price_data.last_price_traded,
                total_matched=price_data.total_matched
            )
            
            # Convert back prices
            for price_dict in price_data.back_prices:
                runner_prices.back_prices.append(
                    PriceVolume(price_dict["price"], price_dict["size"])
                )
            
            # Convert lay prices
            for price_dict in price_data.lay_prices:
                runner_prices.lay_prices.append(
                    PriceVolume(price_dict["price"], price_dict["size"])
                )
            
            market_prices.runners[price_data.selection_id] = runner_prices
        
        return market_prices
    
    def _get_market_info(self) -> Dict:
        """Get market information."""
        try:
            from betfairlightweight import filters
            
            markets = self.provider.client.betting.list_market_catalogue(
                filter=filters.market_filter(market_ids=[self.market_id]),
                market_projection=["EVENT", "MARKET_DESCRIPTION", "RUNNER_DESCRIPTION"],
                max_results=1
            )
            
            if markets:
                market = markets[0]
                event = market.get("event", {})
                return {
                    "name": market.get("marketName", "Match Odds"),
                    "event_name": event.get("name"),
                    "in_play": market.get("inPlay", False)
                }
        except:
            pass
        
        return {}


class StreamingConsole:
    """Console display for streaming prices."""
    
    def __init__(self):
        """Initialize console display."""
        self.market_data = {}
        self.last_update = {}
        self.message_count = 0
        self.start_time = datetime.now()
        self.last_prices = {}  # Track price changes
        
    def handle_stream_message(self, message: StreamMessage):
        """Handle incoming stream message."""
        self.message_count += 1
        
        if message.type == MessageType.CONNECTION:
            self._print_status(f"✅ Stream connected: {message.data}")
            
        elif message.type == MessageType.MARKET_CHANGE:
            self._handle_market_change(message)
            
        elif message.type == MessageType.ERROR:
            self._print_status(f"❌ Error: {message.error}")
    
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
        # Clear screen
        print("\033[2J\033[H", end="")
        
        # Header
        print("=" * 100)
        print("🎾 TENNIS TRADING - LIVE PRICE STREAMING (Simulated)")
        print("=" * 100)
        
        # Connection info
        runtime = datetime.now() - self.start_time
        print(f"Runtime: {runtime} | Updates: {self.message_count} | Mode: Polling")
        print("-" * 100)
        
        # Market info
        print(f"\n📊 Market: {market_prices.market_id}")
        if market_prices.event_name:
            print(f"   Event: {market_prices.event_name}")
        print(f"   Type: Match Odds")
        print(f"   Last Update: {market_prices.timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        
        # Price display with change indicators
        print("\n" + "=" * 100)
        print(f"{'Runner':<35} {'Back':<25} {'Lay':<25} {'Last':<15}")
        print("-" * 100)
        
        for runner_id, runner_prices in market_prices.runners.items():
            runner_name = runner_prices.runner_name or f"Runner {runner_id}"
            
            # Track price changes
            price_key = f"{market_prices.market_id}_{runner_id}"
            prev_back = self.last_prices.get(f"{price_key}_back")
            prev_lay = self.last_prices.get(f"{price_key}_lay")
            
            # Format back price with change indicator
            if runner_prices.best_back:
                back_price = runner_prices.best_back.price
                back = f"{back_price:.2f} @ £{runner_prices.best_back.volume:.0f}"
                
                if prev_back:
                    if back_price > prev_back:
                        back += " ↑"
                    elif back_price < prev_back:
                        back += " ↓"
                
                self.last_prices[f"{price_key}_back"] = back_price
            else:
                back = "---"
            
            # Format lay price with change indicator
            if runner_prices.best_lay:
                lay_price = runner_prices.best_lay.price
                lay = f"{lay_price:.2f} @ £{runner_prices.best_lay.volume:.0f}"
                
                if prev_lay:
                    if lay_price > prev_lay:
                        lay += " ↑"
                    elif lay_price < prev_lay:
                        lay += " ↓"
                
                self.last_prices[f"{price_key}_lay"] = lay_price
            else:
                lay = "---"
            
            # Format last traded
            if runner_prices.last_traded_price:
                last = f"{runner_prices.last_traded_price:.2f}"
                if runner_prices.total_matched:
                    last += f" (£{runner_prices.total_matched:.0f})"
            else:
                last = "---"
            
            # Truncate runner name if too long
            display_name = runner_name[:35]
            print(f"{display_name:<35} {back:<25} {lay:<25} {last:<15}")
        
        print("=" * 100)
        print("\n📌 Price arrows show movement since last update")
        print("Press Ctrl+C to stop streaming...")
    
    def _print_status(self, message: str):
        """Print a status message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")


def main():
    """Main function."""
    print("=" * 100)
    print("🚀 BETFAIR STREAMING TEST (SIMULATED MODE)")
    print("=" * 100)
    print("\n⚠️  Note: Using polling mode for demonstration.")
    print("   Real streaming requires Betfair Stream API access approval.")
    print("-" * 100)
    
    # Setup logging
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create provider
    print("\n📦 Creating Betfair provider...")
    provider = DataProviderFactory.create_provider("betfair")
    
    # Authenticate
    print("🔐 Authenticating...")
    if not provider.authenticate():
        print("❌ Authentication failed!")
        return 1
    
    print("✅ Authentication successful!")
    
    # Get live matches
    print("\n🔍 Looking for tennis markets...")
    matches = provider.get_live_matches("tennis")
    
    market_id = None
    
    if matches:
        # Use first match
        match = matches[0]
        market_id = match.id
        print(f"\n✅ Found live match: {match.event_name}")
        print(f"   Market ID: {market_id}")
    else:
        # Get upcoming match
        print("No live matches. Looking for upcoming...")
        
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
            market_projection=["EVENT", "MARKET_START_TIME"],
            max_results=5,
            sort="FIRST_TO_START"
        )
        
        if markets:
            market = markets[0]
            market_id = market.get("marketId")
            event = market.get("event", {})
            print(f"\n✅ Found upcoming match: {event.get('name')}")
            print(f"   Market ID: {market_id}")
    
    if not market_id:
        print("\n❌ No suitable markets found")
        
        if len(sys.argv) > 1:
            market_id = sys.argv[1]
            print(f"\n📊 Using provided market ID: {market_id}")
        else:
            print("\n💡 You can provide a specific market ID:")
            print("   python test_streaming_simulated.py <market_id>")
            return 1
    
    # Create console and simulated stream
    console = StreamingConsole()
    stream = SimulatedStreaming(provider, market_id, interval=2.0)
    
    print(f"\n📡 Starting simulated stream for market {market_id}...")
    print("   Polling every 2 seconds...")
    
    # Start streaming
    stream.start(console.handle_stream_message)
    
    print("\n✅ Streaming started!")
    print("-" * 100)
    
    # Handle Ctrl+C
    def signal_handler(sig, frame):
        print("\n\n🛑 Stopping stream...")
        stream.stop()
        provider.disconnect()
        print("✅ Done!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()
        provider.disconnect()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())