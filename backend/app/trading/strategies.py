"""Execution strategies for different trading scenarios."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List
import uuid

from .models import (
    TradeInstruction,
    ExecutionReport,
    OrderStatus,
    OrderSide,
    OrderType,
    ExecutionStrategy,
    Fill
)


class BaseExecutionStrategy(ABC):
    """Base class for execution strategies."""
    
    def __init__(self):
        """Initialize strategy."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def execute(
        self,
        instruction: TradeInstruction,
        executor: Any,  # TradeExecutor type
        provider: Optional[str] = None
    ) -> ExecutionReport:
        """
        Execute trade with strategy.
        
        Args:
            instruction: Trade instruction
            executor: Trade executor instance
            provider: Optional specific provider
            
        Returns:
            ExecutionReport with results
        """
        pass
    
    def _create_report(
        self,
        instruction: TradeInstruction,
        status: OrderStatus,
        provider: str,
        executed_size: Decimal = Decimal("0"),
        executed_price: Optional[Decimal] = None,
        error: Optional[str] = None
    ) -> ExecutionReport:
        """Create execution report."""
        return ExecutionReport(
            report_id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            instruction=instruction,
            status=status,
            provider=provider,
            executed_size=executed_size,
            executed_price=executed_price,
            remaining_size=instruction.size - executed_size,
            submitted_at=datetime.now(),
            executed_at=datetime.now() if executed_size > 0 else None,
            error_message=error
        )


class AggressiveStrategy(BaseExecutionStrategy):
    """
    Aggressive execution strategy - crosses the spread immediately.
    
    Takes best available price to ensure immediate execution.
    """
    
    async def execute(
        self,
        instruction: TradeInstruction,
        executor: Any,
        provider: Optional[str] = None
    ) -> ExecutionReport:
        """Execute aggressively by crossing the spread."""
        start_time = datetime.now()
        
        # Get best provider if not specified
        if not provider:
            provider = executor.provider_manager.primary_provider
        
        # Get market book for best prices
        provider_info = executor.provider_manager.providers.get(provider)
        if not provider_info or not provider_info.service:
            return self._create_report(
                instruction, OrderStatus.FAILED, provider or "",
                error="Provider not available"
            )
        
        market_book = provider_info.service.get_market_book(instruction.market_id)
        if not market_book:
            # Fall back to limit order at requested price
            self.logger.warning("Market book not available, using limit price")
            execution_price = instruction.price
        else:
            # Find best available price to cross spread
            execution_price = self._get_aggressive_price(
                market_book,
                instruction.selection_id,
                instruction.side
            )
            
            if not execution_price:
                execution_price = instruction.price
        
        # Adjust instruction for aggressive execution
        aggressive_instruction = TradeInstruction(
            market_id=instruction.market_id,
            selection_id=instruction.selection_id,
            side=instruction.side,
            size=instruction.size,
            price=execution_price,
            order_type=OrderType.LIMIT,
            persistence=instruction.persistence,
            client_ref=instruction.client_ref
        )
        
        # Place order
        try:
            result = await executor.place_order_with_provider(aggressive_instruction, provider)
            
            if result.get("success"):
                latency = (datetime.now() - start_time).total_seconds() * 1000
                
                return ExecutionReport(
                    report_id=str(uuid.uuid4()),
                    order_id=result.get("bet_id", ""),
                    instruction=instruction,
                    status=OrderStatus.MATCHED if result.get("size_matched", 0) == float(instruction.size) 
                           else OrderStatus.PARTIALLY_MATCHED,
                    provider=provider,
                    executed_size=Decimal(str(result.get("size_matched", 0))),
                    executed_price=Decimal(str(result.get("average_price_matched", execution_price))),
                    remaining_size=instruction.size - Decimal(str(result.get("size_matched", 0))),
                    submitted_at=start_time,
                    executed_at=datetime.now(),
                    latency_ms=latency
                )
            else:
                return self._create_report(
                    instruction, OrderStatus.FAILED, provider,
                    error=result.get("error", "Order failed")
                )
                
        except Exception as e:
            self.logger.error(f"Aggressive execution failed: {e}")
            return self._create_report(
                instruction, OrderStatus.FAILED, provider,
                error=str(e)
            )
    
    def _get_aggressive_price(
        self,
        market_book: Dict[str, Any],
        selection_id: str,
        side: OrderSide
    ) -> Optional[Decimal]:
        """Get aggressive price to cross spread."""
        # Find runner in market book
        runners = market_book.get("runners", [])
        for runner in runners:
            if str(runner.get("selectionId")) == str(selection_id):
                if side == OrderSide.BACK:
                    # For back bet, take best lay price (higher)
                    available_to_lay = runner.get("ex", {}).get("availableToLay", [])
                    if available_to_lay:
                        return Decimal(str(available_to_lay[0].get("price")))
                else:  # LAY
                    # For lay bet, take best back price (lower)
                    available_to_back = runner.get("ex", {}).get("availableToBack", [])
                    if available_to_back:
                        return Decimal(str(available_to_back[0].get("price")))
        
        return None


class PassiveStrategy(BaseExecutionStrategy):
    """
    Passive execution strategy - joins the queue at best price.
    
    Places limit order at top of book to wait for execution.
    """
    
    async def execute(
        self,
        instruction: TradeInstruction,
        executor: Any,
        provider: Optional[str] = None
    ) -> ExecutionReport:
        """Execute passively by joining the queue."""
        start_time = datetime.now()
        
        # Get best provider if not specified
        if not provider:
            provider = executor.provider_manager.primary_provider
        
        # Get market book for best prices
        provider_info = executor.provider_manager.providers.get(provider)
        if not provider_info or not provider_info.service:
            return self._create_report(
                instruction, OrderStatus.FAILED, provider or "",
                error="Provider not available"
            )
        
        market_book = provider_info.service.get_market_book(instruction.market_id)
        if market_book:
            # Find best price to join queue
            execution_price = self._get_passive_price(
                market_book,
                instruction.selection_id,
                instruction.side
            )
            
            if not execution_price:
                execution_price = instruction.price
        else:
            execution_price = instruction.price
        
        # Create passive order
        passive_instruction = TradeInstruction(
            market_id=instruction.market_id,
            selection_id=instruction.selection_id,
            side=instruction.side,
            size=instruction.size,
            price=execution_price,
            order_type=OrderType.LIMIT,
            persistence=instruction.persistence,
            client_ref=instruction.client_ref
        )
        
        # Place order
        try:
            result = await executor.place_order_with_provider(passive_instruction, provider)
            
            if result.get("success"):
                # For passive orders, typically not immediately matched
                return ExecutionReport(
                    report_id=str(uuid.uuid4()),
                    order_id=result.get("bet_id", ""),
                    instruction=instruction,
                    status=OrderStatus.SUBMITTED if result.get("size_matched", 0) == 0
                           else OrderStatus.PARTIALLY_MATCHED,
                    provider=provider,
                    executed_size=Decimal(str(result.get("size_matched", 0))),
                    executed_price=execution_price if result.get("size_matched", 0) > 0 else None,
                    remaining_size=instruction.size - Decimal(str(result.get("size_matched", 0))),
                    submitted_at=start_time,
                    executed_at=datetime.now() if result.get("size_matched", 0) > 0 else None,
                    latency_ms=(datetime.now() - start_time).total_seconds() * 1000
                )
            else:
                return self._create_report(
                    instruction, OrderStatus.FAILED, provider,
                    error=result.get("error", "Order failed")
                )
                
        except Exception as e:
            self.logger.error(f"Passive execution failed: {e}")
            return self._create_report(
                instruction, OrderStatus.FAILED, provider,
                error=str(e)
            )
    
    def _get_passive_price(
        self,
        market_book: Dict[str, Any],
        selection_id: str,
        side: OrderSide
    ) -> Optional[Decimal]:
        """Get passive price to join queue."""
        # Find runner in market book
        runners = market_book.get("runners", [])
        for runner in runners:
            if str(runner.get("selectionId")) == str(selection_id):
                if side == OrderSide.BACK:
                    # For back bet, match best back price
                    available_to_back = runner.get("ex", {}).get("availableToBack", [])
                    if available_to_back:
                        return Decimal(str(available_to_back[0].get("price")))
                else:  # LAY
                    # For lay bet, match best lay price
                    available_to_lay = runner.get("ex", {}).get("availableToLay", [])
                    if available_to_lay:
                        return Decimal(str(available_to_lay[0].get("price")))
        
        return None


class IcebergStrategy(BaseExecutionStrategy):
    """
    Iceberg execution strategy - hides large order size.
    
    Breaks large orders into smaller chunks to avoid market impact.
    """
    
    def __init__(self, chunk_size: Decimal = Decimal("10"), interval_seconds: int = 5):
        """
        Initialize iceberg strategy.
        
        Args:
            chunk_size: Size of each chunk
            interval_seconds: Seconds between chunks
        """
        super().__init__()
        self.chunk_size = chunk_size
        self.interval_seconds = interval_seconds
    
    async def execute(
        self,
        instruction: TradeInstruction,
        executor: Any,
        provider: Optional[str] = None
    ) -> ExecutionReport:
        """Execute as iceberg by breaking into chunks."""
        start_time = datetime.now()
        
        if not provider:
            provider = executor.provider_manager.primary_provider
        
        # Calculate chunks
        total_size = instruction.size
        num_chunks = int(total_size / self.chunk_size)
        if total_size % self.chunk_size > 0:
            num_chunks += 1
        
        # Execute chunks
        total_executed = Decimal("0")
        total_value = Decimal("0")
        fills: List[Fill] = []
        last_error = None
        
        for i in range(num_chunks):
            # Calculate chunk size
            remaining = total_size - total_executed
            chunk_size = min(self.chunk_size, remaining)
            
            if chunk_size <= 0:
                break
            
            # Create chunk instruction
            chunk_instruction = TradeInstruction(
                market_id=instruction.market_id,
                selection_id=instruction.selection_id,
                side=instruction.side,
                size=chunk_size,
                price=instruction.price,
                order_type=instruction.order_type,
                persistence=instruction.persistence,
                client_ref=f"{instruction.client_ref}_chunk_{i}" if instruction.client_ref else None
            )
            
            # Execute chunk
            try:
                result = await executor.place_order_with_provider(chunk_instruction, provider)
                
                if result.get("success"):
                    executed = Decimal(str(result.get("size_matched", 0)))
                    price = Decimal(str(result.get("average_price_matched", instruction.price)))
                    
                    if executed > 0:
                        total_executed += executed
                        total_value += executed * price
                        
                        fills.append(Fill(
                            fill_id=str(uuid.uuid4()),
                            size=executed,
                            price=price,
                            timestamp=datetime.now()
                        ))
                    
                    # Stop if chunk not fully filled (market conditions changed)
                    if executed < chunk_size * Decimal("0.9"):  # 90% threshold
                        self.logger.warning(f"Chunk {i} only {executed}/{chunk_size} filled, stopping")
                        break
                else:
                    last_error = result.get("error", "Chunk execution failed")
                    self.logger.error(f"Chunk {i} failed: {last_error}")
                    
            except Exception as e:
                last_error = str(e)
                self.logger.error(f"Chunk {i} exception: {e}")
            
            # Wait between chunks (except last one)
            if i < num_chunks - 1 and total_executed < total_size:
                await asyncio.sleep(self.interval_seconds)
        
        # Calculate average price
        avg_price = total_value / total_executed if total_executed > 0 else None
        
        # Determine final status
        if total_executed == total_size:
            status = OrderStatus.MATCHED
        elif total_executed > 0:
            status = OrderStatus.PARTIALLY_MATCHED
        else:
            status = OrderStatus.FAILED
        
        return ExecutionReport(
            report_id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            instruction=instruction,
            status=status,
            provider=provider,
            executed_size=total_executed,
            executed_price=avg_price,
            remaining_size=total_size - total_executed,
            fills=fills,
            submitted_at=start_time,
            executed_at=datetime.now() if total_executed > 0 else None,
            latency_ms=(datetime.now() - start_time).total_seconds() * 1000,
            error_message=last_error if status == OrderStatus.FAILED else None
        )


class TWAPStrategy(BaseExecutionStrategy):
    """
    Time-Weighted Average Price (TWAP) execution strategy.
    
    Executes order over time period to achieve average price.
    """
    
    def __init__(self, duration_seconds: int = 60, num_slices: int = 6):
        """
        Initialize TWAP strategy.
        
        Args:
            duration_seconds: Total execution duration
            num_slices: Number of time slices
        """
        super().__init__()
        self.duration_seconds = duration_seconds
        self.num_slices = num_slices
    
    async def execute(
        self,
        instruction: TradeInstruction,
        executor: Any,
        provider: Optional[str] = None
    ) -> ExecutionReport:
        """Execute TWAP over time period."""
        start_time = datetime.now()
        
        if not provider:
            provider = executor.provider_manager.primary_provider
        
        # Calculate slices
        slice_size = instruction.size / self.num_slices
        slice_interval = self.duration_seconds / self.num_slices
        
        # Execute slices
        total_executed = Decimal("0")
        total_value = Decimal("0")
        fills: List[Fill] = []
        
        for i in range(self.num_slices):
            slice_time = datetime.now()
            
            # Check if we should stop (market conditions, etc.)
            if (slice_time - start_time).total_seconds() > self.duration_seconds * 1.5:
                self.logger.warning("TWAP execution taking too long, stopping")
                break
            
            # Create slice instruction
            remaining = instruction.size - total_executed
            current_slice_size = min(slice_size, remaining)
            
            if current_slice_size <= 0:
                break
            
            slice_instruction = TradeInstruction(
                market_id=instruction.market_id,
                selection_id=instruction.selection_id,
                side=instruction.side,
                size=current_slice_size,
                price=instruction.price,
                order_type=OrderType.LIMIT,
                strategy=ExecutionStrategy.AGGRESSIVE,  # Use aggressive for each slice
                persistence=instruction.persistence,
                client_ref=f"{instruction.client_ref}_twap_{i}" if instruction.client_ref else None
            )
            
            # Execute slice aggressively
            try:
                aggressive_strategy = AggressiveStrategy()
                slice_report = await aggressive_strategy.execute(slice_instruction, executor, provider)
                
                if slice_report.executed_size > 0:
                    total_executed += slice_report.executed_size
                    total_value += slice_report.executed_size * slice_report.executed_price
                    
                    fills.append(Fill(
                        fill_id=str(uuid.uuid4()),
                        size=slice_report.executed_size,
                        price=slice_report.executed_price,
                        timestamp=datetime.now()
                    ))
                
            except Exception as e:
                self.logger.error(f"TWAP slice {i} failed: {e}")
            
            # Wait for next slice (except last)
            if i < self.num_slices - 1:
                await asyncio.sleep(slice_interval)
        
        # Calculate TWAP
        twap = total_value / total_executed if total_executed > 0 else None
        
        # Determine status
        if total_executed == instruction.size:
            status = OrderStatus.MATCHED
        elif total_executed > 0:
            status = OrderStatus.PARTIALLY_MATCHED
        else:
            status = OrderStatus.FAILED
        
        return ExecutionReport(
            report_id=str(uuid.uuid4()),
            order_id=str(uuid.uuid4()),
            instruction=instruction,
            status=status,
            provider=provider,
            executed_size=total_executed,
            executed_price=twap,
            remaining_size=instruction.size - total_executed,
            fills=fills,
            submitted_at=start_time,
            executed_at=datetime.now() if total_executed > 0 else None,
            latency_ms=(datetime.now() - start_time).total_seconds() * 1000
        )


class SmartStrategy(BaseExecutionStrategy):
    """
    Smart execution strategy - intelligently routes orders.
    
    Analyzes market conditions and chooses best execution approach.
    """
    
    async def execute(
        self,
        instruction: TradeInstruction,
        executor: Any,
        provider: Optional[str] = None
    ) -> ExecutionReport:
        """Execute with smart routing logic."""
        # Analyze order size
        is_large_order = instruction.size > Decimal("50")
        
        # Get market conditions
        if not provider:
            provider = executor.provider_manager.primary_provider
        
        provider_info = executor.provider_manager.providers.get(provider)
        if not provider_info or not provider_info.service:
            return self._create_report(
                instruction, OrderStatus.FAILED, provider or "",
                error="Provider not available"
            )
        
        market_book = provider_info.service.get_market_book(instruction.market_id)
        
        # Determine best strategy based on conditions
        if instruction.order_type == OrderType.MARKET:
            # Use aggressive for market orders
            strategy = AggressiveStrategy()
        elif is_large_order:
            # Use iceberg for large orders
            strategy = IcebergStrategy()
        elif self._has_good_liquidity(market_book, instruction):
            # Use aggressive if good liquidity
            strategy = AggressiveStrategy()
        else:
            # Default to passive
            strategy = PassiveStrategy()
        
        self.logger.info(f"Smart router selected {strategy.__class__.__name__}")
        
        # Execute with selected strategy
        return await strategy.execute(instruction, executor, provider)
    
    def _has_good_liquidity(
        self,
        market_book: Optional[Dict[str, Any]],
        instruction: TradeInstruction
    ) -> bool:
        """Check if market has good liquidity for order."""
        if not market_book:
            return False
        
        # Find runner
        runners = market_book.get("runners", [])
        for runner in runners:
            if str(runner.get("selectionId")) == str(instruction.selection_id):
                if instruction.side == OrderSide.BACK:
                    available = runner.get("ex", {}).get("availableToLay", [])
                else:
                    available = runner.get("ex", {}).get("availableToBack", [])
                
                # Check if enough liquidity at top of book
                if available:
                    top_level_size = Decimal(str(available[0].get("size", 0)))
                    return top_level_size >= instruction.size
        
        return False


class ExecutionStrategyFactory:
    """Factory for creating execution strategies."""
    
    def __init__(self):
        """Initialize factory."""
        self.strategies = {
            ExecutionStrategy.AGGRESSIVE: AggressiveStrategy,
            ExecutionStrategy.PASSIVE: PassiveStrategy,
            ExecutionStrategy.ICEBERG: IcebergStrategy,
            ExecutionStrategy.TWAP: TWAPStrategy,
            ExecutionStrategy.SMART: SmartStrategy
        }
    
    def get_strategy(self, strategy_type: ExecutionStrategy) -> BaseExecutionStrategy:
        """
        Get strategy instance.
        
        Args:
            strategy_type: Type of strategy
            
        Returns:
            Strategy instance
        """
        strategy_class = self.strategies.get(strategy_type, SmartStrategy)
        return strategy_class()