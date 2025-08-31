"""Trade audit and event logging system."""

import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from collections import deque
import aiofiles

from .models import TradeEvent, Order, Bet, ExecutionReport


class TradeAuditLogger:
    """
    Comprehensive audit logging for all trading activity.
    
    Features:
    - Persistent audit trail to file
    - In-memory event buffer
    - Event filtering and querying
    - Compliance reporting
    """
    
    def __init__(
        self,
        log_dir: str = "logs/trading",
        max_memory_events: int = 10000
    ):
        """
        Initialize audit logger.
        
        Args:
            log_dir: Directory for audit logs
            max_memory_events: Maximum events to keep in memory
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_memory_events = max_memory_events
        self.memory_events = deque(maxlen=max_memory_events)
        
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Current log file
        self.current_log_file = self._get_log_file_path()
        
        # Event statistics
        self.event_counts = {}
        self.total_events = 0
    
    def _get_log_file_path(self) -> Path:
        """Get path for current day's log file."""
        date_str = datetime.now().strftime("%Y%m%d")
        return self.log_dir / f"trade_audit_{date_str}.jsonl"
    
    async def log_event(self, event: TradeEvent):
        """
        Log a trade event.
        
        Args:
            event: Trade event to log
        """
        # Update statistics
        self.total_events += 1
        event_type = event.event_type
        self.event_counts[event_type] = self.event_counts.get(event_type, 0) + 1
        
        # Add to memory buffer
        self.memory_events.append(event)
        
        # Persist to file
        await self._write_to_file(event)
        
        # Log to standard logger
        self.logger.info(event.to_audit_log())
    
    async def _write_to_file(self, event: TradeEvent):
        """Write event to audit file."""
        try:
            # Check if we need to rotate to new day's file
            current_file = self._get_log_file_path()
            if current_file != self.current_log_file:
                self.current_log_file = current_file
            
            # Convert event to JSON
            event_dict = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "order_id": event.order_id,
                "bet_id": event.bet_id,
                "market_id": event.market_id,
                "provider": event.provider,
                "data": event.data,
                "user_id": event.user_id,
                "ip_address": event.ip_address
            }
            
            # Append to file
            async with aiofiles.open(self.current_log_file, mode='a') as f:
                await f.write(json.dumps(event_dict) + '\n')
                
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")
    
    def get_recent_events(
        self,
        event_type: Optional[str] = None,
        order_id: Optional[str] = None,
        market_id: Optional[str] = None,
        limit: int = 100
    ) -> List[TradeEvent]:
        """
        Get recent events from memory buffer.
        
        Args:
            event_type: Filter by event type
            order_id: Filter by order ID
            market_id: Filter by market ID
            limit: Maximum events to return
            
        Returns:
            List of matching events
        """
        events = []
        
        for event in reversed(self.memory_events):
            # Apply filters
            if event_type and event.event_type != event_type:
                continue
            if order_id and event.order_id != order_id:
                continue
            if market_id and event.market_id != market_id:
                continue
            
            events.append(event)
            
            if len(events) >= limit:
                break
        
        return events
    
    async def load_events_from_file(
        self,
        date: datetime,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Load events from audit file.
        
        Args:
            date: Date to load events for
            event_type: Optional event type filter
            
        Returns:
            List of event dictionaries
        """
        date_str = date.strftime("%Y%m%d")
        log_file = self.log_dir / f"trade_audit_{date_str}.jsonl"
        
        if not log_file.exists():
            return []
        
        events = []
        
        try:
            async with aiofiles.open(log_file, mode='r') as f:
                async for line in f:
                    if line.strip():
                        event = json.loads(line)
                        if not event_type or event.get("event_type") == event_type:
                            events.append(event)
                            
        except Exception as e:
            self.logger.error(f"Failed to load audit log: {e}")
        
        return events
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get audit statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            "total_events": self.total_events,
            "event_counts": dict(self.event_counts),
            "memory_buffer_size": len(self.memory_events),
            "current_log_file": str(self.current_log_file)
        }
    
    async def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate compliance report for date range.
        
        Args:
            start_date: Start date
            end_date: End date  
            output_file: Optional output file path
            
        Returns:
            Compliance report data
        """
        report = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_orders": 0,
                "total_matched": 0,
                "total_cancelled": 0,
                "total_failed": 0
            },
            "by_market": {},
            "by_provider": {},
            "suspicious_activity": []
        }
        
        # Load events for each day in range
        current_date = start_date
        while current_date <= end_date:
            events = await self.load_events_from_file(current_date)
            
            for event in events:
                event_type = event.get("event_type")
                
                # Update summary
                if event_type == "order_placed":
                    report["summary"]["total_orders"] += 1
                elif event_type == "order_matched":
                    report["summary"]["total_matched"] += 1
                elif event_type == "order_cancelled":
                    report["summary"]["total_cancelled"] += 1
                elif event_type == "order_failed":
                    report["summary"]["total_failed"] += 1
                
                # Track by market
                market_id = event.get("market_id")
                if market_id:
                    if market_id not in report["by_market"]:
                        report["by_market"][market_id] = {"orders": 0, "matched": 0}
                    if event_type == "order_placed":
                        report["by_market"][market_id]["orders"] += 1
                    elif event_type == "order_matched":
                        report["by_market"][market_id]["matched"] += 1
                
                # Track by provider
                provider = event.get("provider")
                if provider:
                    if provider not in report["by_provider"]:
                        report["by_provider"][provider] = {"orders": 0, "matched": 0}
                    if event_type == "order_placed":
                        report["by_provider"][provider]["orders"] += 1
                    elif event_type == "order_matched":
                        report["by_provider"][provider]["matched"] += 1
                
                # Check for suspicious patterns
                if self._is_suspicious(event):
                    report["suspicious_activity"].append(event)
            
            current_date = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
            current_date = current_date + timedelta(days=1)
        
        # Save report if output file specified
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
        
        return report
    
    def _is_suspicious(self, event: Dict[str, Any]) -> bool:
        """
        Check if event shows suspicious activity.
        
        Args:
            event: Event to check
            
        Returns:
            True if suspicious
        """
        # Example suspicious patterns:
        # - Very large order sizes
        # - Rapid order cancellations
        # - Unusual time patterns
        
        data = event.get("data", {})
        
        # Check for large orders
        size = data.get("size")
        if size and size > 1000:
            return True
        
        # Add more suspicious pattern detection as needed
        
        return False


class TradeEventBus:
    """
    Event bus for distributing trade events to subscribers.
    
    Allows different components to subscribe to specific event types.
    """
    
    def __init__(self, audit_logger: Optional[TradeAuditLogger] = None):
        """
        Initialize event bus.
        
        Args:
            audit_logger: Optional audit logger
        """
        self.subscribers: Dict[str, List[Callable]] = {}
        self.audit_logger = audit_logger
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Event queue for async processing
        self.event_queue = asyncio.Queue()
        self.is_running = False
        self._processor_task = None
    
    def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to event type.
        
        Args:
            event_type: Event type to subscribe to (use "*" for all)
            callback: Callback function
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        self.subscribers[event_type].append(callback)
        self.logger.debug(f"Subscribed to {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """
        Unsubscribe from event type.
        
        Args:
            event_type: Event type
            callback: Callback to remove
        """
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(callback)
    
    async def emit(self, event: TradeEvent):
        """
        Emit event to subscribers.
        
        Args:
            event: Event to emit
        """
        # Log to audit trail
        if self.audit_logger:
            await self.audit_logger.log_event(event)
        
        # Add to queue for async processing
        await self.event_queue.put(event)
    
    async def start(self):
        """Start event processing."""
        if self.is_running:
            return
        
        self.is_running = True
        self._processor_task = asyncio.create_task(self._process_events())
        self.logger.info("Started trade event bus")
    
    async def stop(self):
        """Stop event processing."""
        self.is_running = False
        
        if self._processor_task:
            # Process remaining events
            while not self.event_queue.empty():
                await asyncio.sleep(0.1)
            
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped trade event bus")
    
    async def _process_events(self):
        """Process events from queue."""
        while self.is_running:
            try:
                # Get event from queue
                event = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=1.0
                )
                
                # Get subscribers for this event type
                callbacks = []
                
                # Specific subscribers
                if event.event_type in self.subscribers:
                    callbacks.extend(self.subscribers[event.event_type])
                
                # Wildcard subscribers
                if "*" in self.subscribers:
                    callbacks.extend(self.subscribers["*"])
                
                # Call all callbacks
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(event)
                        else:
                            callback(event)
                    except Exception as e:
                        self.logger.error(f"Error in event callback: {e}")
                        
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")
                await asyncio.sleep(0.1)