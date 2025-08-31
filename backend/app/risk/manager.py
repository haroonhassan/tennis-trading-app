"""Risk manager for enforcing limits and managing portfolio risk."""

import asyncio
from typing import Dict, List, Optional, Set, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging

from app.risk.models import (
    Position, RiskMetrics, ExposureReport, RiskAlert,
    MarketExposure, PnLStatement, HedgeInstruction
)
from app.risk.tracker import PositionTracker
from app.risk.calculator import PositionCalculator, GreekCalculator
from app.trading.models import TradeInstruction, OrderSide, ExecutionStrategy

logger = logging.getLogger(__name__)


class RiskLimitType(str, Enum):
    """Types of risk limits."""
    MAX_POSITION_SIZE = "max_position_size"
    MAX_MARKET_EXPOSURE = "max_market_exposure"
    MAX_TOTAL_EXPOSURE = "max_total_exposure"
    MAX_DAILY_LOSS = "max_daily_loss"
    MAX_OPEN_POSITIONS = "max_open_positions"
    MAX_CONCENTRATION = "max_concentration"
    MIN_AVAILABLE_BALANCE = "min_available_balance"


class RiskAction(str, Enum):
    """Risk management actions."""
    BLOCK_TRADE = "block_trade"
    REDUCE_POSITION = "reduce_position"
    HEDGE_POSITION = "hedge_position"
    CLOSE_POSITION = "close_position"
    FREEZE_TRADING = "freeze_trading"
    ALERT_ONLY = "alert_only"


class RiskLimits:
    """Configurable risk limits."""
    
    def __init__(
        self,
        max_position_size: Decimal = Decimal("100"),
        max_market_exposure: Decimal = Decimal("500"),
        max_total_exposure: Decimal = Decimal("1000"),
        max_daily_loss: Decimal = Decimal("200"),
        max_open_positions: int = 20,
        max_concentration: Decimal = Decimal("0.3"),
        min_available_balance: Decimal = Decimal("100")
    ):
        """Initialize risk limits.
        
        Args:
            max_position_size: Maximum size for a single position
            max_market_exposure: Maximum exposure in a single market
            max_total_exposure: Maximum total portfolio exposure
            max_daily_loss: Maximum daily loss allowed
            max_open_positions: Maximum number of open positions
            max_concentration: Maximum concentration in single market (0-1)
            min_available_balance: Minimum balance to maintain
        """
        self.max_position_size = max_position_size
        self.max_market_exposure = max_market_exposure
        self.max_total_exposure = max_total_exposure
        self.max_daily_loss = max_daily_loss
        self.max_open_positions = max_open_positions
        self.max_concentration = max_concentration
        self.min_available_balance = min_available_balance


class RiskManager:
    """Manages portfolio risk and enforces limits."""
    
    def __init__(
        self,
        position_tracker: PositionTracker,
        limits: RiskLimits,
        auto_hedge: bool = False,
        kill_switch_enabled: bool = True
    ):
        """Initialize risk manager.
        
        Args:
            position_tracker: Position tracker instance
            limits: Risk limits to enforce
            auto_hedge: Whether to automatically hedge positions
            kill_switch_enabled: Whether kill switch is enabled
        """
        self.tracker = position_tracker
        self.limits = limits
        self.auto_hedge = auto_hedge
        self.kill_switch_enabled = kill_switch_enabled
        
        # Calculators
        self.calculator = PositionCalculator()
        self.greek_calculator = GreekCalculator()
        
        # State tracking
        self.trading_frozen = False
        self.freeze_reason = None
        self.daily_loss = Decimal("0")
        self.last_reset = datetime.now()
        
        # Breaches and alerts
        self.active_breaches: Set[str] = set()
        self.alert_history: List[RiskAlert] = []
        self.alert_callbacks: List = []
        
        # Monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start risk monitoring."""
        logger.info("Starting risk manager")
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
    async def stop(self):
        """Stop risk monitoring."""
        logger.info("Stopping risk manager")
        if self.monitoring_task:
            self.monitoring_task.cancel()
            
    def add_alert_callback(self, callback):
        """Add alert callback."""
        self.alert_callbacks.append(callback)
        
    async def check_trade(
        self,
        instruction: TradeInstruction,
        current_balance: Decimal
    ) -> Tuple[bool, Optional[str]]:
        """Check if a trade is allowed under risk limits.
        
        Args:
            instruction: Trade instruction to check
            current_balance: Current account balance
            
        Returns:
            Tuple of (is_allowed, rejection_reason)
        """
        # Check if trading is frozen
        if self.trading_frozen:
            return False, f"Trading frozen: {self.freeze_reason}"
        
        # Check position size limit
        if instruction.size > self.limits.max_position_size:
            return False, f"Position size {instruction.size} exceeds limit {self.limits.max_position_size}"
        
        # Check daily loss limit
        if self.daily_loss >= self.limits.max_daily_loss:
            return False, f"Daily loss limit reached: {self.daily_loss}"
        
        # Check minimum balance
        required_balance = instruction.size
        if instruction.side == OrderSide.LAY:
            required_balance = instruction.size * (instruction.price - 1)
        
        if current_balance - required_balance < self.limits.min_available_balance:
            return False, f"Insufficient balance: {current_balance} - {required_balance} < {self.limits.min_available_balance}"
        
        # Check market exposure
        market_exposure = self.tracker.get_market_exposure(instruction.market_id)
        if market_exposure:
            new_exposure = market_exposure.max_loss + required_balance
            if new_exposure > self.limits.max_market_exposure:
                return False, f"Market exposure would exceed limit: {new_exposure} > {self.limits.max_market_exposure}"
        
        # Check total exposure
        total_exposure = self.tracker.get_total_exposure()
        if total_exposure + required_balance > self.limits.max_total_exposure:
            return False, f"Total exposure would exceed limit: {total_exposure + required_balance} > {self.limits.max_total_exposure}"
        
        # Check number of positions
        open_positions = self.tracker.get_open_positions()
        if len(open_positions) >= self.limits.max_open_positions:
            # Check if this is adding to existing position
            existing = False
            for pos in open_positions:
                if (pos.market_id == instruction.market_id and 
                    pos.selection_id == instruction.selection_id):
                    existing = True
                    break
            
            if not existing:
                return False, f"Maximum open positions reached: {self.limits.max_open_positions}"
        
        # Check concentration
        if total_exposure > 0:
            concentration = (market_exposure.max_loss if market_exposure else Decimal("0")) / total_exposure
            if concentration > self.limits.max_concentration:
                return False, f"Position concentration too high: {concentration} > {self.limits.max_concentration}"
        
        return True, None
        
    async def handle_position_update(self, position: Position):
        """Handle position update for risk monitoring.
        
        Args:
            position: Updated position
        """
        # Update daily P&L
        self.daily_loss = -min(Decimal("0"), position.realized_pnl)
        
        # Check for limit breaches
        await self._check_limits()
        
        # Check if hedging needed
        if self.auto_hedge:
            await self._check_hedging(position)
            
    async def trigger_kill_switch(self, reason: str):
        """Trigger the kill switch to stop all trading.
        
        Args:
            reason: Reason for triggering kill switch
        """
        if not self.kill_switch_enabled:
            logger.warning(f"Kill switch triggered but disabled: {reason}")
            return
            
        logger.critical(f"KILL SWITCH ACTIVATED: {reason}")
        
        self.trading_frozen = True
        self.freeze_reason = reason
        
        # Create critical alert
        alert = RiskAlert(
            alert_id=f"kill_switch_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            severity="critical",
            category="kill_switch",
            message=f"Kill switch activated: {reason}",
            suggested_action="Close all positions immediately",
            requires_confirmation=True
        )
        
        await self._send_alert(alert)
        
        # Optionally close all positions
        # await self._close_all_positions()
        
    async def reset_daily_limits(self):
        """Reset daily limits (call at start of trading day)."""
        self.daily_loss = Decimal("0")
        self.last_reset = datetime.now()
        logger.info("Daily risk limits reset")
        
    def get_risk_metrics(self) -> RiskMetrics:
        """Get current risk metrics.
        
        Returns:
            Current risk metrics
        """
        positions = self.tracker.get_open_positions()
        total_exposure = self.tracker.get_total_exposure()
        
        # Calculate metrics
        num_positions = len(positions)
        num_markets = len(set(pos.market_id for pos in positions))
        
        largest_position = max(
            (pos.current_size for pos in positions),
            default=Decimal("0")
        )
        
        # Calculate concentration
        if total_exposure > 0 and positions:
            market_exposures = {}
            for pos in positions:
                market_id = pos.market_id
                if market_id not in market_exposures:
                    market_exposures[market_id] = Decimal("0")
                market_exposures[market_id] += pos.current_size
            
            max_market_exposure = max(market_exposures.values())
            concentration = max_market_exposure / total_exposure
        else:
            concentration = Decimal("0")
        
        # Calculate Greeks
        market_prices = {}  # Would get from provider
        time_to_events = {}  # Would get from provider
        
        greeks = self.greek_calculator.calculate_portfolio_greeks(
            positions, market_prices, time_to_events
        )
        
        # Calculate limit usage
        exposure_limit_used = (
            (total_exposure / self.limits.max_total_exposure * 100)
            if self.limits.max_total_exposure > 0 else Decimal("0")
        )
        
        position_limit_used = (
            (Decimal(num_positions) / Decimal(self.limits.max_open_positions) * 100)
            if self.limits.max_open_positions > 0 else Decimal("0")
        )
        
        loss_limit_used = (
            (self.daily_loss / self.limits.max_daily_loss * 100)
            if self.limits.max_daily_loss > 0 else Decimal("0")
        )
        
        # Calculate risk score (0-100)
        risk_score = max(
            exposure_limit_used,
            position_limit_used,
            loss_limit_used,
            concentration * 100
        )
        
        # Generate alerts
        alerts = []
        if exposure_limit_used > 80:
            alerts.append(f"Exposure limit {exposure_limit_used:.1f}% used")
        if loss_limit_used > 80:
            alerts.append(f"Daily loss limit {loss_limit_used:.1f}% used")
        if concentration > Decimal("0.5"):
            alerts.append(f"High concentration risk: {concentration:.1%}")
        
        return RiskMetrics(
            timestamp=datetime.now(),
            total_exposure=total_exposure,
            max_drawdown=self.daily_loss,
            var_95=total_exposure * Decimal("0.1"),  # Simplified VaR
            expected_value=sum(pos.unrealized_pnl for pos in positions),
            num_open_positions=num_positions,
            num_markets=num_markets,
            largest_position=largest_position,
            concentration_risk=concentration,
            portfolio_delta=greeks.get("delta", Decimal("0")),
            portfolio_gamma=greeks.get("gamma", Decimal("0")),
            portfolio_theta=greeks.get("theta", Decimal("0")),
            exposure_limit_used=exposure_limit_used,
            position_limit_used=position_limit_used,
            loss_limit_used=loss_limit_used,
            risk_score=min(risk_score, Decimal("100")),
            alerts=alerts
        )
        
    def get_exposure_report(self, account_balance: Decimal) -> ExposureReport:
        """Get comprehensive exposure report.
        
        Args:
            account_balance: Current account balance
            
        Returns:
            Exposure report
        """
        # Get market exposures
        market_exposures = list(self.tracker.market_exposures.values())
        
        # Get risk metrics
        risk_metrics = self.get_risk_metrics()
        
        # Get P&L statement
        pnl_statement = self.tracker.get_pnl_statement(period_hours=24)
        
        # Calculate totals
        total_exposure = self.tracker.get_total_exposure()
        total_liability = sum(
            exp.net_lay_liability for exp in market_exposures
        )
        net_exposure = sum(
            exp.net_back_exposure - exp.net_lay_liability 
            for exp in market_exposures
        )
        
        # Calculate open P&L
        open_pnl = sum(
            pos.unrealized_pnl 
            for pos in self.tracker.get_open_positions()
        )
        
        # Available balance
        available_balance = account_balance - total_exposure
        
        # Remaining limits
        exposure_remaining = self.limits.max_total_exposure - total_exposure
        loss_remaining = self.limits.max_daily_loss - self.daily_loss
        
        # Generate warnings
        warnings = []
        if available_balance < self.limits.min_available_balance * Decimal("2"):
            warnings.append("Low available balance")
        if len(market_exposures) > 10:
            warnings.append("High number of active markets")
        if risk_metrics.risk_score > 75:
            warnings.append(f"High risk score: {risk_metrics.risk_score:.1f}")
        
        # Check for breaches
        breaches = list(self.active_breaches)
        
        return ExposureReport(
            timestamp=datetime.now(),
            account_balance=account_balance,
            available_balance=available_balance,
            market_exposures=market_exposures,
            total_exposure=total_exposure,
            total_liability=total_liability,
            net_exposure=net_exposure,
            risk_metrics=risk_metrics,
            daily_pnl=pnl_statement,
            open_pnl=open_pnl,
            exposure_limit=self.limits.max_total_exposure,
            exposure_limit_remaining=max(Decimal("0"), exposure_remaining),
            daily_loss_limit=self.limits.max_daily_loss,
            daily_loss_limit_remaining=max(Decimal("0"), loss_remaining),
            warnings=warnings,
            breaches=breaches
        )
        
    # Private methods
    
    async def _check_limits(self):
        """Check all risk limits and trigger alerts."""
        breaches = set()
        
        # Check total exposure
        total_exposure = self.tracker.get_total_exposure()
        if total_exposure > self.limits.max_total_exposure:
            breaches.add("total_exposure")
            await self._handle_breach(
                RiskLimitType.MAX_TOTAL_EXPOSURE,
                total_exposure,
                self.limits.max_total_exposure
            )
        
        # Check daily loss
        if self.daily_loss > self.limits.max_daily_loss:
            breaches.add("daily_loss")
            await self._handle_breach(
                RiskLimitType.MAX_DAILY_LOSS,
                self.daily_loss,
                self.limits.max_daily_loss
            )
            
            # Trigger kill switch if loss is severe
            if self.daily_loss > self.limits.max_daily_loss * Decimal("1.2"):
                await self.trigger_kill_switch(f"Daily loss exceeded 120% of limit: {self.daily_loss}")
        
        # Check number of positions
        num_positions = len(self.tracker.get_open_positions())
        if num_positions > self.limits.max_open_positions:
            breaches.add("open_positions")
            await self._handle_breach(
                RiskLimitType.MAX_OPEN_POSITIONS,
                Decimal(num_positions),
                Decimal(self.limits.max_open_positions)
            )
        
        # Update active breaches
        self.active_breaches = breaches
        
    async def _handle_breach(
        self,
        limit_type: RiskLimitType,
        current_value: Decimal,
        limit_value: Decimal
    ):
        """Handle a limit breach.
        
        Args:
            limit_type: Type of limit breached
            current_value: Current value
            limit_value: Limit value
        """
        severity = "warning"
        action = RiskAction.ALERT_ONLY
        
        # Determine severity and action
        breach_pct = (current_value / limit_value - 1) * 100
        
        if breach_pct > 20:
            severity = "critical"
            action = RiskAction.FREEZE_TRADING
        elif breach_pct > 10:
            severity = "warning"
            action = RiskAction.REDUCE_POSITION
        
        # Create alert
        alert = RiskAlert(
            alert_id=f"{limit_type}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            severity=severity,
            category="limit_breach",
            message=f"{limit_type} breached: {current_value} > {limit_value}",
            metric_name=limit_type,
            metric_value=current_value,
            threshold=limit_value,
            suggested_action=action.value,
            requires_confirmation=severity == "critical"
        )
        
        await self._send_alert(alert)
        
        # Take action
        if action == RiskAction.FREEZE_TRADING:
            await self.trigger_kill_switch(f"{limit_type} breach")
        elif action == RiskAction.REDUCE_POSITION and self.auto_hedge:
            await self._reduce_largest_position()
            
    async def _check_hedging(self, position: Position):
        """Check if hedging is needed for a position.
        
        Args:
            position: Position to check
        """
        # Get all positions for this market
        market_positions = self.tracker.get_market_positions(position.market_id)
        
        # Calculate hedge requirement
        hedge = self.calculator.calculate_hedge_requirement(market_positions)
        
        if hedge and hedge.urgency in ["high", "critical"]:
            # Create alert
            alert = RiskAlert(
                alert_id=f"hedge_{datetime.now().timestamp()}",
                timestamp=datetime.now(),
                severity="warning" if hedge.urgency == "high" else "critical",
                category="hedging",
                message=f"Hedging recommended: {hedge.reason}",
                market_id=hedge.market_id,
                suggested_action=f"Place {hedge.side} bet of {hedge.size} at {hedge.price}",
                requires_confirmation=True
            )
            
            await self._send_alert(alert)
            
    async def _reduce_largest_position(self):
        """Reduce the largest position to manage risk."""
        positions = self.tracker.get_open_positions()
        
        if not positions:
            return
            
        # Find largest position
        largest = max(positions, key=lambda p: p.current_size)
        
        # Reduce by 50%
        reduce_size = largest.current_size / 2
        
        logger.info(f"Reducing position {largest.position_id} by {reduce_size}")
        
        # Would trigger actual trade here
        
    async def _send_alert(self, alert: RiskAlert):
        """Send risk alert to callbacks.
        
        Args:
            alert: Alert to send
        """
        self.alert_history.append(alert)
        
        # Keep only last 100 alerts
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]
        
        # Send to callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
                
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                # Check limits
                await self._check_limits()
                
                # Reset daily limits if needed
                if datetime.now().date() > self.last_reset.date():
                    await self.reset_daily_limits()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")