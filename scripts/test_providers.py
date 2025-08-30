#!/usr/bin/env python3
"""Test script for data providers."""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# Import provider modules
from app.providers import DataProviderFactory, BetfairProvider


def setup_logging():
    """Configure logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger("test_providers")


def test_factory(logger):
    """Test the DataProviderFactory."""
    print("\n" + "=" * 60)
    print("🏭 Testing DataProviderFactory")
    print("=" * 60)
    
    # List available providers
    providers = DataProviderFactory.list_providers()
    print(f"✅ Available providers: {', '.join(providers)}")
    
    # Create a Betfair provider
    try:
        provider = DataProviderFactory.create_provider("betfair", logger)
        print(f"✅ Successfully created Betfair provider")
        return provider
    except Exception as e:
        print(f"❌ Failed to create provider: {e}")
        return None


def test_authentication(provider):
    """Test provider authentication."""
    print("\n" + "=" * 60)
    print("🔐 Testing Authentication")
    print("=" * 60)
    
    try:
        # Authenticate
        success = provider.authenticate()
        
        if success:
            print(f"✅ Authentication successful!")
            print(f"   Session token: {provider.session_token[:20]}...")
            return True
        else:
            print(f"❌ Authentication failed")
            return False
            
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False


def test_account_balance(provider):
    """Test getting account balance."""
    print("\n" + "=" * 60)
    print("💰 Testing Account Balance")
    print("=" * 60)
    
    try:
        balance = provider.get_account_balance()
        
        if balance:
            print(f"✅ Account balance retrieved:")
            for key, value in balance.items():
                if value is not None:
                    # Handle wallet which might be None or string
                    if isinstance(value, (int, float)):
                        print(f"   {key}: £{value:.2f}")
                    else:
                        print(f"   {key}: {value}")
            return True
        else:
            print(f"❌ Failed to get account balance")
            return False
            
    except Exception as e:
        print(f"❌ Error getting balance: {e}")
        return False


def test_live_matches(provider):
    """Test getting live tennis matches."""
    print("\n" + "=" * 60)
    print("🎾 Testing Live Matches")
    print("=" * 60)
    
    try:
        matches = provider.get_live_matches("tennis")
        
        if matches:
            print(f"✅ Found {len(matches)} live matches:")
            for i, match in enumerate(matches[:5], 1):  # Show first 5
                print(f"\n   Match {i}:")
                print(f"   Event: {match.event_name}")
                print(f"   Competition: {match.competition}")
                print(f"   Players: {match.home_player} vs {match.away_player}")
                print(f"   Status: {match.status}")
                print(f"   Market ID: {match.id}")
                
                # Get prices for first match
                if i == 1:
                    print(f"\n   Getting prices for this match...")
                    prices = provider.get_market_prices(match.id)
                    if prices:
                        for price_data in prices:
                            print(f"\n   {price_data.selection_name}:")
                            if price_data.back_prices:
                                best_back = price_data.back_prices[0]
                                print(f"     Best Back: {best_back['price']} @ £{best_back['size']:.2f}")
                            if price_data.lay_prices:
                                best_lay = price_data.lay_prices[0]
                                print(f"     Best Lay: {best_lay['price']} @ £{best_lay['size']:.2f}")
                            if price_data.last_price_traded:
                                print(f"     Last Traded: {price_data.last_price_traded}")
        else:
            print(f"ℹ️  No live tennis matches found at the moment")
            
        # Try to get upcoming matches instead
        print("\n📅 Getting upcoming tennis matches...")
        upcoming = get_upcoming_matches(provider)
        
        return True
        
    except Exception as e:
        print(f"❌ Error getting live matches: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_upcoming_matches(provider):
    """Get upcoming tennis matches."""
    try:
        from betfairlightweight import filters
        
        # Create filter for upcoming tennis matches
        market_filter = filters.market_filter(
            event_type_ids=[provider.TENNIS_EVENT_TYPE_ID],
            market_type_codes=["MATCH_ODDS"],
            market_start_time={
                "from": datetime.now().isoformat(),
                "to": datetime.now().replace(hour=23, minute=59).isoformat()
            }
        )
        
        # Get markets
        markets = provider.client.betting.list_market_catalogue(
            filter=market_filter,
            market_projection=["EVENT", "MARKET_START_TIME", "RUNNER_DESCRIPTION", "COMPETITION"],
            max_results=10,
            sort="FIRST_TO_START"
        )
        
        if markets:
            print(f"✅ Found {len(markets)} upcoming matches today:")
            for i, market in enumerate(markets[:5], 1):
                runners = market.get('runners', [])
                player1 = runners[0].get('runnerName', 'Unknown') if len(runners) > 0 else "Unknown"
                player2 = runners[1].get('runnerName', 'Unknown') if len(runners) > 1 else "Unknown"
                
                event = market.get('event', {})
                
                print(f"\n   Match {i}:")
                print(f"   Event: {event.get('name', 'Unknown')}")
                print(f"   Players: {player1} vs {player2}")
                print(f"   Start Time: {market.get('marketStartTime')}")
                print(f"   Market ID: {market.get('marketId')}")
                
        return markets
        
    except Exception as e:
        print(f"❌ Error getting upcoming matches: {e}")
        return []


def test_open_bets(provider):
    """Test getting open bets."""
    print("\n" + "=" * 60)
    print("📋 Testing Open Bets")
    print("=" * 60)
    
    try:
        open_bets = provider.get_open_bets()
        
        if open_bets:
            print(f"✅ Found {len(open_bets)} open bets:")
            for bet in open_bets:
                print(f"\n   Bet ID: {bet['bet_id']}")
                print(f"   Market: {bet['market_id']}")
                print(f"   Selection: {bet['selection_id']}")
                print(f"   Side: {bet['side']}")
                print(f"   Price: {bet['price']}")
                print(f"   Size: £{bet['size']:.2f}")
                print(f"   Matched: £{bet['matched_size']:.2f}")
                print(f"   Status: {bet['status']}")
        else:
            print(f"ℹ️  No open bets found")
            
        return True
        
    except Exception as e:
        print(f"❌ Error getting open bets: {e}")
        return False


def run_all_tests():
    """Run all provider tests."""
    print("=" * 60)
    print("🚀 Data Provider Test Suite")
    print("=" * 60)
    
    # Setup logging
    logger = setup_logging()
    
    # Test factory
    provider = test_factory(logger)
    if not provider:
        print("\n❌ Failed to create provider. Exiting.")
        return False
    
    # Test authentication
    if not test_authentication(provider):
        print("\n❌ Authentication failed. Exiting.")
        return False
    
    # Run tests
    all_passed = True
    
    try:
        # Test account balance
        if not test_account_balance(provider):
            all_passed = False
            
        # Test live matches
        if not test_live_matches(provider):
            all_passed = False
            
        # Test open bets
        if not test_open_bets(provider):
            all_passed = False
            
    finally:
        # Disconnect
        print("\n" + "=" * 60)
        print("🔌 Disconnecting")
        print("=" * 60)
        provider.disconnect()
        print("✅ Disconnected from provider")
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed successfully!")
    else:
        print("⚠️  Some tests failed. Check the output above.")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)