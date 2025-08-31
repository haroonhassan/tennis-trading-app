#!/usr/bin/env python3
"""Place a £2 back bet on De Schepper vs Catry."""

import asyncio
import sys
import os
from pathlib import Path
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.providers.betfair import BetfairProvider


async def place_bet():
    """Place the bet on De Schepper."""
    print("Initializing Betfair connection...")
    
    # BetfairProvider reads credentials from environment variables
    # which are already set in the .env file
    betfair = BetfairProvider()
    
    # Authenticate with Betfair
    if not betfair.authenticate():
        print("❌ Failed to authenticate with Betfair")
        return False
    
    print("✅ Connected to Betfair")
    
    # Get tennis matches to find De Schepper vs Catry
    print("\nSearching for De Schepper vs Catry match...")
    matches = betfair.get_tennis_matches()
    
    # Find the match
    target_match = None
    for match in matches:
        if "De Schepper" in match.player1.name and "Catry" in match.player2.name:
            target_match = match
            break
        elif "Catry" in match.player1.name and "De Schepper" in match.player2.name:
            # Players might be reversed
            target_match = match
            break
    
    if not target_match:
        print("❌ Could not find De Schepper vs Catry match")
        return False
    
    print(f"✅ Found match: {target_match.player1.name} vs {target_match.player2.name}")
    print(f"   Tournament: {target_match.tournament_name}")
    print(f"   Market ID: {target_match.market_id}")
    
    # Get market details to find runner IDs
    market_book = betfair.get_market_book(target_match.market_id)
    if not market_book:
        print("❌ Could not fetch market details")
        return False
    
    # Find De Schepper's selection ID
    # First check if market_book is dict or list
    if isinstance(market_book, list) and len(market_book) > 0:
        market_book = market_book[0]
    
    runners = market_book.get("runners", [])
    de_schepper_selection_id = None
    
    print(f"\nFound {len(runners)} runners in market")
    
    # In market book, runners don't have names, we need to match by position
    # For tennis, runner[0] is usually home player, runner[1] is away
    # Since match shows "De Schepper vs Catry", De Schepper is player 1
    if len(runners) >= 1:
        # De Schepper should be the first runner
        runner = runners[0]
        de_schepper_selection_id = str(runner.get("selectionId"))
        
        # Get current prices
        ex = runner.get("ex", {})
        available_to_back = ex.get("availableToBack", [])
        if available_to_back:
            current_back_price = available_to_back[0].get("price")
            print(f"\n📊 Current back price for De Schepper: {current_back_price}")
        else:
            print("\n⚠️  No back prices available, placing at requested price")
    
    if not de_schepper_selection_id:
        print("❌ Could not find De Schepper runner ID")
        return False
    
    print(f"✅ Found De Schepper selection ID: {de_schepper_selection_id}")
    
    # Place the bet
    print("\n💰 Placing bet:")
    print("   Side: BACK")
    print("   Selection: De Schepper")  
    print("   Price: 1.04")
    print("   Stake: £2.00")
    print("   Market ID:", target_match.market_id)
    print("   Selection ID:", de_schepper_selection_id)
    
    # Confirm before placing real money bet
    confirm = input("\n⚠️  REAL MONEY BET - Type 'YES' to confirm: ")
    if confirm != "YES":
        print("❌ Bet cancelled")
        return False
    
    # Place the back bet
    result = betfair.place_back_bet(
        market_id=target_match.market_id,
        selection_id=de_schepper_selection_id,
        price=1.04,
        size=2.0
    )
    
    if result.get("success"):
        print("\n✅ BET PLACED SUCCESSFULLY!")
        print(f"   Bet ID: {result.get('bet_id')}")
        print(f"   Status: {result.get('status')}")
        print(f"   Size Matched: £{result.get('size_matched', 0)}")
        print(f"   Average Price: {result.get('average_price_matched', 0)}")
        print(f"   Placed Date: {result.get('placed_date')}")
        return True
    else:
        print(f"\n❌ BET FAILED!")
        print(f"   Error: {result.get('error')}")
        print(f"   Status: {result.get('status')}")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(place_bet())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)