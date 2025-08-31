#!/usr/bin/env python3
"""Live terminal console for tennis trading - displays real-time prices from backend."""

import asyncio
import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import httpx
import websockets
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.columns import Columns

# Try to import rich, install if not available
try:
    from rich import print as rprint
except ImportError:
    print("Installing rich for better console display...")
    os.system("pip install rich")
    from rich import print as rprint

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class TennisTradingConsole:
    """Live console for tennis trading data."""
    
    def __init__(self, api_url: str = "http://localhost:8000", ws_url: str = "ws://localhost:8000/ws"):
        """Initialize console."""
        self.api_url = api_url
        self.ws_url = ws_url
        self.console = Console()
        self.client = httpx.AsyncClient(timeout=30.0)
        self.websocket = None
        
        # Data storage
        self.matches = {}
        self.prices = {}
        self.price_history = {}
        self.arbitrage_opportunities = []
        self.provider_status = {}
        
        # Display settings
        self.selected_match_id = None
        self.display_mode = "overview"  # overview, detailed, arbitrage
        self.auto_refresh = True
        self.last_update = datetime.now()
        
    async def connect_websocket(self):
        """Connect to WebSocket for real-time updates."""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.console.print("[green]✓ Connected to WebSocket[/green]")
            
            # Start listening for messages
            asyncio.create_task(self.listen_websocket())
            return True
        except Exception as e:
            self.console.print(f"[red]✗ WebSocket connection failed: {e}[/red]")
            return False
    
    async def listen_websocket(self):
        """Listen for WebSocket messages."""
        if not self.websocket:
            return
        
        try:
            async for message in self.websocket:
                data = json.loads(message)
                await self.handle_websocket_message(data)
        except websockets.exceptions.ConnectionClosed:
            self.console.print("[yellow]WebSocket connection closed[/yellow]")
        except Exception as e:
            self.console.print(f"[red]WebSocket error: {e}[/red]")
    
    async def handle_websocket_message(self, data: Dict[str, Any]):
        """Handle incoming WebSocket message."""
        msg_type = data.get("type")
        
        if msg_type == "unified_update":
            # Update match data
            match_data = data.get("data", {}).get("match")
            if match_data:
                match_id = match_data.get("match_id")
                self.matches[match_id] = match_data
                self.last_update = datetime.now()
                
        elif msg_type == "arbitrage_alert":
            # Add arbitrage opportunity
            self.arbitrage_opportunities.append(data.get("data"))
            # Keep only last 10 opportunities
            if len(self.arbitrage_opportunities) > 10:
                self.arbitrage_opportunities.pop(0)
                
        elif msg_type == "provider_status":
            # Update provider status
            self.provider_status = data.get("data", {})
    
    async def fetch_matches(self):
        """Fetch matches from API."""
        try:
            response = await self.client.get(f"{self.api_url}/api/unified/matches")
            if response.status_code == 200:
                data = response.json()
                for match in data.get("matches", []):
                    match_id = match.get("match_id")
                    self.matches[match_id] = match
                    
                    # Store price data if available
                    if match.get("price_comparison"):
                        self.prices[match_id] = match["price_comparison"]
                        
                        # Track price history
                        if match_id not in self.price_history:
                            self.price_history[match_id] = []
                        
                        self.price_history[match_id].append({
                            "time": datetime.now(),
                            "player1_back": match["price_comparison"].get("best_back_player1"),
                            "player2_back": match["price_comparison"].get("best_back_player2")
                        })
                        
                        # Keep only last 20 prices
                        if len(self.price_history[match_id]) > 20:
                            self.price_history[match_id].pop(0)
                
                return True
        except Exception as e:
            self.console.print(f"[red]Error fetching matches: {e}[/red]")
            return False
    
    async def fetch_arbitrage(self):
        """Fetch arbitrage opportunities."""
        try:
            response = await self.client.get(f"{self.api_url}/api/arbitrage")
            if response.status_code == 200:
                data = response.json()
                self.arbitrage_opportunities = data.get("opportunities", [])
        except Exception as e:
            self.console.print(f"[red]Error fetching arbitrage: {e}[/red]")
    
    async def fetch_providers(self):
        """Fetch provider status."""
        try:
            response = await self.client.get(f"{self.api_url}/api/providers")
            if response.status_code == 200:
                data = response.json()
                self.provider_status = data
        except Exception as e:
            self.console.print(f"[red]Error fetching providers: {e}[/red]")
    
    def create_header(self) -> Panel:
        """Create header panel."""
        header_text = Text()
        header_text.append("🎾 TENNIS TRADING CONSOLE", style="bold cyan")
        header_text.append("\n")
        header_text.append(f"Last Update: {self.last_update.strftime('%H:%M:%S')}", style="dim")
        
        # Add provider status
        if self.provider_status.get("providers"):
            header_text.append(" | Providers: ")
            for provider in self.provider_status["providers"]:
                status = provider["status"]
                color = "green" if status == "connected" else "red"
                header_text.append(f"{provider['name']}", style=f"bold {color}")
                header_text.append(" ")
        
        return Panel(Align.center(header_text), style="bold blue")
    
    def create_matches_table(self) -> Table:
        """Create matches table."""
        table = Table(title="Live Matches", show_header=True, header_style="bold magenta")
        
        table.add_column("#", style="dim", width=4)
        table.add_column("Tournament", style="cyan", width=20)
        table.add_column("Match", style="white", width=35)
        table.add_column("Status", style="yellow", width=12)
        table.add_column("P1 Back", style="green", width=10)
        table.add_column("P1 Lay", style="red", width=10)
        table.add_column("P2 Back", style="green", width=10)
        table.add_column("P2 Lay", style="red", width=10)
        table.add_column("Trend", style="blue", width=8)
        
        # Sort matches by tournament
        sorted_matches = sorted(self.matches.items(), 
                              key=lambda x: (x[1]["match"]["tournament"], x[1]["match"]["player1"]))
        
        for idx, (match_id, match) in enumerate(sorted_matches[:20], 1):
            match_info = match["match"]
            price_comp = match.get("price_comparison") or {}
            
            # Format match name
            match_name = f"{match_info['player1']} vs {match_info['player2']}"
            if len(match_name) > 35:
                match_name = match_name[:32] + "..."
            
            # Get prices (handle None price_comparison)
            p1_back = price_comp.get("best_back_player1", "-") if price_comp else "-"
            p1_lay = price_comp.get("best_lay_player1", "-") if price_comp else "-"
            p2_back = price_comp.get("best_back_player2", "-") if price_comp else "-"
            p2_lay = price_comp.get("best_lay_player2", "-") if price_comp else "-"
            
            # Format prices
            if p1_back != "-":
                p1_back = f"{p1_back:.2f}"
            if p1_lay != "-":
                p1_lay = f"{p1_lay:.2f}"
            if p2_back != "-":
                p2_back = f"{p2_back:.2f}"
            if p2_lay != "-":
                p2_lay = f"{p2_lay:.2f}"
            
            # Get trend
            trend = self.get_price_trend(match_id)
            
            # Status with emoji
            status = match_info["status"]
            if status == "in_progress":
                status = "🔴 LIVE"
            elif status == "not_started":
                status = "⏳ Upcoming"
            
            table.add_row(
                str(idx),
                match_info["tournament"][:20],
                match_name,
                status,
                p1_back,
                p1_lay,
                p2_back,
                p2_lay,
                trend
            )
        
        return table
    
    def get_price_trend(self, match_id: str) -> str:
        """Get price trend for a match."""
        if match_id not in self.price_history or len(self.price_history[match_id]) < 2:
            return "→"
        
        history = self.price_history[match_id]
        latest = history[-1]
        previous = history[-2]
        
        if not latest["player1_back"] or not previous["player1_back"]:
            return "→"
        
        if latest["player1_back"] > previous["player1_back"]:
            return "↑ " + f"{latest['player1_back']:.2f}"
        elif latest["player1_back"] < previous["player1_back"]:
            return "↓ " + f"{latest['player1_back']:.2f}"
        else:
            return "→ " + f"{latest['player1_back']:.2f}"
    
    def create_arbitrage_panel(self) -> Panel:
        """Create arbitrage opportunities panel."""
        if not self.arbitrage_opportunities:
            return Panel("No arbitrage opportunities found", title="💰 Arbitrage Opportunities", style="yellow")
        
        arb_text = Text()
        for opp in self.arbitrage_opportunities[:5]:
            profit = opp.get("profit_percentage", 0)
            match_id = opp.get("match_id", "Unknown")
            
            # Get match name
            match_name = "Unknown Match"
            if match_id in self.matches:
                match_info = self.matches[match_id]["match"]
                match_name = f"{match_info['player1']} vs {match_info['player2']}"
            
            color = "green" if profit > 2 else "yellow"
            arb_text.append(f"• {match_name[:40]}: ", style="white")
            arb_text.append(f"{profit:.2f}% profit", style=f"bold {color}")
            arb_text.append(f" ({opp.get('type', 'unknown')})\n", style="dim")
        
        return Panel(arb_text, title="💰 Arbitrage Opportunities", style="green")
    
    def create_stats_panel(self) -> Panel:
        """Create statistics panel."""
        stats_text = Text()
        
        total_matches = len(self.matches)
        live_matches = sum(1 for m in self.matches.values() if m["match"]["status"] == "in_progress")
        matches_with_prices = sum(1 for m in self.matches.values() if m.get("price_comparison"))
        
        stats_text.append(f"Total Matches: {total_matches}\n", style="cyan")
        stats_text.append(f"Live Matches: {live_matches}\n", style="red")
        stats_text.append(f"Matches with Prices: {matches_with_prices}\n", style="green")
        stats_text.append(f"Arbitrage Opportunities: {len(self.arbitrage_opportunities)}\n", style="yellow")
        
        # Calculate average latency
        avg_latency = 0
        latency_count = 0
        for match in self.matches.values():
            if match.get("data_quality"):
                for provider, quality in match["data_quality"].items():
                    avg_latency += quality.get("latency_ms", 0)
                    latency_count += 1
        
        if latency_count > 0:
            avg_latency = avg_latency / latency_count
            stats_text.append(f"Avg Latency: {avg_latency:.1f}ms\n", style="blue")
        
        return Panel(stats_text, title="📊 Statistics", style="cyan")
    
    def create_layout(self) -> Layout:
        """Create the main layout."""
        layout = Layout()
        
        layout.split_column(
            Layout(self.create_header(), size=4),
            Layout(name="main"),
            Layout(name="bottom", size=8)
        )
        
        layout["main"].update(self.create_matches_table())
        
        layout["bottom"].split_row(
            Layout(self.create_arbitrage_panel()),
            Layout(self.create_stats_panel())
        )
        
        return layout
    
    async def run(self):
        """Run the live console."""
        self.console.clear()
        self.console.print("[bold cyan]Starting Tennis Trading Console...[/bold cyan]")
        
        # Connect to WebSocket
        await self.connect_websocket()
        
        # Initial data fetch
        await self.fetch_providers()
        await self.fetch_matches()
        await self.fetch_arbitrage()
        
        # Start auto-refresh task
        asyncio.create_task(self.auto_refresh_data())
        
        # Live display
        with Live(self.create_layout(), refresh_per_second=2, console=self.console) as live:
            try:
                while True:
                    # Update display
                    live.update(self.create_layout())
                    
                    # Check for user input (non-blocking)
                    await asyncio.sleep(0.5)
                    
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Shutting down...[/yellow]")
                if self.websocket:
                    await self.websocket.close()
                await self.client.aclose()
    
    async def auto_refresh_data(self):
        """Auto-refresh data periodically."""
        while self.auto_refresh:
            try:
                await asyncio.sleep(5)  # Refresh every 5 seconds
                await self.fetch_matches()
                await self.fetch_arbitrage()
                await self.fetch_providers()
                self.last_update = datetime.now()
            except Exception as e:
                self.console.print(f"[red]Auto-refresh error: {e}[/red]")


async def main():
    """Main entry point."""
    console = TennisTradingConsole()
    await console.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")