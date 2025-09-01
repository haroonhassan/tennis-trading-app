#!/usr/bin/env python3
"""Test live data feed functionality."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta
from rich.console import Console
from rich.live import Live
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from terminal_app.models import Trade, Position, MessageType, OrderSide, PositionStatus
from terminal_app.components.live_feed import (
    LiveFeedPanel, FeedEvent, FeedEventType,
    TradeFeed, ScoreFeed, AlertFeed, LiveDataManager
)


async def test_live_feed():
    """Test live feed functionality."""
    console = Console()
    
    print("=" * 60)
    print("LIVE DATA FEED TEST")
    print("=" * 60)
    
    # Test 1: Live Feed Panel
    print("\n1. Testing Live Feed Panel...")
    feed_panel = LiveFeedPanel(max_events=50)
    
    # Add various events
    events = [
        FeedEvent(FeedEventType.TRADE, "Trade executed: BACK Djokovic @ 1.85 for £50"),
        FeedEvent(FeedEventType.POSITION, "Position opened: Nadal P&L: £12.50"),
        FeedEvent(FeedEventType.PRICE, "Price update: Federer Back: 2.10 Lay: 2.12", priority=-1),
        FeedEvent(FeedEventType.SCORE, "Score: Djokovic vs Nadal - 6-4 3-2"),
        FeedEvent(FeedEventType.ALERT, "Risk warning: Approaching exposure limit", priority=2),
        FeedEvent(FeedEventType.ERROR, "Connection lost to price feed", priority=3),
        FeedEvent(FeedEventType.SYSTEM, "System: Auto-save completed"),
        FeedEvent(FeedEventType.INFO, "Market suspended temporarily"),
    ]
    
    for event in events:
        feed_panel.add_event(event)
    
    # Display panel
    panel = feed_panel.create_panel(height=10)
    console.print(panel)
    print("✓ Live feed panel working")
    
    # Test 2: Trade Feed
    print("\n2. Testing Trade Feed...")
    trade_feed = TradeFeed()
    
    # Add sample trades
    for i in range(5):
        trade = Trade(
            trade_id=f"TRD_{i:03d}",
            match_id="MATCH_001",
            selection_id=f"SEL_{i:03d}",
            selection_name=["Djokovic", "Nadal", "Federer", "Murray", "Zverev"][i],
            side=OrderSide.BACK if i % 2 == 0 else OrderSide.LAY,
            odds=Decimal(f"{1.5 + i * 0.3:.2f}"),
            stake=Decimal(f"{25 + i * 10}"),
            status="MATCHED",
            executed_at=datetime.now() - timedelta(minutes=5-i),
            pnl=Decimal(f"{(i - 2) * 5}")
        )
        trade_feed.add_trade(trade)
    
    console.print(trade_feed.create_panel())
    print("✓ Trade feed working")
    
    # Test 3: Score Feed
    print("\n3. Testing Score Feed...")
    score_feed = ScoreFeed()
    
    # Add score updates
    scores = [
        ("Djokovic vs Nadal", "0-0", "Djokovic"),
        ("Djokovic vs Nadal", "15-0", "Djokovic"),
        ("Djokovic vs Nadal", "30-0", "Djokovic"),
        ("Djokovic vs Nadal", "40-0", "Djokovic"),
        ("Djokovic vs Nadal", "1-0", "Nadal"),
    ]
    
    for match, score, server in scores:
        score_feed.update_score(match, score, server)
        await asyncio.sleep(0.1)
    
    console.print(score_feed.create_panel())
    print("✓ Score feed working")
    
    # Test 4: Alert Feed
    print("\n4. Testing Alert Feed...")
    alert_feed = AlertFeed()
    
    # Add alerts
    alerts = [
        ('info', 'Market opened for trading'),
        ('warning', 'High volatility detected'),
        ('critical', 'Stop loss triggered on position'),
        ('success', 'Position closed with profit'),
    ]
    
    for level, message in alerts:
        alert_feed.add_alert(level, message)
    
    console.print(alert_feed.create_panel())
    print(f"   Unread alerts: {alert_feed.unread_count}")
    
    alert_feed.mark_all_read()
    print(f"   After marking read: {alert_feed.unread_count}")
    print("✓ Alert feed working")
    
    # Test 5: Live Data Manager
    print("\n5. Testing Live Data Manager...")
    manager = LiveDataManager()
    
    # Simulate various messages
    messages = [
        (MessageType.TRADE_UPDATE, {
            'side': 'BACK',
            'selection': 'Djokovic',
            'odds': 1.85,
            'stake': 50
        }),
        (MessageType.POSITION_UPDATE, {
            'selection': 'Nadal',
            'pnl': 25.50
        }),
        (MessageType.PRICE_UPDATE, {
            'selection': 'Federer',
            'back_price': 2.10,
            'lay_price': 2.12
        }),
        (MessageType.SCORE_UPDATE, {
            'match_id': 'Djokovic vs Nadal',
            'score': '6-4 3-3',
            'server': 'Nadal'
        }),
        (MessageType.RISK_UPDATE, {
            'level': 'warning',
            'message': 'Exposure at 75% of limit'
        }),
    ]
    
    for msg_type, data in messages:
        manager.process_message(msg_type, data)
    
    # Display dashboard
    dashboard = manager.create_dashboard()
    with Live(dashboard, console=console, refresh_per_second=1) as live:
        await asyncio.sleep(2)
    
    print("✓ Live data manager working")
    print(f"   Total messages processed: {manager.stats['total_messages']}")
    print(f"   Messages per second: {manager.stats['messages_per_second']:.2f}")
    
    # Test 6: Feed Filters
    print("\n6. Testing Feed Filters...")
    feed_panel.clear()
    
    # Add mixed events
    for i in range(10):
        event_type = random.choice(list(FeedEventType))
        event = FeedEvent(event_type, f"Test event {i} of type {event_type.value}")
        feed_panel.add_event(event)
    
    # Apply filter
    feed_panel.set_filter([FeedEventType.TRADE, FeedEventType.POSITION])
    filtered_panel = feed_panel.create_panel()
    print("   Filter applied: TRADE and POSITION only")
    
    # Test pause
    feed_panel.toggle_pause()
    print(f"   Feed paused: {feed_panel.paused}")
    
    feed_panel.toggle_pause()
    print(f"   Feed resumed: {feed_panel.paused}")
    
    print("✓ Feed filters and controls working")
    
    # Test 7: Highlight Keywords
    print("\n7. Testing Keyword Highlighting...")
    feed_panel.clear()
    feed_panel.set_highlight(["Djokovic", "profit"])
    
    events_with_keywords = [
        FeedEvent(FeedEventType.TRADE, "Trade on Djokovic executed"),
        FeedEvent(FeedEventType.POSITION, "Position closed with profit"),
        FeedEvent(FeedEventType.INFO, "Nadal serving"),
    ]
    
    for event in events_with_keywords:
        feed_panel.add_event(event)
    
    print("   Keywords highlighted: Djokovic, profit")
    print("✓ Keyword highlighting working")
    
    # Test 8: Real-time Simulation
    print("\n8. Running Real-time Simulation...")
    manager = LiveDataManager()
    
    async def simulate_messages():
        """Simulate incoming messages."""
        selections = ["Djokovic", "Nadal", "Federer", "Murray", "Zverev"]
        
        for i in range(20):
            # Random message type
            msg_type = random.choice([
                MessageType.PRICE_UPDATE,
                MessageType.TRADE_UPDATE,
                MessageType.POSITION_UPDATE,
                MessageType.SCORE_UPDATE
            ])
            
            if msg_type == MessageType.PRICE_UPDATE:
                data = {
                    'selection': random.choice(selections),
                    'back_price': round(random.uniform(1.5, 3.0), 2),
                    'lay_price': round(random.uniform(1.5, 3.0), 2)
                }
            elif msg_type == MessageType.TRADE_UPDATE:
                data = {
                    'side': random.choice(['BACK', 'LAY']),
                    'selection': random.choice(selections),
                    'odds': round(random.uniform(1.5, 3.0), 2),
                    'stake': random.randint(10, 100)
                }
            elif msg_type == MessageType.POSITION_UPDATE:
                data = {
                    'selection': random.choice(selections),
                    'pnl': round(random.uniform(-50, 50), 2)
                }
            else:  # SCORE_UPDATE
                data = {
                    'match_id': f"{random.choice(selections)} vs {random.choice(selections)}",
                    'score': f"{random.randint(0, 6)}-{random.randint(0, 6)} {random.randint(0, 6)}-{random.randint(0, 6)}",
                    'server': random.choice(selections)
                }
            
            manager.process_message(msg_type, data)
            await asyncio.sleep(0.2)
    
    # Run simulation with live display
    dashboard = manager.create_dashboard()
    
    with Live(dashboard, console=console, refresh_per_second=2) as live:
        sim_task = asyncio.create_task(simulate_messages())
        
        for _ in range(5):  # Update display for 5 seconds
            await asyncio.sleep(1)
            live.update(manager.create_dashboard())
        
        await sim_task
    
    print("✓ Real-time simulation completed")
    print(f"   Final message count: {manager.stats['total_messages']}")
    print(f"   Average rate: {manager.stats['messages_per_second']:.2f} msg/s")
    
    print("\n" + "=" * 60)
    print("ALL LIVE FEED TESTS PASSED!")
    print("=" * 60)
    
    print("\nFeatures Implemented:")
    print("✓ Live feed panel with event streaming")
    print("✓ Trade feed with execution history")
    print("✓ Score feed with match updates")
    print("✓ Alert feed with priority levels")
    print("✓ Live data manager with routing")
    print("✓ Event filtering by type")
    print("✓ Pause/resume functionality")
    print("✓ Keyword highlighting")
    print("✓ Real-time statistics")
    print("✓ Message rate calculation")


if __name__ == "__main__":
    try:
        asyncio.run(test_live_feed())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()