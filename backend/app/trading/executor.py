"""Trade execution service with smart routing and risk management."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict
import time

from .models import (
    TradeInstruction,
    Order,
    Bet,
    ExecutionReport,
    Fill,
    OrderStatus,
    OrderSide,
    OrderType,
    ExecutionStrategy,
    RiskLimits,
    TradeEvent
)
from .strategies import ExecutionStrategyFactory
from ..providers.base import BaseDataProvider
from ..server.provider_manager import ProviderManager


class TradeExecutor:
    """
    Trade execution engine with smart routing and risk management.
    
    Features:
    - Multi-provider order routing
    - Execution strategies (aggressive, passive, TWAP, etc.)
    - Risk management and safeguards
    - Order retry and recovery
    - Trade event logging
    """
    
    def __init__(
        self,
        provider_manager: ProviderManager,
        risk_limits: Optional[RiskLimits] = None,
        position_tracker: Optional[Any] = None,  # Avoid circular import
        risk_manager: Optional[Any] = None  # Avoid circular import
    ):
        """
        Initialize trade executor.
        
        Args:
            provider_manager: Provider manager for routing
            risk_limits: Risk management limits
            position_tracker: Optional position tracker for P&L
            risk_manager: Optional risk manager for limit enforcement
        """
        self.provider_manager = provider_manager
        self.risk_limits = risk_limits or RiskLimits()
        self.position_tracker = position_tracker
        self.risk_manager = risk_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Order tracking
        self.orders: Dict[str, Order] = {}
        self.matched_bets: Dict[str, Bet] = {}
        
        # Rate limiting
        self.order_timestamps: Dict[str, List[datetime]] = defaultdict(list)
        self.market_order_counts: Dict[str, int] = defaultdict(int)
        
        # Duplicate detection
        self.recent_instructions: List[tuple] = []
        self.duplicate_window = 5  # seconds
        
        # Event callbacks
        self.event_callbacks: List[Callable] = []
        
        # Execution strategies
        self.strategy_factory = ExecutionStrategyFactory()
        
        # Statistics
        self.total_orders = 0
        self.successful_orders = 0
        self.failed_orders = 0
        
        # Running state
        self.is_running = False
        self._monitor_task = None
    
    async def execute_order(
        self,
        instruction: TradeInstruction,
        provider: Optional[str] = None
    ) -> ExecutionReport:
        """
        Execute a trade instruction.
        
        Args:
            instruction: Trade instruction to execute
            provider: Optional specific provider to use
            
        Returns:
            ExecutionReport with execution status
        """
        # Validate instruction
        try:
            instruction.validate()
        except ValueError as e:
            return self._create_error_report(instruction, str(e))
        
        # Check risk limits
        is_valid, error_msg = self.risk_limits.validate_order(instruction)
        if not is_valid:
            return self._create_error_report(instruction, error_msg)
        
        # Check with risk manager if available
        if self.risk_manager:
            # Get current balance (would come from provider)
            current_balance = Decimal("1000")  # Placeholder
            is_allowed, rejection_reason = await self.risk_manager.check_trade(
                instruction, current_balance
            )
            if not is_allowed:
                return self._create_error_report(instruction, rejection_reason)
        
        # Check for duplicates
        if self._is_duplicate(instruction):
            return self._create_error_report(instruction, "Duplicate order detected")
        
        # Check rate limits
        if not self._check_rate_limits(instruction.market_id):
            return self._create_error_report(instruction, "Rate limit exceeded")
        
        # Check market suspension
        if await self._is_market_suspended(instruction.market_id, provider):
            return self._create_error_report(instruction, "Market is suspended")
        
        # Create order
        order = self._create_order(instruction, provider)
        self.orders[order.order_id] = order
        
        # Emit order placed event
        await self._emit_event(TradeEvent(
            event_id=str(uuid.uuid4()),
            event_type="order_placed",
            timestamp=datetime.now(),
            order_id=order.order_id,
            market_id=instruction.market_id,
            provider=provider,
            data={"instruction": instruction.__dict__}
        ))
        
        # Get execution strategy
        strategy = self.strategy_factory.get_strategy(instruction.strategy)
        
        # Execute with strategy
        try:
            report = await strategy.execute(
                instruction=instruction,
                executor=self,
                provider=provider
            )
            
            # Update order status
            order.status = report.status
            order.matched_size = report.executed_size
            order.average_matched_price = report.executed_price
            
            # Update statistics
            self.total_orders += 1
            if report.is_successful:
                self.successful_orders += 1
                
                # Track position if position tracker available
                if self.position_tracker and report.executed_size > 0:
                    await self.position_tracker.open_position(
                        market_id=instruction.market_id,
                        selection_id=instruction.selection_id,
                        side=instruction.side,
                        price=report.executed_price,
                        size=report.executed_size,
                        order_id=order.order_id,
                        provider=provider or "betfair",
                        strategy=instruction.strategy.value if instruction.strategy else None
                    )
            else:
                self.failed_orders += 1
            
            # Emit appropriate event
            if report.status == OrderStatus.MATCHED:
                await self._emit_event(TradeEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="order_matched",
                    timestamp=datetime.now(),
                    order_id=order.order_id,
                    market_id=instruction.market_id,
                    provider=provider,
                    data={"size": float(report.executed_size), "price": float(report.executed_price)}
                ))
            elif report.status == OrderStatus.PARTIALLY_MATCHED:
                await self._emit_event(TradeEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="partial_fill",
                    timestamp=datetime.now(),
                    order_id=order.order_id,
                    market_id=instruction.market_id,
                    provider=provider,
                    data={"filled": float(report.executed_size), "remaining": float(report.remaining_size)}
                ))
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
            self.failed_orders += 1
            order.status = OrderStatus.FAILED
            order.error_message = str(e)
            
            return self._create_error_report(instruction, str(e))
    
    async def place_order_with_provider(
        self,
        instruction: TradeInstruction,
        provider: str
    ) -> Dict[str, Any]:
        """
        Place order with specific provider.
        
        Args:
            instruction: Trade instruction
            provider: Provider name
            
        Returns:
            Provider response
        """
        provider_info = self.provider_manager.providers.get(provider)
        if not provider_info or not provider_info.service:
            raise ValueError(f"Provider {provider} not available")
        
        service = provider_info.service
        
        # Place order based on side
        if instruction.side == OrderSide.BACK:
            return service.place_back_bet(
                market_id=instruction.market_id,
                selection_id=instruction.selection_id,
                price=float(instruction.price),
                size=float(instruction.size)
            )
        else:  # LAY
            return service.place_lay_bet(
                market_id=instruction.market_id,
                selection_id=instruction.selection_id,
                price=float(instruction.price),
                size=float(instruction.size)
            )
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if successful
        """
        order = self.orders.get(order_id)
        if not order:
            return False
        
        if order.is_complete:
            return False
        
        # Get provider
        provider_info = self.provider_manager.providers.get(order.provider)
        if not provider_info or not provider_info.service:
            return False
        
        # Cancel with provider
        success = provider_info.service.cancel_bet(order.provider_order_id)
        
        if success:
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.now()
            
            # Emit event
            await self._emit_event(TradeEvent(
                event_id=str(uuid.uuid4()),
                event_type="order_cancelled",
                timestamp=datetime.now(),
                order_id=order_id,
                provider=order.provider,
                data={}
            ))
        
        return success
    
    async def update_order(
        self,
        order_id: str,
        new_price: Optional[Decimal] = None,
        new_size: Optional[Decimal] = None
    ) -> bool:
        """
        Update an order's price or size.
        
        Args:
            order_id: Order ID to update
            new_price: New price (optional)
            new_size: New size (optional)
            
        Returns:
            True if successful
        """
        order = self.orders.get(order_id)
        if not order or order.is_complete:
            return False
        
        # Get provider
        provider_info = self.provider_manager.providers.get(order.provider)
        if not provider_info or not provider_info.service:
            return False
        
        # Update with provider
        result = provider_info.service.update_bet(
            bet_id=order.provider_order_id,
            new_price=float(new_price) if new_price else None,
            new_size=float(new_size) if new_size else None
        )
        
        if result.get("success"):
            order.requested_price = new_price or order.requested_price
            order.requested_size = new_size or order.requested_size
            order.updated_at = datetime.now()
            return True
        
        return False
    
    def get_open_orders(self, market_id: Optional[str] = None) -> List[Order]:
        """
        Get list of open orders.
        
        Args:
            market_id: Optional market filter
            
        Returns:
            List of open orders
        """
        open_orders = []
        for order in self.orders.values():
            if not order.is_complete:
                if not market_id or order.instruction.market_id == market_id:
                    open_orders.append(order)
        return open_orders
    
    def get_matched_bets(self, market_id: Optional[str] = None) -> List[Bet]:
        """
        Get list of matched bets.
        
        Args:
            market_id: Optional market filter
            
        Returns:
            List of matched bets
        """
        matched = []
        for bet in self.matched_bets.values():
            if not market_id or bet.market_id == market_id:
                matched.append(bet)
        return matched
    
    def get_market_exposure(self, market_id: str) -> Decimal:
        """
        Calculate total exposure for a market.
        
        Args:
            market_id: Market ID
            
        Returns:
            Total exposure amount
        """
        exposure = Decimal("0")
        
        # Add exposure from matched bets
        for bet in self.matched_bets.values():
            if bet.market_id == market_id:
                exposure += bet.liability
        
        # Add potential exposure from open orders
        for order in self.orders.values():
            if not order.is_complete and order.instruction.market_id == market_id:
                if order.instruction.side == OrderSide.LAY:
                    potential_liability = order.remaining_size * (order.requested_price - 1)
                    exposure += potential_liability
                else:
                    exposure += order.remaining_size
        
        return exposure
    
    def add_event_callback(self, callback: Callable):
        """Add callback for trade events."""
        self.event_callbacks.append(callback)
    
    async def start_monitoring(self):
        """Start order monitoring."""
        if self.is_running:
            return
        
        self.is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_orders())
        self.logger.info("Started trade executor monitoring")
    
    async def stop_monitoring(self):
        """Stop order monitoring."""
        self.is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Stopped trade executor monitoring")
    
    async def _monitor_orders(self):
        """Monitor open orders for updates."""
        while self.is_running:
            try:
                # Check each open order
                for order in list(self.orders.values()):
                    if order.is_complete:
                        continue
                    
                    # Check for timeout
                    if order.instruction.time_in_force:
                        elapsed = (datetime.now() - order.created_at).total_seconds()
                        if elapsed > order.instruction.time_in_force:
                            await self.cancel_order(order.order_id)
                    
                    # Update order status from provider
                    # (Implementation depends on provider capabilities)
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                self.logger.error(f"Error in order monitoring: {e}")
                await asyncio.sleep(5)
    
    def _create_order(self, instruction: TradeInstruction, provider: Optional[str]) -> Order:
        """Create order object from instruction."""
        order_id = str(uuid.uuid4())
        
        return Order(
            order_id=order_id,
            instruction=instruction,
            provider=provider or self.provider_manager.primary_provider,
            requested_size=instruction.size,
            requested_price=instruction.price,
            remaining_size=instruction.size,
            status=OrderStatus.PENDING,
            created_at=datetime.now()
        )
    
    def _create_error_report(self, instruction: TradeInstruction, error: str) -> ExecutionReport:
        """Create error execution report."""
        return ExecutionReport(
            report_id=str(uuid.uuid4()),
            order_id="",
            instruction=instruction,
            status=OrderStatus.FAILED,
            provider="",
            error_message=error,
            submitted_at=datetime.now()
        )
    
    def _is_duplicate(self, instruction: TradeInstruction) -> bool:
        """Check if instruction is duplicate."""
        # Create instruction signature
        sig = (
            instruction.market_id,
            instruction.selection_id,
            instruction.side,
            float(instruction.size),
            float(instruction.price) if instruction.price else None
        )
        
        # Check recent instructions
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.duplicate_window)
        
        # Clean old instructions
        self.recent_instructions = [
            (ts, s) for ts, s in self.recent_instructions
            if ts > cutoff
        ]
        
        # Check for duplicate
        for ts, prev_sig in self.recent_instructions:
            if prev_sig == sig:
                return True
        
        # Add to recent
        self.recent_instructions.append((now, sig))
        return False
    
    def _check_rate_limits(self, market_id: str) -> bool:
        """Check if rate limits allow order."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)
        
        # Clean old timestamps
        self.order_timestamps[market_id] = [
            ts for ts in self.order_timestamps[market_id]
            if ts > cutoff
        ]
        
        # Check per-minute limit
        if len(self.order_timestamps[market_id]) >= self.risk_limits.max_orders_per_minute:
            return False
        
        # Check per-market limit
        if self.market_order_counts[market_id] >= self.risk_limits.max_orders_per_market:
            return False
        
        # Update counters
        self.order_timestamps[market_id].append(now)
        self.market_order_counts[market_id] += 1
        
        return True
    
    async def _is_market_suspended(self, market_id: str, provider: Optional[str]) -> bool:
        """Check if market is suspended."""
        # Get market status from provider
        if provider:
            provider_info = self.provider_manager.providers.get(provider)
            if provider_info and provider_info.service:
                market_book = provider_info.service.get_market_book(market_id)
                if market_book:
                    return market_book.get("status") == "SUSPENDED"
        
        return False
    
    async def _emit_event(self, event: TradeEvent):
        """Emit trade event to callbacks."""
        for callback in self.event_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                self.logger.error(f"Error in event callback: {e}")