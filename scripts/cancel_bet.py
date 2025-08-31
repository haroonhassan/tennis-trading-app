#!/usr/bin/env python3
"""Cancel the bet that was placed."""

import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.providers.betfair import BetfairProvider


async def cancel_bet():
    """Cancel the bet."""
    print("Initializing Betfair connection...")
    
    # BetfairProvider reads credentials from environment variables
    betfair = BetfairProvider()
    
    # Authenticate with Betfair
    if not betfair.authenticate():
        print("❌ Failed to authenticate with Betfair")
        return False
    
    print("✅ Connected to Betfair")
    
    # The bet ID from the previous placement
    bet_id = "400263271157"
    
    print(f"\n🔍 Looking for bet ID: {bet_id}")
    
    # First, let's check if the bet is still open
    open_orders = betfair.get_open_orders()
    
    bet_found = False
    for order in open_orders:
        if order.get("bet_id") == bet_id:
            bet_found = True
            print(f"✅ Found open bet:")
            print(f"   Market ID: {order.get('market_id')}")
            print(f"   Selection ID: {order.get('selection_id')}")
            print(f"   Price: {order.get('price')}")
            print(f"   Size: £{order.get('size')}")
            print(f"   Remaining: £{order.get('remaining_size')}")
            print(f"   Status: {order.get('status')}")
            break
    
    if not bet_found:
        print("⚠️  Bet not found in open orders - it may have been matched or already cancelled")
        return False
    
    # Cancel the bet
    print(f"\n❌ Cancelling bet {bet_id}...")
    
    # Confirm before cancelling
    confirm = input("\n⚠️  CANCEL BET - Type 'YES' to confirm: ")
    if confirm != "YES":
        print("❌ Cancellation aborted")
        return False
    
    success = betfair.cancel_bet(bet_id)
    
    if success:
        print("\n✅ BET CANCELLED SUCCESSFULLY!")
        print(f"   Bet ID: {bet_id}")
        
        # Verify cancellation
        open_orders_after = betfair.get_open_orders()
        still_found = any(order.get("bet_id") == bet_id for order in open_orders_after)
        
        if not still_found:
            print("   Verified: Bet no longer in open orders")
        else:
            print("   Warning: Bet may still be processing cancellation")
            
        return True
    else:
        print(f"\n❌ FAILED TO CANCEL BET!")
        print("   The bet may have already been matched or cancelled")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(cancel_bet())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)