#!/usr/bin/env python3
"""Test tennis scores and statistics service."""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
import signal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Load environment variables from main folder
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.providers import DataProviderFactory
from app.services import TennisScoresService
from app.providers.tennis_models import MatchStatus


class TennisScoresConsole:
    """Console display for tennis scores service."""
    
    def __init__(self):
        """Initialize console."""
        self.last_update = datetime.now()
        self.update_count = 0
        
    def display_matches(self, matches):
        """Display list of matches."""
        print("\n" + "=" * 100)
        print(f"{'#':<3} {'Match':<40} {'Tournament':<25} {'Status':<12} {'ID':<15}")
        print("-" * 100)
        
        for i, match in enumerate(matches, 1):
            player1 = match.player1.name[:18]
            player2 = match.player2.name[:18]
            match_name = f"{player1} v {player2}"
            tournament = match.tournament_name[:23]
            status = match.status.value
            
            # Add indicator for live matches
            if match.is_live():
                status = f"🔴 {status}"
            
            print(f"{i:<3} {match_name:<40} {tournament:<25} {status:<12} {match.id:<15}")
    
    def display_match_details(self, match_id: str, service: TennisScoresService):
        """Display detailed match information."""
        # Clear screen
        print("\033[2J\033[H", end="")
        
        # Get match summary
        summary = service.get_match_summary(match_id)
        
        print("=" * 100)
        print("🎾 TENNIS MATCH DETAILS")
        print("=" * 100)
        
        # Match info
        if summary["match"]:
            match = summary["match"]
            print(f"\n📊 Match Information")
            print(f"   ID: {match['id']}")
            print(f"   Tournament: {match['tournament_name']}")
            print(f"   Surface: {match['surface']}")
            print(f"   Status: {match['status']}")
            
            # Players
            print(f"\n👥 Players")
            print(f"   Player 1: {match['player1']['name']}")
            if match['player1'].get('ranking'):
                print(f"      Ranking: {match['player1']['ranking']}")
            print(f"   Player 2: {match['player2']['name']}")
            if match['player2'].get('ranking'):
                print(f"      Ranking: {match['player2']['ranking']}")
        
        # Score
        if summary["score"]:
            score = summary["score"]
            print(f"\n🏆 Score")
            print(f"   {score['score_string']}")
            print(f"   Sets: {score['player1_sets']} - {score['player2_sets']}")
            print(f"   Current Set: {score['current_set']}")
            print(f"   Status: {score['status']}")
        else:
            print(f"\n⚠️  Score data not available")
        
        # Server
        if summary["server"]:
            server = summary["server"]
            print(f"\n🎾 Current Server: {server['name']}")
        
        # Statistics
        if summary["statistics"]:
            stats = summary["statistics"]
            print(f"\n📈 Match Statistics")
            print("   (Would display detailed stats here if available)")
        else:
            print(f"\n⚠️  Statistics not available from Betfair API")
        
        print("\n" + "=" * 100)
        print(f"Last Update: {datetime.now().strftime('%H:%M:%S')} | Updates: {self.update_count}")
        self.update_count += 1


def main():
    """Main test function."""
    print("=" * 100)
    print("🎾 TENNIS SCORES SERVICE TEST")
    print("=" * 100)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("tennis_scores_test")
    
    # Create provider
    print("\n📦 Creating Betfair provider...")
    provider = DataProviderFactory.create_provider("betfair", logger)
    
    # Authenticate
    print("🔐 Authenticating...")
    if not provider.authenticate():
        print("❌ Authentication failed!")
        return 1
    
    print("✅ Authentication successful!")
    
    # Create scores service
    print("\n🎯 Creating Tennis Scores Service...")
    service = TennisScoresService(
        provider=provider,
        cache_ttl=30,  # 30 second cache
        update_interval=20,  # Update every 20 seconds
        logger=logger
    )
    
    # Start monitoring
    service.start_monitoring()
    print("✅ Service started with automatic updates every 20 seconds")
    
    # Console display
    console = TennisScoresConsole()
    
    print("\n" + "=" * 100)
    print("COMMANDS:")
    print("  1. Show live matches")
    print("  2. Show upcoming matches")
    print("  3. Show all matches")
    print("  4. Show match details (enter match number)")
    print("  5. Test caching")
    print("  6. Clear cache")
    print("  q. Quit")
    print("=" * 100)
    
    selected_match_id = None
    
    # Handle Ctrl+C
    def signal_handler(sig, frame):
        print("\n\n🛑 Stopping service...")
        service.stop_monitoring()
        provider.disconnect()
        print("✅ Done!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Interactive loop
    while True:
        try:
            command = input("\n> Enter command: ").strip().lower()
            
            if command == 'q':
                break
            elif command == '1':
                print("\n🔴 LIVE MATCHES")
                matches = service.get_matches(status="live")
                if matches:
                    console.display_matches(matches)
                else:
                    print("No live matches found")
                    
            elif command == '2':
                print("\n📅 UPCOMING MATCHES")
                matches = service.get_matches(status="upcoming")
                if matches:
                    console.display_matches(matches[:10])  # Show first 10
                else:
                    print("No upcoming matches found")
                    
            elif command == '3':
                print("\n📋 ALL MATCHES")
                matches = service.get_matches()
                if matches:
                    console.display_matches(matches[:20])  # Show first 20
                else:
                    print("No matches found")
                    
            elif command == '4':
                # Get match list first
                matches = service.get_matches()
                if not matches:
                    print("No matches available")
                    continue
                    
                console.display_matches(matches[:10])
                
                try:
                    match_num = int(input("\nEnter match number (1-10): "))
                    if 1 <= match_num <= min(10, len(matches)):
                        selected_match = matches[match_num - 1]
                        selected_match_id = selected_match.id
                        
                        # Add to monitored matches
                        service.add_monitored_match(selected_match_id)
                        
                        # Display details
                        console.display_match_details(selected_match_id, service)
                        
                        # Auto-refresh option
                        refresh = input("\nAuto-refresh every 10 seconds? (y/n): ").lower()
                        if refresh == 'y':
                            print("Press Ctrl+C to stop auto-refresh...")
                            while True:
                                time.sleep(10)
                                console.display_match_details(selected_match_id, service)
                    else:
                        print("Invalid match number")
                except (ValueError, KeyboardInterrupt):
                    print("\nReturning to menu...")
                    
            elif command == '5':
                print("\n🔄 TESTING CACHE")
                
                # First call - from provider
                start = time.time()
                matches1 = service.get_matches(use_cache=False)
                time1 = time.time() - start
                print(f"First call (no cache): {len(matches1)} matches in {time1:.3f}s")
                
                # Second call - from cache
                start = time.time()
                matches2 = service.get_matches(use_cache=True)
                time2 = time.time() - start
                print(f"Second call (cached): {len(matches2)} matches in {time2:.3f}s")
                
                print(f"Cache speedup: {time1/time2:.1f}x faster")
                
            elif command == '6':
                print("\n🗑️  Clearing cache...")
                service.cache.clear_all()
                print("✅ Cache cleared")
                
            else:
                print("Invalid command. Try again.")
                
        except KeyboardInterrupt:
            print("\nUse 'q' to quit or Ctrl+C again to force exit")
            continue
    
    # Cleanup
    print("\n🛑 Stopping service...")
    service.stop_monitoring()
    provider.disconnect()
    print("✅ Done!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())