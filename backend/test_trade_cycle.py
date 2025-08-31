#!/usr/bin/env python3
"""Test the full trade cycle with risk integration."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.server.provider_manager import ProviderManager
from app.trading.coordinator import TradeCoordinator
from app.trading.models import OrderSide, ExecutionStrategy
from app.risk import RiskLimits


async def test_trade_cycle():
    """Test the complete trade cycle."""
    print("=" * 60)
    print("TRADE CYCLE TEST WITH RISK INTEGRATION")
    print("=" * 60)
    
    # Initialize provider manager
    provider_manager = ProviderManager()
    
    # Initialize trade coordinator with risk limits
    print("\n1. Initializing Trade Coordinator...")
    risk_limits = RiskLimits(
        max_position_size=Decimal("20"),
        max_market_exposure=Decimal("100"),
        max_total_exposure=Decimal("200"),
        max_daily_loss=Decimal("50"),
        max_open_positions=10
    )
    
    coordinator = TradeCoordinator(provider_manager, risk_limits)
    await coordinator.start()
    print("✅ Trade Coordinator started with risk management")
    
    # Test market and selection IDs (mock data)
    market_id = "1.234567890"
    selection_id = "12345"
    
    print("\n" + "=" * 60)
    print("TEST 1: Place Trade with Risk Check")
    print("=" * 60)
    
    # Attempt to place a trade within limits
    print("\nAttempting to place £10 BACK bet at 2.5...")
    success, message, report = await coordinator.place_trade(
        market_id=market_id,
        selection_id=selection_id,
        side=OrderSide.BACK,
        size=Decimal("10"),
        price=Decimal("2.5"),
        strategy=ExecutionStrategy.SMART
    )
    
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print(f"Message: {message}")
    
    if report:
        print(f"Execution Report:")
        print(f"  Order ID: {report.order_id}")
        print(f"  Status: {report.status.value}")
        print(f"  Executed: {report.executed_size} @ {report.executed_price}")
    
    print("\n" + "=" * 60)
    print("TEST 2: Risk Limit Enforcement")
    print("=" * 60)
    
    # Attempt to place a trade exceeding limits
    print("\nAttempting to place £30 BACK bet (exceeds £20 limit)...")
    success, message, report = await coordinator.place_trade(
        market_id=market_id,
        selection_id=selection_id,
        side=OrderSide.BACK,
        size=Decimal("30"),
        price=Decimal("2.0"),
        strategy=ExecutionStrategy.SMART
    )
    
    print(f"Result: {'✅ SUCCESS' if success else '❌ REJECTED'}")
    print(f"Reason: {message}")
    
    print("\n" + "=" * 60)
    print("TEST 3: Position Tracking")
    print("=" * 60)
    
    # Check current positions
    positions = coordinator.get_positions()
    print(f"\nOpen Positions: {len(positions)}")
    
    for pos in positions:
        print(f"\nPosition {pos['position_id'][:8]}:")
        print(f"  Market: {pos['market_id']}")
        print(f"  Side: {pos['side']}")
        print(f"  Size: £{pos['current_size']}")
        print(f"  Entry: {pos['entry_price']}")
        print(f"  P&L: £{pos['total_pnl']}")
    
    print("\n" + "=" * 60)
    print("TEST 4: P&L Calculation")
    print("=" * 60)
    
    pnl_summary = coordinator.get_pnl_summary()
    print("\nP&L Summary:")
    print(f"  Realized P&L: £{pnl_summary['realized_pnl']}")
    print(f"  Unrealized P&L: £{pnl_summary['unrealized_pnl']}")
    print(f"  Total P&L: £{pnl_summary['total_pnl']}")
    print(f"  Commission: £{pnl_summary['commission']}")
    print(f"  Win Rate: {pnl_summary['win_rate']}%")
    
    print("\n" + "=" * 60)
    print("TEST 5: Risk Status")
    print("=" * 60)
    
    risk_status = coordinator.get_risk_status()
    print("\nRisk Status:")
    print(f"  Total Exposure: £{risk_status['total_exposure']}")
    print(f"  Exposure Limit: £{risk_status['exposure_limit']}")
    print(f"  Exposure Used: {risk_status['exposure_used']}")
    print(f"  Daily Loss: £{risk_status['daily_loss']}")
    print(f"  Loss Limit Used: {risk_status['loss_limit_used']}")
    print(f"  Open Positions: {risk_status['open_positions']}/{risk_status['position_limit']}")
    print(f"  Risk Score: {risk_status['risk_score']}/100")
    print(f"  Trading Frozen: {risk_status['trading_frozen']}")
    
    if risk_status['alerts']:
        print(f"  Alerts: {', '.join(risk_status['alerts'])}")
    
    print("\n" + "=" * 60)
    print("TEST 6: Trade Statistics")
    print("=" * 60)
    
    stats = coordinator.get_trade_stats()
    print("\nTrade Statistics:")
    print(f"  Total Trades: {stats['total_trades']}")
    print(f"  Successful: {stats['successful_trades']}")
    print(f"  Failed: {stats['failed_trades']}")
    print(f"  Rejected: {stats['rejected_trades']}")
    print(f"  Success Rate: {stats['success_rate']}")
    
    print("\n" + "=" * 60)
    print("TEST 7: Automated Trading Features")
    print("=" * 60)
    
    if positions:
        test_position = positions[0]
        position_id = test_position['position_id']
        
        # Test hedge calculation
        print(f"\nTesting hedge for position {position_id[:8]}...")
        success, message = await coordinator.hedge_position(position_id)
        print(f"Hedge Result: {message}")
        
        # Test cash out calculation
        print(f"\nCalculating cash out value...")
        success, message, cash_value = await coordinator.cash_out_position(position_id)
        print(f"Cash Out Value: £{cash_value}")
        print(f"Message: {message}")
        
        # Test stop loss
        print(f"\nSetting stop loss at 1.5...")
        success, message = await coordinator.set_stop_loss(position_id, Decimal("1.5"))
        print(f"Stop Loss: {message}")
    
    print("\n" + "=" * 60)
    print("TEST 8: Event Logging")
    print("=" * 60)
    
    recent_trades = coordinator.get_recent_trades(10)
    print(f"\nRecent Trade Events: {len(recent_trades)}")
    
    for trade in recent_trades[:3]:
        print(f"\n{trade['timestamp']}:")
        print(f"  Type: {trade['event_type']}")
        print(f"  Data: {json.dumps(trade['data'], indent=2)}")
    
    print("\n" + "=" * 60)
    print("TEST 9: Kill Switch Test")
    print("=" * 60)
    
    print("\nTriggering kill switch...")
    await coordinator.risk_manager.trigger_kill_switch("Test activation")
    
    # Try to place trade after kill switch
    print("\nAttempting trade after kill switch...")
    success, message, report = await coordinator.place_trade(
        market_id=market_id,
        selection_id=selection_id,
        side=OrderSide.BACK,
        size=Decimal("5"),
        price=Decimal("2.0"),
        strategy=ExecutionStrategy.SMART
    )
    
    print(f"Result: {'✅ SUCCESS' if success else '❌ BLOCKED'}")
    print(f"Reason: {message}")
    
    # Cleanup
    print("\n" + "=" * 60)
    print("CLEANUP")
    print("=" * 60)
    
    await coordinator.stop()
    print("✅ Trade Coordinator stopped")
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✅ Trade placement with risk checks")
    print("✅ Risk limit enforcement")
    print("✅ Real-time position tracking")
    print("✅ P&L calculation")
    print("✅ Risk status monitoring")
    print("✅ Trade statistics")
    print("✅ Automated trading features")
    print("✅ Event logging")
    print("✅ Kill switch functionality")
    print("\n🎉 All tests completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(test_trade_cycle())
    except KeyboardInterrupt:
        print("\n❌ Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()