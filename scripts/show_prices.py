#!/usr/bin/env python3
"""Show current tennis prices from the backend."""

import httpx
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def show_prices():
    """Show current prices."""
    api_url = "http://localhost:8000"
    
    with httpx.Client() as client:
        # Get provider status
        print("\n" + "=" * 100)
        print("🎾 TENNIS TRADING - CURRENT PRICES FROM BETFAIR")
        print("=" * 100)
        
        response = client.get(f"{api_url}/api/providers")
        if response.status_code == 200:
            data = response.json()
            for provider in data["providers"]:
                status = "✅ Connected" if provider["status"] == "connected" else "❌ Disconnected"
                print(f"Provider: {provider['name']} - {status}")
                if provider["last_update"]:
                    print(f"Last Update: {provider['last_update']}")
        
        print("\n" + "=" * 100)
        print("CURRENT MATCHES AND PRICES")
        print("=" * 100)
        
        # Get matches with prices
        response = client.get(f"{api_url}/api/unified/matches")
        if response.status_code == 200:
            data = response.json()
            matches = data.get("matches", [])
            
            print(f"\nTotal Matches: {len(matches)}")
            print("-" * 100)
            
            # Group by tournament
            tournaments = {}
            for match in matches:
                tournament = match["match"]["tournament"]
                if tournament not in tournaments:
                    tournaments[tournament] = []
                tournaments[tournament].append(match)
            
            # Display by tournament
            for tournament, tournament_matches in sorted(tournaments.items()):
                print(f"\n📋 {tournament} ({len(tournament_matches)} matches)")
                print("-" * 80)
                
                for match in tournament_matches[:10]:  # Show first 10 per tournament
                    match_info = match["match"]
                    player1 = match_info["player1"]
                    player2 = match_info["player2"]
                    status = match_info["status"]
                    
                    # Status emoji
                    if status == "in_progress":
                        status_emoji = "🔴"
                    elif status == "not_started":
                        status_emoji = "⏳"
                    else:
                        status_emoji = "✅"
                    
                    print(f"\n{status_emoji} {player1} vs {player2}")
                    print(f"   Status: {status}")
                    
                    # Show prices if available
                    price_comp = match.get("price_comparison")
                    if price_comp:
                        p1_back = price_comp.get("best_back_player1")
                        p1_lay = price_comp.get("best_lay_player1")
                        p2_back = price_comp.get("best_back_player2")
                        p2_lay = price_comp.get("best_lay_player2")
                        
                        if p1_back:
                            p1_lay_str = f"{p1_lay:.2f}" if p1_lay else "-"
                            print(f"   {player1}: Back {p1_back:.2f} / Lay {p1_lay_str}")
                        if p2_back:
                            p2_lay_str = f"{p2_lay:.2f}" if p2_lay else "-"
                            print(f"   {player2}: Back {p2_back:.2f} / Lay {p2_lay_str}")
                        
                        # Show provider info
                        if price_comp.get("providers"):
                            print(f"   Providers: {', '.join(price_comp['providers'])}")
                    else:
                        print("   Prices: Not available yet")
                    
                    # Show data quality
                    if match.get("data_quality"):
                        for provider, quality in match["data_quality"].items():
                            latency = quality.get("latency_ms", 0)
                            print(f"   Data Quality ({provider}): {quality['status']} - {latency:.1f}ms")
            
            # Show arbitrage opportunities
            print("\n" + "=" * 100)
            print("💰 ARBITRAGE OPPORTUNITIES")
            print("=" * 100)
            
            response = client.get(f"{api_url}/api/arbitrage")
            if response.status_code == 200:
                data = response.json()
                opportunities = data.get("opportunities", [])
                
                if opportunities:
                    for opp in opportunities[:5]:
                        print(f"\n• Match ID: {opp['match_id']}")
                        print(f"  Type: {opp['type']}")
                        print(f"  Profit: {opp['profit_percentage']:.2f}%")
                        print(f"  Risk: {opp['risk_level']}")
                else:
                    print("\nNo arbitrage opportunities found")
            
            print("\n" + "=" * 100)


if __name__ == "__main__":
    show_prices()