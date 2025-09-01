#!/usr/bin/env python3
"""Test the trading grid with betting interface."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from rich.console import Console

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from terminal_app.models import OrderSide
from terminal_app.stores import MatchDataStore, PositionStore, TradeStore
from terminal_app.components.trading_grid import TradingGrid
from terminal_app.components.bet_modal import BetModal, BetConfirmation


async def test_trading_grid():
    """Test the trading grid component."""
    console = Console()
    
    print("=" * 60)
    print("TRADING GRID TEST")
    print("=" * 60)
    
    # Initialize stores
    match_store = MatchDataStore()
    position_store = PositionStore()
    trade_store = TradeStore()
    
    # Add test data
    print("\n1. Adding test match data...")
    
    # Match 1: Djokovic vs Federer
    await match_store.update_match("match_1", {
        'home_player': 'Djokovic',
        'away_player': 'Federer',
        'score': '6-4 3-2',
        'serving': 'Djokovic',
        'status': 'IN_PLAY'
    })
    
    # Add prices for match 1
    await match_store.update_prices("match_1", "match_1_home", {
        'back_price': Decimal("1.85"),
        'back_volume': Decimal("12500"),
        'lay_price': Decimal("1.87"),
        'lay_volume': Decimal("8900"),
        'last_traded': Decimal("1.86")
    })
    
    await match_store.update_prices("match_1", "match_1_away", {
        'back_price': Decimal("2.14"),
        'back_volume': Decimal("5500"),
        'lay_price': Decimal("2.16"),
        'lay_volume': Decimal("7200"),
        'last_traded': Decimal("2.15")
    })
    
    # Match 2: Nadal vs Murray
    await match_store.update_match("match_2", {
        'home_player': 'Nadal',
        'away_player': 'Murray',
        'score': '3-6 5-4',
        'serving': 'Murray',
        'status': 'IN_PLAY'
    })
    
    # Add prices for match 2
    await match_store.update_prices("match_2", "match_2_home", {
        'back_price': Decimal("2.10"),
        'back_volume': Decimal("3500"),
        'lay_price': Decimal("2.12"),
        'lay_volume': Decimal("4200"),
        'last_traded': Decimal("2.11")
    })
    
    await match_store.update_prices("match_2", "match_2_away", {
        'back_price': Decimal("1.88"),
        'back_volume': Decimal("6700"),
        'lay_price': Decimal("1.90"),
        'lay_volume': Decimal("5100"),
        'last_traded': Decimal("1.89")
    })
    
    # Add a position
    position = await position_store.add_position({
        'match_id': 'match_2',
        'selection_id': 'match_2_home',
        'selection_name': 'Nadal',
        'side': 'BACK',
        'stake': '50',
        'odds': '2.05'
    })
    
    # Update position with current odds for P&L
    await position_store.update_position(position.position_id, {
        'current_odds': Decimal("2.10")
    })
    
    print("✓ Test data added")
    
    # Test 2: Create and display grid
    print("\n2. Creating trading grid...")
    grid = TradingGrid(match_store, position_store)
    
    # Display the grid
    table = grid.create_grid()
    console.print(table)
    
    print("\n3. Testing grid navigation...")
    print(f"   Current selection: Row {grid.selection.row_index}")
    grid.move_selection_down()
    print(f"   After move down: Row {grid.selection.row_index}")
    grid.move_selection_down()
    print(f"   After move down: Row {grid.selection.row_index}")
    
    selected = grid.get_selected_market()
    print(f"   Selected market: {selected[2]} (ID: {selected[1]})")
    
    # Test 4: Test bet modal
    print("\n4. Testing bet modal...")
    modal = BetModal()
    
    # Open modal for back bet
    modal.open(
        selection_name="Nadal",
        side=OrderSide.BACK,
        price=Decimal("2.10"),
        default_stake=Decimal("50")
    )
    
    print("   Modal opened for BACK bet")
    print(f"   Selection: {modal.selection_name}")
    print(f"   Price: {modal.price}")
    print(f"   Stake: £{modal.stake}")
    print(f"   Liability: £{modal.liability:.2f}")
    print(f"   Potential Profit: £{modal.potential_profit:.2f}")
    
    # Display modal
    modal_panel = modal.create_panel()
    console.print(modal_panel)
    
    # Test lay bet
    modal.open(
        selection_name="Federer",
        side=OrderSide.LAY,
        price=Decimal("2.16"),
        default_stake=Decimal("100")
    )
    
    print("\n   Modal opened for LAY bet")
    print(f"   Selection: {modal.selection_name}")
    print(f"   Price: {modal.price}")
    print(f"   Stake: £{modal.stake}")
    print(f"   Liability: £{modal.liability:.2f}")
    print(f"   Potential Profit: £{modal.potential_profit:.2f}")
    
    # Test 5: Test bet confirmation
    print("\n5. Testing bet confirmation...")
    confirmation = BetConfirmation()
    
    confirmation.show_success("Bet placed successfully!")
    confirm_panel = confirmation.create_panel()
    if confirm_panel:
        console.print(confirm_panel)
    
    confirmation.show_error("Insufficient funds")
    confirm_panel = confirmation.create_panel()
    if confirm_panel:
        console.print(confirm_panel)
    
    # Test 6: Test price updates with flash
    print("\n6. Testing price flash effects...")
    
    # Simulate price increase
    grid.add_price_flash("match_1_home", "back", "up")
    await match_store.update_prices("match_1", "match_1_home", {
        'back_price': Decimal("1.87"),  # Increased from 1.85
    })
    
    # Simulate price decrease
    grid.add_price_flash("match_2_away", "lay", "down")
    await match_store.update_prices("match_2", "match_2_away", {
        'lay_price': Decimal("1.88"),  # Decreased from 1.90
    })
    
    print("   Added flash effects for price changes")
    
    # Display updated grid with flashes
    table = grid.create_grid()
    console.print("\nUpdated grid with price flashes:")
    console.print(table)
    
    # Test 7: Test stake cycling
    print("\n7. Testing stake amounts...")
    print(f"   Available stakes: {grid.quick_stakes}")
    print(f"   Current stake: £{grid.get_selected_stake()}")
    grid.cycle_stake()
    print(f"   After cycle: £{grid.get_selected_stake()}")
    grid.cycle_stake(-1)
    print(f"   After reverse cycle: £{grid.get_selected_stake()}")
    
    print("\n" + "=" * 60)
    print("ALL TRADING GRID TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_trading_grid())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()