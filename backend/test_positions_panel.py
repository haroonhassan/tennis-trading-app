#!/usr/bin/env python3
"""Test the positions management panel."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta
from rich.console import Console
from rich.layout import Layout

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from terminal_app.models import OrderSide
from terminal_app.stores import MatchDataStore, PositionStore
from terminal_app.components.positions_panel import PositionsPanel, SortColumn
from terminal_app.components.position_modals import (
    ClosePositionModal, HedgePositionModal, StopLossModal
)
from terminal_app.components.layout_manager import LayoutManager, ViewMode
from terminal_app.components.trading_grid import TradingGrid
from terminal_app.components.layout import AppLayout


async def test_positions_panel():
    """Test the positions panel and management features."""
    console = Console()
    
    print("=" * 60)
    print("POSITIONS PANEL TEST")
    print("=" * 60)
    
    # Initialize stores
    match_store = MatchDataStore()
    position_store = PositionStore()
    
    # Add test matches
    await match_store.update_match("match_1", {
        'home_player': 'Djokovic',
        'away_player': 'Federer',
        'score': '6-4 3-2',
        'status': 'IN_PLAY'
    })
    
    await match_store.update_match("match_2", {
        'home_player': 'Nadal',
        'away_player': 'Murray',
        'score': '3-6 5-4',
        'status': 'IN_PLAY'
    })
    
    await match_store.update_match("match_3", {
        'home_player': 'Alcaraz',
        'away_player': 'Sinner',
        'score': '2-1',
        'status': 'IN_PLAY'
    })
    
    # Add various positions with different P&L
    print("\n1. Adding test positions...")
    
    # Winning position
    pos1 = await position_store.add_position({
        'match_id': 'match_1',
        'selection_id': 'match_1_home',
        'selection_name': 'Djokovic',
        'side': 'LAY',
        'stake': '100',
        'odds': '1.90'
    })
    await position_store.update_position(pos1.position_id, {
        'current_odds': Decimal("1.85")
    })
    
    # Losing position
    pos2 = await position_store.add_position({
        'match_id': 'match_2',
        'selection_id': 'match_2_home',
        'selection_name': 'Nadal',
        'side': 'BACK',
        'stake': '50',
        'odds': '2.05'
    })
    await position_store.update_position(pos2.position_id, {
        'current_odds': Decimal("2.10")
    })
    
    # Neutral position
    pos3 = await position_store.add_position({
        'match_id': 'match_3',
        'selection_id': 'match_3_away',
        'selection_name': 'Sinner',
        'side': 'BACK',
        'stake': '75',
        'odds': '2.40'
    })
    await position_store.update_position(pos3.position_id, {
        'current_odds': Decimal("2.40")
    })
    
    # Another winning position
    pos4 = await position_store.add_position({
        'match_id': 'match_1',
        'selection_id': 'match_1_away',
        'selection_name': 'Federer',
        'side': 'BACK',
        'stake': '25',
        'odds': '2.10'
    })
    await position_store.update_position(pos4.position_id, {
        'current_odds': Decimal("2.20")
    })
    
    print("✓ Test positions added")
    
    # Test 2: Create and display positions table
    print("\n2. Creating positions panel...")
    panel = PositionsPanel(position_store, match_store)
    
    table = panel.create_positions_table()
    console.print(table)
    
    # Test 3: Test sorting
    print("\n3. Testing sorting...")
    print(f"   Current sort: {panel.sort_column.value} ({'↑' if panel.sort_ascending else '↓'})")
    
    panel.cycle_sort()
    print(f"   After cycle: {panel.sort_column.value}")
    
    panel.toggle_sort_direction()
    print(f"   After toggle direction: {'↑' if panel.sort_ascending else '↓'}")
    
    # Test 4: Display P&L ladder
    print("\n4. Creating P&L ladder...")
    selected = panel.get_selected_position()
    if selected:
        ladder = panel.create_pnl_ladder(selected)
        console.print(ladder)
    
    # Test 5: Display summary panel
    print("\n5. Creating summary panel...")
    summary = panel.create_summary_panel()
    console.print(summary)
    
    # Test 6: Test position management modals
    print("\n6. Testing position management modals...")
    
    # Close position modal
    close_modal = ClosePositionModal()
    close_modal.open(pos2, Decimal("2.10"))
    console.print("\nClose Position Modal:")
    console.print(close_modal.create_panel())
    
    # Hedge position modal
    hedge_modal = HedgePositionModal()
    hedge_modal.open(pos1, Decimal("1.85"))
    console.print("\nHedge Position Modal:")
    console.print(hedge_modal.create_panel())
    
    # Stop loss modal
    stop_modal = StopLossModal()
    stop_modal.open(pos2)
    console.print("\nStop Loss Modal:")
    console.print(stop_modal.create_panel())
    
    # Test 7: Test layout manager with different views
    print("\n7. Testing layout manager...")
    
    app_layout = AppLayout()
    trading_grid = TradingGrid(match_store, position_store)
    layout_manager = LayoutManager(app_layout, trading_grid, panel)
    
    # Test different view modes
    modes = [ViewMode.TRADING, ViewMode.POSITIONS, ViewMode.SPLIT, ViewMode.RISK]
    
    for mode in modes:
        print(f"\n   Testing {mode.value} view...")
        layout_manager.switch_mode(mode)
        layout = layout_manager.create_layout()
        # Just verify it creates without error
        print(f"   ✓ {mode.value} layout created")
        print(f"   Mode indicator: {layout_manager.get_mode_indicator()}")
    
    # Show split view
    print("\n8. Displaying split view...")
    layout_manager.switch_mode(ViewMode.SPLIT)
    split_layout = layout_manager.create_layout()
    console.print(split_layout)
    
    print("\n" + "=" * 60)
    print("ALL POSITION PANEL TESTS PASSED!")
    print("=" * 60)
    
    # Summary of features
    print("\nPosition Panel Features:")
    print("• Sortable columns (match, stake, odds, P&L, time)")
    print("• P&L ladder showing profit at different prices")
    print("• Position summary with totals and best/worst")
    print("• Close position modal with P&L calculation")
    print("• Hedge/green-up modal with guaranteed profit")
    print("• Stop loss modal with max loss display")
    print("• Multiple view modes (F1-F4)")
    print("• Split screen support")


if __name__ == "__main__":
    try:
        asyncio.run(test_positions_panel())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()