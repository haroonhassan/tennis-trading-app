#!/usr/bin/env python3
"""Simple price console for tennis trading - displays prices in terminal."""

import asyncio
import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class SimplePriceConsole:
    """Simple console for displaying tennis prices."""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        """Initialize console."""
        self.api_url = api_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.matches = {}
        self.last_prices = {}
        
    async def fetch_matches(self):
        """Fetch matches from API."""
        try:
            response = await self.client.get(f"{self.api_url}/api/unified/matches")
            if response.status_code == 200:
                data = response.json()
                self.matches = {m["match_id"]: m for m in data.get("matches", [])}
                return True
        except Exception as e:
            print(f"Error fetching matches: {e}")
            return False
    
    async def fetch_prices(self):
        """Fetch prices for matches (simulated from match data)."""
        # For now, prices come with match data
        # In a real system, you'd have a separate price endpoint
        pass
    
    def display_matches(self):
        """Display matches with prices."""
        # Clear screen
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("=" * 120)
        print("🎾 LIVE TENNIS PRICES - BETFAIR DATA")
        print("=" * 120)
        print(f"Last Update: {datetime.now().strftime('%H:%M:%S')} | Total Matches: {len(self.matches)}")
        print("=" * 120)
        
        # Header
        print(f"{'#':<3} {'Tournament':<25} {'Match':<40} {'Status':<12} {'P1 Back':<10} {'P2 Back':<10} {'Trend':<10}")
        print("-" * 120)
        
        # Sort matches by tournament
        sorted_matches = sorted(self.matches.items(), 
                              key=lambda x: (x[1]["match"]["tournament"], x[1]["match"]["player1"]))
        
        # Display top 30 matches
        for idx, (match_id, match) in enumerate(sorted_matches[:30], 1):
            match_info = match["match"]
            
            # Format tournament name
            tournament = match_info["tournament"]
            if len(tournament) > 25:
                tournament = tournament[:22] + "..."
            
            # Format match name
            player1 = match_info["player1"]
            player2 = match_info["player2"]
            match_name = f"{player1} vs {player2}"
            if len(match_name) > 40:
                match_name = match_name[:37] + "..."
            
            # Get status
            status = match_info["status"]
            if status == "in_progress":
                status = "🔴 LIVE"
            elif status == "not_started":
                status = "⏳ Soon"
            
            # Get prices
            price_comp = match.get("price_comparison") or {}
            p1_back = price_comp.get("best_back_player1", 0) if price_comp else 0
            p2_back = price_comp.get("best_back_player2", 0) if price_comp else 0
            
            # Format prices
            p1_back_str = f"{p1_back:.2f}" if p1_back > 0 else "-"
            p2_back_str = f"{p2_back:.2f}" if p2_back > 0 else "-"
            
            # Calculate trend
            trend = ""
            if match_id in self.last_prices and p1_back > 0:
                last_p1 = self.last_prices[match_id].get("p1_back", 0)
                if last_p1 > 0:
                    if p1_back > last_p1:
                        trend = f"↑ {p1_back - last_p1:+.2f}"
                    elif p1_back < last_p1:
                        trend = f"↓ {p1_back - last_p1:+.2f}"
                    else:
                        trend = "→"
            
            # Store current prices
            if p1_back > 0 or p2_back > 0:
                self.last_prices[match_id] = {"p1_back": p1_back, "p2_back": p2_back}
            
            # Print row
            print(f"{idx:<3} {tournament:<25} {match_name:<40} {status:<12} {p1_back_str:<10} {p2_back_str:<10} {trend:<10}")
        
        # Show some statistics
        print("\n" + "=" * 120)
        matches_with_prices = sum(1 for m in self.matches.values() if m.get("price_comparison"))
        live_matches = sum(1 for m in self.matches.values() if m["match"]["status"] == "in_progress")
        
        print(f"📊 Stats: {matches_with_prices} matches with prices | {live_matches} live matches")
        
        # Show data quality for first match with quality info
        for match in self.matches.values():
            if match.get("data_quality"):
                quality = list(match["data_quality"].values())[0]
                latency = quality.get("latency_ms", 0)
                print(f"📡 Data Quality: {quality['status']} | Latency: {latency:.1f}ms")
                break
        
        print("=" * 120)
        print("Press Ctrl+C to exit | Refreshing every 5 seconds...")
    
    async def run(self):
        """Run the console."""
        print("Starting Simple Price Console...")
        print("Connecting to backend at", self.api_url)
        
        try:
            while True:
                # Fetch latest data
                await self.fetch_matches()
                
                # Display
                self.display_matches()
                
                # Wait 5 seconds
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        finally:
            await self.client.aclose()


async def main():
    """Main entry point."""
    console = SimplePriceConsole()
    await console.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")