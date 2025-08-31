#!/usr/bin/env python3
"""Basic console using only standard library and requests."""

import json
import time
import sys
from datetime import datetime
from pathlib import Path

# Use requests which is already installed
import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def show_live_data():
    """Show live tennis data."""
    api_url = "http://localhost:8000"
    
    print("Starting Basic Tennis Console...")
    print("Press Ctrl+C to exit")
    print()
    
    try:
        while True:
            # Clear screen (optional - comment out if you prefer scrolling)
            print("\033[2J\033[H", end="")
            
            print("=" * 100)
            print(f"🎾 TENNIS LIVE DATA - {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 100)
            
            try:
                # Get provider status
                response = requests.get(f"{api_url}/api/providers", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    for provider in data["providers"]:
                        status = "✅" if provider["status"] == "connected" else "❌"
                        print(f"{status} {provider['name']} - {provider['status']}")
                
                print("\n" + "-" * 100)
                print("MATCHES AND PRICES")
                print("-" * 100)
                
                # Get matches
                response = requests.get(f"{api_url}/api/unified/matches", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    matches = data.get("matches", [])
                    
                    print(f"Total: {len(matches)} matches\n")
                    
                    # Show first 20 matches
                    for i, match in enumerate(matches[:20], 1):
                        match_info = match["match"]
                        tournament = match_info["tournament"][:30]
                        player1 = match_info["player1"]
                        player2 = match_info["player2"]
                        status = match_info["status"]
                        
                        # Status indicator
                        if status == "in_progress":
                            status_icon = "🔴"
                        else:
                            status_icon = "⏳"
                        
                        print(f"{i:2}. {status_icon} {tournament}")
                        print(f"    {player1} vs {player2}")
                        
                        # Show prices if available
                        price_comp = match.get("price_comparison")
                        if price_comp:
                            p1_back = price_comp.get("best_back_player1")
                            p2_back = price_comp.get("best_back_player2")
                            
                            if p1_back or p2_back:
                                prices = []
                                if p1_back:
                                    prices.append(f"{player1}: {p1_back:.2f}")
                                if p2_back:
                                    prices.append(f"{player2}: {p2_back:.2f}")
                                print(f"    Prices: {' | '.join(prices)}")
                        
                        # Show data quality
                        if match.get("data_quality"):
                            for provider, quality in match["data_quality"].items():
                                latency = quality.get("latency_ms", 0)
                                print(f"    Quality: {quality['status']} ({latency:.1f}ms)")
                        
                        print()
                
                # Show arbitrage
                response = requests.get(f"{api_url}/api/arbitrage", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    opps = data.get("opportunities", [])
                    
                    if opps:
                        print("-" * 100)
                        print(f"💰 ARBITRAGE: {len(opps)} opportunities")
                        for opp in opps[:3]:
                            print(f"  • {opp['profit_percentage']:.2f}% profit - {opp['type']}")
                
            except requests.exceptions.RequestException as e:
                print(f"Error connecting to server: {e}")
                print("Make sure the server is running at http://localhost:8000")
            
            # Wait 5 seconds before refreshing
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\nGoodbye!")


if __name__ == "__main__":
    show_live_data()