#!/usr/bin/env python3
"""Test the terminal trading app with mock data."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from terminal_app.app import TradingTerminalApp
from terminal_app.models import OrderSide


async def test_with_mock_data():
    """Test the terminal app with mock data."""
    print("Starting Terminal App Test...")
    
    # Create app instance
    app = TradingTerminalApp()
    
    # Add some mock data
    await app.match_store.update_match("match_1", {
        'home_player': 'Djokovic',
        'away_player': 'Federer',
        'score': '6-4 3-2',
        'serving': 'Djokovic',
        'status': 'IN_PLAY'
    })
    
    await app.match_store.update_match("match_2", {
        'home_player': 'Nadal',
        'away_player': 'Murray',
        'score': '3-6 5-4',
        'serving': 'Murray',
        'status': 'IN_PLAY'
    })
    
    # Add mock prices
    await app.match_store.update_prices("match_1", "selection_1", {
        'back_price': Decimal("1.85"),
        'back_volume': Decimal("1250"),
        'lay_price': Decimal("1.87"),
        'lay_volume': Decimal("890"),
        'last_traded': Decimal("1.86")
    })
    
    await app.match_store.update_prices("match_2", "selection_3", {
        'back_price': Decimal("2.10"),
        'back_volume': Decimal("550"),
        'lay_price': Decimal("2.12"),
        'lay_volume': Decimal("720"),
        'last_traded': Decimal("2.11")
    })
    
    # Add mock position
    await app.position_store.add_position({
        'match_id': 'match_2',
        'selection_id': 'selection_3',
        'selection_name': 'Nadal',
        'side': 'BACK',
        'stake': '50',
        'odds': '2.05'
    })
    
    # Update position with current odds
    positions = app.position_store.get_open_positions()
    if positions:
        await app.position_store.update_position(
            positions[0].position_id,
            {'current_odds': Decimal("2.10")}
        )
    
    # Add mock trades
    await app.trade_store.add_trade({
        'match_id': 'match_1',
        'selection_id': 'selection_1',
        'selection_name': 'Djokovic',
        'side': 'LAY',
        'stake': '25',
        'odds': '1.90',
        'status': 'EXECUTED',
        'pnl': '5.50'
    })
    
    await app.trade_store.add_trade({
        'match_id': 'match_2',
        'selection_id': 'selection_3',
        'selection_name': 'Nadal',
        'side': 'BACK',
        'stake': '50',
        'odds': '2.05',
        'status': 'EXECUTED'
    })
    
    # Add feed messages
    app.add_feed_message("✓ Backed Nadal £50 @ 2.05", "green")
    app.add_feed_message("↑ Djokovic 1.85 → 1.87", "yellow")
    app.add_feed_message("◆ Federer breaks! 6-4 3-3", "blue")
    app.add_feed_message("✗ Order rejected: Insufficient funds", "red")
    
    # Update risk metrics
    app.risk_metrics.total_exposure = Decimal("150")
    app.risk_metrics.daily_pnl = Decimal("12.50")
    app.risk_metrics.open_positions = 2
    app.risk_metrics.risk_score = 35
    
    print("Mock data loaded. Starting app...")
    print("\nControls:")
    print("  q     - Quit")
    print("  r     - Refresh")
    print("  b     - Back bet (placeholder)")
    print("  l     - Lay bet (placeholder)")
    print("  ↑/k   - Move up")
    print("  ↓/j   - Move down")
    print("  ?/h   - Help")
    print("\nPress Ctrl+C to exit\n")
    
    # Run the app
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(test_with_mock_data())
    except KeyboardInterrupt:
        print("\n\nTerminal app stopped.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()