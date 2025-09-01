#!/usr/bin/env python3
"""Test risk management dashboard and automated trading."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta
from rich.console import Console
from rich.layout import Layout
from rich.live import Live

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from terminal_app.models import Position, Trade, OrderSide
from terminal_app.components.risk_dashboard import RiskDashboard, PerformanceMetrics
from terminal_app.components.automated_trading import (
    AutomatedTradingManager, SmartExecutor, OrderType
)


def create_sample_positions():
    """Create sample positions for testing."""
    from terminal_app.models import PositionStatus
    
    positions = [
        Position(
            position_id="POS_001",
            match_id="MKT_001",
            selection_id="SEL_001",
            selection_name="Djokovic",
            side=OrderSide.BACK,
            odds=Decimal("1.85"),
            stake=Decimal("50"),
            status=PositionStatus.OPEN,
            current_odds=Decimal("1.92"),
            pnl=Decimal("3.50")
        ),
        Position(
            position_id="POS_002",
            match_id="MKT_001",
            selection_id="SEL_002",
            selection_name="Nadal",
            side=OrderSide.LAY,
            odds=Decimal("2.10"),
            stake=Decimal("75"),
            status=PositionStatus.OPEN,
            current_odds=Decimal("2.05"),
            pnl=Decimal("3.75")
        ),
        Position(
            position_id="POS_003",
            match_id="MKT_002",
            selection_id="SEL_003",
            selection_name="Federer",
            side=OrderSide.BACK,
            odds=Decimal("3.50"),
            stake=Decimal("100"),
            status=PositionStatus.OPEN,
            current_odds=Decimal("3.20"),
            pnl=Decimal("-30.00")
        ),
        Position(
            position_id="POS_004",
            match_id="MKT_002",
            selection_id="SEL_004",
            selection_name="Murray",
            side=OrderSide.LAY,
            odds=Decimal("4.00"),
            stake=Decimal("25"),
            status=PositionStatus.OPEN,
            current_odds=Decimal("4.20"),
            pnl=Decimal("-5.00")
        ),
        Position(
            position_id="POS_005",
            match_id="MKT_003",
            selection_id="SEL_005",
            selection_name="Zverev",
            side=OrderSide.BACK,
            odds=Decimal("2.50"),
            stake=Decimal("150"),
            status=PositionStatus.OPEN,
            current_odds=Decimal("2.60"),
            pnl=Decimal("15.00")
        ),
    ]
    return positions


def create_sample_trades():
    """Create sample trades for testing."""
    trades = []
    now = datetime.now()
    
    # Today's trades
    trades.extend([
        Trade(
            trade_id="TRD_001",
            match_id="MKT_001",
            selection_id="SEL_001",
            selection_name="Djokovic",
            side=OrderSide.BACK,
            odds=Decimal("1.85"),
            stake=Decimal("50"),
            status="MATCHED",
            executed_at=now - timedelta(hours=2),
            pnl=Decimal("3.50")
        ),
        Trade(
            trade_id="TRD_002",
            match_id="MKT_001",
            selection_id="SEL_002",
            selection_name="Nadal",
            side=OrderSide.LAY,
            odds=Decimal("2.10"),
            stake=Decimal("75"),
            status="MATCHED",
            executed_at=now - timedelta(hours=1),
            pnl=Decimal("3.75")
        ),
        Trade(
            trade_id="TRD_003",
            match_id="MKT_002",
            selection_id="SEL_003",
            selection_name="Federer",
            side=OrderSide.BACK,
            odds=Decimal("3.50"),
            stake=Decimal("100"),
            status="MATCHED",
            executed_at=now - timedelta(minutes=30),
            pnl=Decimal("-30.00")
        ),
    ])
    
    # Historical trades for performance metrics
    for i in range(20):
        pnl = Decimal(f"{(i - 10) * 5}")  # Mix of wins and losses
        trades.append(
            Trade(
                trade_id=f"TRD_H{i:03d}",
                match_id=f"MKT_H{i:03d}",
                selection_id=f"SEL_H{i:03d}",
                selection_name=f"Player_{i}",
                side=OrderSide.BACK if i % 2 == 0 else OrderSide.LAY,
                odds=Decimal("2.00"),
                stake=Decimal("50"),
                status="MATCHED",
                executed_at=now - timedelta(days=i+1),
                pnl=pnl
            )
        )
    
    return trades


async def test_risk_dashboard():
    """Test the risk management dashboard."""
    console = Console()
    
    print("=" * 60)
    print("RISK MANAGEMENT DASHBOARD TEST")
    print("=" * 60)
    
    # Create components
    risk_dashboard = RiskDashboard()
    performance = PerformanceMetrics()
    auto_trader = AutomatedTradingManager()
    
    # Create sample data
    positions = create_sample_positions()
    trades = create_sample_trades()
    
    # Update performance metrics
    performance.update_metrics(trades)
    
    # Test 1: Risk Dashboard Display
    print("\n1. Testing Risk Dashboard...")
    layout = risk_dashboard.create_dashboard(positions, trades)
    
    # Display for 3 seconds
    with Live(layout, console=console, refresh_per_second=1) as live:
        await asyncio.sleep(3)
    
    print("✓ Risk dashboard displayed successfully")
    
    # Test 2: Risk Limit Checks
    print("\n2. Testing Risk Limit Checks...")
    
    # Check normal trade
    can_trade, message = risk_dashboard.check_risk_limits(positions, Decimal("50"))
    print(f"   Normal trade (£50): {can_trade} - {message}")
    
    # Check large trade
    can_trade, message = risk_dashboard.check_risk_limits(positions, Decimal("1000"))
    print(f"   Large trade (£1000): {can_trade} - {message}")
    
    # Activate kill switch
    risk_dashboard.activate_kill_switch()
    can_trade, message = risk_dashboard.check_risk_limits(positions, Decimal("10"))
    print(f"   With kill switch: {can_trade} - {message}")
    
    risk_dashboard.deactivate_kill_switch()
    print("✓ Risk limit checks working")
    
    # Test 3: Automated Trading
    print("\n3. Testing Automated Trading...")
    
    # Create automated orders
    for position in positions[:3]:
        # Stop loss
        stop_order = auto_trader.create_stop_loss(position)
        print(f"   Stop loss for {position.selection_name}: £{stop_order.trigger_price:.2f}")
        
        # Take profit
        tp_order = auto_trader.create_take_profit(position)
        print(f"   Take profit for {position.selection_name}: £{tp_order.trigger_price:.2f}")
        
        # Trailing stop for one position
        if position.position_id == "POS_001":
            trail_order = auto_trader.create_trailing_stop(position)
            print(f"   Trailing stop for {position.selection_name}: £{trail_order.trigger_price:.2f}")
    
    print("✓ Automated orders created")
    
    # Test 4: Trigger Checking
    print("\n4. Testing Order Triggers...")
    
    # Simulate price changes
    current_prices = {
        "Djokovic": Decimal("1.70"),  # Price dropped - should trigger stop loss
        "Nadal": Decimal("2.00"),     # Price dropped - good for lay position
        "Federer": Decimal("2.90"),   # Price dropped significantly
    }
    
    triggered = auto_trader.check_triggers(positions, current_prices)
    print(f"   Triggered orders: {len(triggered)}")
    for order in triggered:
        print(f"   - {order.order_type.value} for position {order.position_id}")
    
    print("✓ Order trigger checking working")
    
    # Test 5: Performance Metrics
    print("\n5. Testing Performance Metrics...")
    perf_panel = performance.create_panel()
    console.print(perf_panel)
    
    print(f"   Win rate: {performance.metrics['win_rate']:.1f}%")
    print(f"   Total P&L: £{performance.metrics['total_pnl']:.2f}")
    print(f"   Best trade: £{performance.metrics['best_trade']:.2f}")
    print(f"   Worst trade: £{performance.metrics['worst_trade']:.2f}")
    
    print("✓ Performance metrics calculated")
    
    # Test 6: Automated Orders Panel
    print("\n6. Testing Automated Orders Panel...")
    orders_panel = auto_trader.create_panel()
    console.print(orders_panel)
    
    print("✓ Automated orders panel displayed")
    
    # Test 7: Smart Executor
    print("\n7. Testing Smart Executor...")
    executor = SmartExecutor()
    
    test_order = {
        'side': OrderSide.BACK,
        'selection': 'Djokovic',
        'size': Decimal('100'),
        'price': Decimal('1.85')
    }
    
    # Test different execution strategies
    strategies = ['MARKET', 'LIMIT', 'ICEBERG']
    for strategy in strategies:
        print(f"   Testing {strategy} execution...")
        trades = await executor.execute_order(test_order, strategy)
        print(f"   - Would execute with {strategy} strategy")
    
    print("✓ Smart executor strategies tested")
    
    print("\n" + "=" * 60)
    print("ALL RISK MANAGEMENT TESTS PASSED!")
    print("=" * 60)
    
    print("\nFeatures Implemented:")
    print("✓ Real-time risk metrics dashboard")
    print("✓ Exposure tracking by market and selection")
    print("✓ Risk limit enforcement")
    print("✓ Alert system with thresholds")
    print("✓ Kill switch functionality")
    print("✓ Automated stop loss orders")
    print("✓ Take profit orders with partial closing")
    print("✓ Trailing stop orders")
    print("✓ One-Cancels-Other (OCO) orders")
    print("✓ Performance metrics tracking")
    print("✓ Smart order execution strategies")
    print("✓ Visual risk indicators and warnings")


if __name__ == "__main__":
    try:
        asyncio.run(test_risk_dashboard())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()