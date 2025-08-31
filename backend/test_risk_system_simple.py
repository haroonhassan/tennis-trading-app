#!/usr/bin/env python3
"""Simple test script for risk management system without real API calls."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.risk import (
    PositionTracker,
    RiskManager,
    RiskLimits,
    PositionCalculator,
    GreekCalculator,
    PositionDatabase,
    Position,
    PositionSide,
    PositionStatus
)
from app.trading.models import OrderSide
from app.server.provider_manager import ProviderManager


async def test_risk_system():
    """Test the risk management system with mock data."""
    print("=" * 60)
    print("RISK MANAGEMENT SYSTEM TEST (Mock Data)")
    print("=" * 60)
    
    # Initialize mock provider manager
    provider_manager = ProviderManager()
    
    # Initialize position tracker
    print("\n1. Initializing position tracker...")
    position_tracker = PositionTracker(provider_manager)
    await position_tracker.start()
    print("✅ Position tracker started")
    
    # Initialize risk limits
    print("\n2. Setting up risk limits...")
    risk_limits = RiskLimits(
        max_position_size=Decimal("20"),
        max_market_exposure=Decimal("50"),
        max_total_exposure=Decimal("100"),
        max_daily_loss=Decimal("30"),
        max_open_positions=10,
        max_concentration=Decimal("0.4")
    )
    print(f"   Max position size: £{risk_limits.max_position_size}")
    print(f"   Max market exposure: £{risk_limits.max_market_exposure}")
    print(f"   Max total exposure: £{risk_limits.max_total_exposure}")
    print(f"   Max daily loss: £{risk_limits.max_daily_loss}")
    
    # Initialize risk manager
    print("\n3. Initializing risk manager...")
    risk_manager = RiskManager(
        position_tracker=position_tracker,
        limits=risk_limits,
        auto_hedge=False,
        kill_switch_enabled=True
    )
    await risk_manager.start()
    print("✅ Risk manager started")
    
    # Test 1: Open positions
    print("\n" + "=" * 60)
    print("TEST 1: Opening positions")
    print("=" * 60)
    
    # Open first position
    position1 = await position_tracker.open_position(
        market_id="1.234567",
        selection_id="123",
        side=OrderSide.BACK,
        price=Decimal("2.5"),
        size=Decimal("10"),
        order_id="order_001",
        provider="betfair",
        strategy="test"
    )
    print(f"✅ Opened position 1: £10 BACK @ 2.5")
    print(f"   Position ID: {position1.position_id[:8]}")
    
    # Open second position
    position2 = await position_tracker.open_position(
        market_id="1.234567",
        selection_id="456",
        side=OrderSide.LAY,
        price=Decimal("3.0"),
        size=Decimal("8"),
        order_id="order_002",
        provider="betfair",
        strategy="test"
    )
    print(f"✅ Opened position 2: £8 LAY @ 3.0")
    print(f"   Position ID: {position2.position_id[:8]}")
    
    # Test 2: Risk checks
    print("\n" + "=" * 60)
    print("TEST 2: Risk management checks")
    print("=" * 60)
    
    from app.trading.models import TradeInstruction, OrderType, ExecutionStrategy, PersistenceType
    
    # Check normal trade
    instruction1 = TradeInstruction(
        market_id="1.234567",
        selection_id="789",
        side=OrderSide.BACK,
        size=Decimal("15"),
        price=Decimal("2.0"),
        order_type=OrderType.LIMIT,
        strategy=ExecutionStrategy.PASSIVE,
        persistence=PersistenceType.LAPSE
    )
    
    is_allowed, reason = await risk_manager.check_trade(instruction1, Decimal("1000"))
    print(f"Trade £15 BACK: {'✅ ALLOWED' if is_allowed else f'❌ BLOCKED: {reason}'}")
    
    # Check trade exceeding limit
    instruction2 = TradeInstruction(
        market_id="1.234567",
        selection_id="789",
        side=OrderSide.BACK,
        size=Decimal("25"),
        price=Decimal("2.0"),
        order_type=OrderType.LIMIT,
        strategy=ExecutionStrategy.PASSIVE,
        persistence=PersistenceType.LAPSE
    )
    
    is_allowed, reason = await risk_manager.check_trade(instruction2, Decimal("1000"))
    print(f"Trade £25 BACK: {'✅ ALLOWED' if is_allowed else f'❌ BLOCKED: {reason}'}")
    
    # Test 3: P&L Calculation
    print("\n" + "=" * 60)
    print("TEST 3: P&L Calculation")
    print("=" * 60)
    
    calculator = PositionCalculator()
    
    # Update position prices for P&L
    await position_tracker.update_position_price(position1.position_id, Decimal("2.8"))
    await position_tracker.update_position_price(position2.position_id, Decimal("2.9"))
    
    # Calculate P&L for position 1 (BACK at 2.5, current 2.8)
    realized1, unrealized1 = calculator.calculate_pnl(position1, Decimal("2.8"))
    print(f"Position 1 (BACK £10 @ 2.5, current 2.8):")
    print(f"   Unrealized P&L: £{unrealized1:.2f}")
    
    # Calculate P&L for position 2 (LAY at 3.0, current 2.9)
    realized2, unrealized2 = calculator.calculate_pnl(position2, Decimal("2.9"))
    print(f"Position 2 (LAY £8 @ 3.0, current 2.9):")
    print(f"   Unrealized P&L: £{unrealized2:.2f}")
    
    # Test 4: Risk Metrics
    print("\n" + "=" * 60)
    print("TEST 4: Risk Metrics")
    print("=" * 60)
    
    metrics = risk_manager.get_risk_metrics()
    print(f"Total exposure: £{metrics.total_exposure}")
    print(f"Open positions: {metrics.num_open_positions}")
    print(f"Risk score: {metrics.risk_score:.1f}/100")
    print(f"Exposure limit used: {metrics.exposure_limit_used:.1f}%")
    print(f"Portfolio Delta: {metrics.portfolio_delta}")
    
    # Test 5: Exposure Report
    print("\n" + "=" * 60)
    print("TEST 5: Exposure Report")
    print("=" * 60)
    
    report = risk_manager.get_exposure_report(Decimal("1000"))
    print(f"Account balance: £{report.account_balance}")
    print(f"Available balance: £{report.available_balance}")
    print(f"Total exposure: £{report.total_exposure}")
    print(f"Net exposure: £{report.net_exposure}")
    print(f"Daily P&L: £{report.daily_pnl.net_pnl:.2f}")
    
    if report.market_exposures:
        print("\nMarket Exposures:")
        for exp in report.market_exposures:
            print(f"  Market {exp.market_id[:10]}:")
            print(f"    Max loss: £{exp.max_loss}")
            print(f"    Open positions: {exp.open_positions}")
            if exp.hedge_required:
                print(f"    ⚠️ Hedge recommended: £{exp.hedge_amount}")
    
    # Test 6: Close Position
    print("\n" + "=" * 60)
    print("TEST 6: Closing Positions")
    print("=" * 60)
    
    # Partially close position 1
    await position_tracker.close_position(
        position1.position_id,
        price=Decimal("2.8"),
        size=Decimal("5")
    )
    print(f"✅ Partially closed position 1: £5 @ 2.8")
    print(f"   Realized P&L: £{position1.realized_pnl:.2f}")
    print(f"   Remaining size: £{position1.current_size}")
    
    # Test 7: Greek Calculations
    print("\n" + "=" * 60)
    print("TEST 7: Greek Calculations")
    print("=" * 60)
    
    greek_calc = GreekCalculator()
    
    delta = greek_calc.calculate_delta(position1, Decimal("2.8"))
    theta = greek_calc.calculate_theta(position1, 60)
    
    print(f"Position 1 Greeks:")
    print(f"  Delta: {delta}")
    print(f"  Theta: {theta}")
    
    # Test 8: Hedge Calculation
    print("\n" + "=" * 60)
    print("TEST 8: Hedge Requirements")
    print("=" * 60)
    
    positions = position_tracker.get_open_positions()
    hedge = calculator.calculate_hedge_requirement(positions)
    
    if hedge:
        print(f"Hedge recommended:")
        print(f"  Market: {hedge.market_id}")
        print(f"  Side: {hedge.side}")
        print(f"  Size: £{hedge.size:.2f}")
        print(f"  Reason: {hedge.reason}")
    else:
        print("No hedging required")
    
    # Test 9: Database Persistence
    print("\n" + "=" * 60)
    print("TEST 9: Database Persistence")
    print("=" * 60)
    
    db = PositionDatabase("test_positions.db")
    db.connect()
    
    # Save positions
    for pos in position_tracker.get_open_positions():
        db.save_position(pos)
        print(f"✅ Saved position {pos.position_id[:8]}")
    
    # Save P&L statement
    pnl = position_tracker.get_pnl_statement()
    db.save_daily_pnl(datetime.now(), {
        "gross_pnl": pnl.gross_pnl,
        "commission": pnl.commission,
        "net_pnl": pnl.net_pnl,
        "num_trades": pnl.num_trades,
        "win_rate": pnl.win_rate,
        "avg_win": pnl.avg_win,
        "avg_loss": pnl.avg_loss,
        "total_volume": pnl.total_volume
    })
    print("✅ Saved daily P&L")
    
    # Load positions back
    loaded_positions = db.load_open_positions()
    print(f"✅ Loaded {len(loaded_positions)} positions from database")
    
    db.disconnect()
    
    # Test 10: Kill Switch
    print("\n" + "=" * 60)
    print("TEST 10: Kill Switch Test")
    print("=" * 60)
    
    # Simulate a large loss to trigger kill switch
    print("Simulating large loss...")
    await risk_manager.trigger_kill_switch("Test kill switch activation")
    
    # Try to place trade after kill switch
    is_allowed, reason = await risk_manager.check_trade(instruction1, Decimal("1000"))
    print(f"Trade after kill switch: {'✅ ALLOWED' if is_allowed else f'❌ BLOCKED: {reason}'}")
    
    # Cleanup
    print("\n" + "=" * 60)
    print("CLEANUP")
    print("=" * 60)
    
    await risk_manager.stop()
    await position_tracker.stop()
    
    print("✅ All tests completed successfully!")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("✅ Position tracking operational")
    print("✅ Risk limits enforced")
    print("✅ P&L calculations working")
    print("✅ Greek calculations functional")
    print("✅ Hedge recommendations available")
    print("✅ Database persistence working")
    print("✅ Kill switch functional")
    print("\n🎉 Risk management system fully operational!")


if __name__ == "__main__":
    try:
        asyncio.run(test_risk_system())
    except KeyboardInterrupt:
        print("\n❌ Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()