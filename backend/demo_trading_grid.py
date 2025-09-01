#!/usr/bin/env python3
"""Demo the trading grid with sample data."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from rich.console import Console
from rich.live import Live

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from terminal_app.models import OrderSide
from terminal_app.stores import MatchDataStore, PositionStore, TradeStore
from terminal_app.components.trading_grid import TradingGrid
from terminal_app.components.bet_modal import BetModal


async def demo_grid():
    """Demo the trading grid with sample data."""
    console = Console()
    
    # Initialize stores
    match_store = MatchDataStore()
    position_store = PositionStore()
    
    # Add sample matches
    await match_store.update_match("match_1", {
        'home_player': 'Djokovic',
        'away_player': 'Federer',
        'score': '6-4 3-2',
        'serving': 'Djokovic',
        'status': 'IN_PLAY'
    })
    
    await match_store.update_match("match_2", {
        'home_player': 'Nadal',
        'away_player': 'Murray',
        'score': '3-6 5-4',
        'serving': 'Murray',
        'status': 'IN_PLAY'
    })
    
    await match_store.update_match("match_3", {
        'home_player': 'Alcaraz',
        'away_player': 'Sinner',
        'score': '2-1',
        'serving': 'Alcaraz',
        'status': 'IN_PLAY'
    })
    
    # Add prices with varying volumes
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
    
    await match_store.update_prices("match_3", "match_3_home", {
        'back_price': Decimal("1.72"),
        'back_volume': Decimal("15000"),
        'lay_price': Decimal("1.73"),
        'lay_volume': Decimal("12000"),
        'last_traded': Decimal("1.72")
    })
    
    await match_store.update_prices("match_3", "match_3_away", {
        'back_price': Decimal("2.34"),
        'back_volume': Decimal("8200"),
        'lay_price': Decimal("2.36"),
        'lay_volume': Decimal("9100"),
        'last_traded': Decimal("2.35")
    })
    
    # Add some positions with P&L
    pos1 = await position_store.add_position({
        'match_id': 'match_2',
        'selection_id': 'match_2_home',
        'selection_name': 'Nadal',
        'side': 'BACK',
        'stake': '50',
        'odds': '2.05'
    })
    await position_store.update_position(pos1.position_id, {
        'current_odds': Decimal("2.10")
    })
    
    pos2 = await position_store.add_position({
        'match_id': 'match_1',
        'selection_id': 'match_1_home',
        'selection_name': 'Djokovic',
        'side': 'LAY',
        'stake': '100',
        'odds': '1.90'
    })
    await position_store.update_position(pos2.position_id, {
        'current_odds': Decimal("1.85")
    })
    
    pos3 = await position_store.add_position({
        'match_id': 'match_3',
        'selection_id': 'match_3_away',
        'selection_name': 'Sinner',
        'side': 'BACK',
        'stake': '75',
        'odds': '2.40'
    })
    await position_store.update_position(pos3.position_id, {
        'current_odds': Decimal("2.34")
    })
    
    # Create grid
    grid = TradingGrid(match_store, position_store)
    
    # Set selection to row 2 (Nadal)
    grid.selection.row_index = 2
    
    # Add some price flashes for effect
    grid.add_price_flash("match_1_home", "back", "up")
    grid.add_price_flash("match_3_away", "lay", "down")
    
    # Display the grid
    console.clear()
    console.print("\n[bold cyan]🎾 TENNIS TRADING TERMINAL - LIVE MARKETS[/bold cyan]\n")
    
    table = grid.create_grid()
    console.print(table)
    
    # Show current selection info
    match_id, selection_id, selection_name = grid.get_selected_market()
    console.print(f"\n[cyan]Selected:[/cyan] {selection_name} | [yellow]Stake: £{grid.get_selected_stake()}[/yellow]")
    
    # Show keyboard shortcuts
    console.print("\n[dim]Keys: ↑↓=navigate, b=back, l=lay, 1-5=stake, q=quit[/dim]")
    
    # Show a sample bet modal
    console.print("\n[bold]Sample Bet Modal:[/bold]")
    modal = BetModal()
    modal.open(
        selection_name="Nadal",
        side=OrderSide.BACK,
        price=Decimal("2.10"),
        default_stake=Decimal("50")
    )
    console.print(modal.create_panel())
    
    # Show position summary
    console.print("\n[bold]Open Positions:[/bold]")
    positions = position_store.get_open_positions()
    total_pnl = Decimal("0")
    for pos in positions:
        pnl_color = "green" if pos.pnl > 0 else "red" if pos.pnl < 0 else "white"
        console.print(f"  • {pos.selection_name}: [{pnl_color}]£{pos.pnl:.2f}[/{pnl_color}]")
        total_pnl += pos.pnl
    
    pnl_color = "green" if total_pnl > 0 else "red" if total_pnl < 0 else "white"
    console.print(f"\n[bold]Total P&L: [{pnl_color}]£{total_pnl:.2f}[/{pnl_color}][/bold]")


if __name__ == "__main__":
    try:
        asyncio.run(demo_grid())
        print("\n" + "="*60)
        print("This is a static demo. The full app includes:")
        print("- Real-time WebSocket updates")
        print("- Interactive keyboard navigation")
        print("- Live betting functionality")
        print("- Dynamic price updates with flashing")
        print("="*60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()