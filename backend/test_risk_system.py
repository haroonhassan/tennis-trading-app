#!/usr/bin/env python3
"""Test script for the integrated risk management system."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.server.provider_manager import ProviderManager, ProviderStatus
from app.providers.betfair import BetfairProvider
from app.config import Settings
from app.risk import (
    PositionTracker,
    RiskManager,
    RiskLimits,
    PositionCalculator,
    GreekCalculator,
    PositionDatabase
)
from app.trading.executor import TradeExecutor
from app.trading.models import (
    TradeInstruction,
    OrderSide,
    OrderType,
    ExecutionStrategy,
    PersistenceType,
    RiskLimits as TradingRiskLimits
)


async def test_risk_system():
    """Test the integrated risk management system."""
    print("=" * 60)
    print("RISK MANAGEMENT SYSTEM TEST")
    print("=" * 60)
    
    # Initialize settings
    settings = Settings()
    
    # Initialize provider manager
    provider_manager = ProviderManager()
    
    # Initialize Betfair provider manually for testing
    print("\n1. Initializing Betfair provider...")
    betfair = BetfairProvider()  # Uses environment variables automatically
    
    if betfair.authenticate():
        # Manually add provider to manager for testing
        from app.server.provider_manager import ProviderInfo
        provider_info = ProviderInfo("betfair", betfair)
        provider_info.service = betfair  # Use provider directly as service
        provider_info.is_primary = True
        provider_info.status = ProviderStatus.CONNECTED
        provider_manager.providers["betfair"] = provider_info
        provider_manager.primary_provider = "betfair"
        print("✅ Connected to Betfair")
    else:
        print("❌ Failed to connect to Betfair")
        return
    
    # Initialize position tracker
    print("\n2. Initializing position tracker...")
    position_tracker = PositionTracker(provider_manager)
    await position_tracker.start()
    print("✅ Position tracker started")
    
    # Initialize risk limits
    print("\n3. Setting up risk limits...")
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
    print("\n4. Initializing risk manager...")
    risk_manager = RiskManager(
        position_tracker=position_tracker,
        limits=risk_limits,
        auto_hedge=False,
        kill_switch_enabled=True
    )
    await risk_manager.start()
    print("✅ Risk manager started")
    
    # Initialize trade executor with risk management
    print("\n5. Initializing trade executor with risk integration...")
    trading_limits = TradingRiskLimits(
        max_order_size=Decimal("20"),
        max_market_exposure=Decimal("50")
    )
    
    executor = TradeExecutor(
        provider_manager=provider_manager,
        risk_limits=trading_limits,
        position_tracker=position_tracker,
        risk_manager=risk_manager
    )
    print("✅ Trade executor initialized with risk management")
    
    # Get test market
    print("\n6. Fetching test market...")
    matches = await provider_manager.get_all_matches()
    
    if not matches:
        print("❌ No markets available")
        return
    
    test_match = matches[0]
    print(f"✅ Using market: {test_match.player1.name} vs {test_match.player2.name}")
    
    # Get market details
    market_book = betfair.get_market_book(test_match.market_id)
    if not market_book or not market_book.get("runners"):
        print("❌ Could not fetch market details")
        return
    
    runner = market_book["runners"][0]
    selection_id = str(runner.get("selectionId"))
    
    # Test 1: Normal trade within limits
    print("\n" + "=" * 60)
    print("TEST 1: Normal trade within limits")
    print("=" * 60)
    
    instruction1 = TradeInstruction(
        market_id=test_match.market_id,
        selection_id=selection_id,
        side=OrderSide.BACK,
        size=Decimal("5"),
        price=Decimal("2.0"),
        order_type=OrderType.LIMIT,
        strategy=ExecutionStrategy.PASSIVE,
        persistence=PersistenceType.LAPSE
    )
    
    print(f"Placing £5 BACK bet at 2.0...")
    
    # Check if trade is allowed
    is_allowed, reason = await risk_manager.check_trade(instruction1, Decimal("1000"))
    print(f"Risk check: {'✅ ALLOWED' if is_allowed else f'❌ BLOCKED: {reason}'}")
    
    if is_allowed:
        # Simulate position opening
        position = await position_tracker.open_position(
            market_id=test_match.market_id,
            selection_id=selection_id,
            side=OrderSide.BACK,
            price=Decimal("2.0"),
            size=Decimal("5"),
            order_id="test_order_1",
            provider="betfair"
        )
        print(f"Position opened: {position.position_id[:8]}")
    
    # Test 2: Trade exceeding position size limit
    print("\n" + "=" * 60)
    print("TEST 2: Trade exceeding position size limit")
    print("=" * 60)
    
    instruction2 = TradeInstruction(
        market_id=test_match.market_id,
        selection_id=selection_id,
        side=OrderSide.BACK,
        size=Decimal("25"),  # Exceeds max_position_size of 20
        price=Decimal("2.0"),
        order_type=OrderType.LIMIT,
        strategy=ExecutionStrategy.PASSIVE,
        persistence=PersistenceType.LAPSE
    )
    
    print(f"Attempting £25 BACK bet (exceeds £20 limit)...")
    
    is_allowed, reason = await risk_manager.check_trade(instruction2, Decimal("1000"))
    print(f"Risk check: {'✅ ALLOWED' if is_allowed else f'❌ BLOCKED: {reason}'}")
    
    # Test 3: Check risk metrics
    print("\n" + "=" * 60)
    print("TEST 3: Risk metrics and exposure report")
    print("=" * 60)
    
    # Get risk metrics
    metrics = risk_manager.get_risk_metrics()
    print("\nRisk Metrics:")
    print(f"  Total exposure: £{metrics.total_exposure}")
    print(f"  Open positions: {metrics.num_open_positions}")
    print(f"  Risk score: {metrics.risk_score}/100")
    print(f"  Exposure limit used: {metrics.exposure_limit_used:.1f}%")
    print(f"  Alerts: {', '.join(metrics.alerts) if metrics.alerts else 'None'}")
    
    # Get exposure report
    report = risk_manager.get_exposure_report(Decimal("1000"))
    print("\nExposure Report:")
    print(f"  Account balance: £{report.account_balance}")
    print(f"  Available balance: £{report.available_balance}")
    print(f"  Total exposure: £{report.total_exposure}")
    print(f"  Daily P&L: £{report.daily_pnl.net_pnl}")
    print(f"  Warnings: {', '.join(report.warnings) if report.warnings else 'None'}")
    
    # Test 4: Position P&L calculation
    print("\n" + "=" * 60)
    print("TEST 4: P&L and Greek calculations")
    print("=" * 60)
    
    calculator = PositionCalculator()
    greek_calc = GreekCalculator()
    
    if position_tracker.get_open_positions():
        test_position = position_tracker.get_open_positions()[0]
        
        # Calculate P&L at different prices
        for price in [Decimal("1.8"), Decimal("2.0"), Decimal("2.2")]:
            realized, unrealized = calculator.calculate_pnl(
                test_position, price, include_commission=True
            )
            print(f"  At {price}: Realized P&L: £{realized:.2f}, Unrealized P&L: £{unrealized:.2f}")
        
        # Calculate Greeks
        delta = greek_calc.calculate_delta(test_position, Decimal("2.0"))
        theta = greek_calc.calculate_theta(test_position, 60)
        print(f"\nGreeks:")
        print(f"  Delta: {delta}")
        print(f"  Theta: {theta}")
    
    # Test 5: Hedge calculation
    print("\n" + "=" * 60)
    print("TEST 5: Hedge requirement calculation")
    print("=" * 60)
    
    positions = position_tracker.get_open_positions()
    if positions:
        hedge = calculator.calculate_hedge_requirement(positions)
        if hedge:
            print(f"Hedge recommended:")
            print(f"  Market: {hedge.market_id[:20]}...")
            print(f"  Selection: {hedge.selection_id}")
            print(f"  Side: {hedge.side}")
            print(f"  Size: £{hedge.size}")
            print(f"  Reason: {hedge.reason}")
        else:
            print("No hedging required")
    
    # Test 6: Database persistence
    print("\n" + "=" * 60)
    print("TEST 6: Database persistence")
    print("=" * 60)
    
    db = PositionDatabase("test_positions.db")
    db.connect()
    
    # Save positions
    for pos in position_tracker.get_open_positions():
        db.save_position(pos)
        print(f"Saved position {pos.position_id[:8]} to database")
    
    # Save daily P&L
    pnl_statement = position_tracker.get_pnl_statement()
    db.save_daily_pnl(datetime.now(), {
        "gross_pnl": pnl_statement.gross_pnl,
        "commission": pnl_statement.commission,
        "net_pnl": pnl_statement.net_pnl,
        "num_trades": pnl_statement.num_trades,
        "win_rate": pnl_statement.win_rate,
        "avg_win": pnl_statement.avg_win,
        "avg_loss": pnl_statement.avg_loss,
        "total_volume": pnl_statement.total_volume
    })
    print("Saved daily P&L to database")
    
    db.disconnect()
    
    # Cleanup
    print("\n" + "=" * 60)
    print("CLEANUP")
    print("=" * 60)
    
    await risk_manager.stop()
    await position_tracker.stop()
    
    print("✅ Test completed successfully")


if __name__ == "__main__":
    try:
        asyncio.run(test_risk_system())
    except KeyboardInterrupt:
        print("\n❌ Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()