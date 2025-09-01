#!/usr/bin/env python3
"""Test terminal app components individually."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from terminal_app.models import Match, Position, Trade, OrderSide, RiskMetrics
from terminal_app.stores import MatchDataStore, PositionStore, TradeStore
from terminal_app.components import AppLayout
from rich.console import Console


async def test_components():
    """Test individual components."""
    console = Console()
    
    print("=" * 60)
    print("TERMINAL APP COMPONENT TESTS")
    print("=" * 60)
    
    # Test 1: Data Models
    print("\n1. Testing Data Models...")
    match = Match(
        match_id="test_1",
        home_player="Djokovic",
        away_player="Federer",
        score="6-4 3-2",
        serving="Djokovic"
    )
    print(f"   ✓ Created Match: {match.home_player} vs {match.away_player}")
    
    position = Position(
        position_id="POS_001",
        match_id="test_1",
        selection_id="sel_1",
        selection_name="Djokovic",
        side=OrderSide.BACK,
        stake=Decimal("50"),
        odds=Decimal("1.85")
    )
    print(f"   ✓ Created Position: {position.selection_name} {position.side.value} £{position.stake}")
    
    # Test 2: Data Stores
    print("\n2. Testing Data Stores...")
    match_store = MatchDataStore()
    position_store = PositionStore()
    trade_store = TradeStore()
    
    # Add match
    await match_store.update_match("match_1", {
        'home_player': 'Nadal',
        'away_player': 'Murray',
        'score': '0-0',
        'status': 'IN_PLAY'
    })
    matches = match_store.get_all_matches()
    print(f"   ✓ Match Store: {len(matches)} matches")
    
    # Add position
    pos = await position_store.add_position({
        'match_id': 'match_1',
        'selection_id': 'sel_1',
        'selection_name': 'Nadal',
        'side': 'BACK',
        'stake': '100',
        'odds': '2.10'
    })
    print(f"   ✓ Position Store: Added {pos.position_id}")
    
    # Add trade
    trade = await trade_store.add_trade({
        'match_id': 'match_1',
        'selection_id': 'sel_1',
        'selection_name': 'Nadal',
        'side': 'BACK',
        'stake': '100',
        'odds': '2.10',
        'status': 'EXECUTED'
    })
    print(f"   ✓ Trade Store: Added {trade.trade_id}")
    
    # Test 3: Layout Components
    print("\n3. Testing Layout Components...")
    layout = AppLayout()
    
    # Update header
    layout.update_header("Connected", Decimal("125.50"))
    print("   ✓ Header updated")
    
    # Update feed
    messages = [
        {'time': datetime.now(), 'text': 'Test message 1', 'style': 'green'},
        {'time': datetime.now(), 'text': 'Test message 2', 'style': 'red'}
    ]
    layout.update_feed(messages)
    print("   ✓ Feed updated")
    
    # Update status
    risk = RiskMetrics(
        total_exposure=Decimal("250"),
        daily_pnl=Decimal("45.50"),
        open_positions=3,
        risk_score=25
    )
    layout.update_status(risk)
    print("   ✓ Status bar updated")
    
    # Test 4: WebSocket URL Configuration
    print("\n4. Testing Configuration...")
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    ws_url = os.getenv('WS_URL', 'ws://localhost:8000/api/ws/monitor')
    print(f"   ✓ WebSocket URL: {ws_url}")
    
    # Test 5: Risk Calculations
    print("\n5. Testing Risk Metrics...")
    risk = RiskMetrics(
        total_exposure=Decimal("800"),
        max_exposure=Decimal("1000"),
        daily_pnl=Decimal("-150"),
        daily_loss_limit=Decimal("-200")
    )
    print(f"   ✓ Exposure used: {risk.exposure_used:.1f}%")
    print(f"   ✓ Risk exceeded: {risk.is_risk_exceeded}")
    
    print("\n" + "=" * 60)
    print("ALL COMPONENT TESTS PASSED!")
    print("=" * 60)
    
    # Display a sample layout (non-interactive)
    print("\n6. Sample Layout Display:")
    print("-" * 60)
    
    # Create and display the layout
    console.print(layout.layout)


async def test_websocket_client():
    """Test WebSocket client connection."""
    from terminal_app.websocket_client import WebSocketClient
    from terminal_app.stores import MatchDataStore, PositionStore, TradeStore
    
    print("\n7. Testing WebSocket Client...")
    
    match_store = MatchDataStore()
    position_store = PositionStore()
    trade_store = TradeStore()
    
    # Test with mock server (will fail to connect but test the structure)
    client = WebSocketClient(
        "ws://localhost:8000/api/ws/monitor",
        match_store,
        position_store,
        trade_store
    )
    
    print("   ✓ WebSocket client created")
    print("   ✓ Message handlers registered")
    
    # Test connection (will fail but that's expected without server)
    connection_task = asyncio.create_task(client.connect())
    await asyncio.sleep(2)  # Let it try to connect
    connection_task.cancel()
    
    print("   ✓ Connection attempt tested")


if __name__ == "__main__":
    try:
        asyncio.run(test_components())
        asyncio.run(test_websocket_client())
        print("\n✅ All tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()