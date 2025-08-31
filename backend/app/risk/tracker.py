"""Position tracker for real-time position management and P&L calculation."""

import asyncio
from typing import Dict, List, Optional, Set, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict
import uuid
import logging

from app.risk.models import (
    Position, PositionStatus, PositionSide,
    MarketExposure, ExposureReport, RiskMetrics,
    PnLStatement, PositionUpdate, RiskAlert
)
from app.trading.models import OrderStatus, OrderSide
from app.server.provider_manager import ProviderManager

logger = logging.getLogger(__name__)


class PositionTracker:
    """Tracks all positions and calculates P&L in real-time."""
    
    def __init__(self, provider_manager: ProviderManager):
        """Initialize position tracker.
        
        Args:
            provider_manager: Provider manager for market data
        """
        self.provider_manager = provider_manager
        
        # Position storage
        self.positions: Dict[str, Position] = {}  # position_id -> Position
        self.market_positions: Dict[str, List[str]] = defaultdict(list)  # market_id -> [position_ids]
        self.selection_positions: Dict[Tuple[str, str], List[str]] = defaultdict(list)  # (market_id, selection_id) -> [position_ids]
        
        # Order tracking
        self.order_to_position: Dict[str, str] = {}  # order_id -> position_id
        self.pending_orders: Dict[str, Dict] = {}  # order_id -> order_details
        
        # P&L tracking
        self.daily_pnl: Decimal = Decimal("0")
        self.total_commission: Decimal = Decimal("0")
        self.pnl_by_market: Dict[str, Decimal] = defaultdict(Decimal)
        self.pnl_by_strategy: Dict[str, Decimal] = defaultdict(Decimal)
        
        # Risk tracking
        self.total_exposure: Decimal = Decimal("0")
        self.market_exposures: Dict[str, MarketExposure] = {}
        
        # Event callbacks
        self.update_callbacks: List = []
        self.alert_callbacks: List = []
        
        # Background tasks
        self.update_task: Optional[asyncio.Task] = None
        self.reconciliation_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start position tracking."""
        logger.info("Starting position tracker")
        
        # Start background tasks
        self.update_task = asyncio.create_task(self._update_loop())
        self.reconciliation_task = asyncio.create_task(self._reconciliation_loop())
        
        # Load existing positions from persistence
        await self._load_positions()
        
    async def stop(self):
        """Stop position tracking."""
        logger.info("Stopping position tracker")
        
        # Cancel background tasks
        if self.update_task:
            self.update_task.cancel()
        if self.reconciliation_task:
            self.reconciliation_task.cancel()
        
        # Save positions
        await self._save_positions()
        
    def add_update_callback(self, callback):
        """Add position update callback."""
        self.update_callbacks.append(callback)
        
    def add_alert_callback(self, callback):
        """Add risk alert callback."""
        self.alert_callbacks.append(callback)
        
    async def open_position(
        self,
        market_id: str,
        selection_id: str,
        side: OrderSide,
        price: Decimal,
        size: Decimal,
        order_id: str,
        provider: str = "betfair",
        strategy: Optional[str] = None
    ) -> Position:
        """Open a new position or add to existing.
        
        Args:
            market_id: Market identifier
            selection_id: Selection identifier
            side: Order side (back/lay)
            price: Execution price
            size: Execution size
            order_id: Order identifier
            provider: Data provider
            strategy: Strategy name
            
        Returns:
            Updated position
        """
        # Check if we have an existing position
        existing = self._find_position(market_id, selection_id, side)
        
        if existing:
            # Add to existing position
            position = await self._add_to_position(existing, price, size)
        else:
            # Create new position
            position = await self._create_position(
                market_id, selection_id, side, price, size,
                provider, strategy
            )
        
        # Link order to position
        self.order_to_position[order_id] = position.position_id
        
        # Update exposures
        await self._update_market_exposure(market_id)
        
        # Trigger callbacks
        await self._trigger_position_update(
            position, "open" if not existing else "adjust", size, price
        )
        
        return position
        
    async def close_position(
        self,
        position_id: str,
        price: Decimal,
        size: Optional[Decimal] = None,
        order_id: Optional[str] = None
    ) -> Position:
        """Close or partially close a position.
        
        Args:
            position_id: Position identifier
            price: Exit price
            size: Size to close (None for full close)
            order_id: Order identifier
            
        Returns:
            Updated position
        """
        if position_id not in self.positions:
            raise ValueError(f"Position {position_id} not found")
        
        position = self.positions[position_id]
        
        # Determine close size
        close_size = size if size else position.current_size
        if close_size > position.current_size:
            close_size = position.current_size
        
        # Calculate P&L for this close
        if position.side == PositionSide.LONG:
            pnl = (price - position.entry_price) * close_size
        else:  # SHORT
            pnl = (position.entry_price - price) * close_size
        
        # Apply commission (assuming 2% for Betfair)
        commission = abs(pnl) * Decimal("0.02") if pnl > 0 else Decimal("0")
        net_pnl = pnl - commission
        
        # Update position
        position.exit_size += close_size
        position.current_size -= close_size
        position.realized_pnl += net_pnl
        position.commission += commission
        position.last_update = datetime.now()
        
        # Update exit price (weighted average)
        if position.exit_price:
            total_exit = position.exit_size - close_size
            position.exit_price = (
                (position.exit_price * total_exit + price * close_size) /
                position.exit_size
            )
        else:
            position.exit_price = price
        
        # Update status
        if position.current_size == 0:
            position.status = PositionStatus.CLOSED
        else:
            position.status = PositionStatus.PARTIALLY_CLOSED
        
        # Update P&L tracking
        self.daily_pnl += net_pnl
        self.total_commission += commission
        self.pnl_by_market[position.market_id] += net_pnl
        if position.strategy:
            self.pnl_by_strategy[position.strategy] += net_pnl
        
        # Link order if provided
        if order_id:
            self.order_to_position[order_id] = position_id
        
        # Update exposures
        await self._update_market_exposure(position.market_id)
        
        # Trigger callbacks
        update_type = "close" if position.status == PositionStatus.CLOSED else "partial_close"
        await self._trigger_position_update(position, update_type, close_size, price)
        
        return position
        
    async def update_position_price(self, position_id: str, current_price: Decimal):
        """Update position with current market price for unrealized P&L.
        
        Args:
            position_id: Position identifier
            current_price: Current market price
        """
        if position_id not in self.positions:
            return
        
        position = self.positions[position_id]
        
        # Calculate unrealized P&L
        if position.current_size > 0:
            if position.side == PositionSide.LONG:
                position.unrealized_pnl = (current_price - position.entry_price) * position.current_size
            else:  # SHORT
                position.unrealized_pnl = (position.entry_price - current_price) * position.current_size
            
            # Subtract potential commission
            if position.unrealized_pnl > 0:
                position.unrealized_pnl *= Decimal("0.98")  # 2% commission
        
        position.last_update = datetime.now()
        
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        return self.positions.get(position_id)
        
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [
            pos for pos in self.positions.values()
            if pos.status != PositionStatus.CLOSED
        ]
        
    def get_market_positions(self, market_id: str) -> List[Position]:
        """Get all positions for a market."""
        position_ids = self.market_positions.get(market_id, [])
        return [self.positions[pid] for pid in position_ids if pid in self.positions]
        
    def get_selection_positions(self, market_id: str, selection_id: str) -> List[Position]:
        """Get all positions for a selection."""
        position_ids = self.selection_positions.get((market_id, selection_id), [])
        return [self.positions[pid] for pid in position_ids if pid in self.positions]
        
    def get_net_position(self, market_id: str, selection_id: str) -> Tuple[Decimal, Decimal]:
        """Get net position for a selection.
        
        Returns:
            Tuple of (net_size, average_price)
        """
        positions = self.get_selection_positions(market_id, selection_id)
        
        long_size = Decimal("0")
        long_value = Decimal("0")
        short_size = Decimal("0")
        short_value = Decimal("0")
        
        for pos in positions:
            if pos.status != PositionStatus.CLOSED:
                if pos.side == PositionSide.LONG:
                    long_size += pos.current_size
                    long_value += pos.current_size * pos.entry_price
                else:
                    short_size += pos.current_size
                    short_value += pos.current_size * pos.entry_price
        
        net_size = long_size - short_size
        
        if net_size > 0:
            avg_price = long_value / long_size if long_size > 0 else Decimal("0")
        elif net_size < 0:
            avg_price = short_value / short_size if short_size > 0 else Decimal("0")
        else:
            avg_price = Decimal("0")
        
        return net_size, avg_price
        
    def get_market_exposure(self, market_id: str) -> Optional[MarketExposure]:
        """Get exposure for a market."""
        return self.market_exposures.get(market_id)
        
    def get_total_exposure(self) -> Decimal:
        """Get total portfolio exposure."""
        return self.total_exposure
        
    def get_pnl_statement(self, period_hours: int = 24) -> PnLStatement:
        """Get P&L statement for a period.
        
        Args:
            period_hours: Period in hours
            
        Returns:
            P&L statement
        """
        now = datetime.now()
        period_start = now - timedelta(hours=period_hours)
        
        # Calculate metrics
        positions_in_period = [
            pos for pos in self.positions.values()
            if pos.entry_time >= period_start
        ]
        
        num_wins = sum(1 for pos in positions_in_period if pos.realized_pnl > 0)
        num_losses = sum(1 for pos in positions_in_period if pos.realized_pnl < 0)
        num_trades = num_wins + num_losses
        
        win_rate = Decimal(num_wins) / Decimal(num_trades) * 100 if num_trades > 0 else Decimal("0")
        
        avg_win = (
            sum(pos.realized_pnl for pos in positions_in_period if pos.realized_pnl > 0) / num_wins
            if num_wins > 0 else Decimal("0")
        )
        
        avg_loss = (
            sum(abs(pos.realized_pnl) for pos in positions_in_period if pos.realized_pnl < 0) / num_losses
            if num_losses > 0 else Decimal("0")
        )
        
        total_volume = sum(pos.entry_size for pos in positions_in_period)
        
        return PnLStatement(
            period_start=period_start,
            period_end=now,
            gross_pnl=self.daily_pnl + self.total_commission,
            commission=self.total_commission,
            net_pnl=self.daily_pnl,
            realized_pnl=sum(pos.realized_pnl for pos in self.positions.values()),
            unrealized_pnl=sum(pos.unrealized_pnl for pos in self.positions.values()),
            pnl_by_market=dict(self.pnl_by_market),
            pnl_by_strategy=dict(self.pnl_by_strategy),
            num_trades=num_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_volume=total_volume,
            total_stake=total_volume
        )
        
    async def reconcile_with_provider(self, provider: str = "betfair"):
        """Reconcile positions with provider's records.
        
        Args:
            provider: Provider to reconcile with
        """
        logger.info(f"Reconciling positions with {provider}")
        
        try:
            # Get provider's view of positions
            provider_service = self.provider_manager.providers[provider].service
            
            # Get open orders
            open_orders = provider_service.get_open_orders()
            
            # Get matched bets
            matched_bets = provider_service.get_matched_bets()
            
            # Reconcile orders
            for order in open_orders:
                order_id = order.get("bet_id")
                if order_id not in self.order_to_position:
                    # Missing position for this order
                    logger.warning(f"Found untracked order: {order_id}")
                    # Could create position here if needed
            
            # Reconcile matched bets
            for bet in matched_bets:
                bet_id = bet.get("bet_id")
                if bet_id not in self.order_to_position:
                    logger.warning(f"Found untracked bet: {bet_id}")
            
            logger.info("Position reconciliation complete")
            
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            
    # Private methods
    
    def _find_position(
        self,
        market_id: str,
        selection_id: str,
        side: OrderSide
    ) -> Optional[Position]:
        """Find an open position matching criteria."""
        positions = self.get_selection_positions(market_id, selection_id)
        
        position_side = PositionSide.LONG if side == OrderSide.BACK else PositionSide.SHORT
        
        for pos in positions:
            if (pos.side == position_side and 
                pos.status != PositionStatus.CLOSED):
                return pos
        
        return None
        
    async def _create_position(
        self,
        market_id: str,
        selection_id: str,
        side: OrderSide,
        price: Decimal,
        size: Decimal,
        provider: str,
        strategy: Optional[str]
    ) -> Position:
        """Create a new position."""
        position_id = str(uuid.uuid4())
        position_side = PositionSide.LONG if side == OrderSide.BACK else PositionSide.SHORT
        
        position = Position(
            position_id=position_id,
            market_id=market_id,
            selection_id=selection_id,
            side=position_side,
            entry_price=price,
            entry_size=size,
            entry_time=datetime.now(),
            current_size=size,
            last_update=datetime.now(),
            status=PositionStatus.OPEN,
            provider=provider,
            strategy=strategy
        )
        
        # Store position
        self.positions[position_id] = position
        self.market_positions[market_id].append(position_id)
        self.selection_positions[(market_id, selection_id)].append(position_id)
        
        return position
        
    async def _add_to_position(
        self,
        position: Position,
        price: Decimal,
        size: Decimal
    ) -> Position:
        """Add to an existing position."""
        # Calculate new average price
        total_value = position.entry_price * position.current_size + price * size
        total_size = position.current_size + size
        
        position.entry_price = total_value / total_size
        position.entry_size += size
        position.current_size += size
        position.last_update = datetime.now()
        
        return position
        
    async def _update_market_exposure(self, market_id: str):
        """Update exposure for a market."""
        positions = self.get_market_positions(market_id)
        
        if not positions:
            if market_id in self.market_exposures:
                del self.market_exposures[market_id]
            return
        
        # Calculate exposures by selection
        selection_exposures = {}
        net_back_exposure = Decimal("0")
        net_lay_liability = Decimal("0")
        
        for pos in positions:
            if pos.status != PositionStatus.CLOSED:
                selection_id = pos.selection_id
                
                if pos.side == PositionSide.LONG:
                    # Back bet exposure is stake
                    exposure = pos.current_size
                    net_back_exposure += exposure
                else:
                    # Lay bet liability is (price - 1) * stake
                    liability = (pos.entry_price - 1) * pos.current_size
                    net_lay_liability += liability
                    exposure = liability
                
                if selection_id not in selection_exposures:
                    selection_exposures[selection_id] = Decimal("0")
                selection_exposures[selection_id] += exposure
        
        # Calculate max loss (worst case scenario)
        max_loss = max(
            net_back_exposure,  # All backs lose
            net_lay_liability,  # All lays lose
            max(selection_exposures.values()) if selection_exposures else Decimal("0")
        )
        
        # Determine if hedging is needed
        hedge_required = False
        hedge_amount = None
        hedge_selection = None
        hedge_price = None
        
        # Simple hedge detection: if one selection has much higher exposure
        if len(selection_exposures) > 1:
            exposures = list(selection_exposures.values())
            max_exposure = max(exposures)
            min_exposure = min(exposures)
            
            if max_exposure > min_exposure * Decimal("1.5"):
                hedge_required = True
                # Find selection with lowest exposure to hedge on
                for sel_id, exp in selection_exposures.items():
                    if exp == min_exposure:
                        hedge_selection = sel_id
                        hedge_amount = (max_exposure - min_exposure) / 2
                        hedge_price = Decimal("2.0")  # Placeholder
                        break
        
        # Create exposure report
        exposure = MarketExposure(
            market_id=market_id,
            market_name=f"Market {market_id}",  # Would get from provider
            selection_exposures=selection_exposures,
            net_back_exposure=net_back_exposure,
            net_lay_liability=net_lay_liability,
            max_loss=max_loss,
            open_positions=len([p for p in positions if p.status != PositionStatus.CLOSED]),
            total_stake=sum(p.current_size for p in positions if p.status != PositionStatus.CLOSED),
            hedge_required=hedge_required,
            hedge_amount=hedge_amount,
            hedge_selection=hedge_selection,
            hedge_price=hedge_price
        )
        
        self.market_exposures[market_id] = exposure
        
        # Update total exposure
        self.total_exposure = sum(
            exp.max_loss for exp in self.market_exposures.values()
        )
        
    async def _trigger_position_update(
        self,
        position: Position,
        update_type: str,
        size_change: Decimal,
        price: Decimal
    ):
        """Trigger position update callbacks."""
        update = PositionUpdate(
            timestamp=datetime.now(),
            position_id=position.position_id,
            update_type=update_type,
            size_change=size_change,
            price=price,
            pnl_impact=position.realized_pnl,
            new_size=position.current_size,
            new_avg_price=position.entry_price,
            new_pnl=position.realized_pnl + position.unrealized_pnl,
            source="trade",
            order_id=None
        )
        
        for callback in self.update_callbacks:
            try:
                await callback(update)
            except Exception as e:
                logger.error(f"Update callback failed: {e}")
                
    async def _update_loop(self):
        """Background task to update positions with market prices."""
        while True:
            try:
                await asyncio.sleep(5)  # Update every 5 seconds
                
                # Get current prices for all open positions
                for position in self.get_open_positions():
                    try:
                        # Get market book from provider
                        provider = self.provider_manager.providers.get(position.provider)
                        if provider and provider.service:
                            market_book = provider.service.get_market_book(position.market_id)
                            
                            if market_book:
                                # Find runner
                                runners = market_book.get("runners", [])
                                for runner in runners:
                                    if str(runner.get("selectionId")) == position.selection_id:
                                        # Get best back price
                                        ex = runner.get("ex", {})
                                        back_prices = ex.get("availableToBack", [])
                                        if back_prices:
                                            current_price = Decimal(str(back_prices[0]["price"]))
                                            await self.update_position_price(
                                                position.position_id,
                                                current_price
                                            )
                                        break
                                        
                    except Exception as e:
                        logger.error(f"Failed to update position {position.position_id}: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                
    async def _reconciliation_loop(self):
        """Background task for periodic reconciliation."""
        while True:
            try:
                await asyncio.sleep(300)  # Reconcile every 5 minutes
                await self.reconcile_with_provider()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reconciliation loop error: {e}")
                
    async def _load_positions(self):
        """Load positions from persistence."""
        # TODO: Implement SQLite loading
        logger.info("Loading positions from persistence")
        
    async def _save_positions(self):
        """Save positions to persistence."""
        # TODO: Implement SQLite saving
        logger.info("Saving positions to persistence")