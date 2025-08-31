"""Trade coordinator that integrates execution with risk management."""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import datetime
import uuid

from app.trading.models import (
    TradeInstruction,
    ExecutionReport,
    OrderSide,
    OrderType,
    ExecutionStrategy,
    PersistenceType,
    OrderStatus
)
from app.trading.executor import TradeExecutor
from app.risk.tracker import PositionTracker
from app.risk.manager import RiskManager, RiskLimits
from app.risk.calculator import PositionCalculator
from app.server.provider_manager import ProviderManager

logger = logging.getLogger(__name__)


class TradeEvent:
    """Trade event for logging and notifications."""
    
    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.timestamp = datetime.now()
        self.data = data


class TradeCoordinator:
    """
    Coordinates trade execution with risk management.
    
    Flow: Trade Request → Risk Check → Execute → Update Position → Emit Events
    """
    
    def __init__(
        self,
        provider_manager: ProviderManager,
        risk_limits: Optional[RiskLimits] = None
    ):
        """Initialize trade coordinator.
        
        Args:
            provider_manager: Provider manager for market data
            risk_limits: Risk limits configuration
        """
        self.provider_manager = provider_manager
        
        # Initialize risk limits
        self.risk_limits = risk_limits or RiskLimits(
            max_position_size=Decimal("100"),
            max_market_exposure=Decimal("500"),
            max_total_exposure=Decimal("1000"),
            max_daily_loss=Decimal("200"),
            max_open_positions=20,
            max_concentration=Decimal("0.4"),
            min_available_balance=Decimal("50")
        )
        
        # Initialize components
        self.position_tracker = PositionTracker(provider_manager)
        self.risk_manager = RiskManager(
            position_tracker=self.position_tracker,
            limits=self.risk_limits,
            auto_hedge=False,
            kill_switch_enabled=True
        )
        self.executor = TradeExecutor(
            provider_manager=provider_manager,
            position_tracker=self.position_tracker,
            risk_manager=self.risk_manager
        )
        self.calculator = PositionCalculator()
        
        # Event callbacks
        self.event_callbacks = []
        
        # Statistics
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.rejected_trades = 0
        
        # Trade log
        self.trade_log: List[TradeEvent] = []
        self.max_log_size = 1000
        
        # Current account balance (would come from provider)
        self.account_balance = Decimal("1000")
        
        logger.info("Trade coordinator initialized")
        
    async def start(self):
        """Start the coordinator and its components."""
        logger.info("Starting trade coordinator")
        
        # Start components
        await self.position_tracker.start()
        await self.risk_manager.start()
        await self.executor.start_monitoring()
        
        # Add callbacks
        self.position_tracker.add_update_callback(self._on_position_update)
        self.risk_manager.add_alert_callback(self._on_risk_alert)
        
        logger.info("Trade coordinator started")
        
    async def stop(self):
        """Stop the coordinator and its components."""
        logger.info("Stopping trade coordinator")
        
        await self.executor.stop_monitoring()
        await self.risk_manager.stop()
        await self.position_tracker.stop()
        
        logger.info("Trade coordinator stopped")
        
    def add_event_callback(self, callback):
        """Add event callback for notifications."""
        self.event_callbacks.append(callback)
        
    async def place_trade(
        self,
        market_id: str,
        selection_id: str,
        side: OrderSide,
        size: Decimal,
        price: Decimal,
        strategy: ExecutionStrategy = ExecutionStrategy.SMART,
        provider: str = "betfair"
    ) -> Tuple[bool, str, Optional[ExecutionReport]]:
        """
        Place a trade with full risk management.
        
        Args:
            market_id: Market identifier
            selection_id: Selection/runner identifier
            side: BACK or LAY
            size: Stake size
            price: Odds
            strategy: Execution strategy
            provider: Provider to use
            
        Returns:
            Tuple of (success, message, execution_report)
        """
        self.total_trades += 1
        
        # Create trade instruction
        instruction = TradeInstruction(
            market_id=market_id,
            selection_id=selection_id,
            side=side,
            size=size,
            price=price,
            order_type=OrderType.LIMIT,
            strategy=strategy,
            persistence=PersistenceType.LAPSE,
            client_ref=f"coord_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        # Log trade attempt
        await self._log_event("trade_attempt", {
            "market_id": market_id,
            "selection_id": selection_id,
            "side": side.value if hasattr(side, 'value') else str(side),
            "size": str(size),
            "price": str(price)
        })
        
        # Step 1: Risk Check
        is_allowed, rejection_reason = await self.risk_manager.check_trade(
            instruction, self.account_balance
        )
        
        if not is_allowed:
            self.rejected_trades += 1
            await self._log_event("trade_rejected", {
                "reason": rejection_reason,
                "market_id": market_id,
                "selection_id": selection_id,
                "side": side.value if hasattr(side, 'value') else str(side),
                "size": str(size),
                "price": str(price)
            })
            return False, rejection_reason, None
        
        # Step 2: Execute Trade
        try:
            report = await self.executor.execute_order(instruction, provider)
            
            if report.is_successful:
                self.successful_trades += 1
                
                # Step 3: Update Position (already done in executor if configured)
                # But we'll ensure it's done here
                if report.executed_size > 0:
                    position = await self.position_tracker.open_position(
                        market_id=market_id,
                        selection_id=selection_id,
                        side=side,
                        price=report.executed_price,
                        size=report.executed_size,
                        order_id=report.order_id,
                        provider=provider,
                        strategy=strategy.value
                    )
                    
                    await self._log_event("position_opened", {
                        "position_id": position.position_id,
                        "size": str(report.executed_size),
                        "price": str(report.executed_price)
                    })
                
                # Step 4: Emit Success Event
                await self._emit_event({
                    "type": "trade_executed",
                    "order_id": report.order_id,
                    "market_id": market_id,
                    "selection_id": selection_id,
                    "side": side.value,
                    "executed_size": str(report.executed_size),
                    "executed_price": str(report.executed_price),
                    "status": report.status.value
                })
                
                return True, "Trade executed successfully", report
                
            else:
                self.failed_trades += 1
                await self._log_event("trade_failed", {
                    "error": report.error_message,
                    "status": report.status.value
                })
                return False, report.error_message or "Trade execution failed", report
                
        except Exception as e:
            self.failed_trades += 1
            logger.error(f"Trade execution error: {e}")
            await self._log_event("trade_error", {"error": str(e)})
            return False, str(e), None
            
    async def close_position(
        self,
        position_id: str,
        size: Optional[Decimal] = None
    ) -> Tuple[bool, str]:
        """
        Close a position (fully or partially).
        
        Args:
            position_id: Position to close
            size: Size to close (None for full close)
            
        Returns:
            Tuple of (success, message)
        """
        position = self.position_tracker.get_position(position_id)
        if not position:
            return False, "Position not found"
        
        # Get current market price
        market_book = self._get_market_book(position.market_id)
        if not market_book:
            return False, "Could not fetch market prices"
        
        # Find best price to close
        close_price = self._get_close_price(market_book, position)
        if not close_price:
            return False, "No available price to close position"
        
        # Determine close side (opposite of position)
        close_side = OrderSide.LAY if position.side == "long" else OrderSide.BACK
        close_size = size or position.current_size
        
        # Place closing trade
        success, message, report = await self.place_trade(
            market_id=position.market_id,
            selection_id=position.selection_id,
            side=close_side,
            size=close_size,
            price=close_price,
            strategy=ExecutionStrategy.AGGRESSIVE  # Use aggressive to ensure fill
        )
        
        if success and report:
            # Update position
            closed_position = await self.position_tracker.close_position(
                position_id=position_id,
                price=report.executed_price,
                size=report.executed_size,
                order_id=report.order_id
            )
            
            await self._log_event("position_closed", {
                "position_id": position_id,
                "size": str(report.executed_size),
                "price": str(report.executed_price),
                "pnl": str(closed_position.realized_pnl)
            })
            
            return True, f"Position closed. P&L: {closed_position.realized_pnl:.2f}"
        
        return False, message
        
    async def hedge_position(self, position_id: str) -> Tuple[bool, str]:
        """
        Hedge a position to lock in profit/loss (green up).
        
        Args:
            position_id: Position to hedge
            
        Returns:
            Tuple of (success, message)
        """
        position = self.position_tracker.get_position(position_id)
        if not position:
            return False, "Position not found"
        
        # Calculate hedge requirement
        positions = [position]
        hedge = self.calculator.calculate_hedge_requirement(positions)
        
        if not hedge:
            return False, "No hedging required"
        
        # Place hedge trade
        hedge_side = OrderSide.BACK if hedge.side == "long" else OrderSide.LAY
        
        success, message, report = await self.place_trade(
            market_id=hedge.market_id,
            selection_id=hedge.selection_id,
            side=hedge_side,
            size=hedge.size,
            price=hedge.price,
            strategy=ExecutionStrategy.PASSIVE
        )
        
        if success:
            await self._log_event("position_hedged", {
                "position_id": position_id,
                "hedge_size": str(hedge.size),
                "hedge_price": str(hedge.price)
            })
            return True, "Position hedged successfully"
        
        return False, message
        
    async def cash_out_position(
        self,
        position_id: str,
        target_pnl: Optional[Decimal] = None
    ) -> Tuple[bool, str, Decimal]:
        """
        Cash out a position at current market price.
        
        Args:
            position_id: Position to cash out
            target_pnl: Target P&L (None for best available)
            
        Returns:
            Tuple of (success, message, cash_out_value)
        """
        position = self.position_tracker.get_position(position_id)
        if not position:
            return False, "Position not found", Decimal("0")
        
        # Get current market price
        market_book = self._get_market_book(position.market_id)
        if not market_book:
            return False, "Could not fetch market prices", Decimal("0")
        
        # Calculate cash out value
        close_price = self._get_close_price(market_book, position)
        if not close_price:
            return False, "No available price", Decimal("0")
        
        # Calculate P&L if we close at this price
        _, unrealized_pnl = self.calculator.calculate_pnl(
            position, close_price, include_commission=True
        )
        
        cash_out_value = position.realized_pnl + unrealized_pnl
        
        # Check if target P&L is achievable
        if target_pnl and cash_out_value < target_pnl:
            return False, f"Cannot achieve target P&L. Available: {cash_out_value:.2f}", cash_out_value
        
        # Close the position
        success, message = await self.close_position(position_id)
        
        if success:
            await self._log_event("position_cashed_out", {
                "position_id": position_id,
                "cash_out_value": str(cash_out_value)
            })
            return True, f"Cashed out for {cash_out_value:.2f}", cash_out_value
        
        return False, message, Decimal("0")
        
    async def set_stop_loss(
        self,
        position_id: str,
        stop_price: Decimal
    ) -> Tuple[bool, str]:
        """
        Set a stop loss for a position.
        
        Args:
            position_id: Position ID
            stop_price: Stop loss trigger price
            
        Returns:
            Tuple of (success, message)
        """
        position = self.position_tracker.get_position(position_id)
        if not position:
            return False, "Position not found"
        
        # Store stop loss (in real implementation, would monitor and trigger)
        # For now, just log it
        await self._log_event("stop_loss_set", {
            "position_id": position_id,
            "stop_price": str(stop_price)
        })
        
        return True, f"Stop loss set at {stop_price}"
        
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all current positions."""
        positions = self.position_tracker.get_open_positions()
        return [self._position_to_dict(pos) for pos in positions]
        
    def get_pnl_summary(self) -> Dict[str, Any]:
        """Get P&L summary."""
        pnl = self.position_tracker.get_pnl_statement()
        
        return {
            "realized_pnl": str(pnl.realized_pnl),
            "unrealized_pnl": str(pnl.unrealized_pnl),
            "total_pnl": str(pnl.realized_pnl + pnl.unrealized_pnl),
            "commission": str(pnl.commission),
            "num_trades": pnl.num_trades,
            "win_rate": str(pnl.win_rate),
            "avg_win": str(pnl.avg_win),
            "avg_loss": str(pnl.avg_loss)
        }
        
    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        metrics = self.risk_manager.get_risk_metrics()
        report = self.risk_manager.get_exposure_report(self.account_balance)
        
        return {
            "total_exposure": str(report.total_exposure),
            "exposure_limit": str(report.exposure_limit),
            "exposure_used": str(metrics.exposure_limit_used) + "%",
            "daily_loss": str(report.daily_pnl.net_pnl),
            "daily_loss_limit": str(report.daily_loss_limit),
            "loss_limit_used": str(metrics.loss_limit_used) + "%",
            "open_positions": metrics.num_open_positions,
            "position_limit": self.risk_limits.max_open_positions,
            "risk_score": str(metrics.risk_score),
            "trading_frozen": self.risk_manager.trading_frozen,
            "alerts": metrics.alerts
        }
        
    def get_trade_stats(self) -> Dict[str, Any]:
        """Get trade execution statistics."""
        return {
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "rejected_trades": self.rejected_trades,
            "success_rate": (
                f"{(self.successful_trades / self.total_trades * 100):.1f}%"
                if self.total_trades > 0 else "0%"
            )
        }
        
    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trade events."""
        trades = [
            event for event in self.trade_log
            if event.event_type in ["trade_executed", "trade_failed", "trade_rejected"]
        ]
        return [self._event_to_dict(event) for event in trades[-limit:]]
        
    # Private methods
    
    def _get_market_book(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get market book from provider."""
        try:
            provider = self.provider_manager.providers.get("betfair")
            if provider and provider.service:
                return provider.service.get_market_book(market_id)
        except Exception as e:
            logger.error(f"Error fetching market book: {e}")
        return None
        
    def _get_close_price(self, market_book: Dict[str, Any], position) -> Optional[Decimal]:
        """Get best price to close a position."""
        try:
            runners = market_book.get("runners", [])
            for runner in runners:
                if str(runner.get("selectionId")) == position.selection_id:
                    ex = runner.get("ex", {})
                    
                    # If long position, need to lay to close
                    if position.side == "long":
                        lay_prices = ex.get("availableToLay", [])
                        if lay_prices:
                            return Decimal(str(lay_prices[0]["price"]))
                    # If short position, need to back to close
                    else:
                        back_prices = ex.get("availableToBack", [])
                        if back_prices:
                            return Decimal(str(back_prices[0]["price"]))
        except Exception as e:
            logger.error(f"Error getting close price: {e}")
        return None
        
    def _position_to_dict(self, position) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            "position_id": position.position_id,
            "market_id": position.market_id,
            "selection_id": position.selection_id,
            "side": position.side.value if hasattr(position.side, 'value') else str(position.side),
            "entry_price": str(position.entry_price),
            "current_size": str(position.current_size),
            "entry_time": position.entry_time.isoformat(),
            "realized_pnl": str(position.realized_pnl),
            "unrealized_pnl": str(position.unrealized_pnl),
            "total_pnl": str(position.realized_pnl + position.unrealized_pnl),
            "status": position.status.value if hasattr(position.status, 'value') else str(position.status)
        }
        
    def _event_to_dict(self, event: TradeEvent) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data
        }
        
    async def _log_event(self, event_type: str, data: Dict[str, Any]):
        """Log a trade event."""
        event = TradeEvent(event_type, data)
        self.trade_log.append(event)
        
        # Trim log if too large
        if len(self.trade_log) > self.max_log_size:
            self.trade_log = self.trade_log[-self.max_log_size:]
        
        logger.info(f"Trade event: {event_type} - {data}")
        
    async def _emit_event(self, data: Dict[str, Any]):
        """Emit event to callbacks."""
        for callback in self.event_callbacks:
            try:
                await callback(data)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
                
    async def _on_position_update(self, update):
        """Handle position update."""
        await self._emit_event({
            "type": "position_update",
            "position_id": update.position_id,
            "new_size": str(update.new_size),
            "new_pnl": str(update.new_pnl)
        })
        
    async def _on_risk_alert(self, alert):
        """Handle risk alert."""
        await self._emit_event({
            "type": "risk_alert",
            "severity": alert.severity,
            "message": alert.message,
            "suggested_action": alert.suggested_action
        })