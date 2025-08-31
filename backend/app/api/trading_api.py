"""Trading API endpoints with WebSocket support."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime
import asyncio
import json
import logging

from app.trading.coordinator import TradeCoordinator
from app.trading.models import OrderSide, ExecutionStrategy
from app.server.provider_manager import ProviderManager
from app.server.connection_manager import ConnectionManager
from app.risk import RiskLimits
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses

class PlaceTradeRequest(BaseModel):
    """Request model for placing a trade."""
    market_id: str
    selection_id: str
    side: str  # "BACK" or "LAY"
    size: Decimal
    price: Decimal
    strategy: str = "SMART"
    provider: str = "betfair"
    
    
class ClosePositionRequest(BaseModel):
    """Request model for closing a position."""
    position_id: str
    size: Optional[Decimal] = None
    

class CashOutRequest(BaseModel):
    """Request model for cashing out."""
    position_id: str
    target_pnl: Optional[Decimal] = None
    

class StopLossRequest(BaseModel):
    """Request model for setting stop loss."""
    position_id: str
    stop_price: Decimal


# Initialize components (these would be dependency injected in production)
provider_manager = ProviderManager()
trade_coordinator: Optional[TradeCoordinator] = None
connection_manager = ConnectionManager()

# Create router
router = APIRouter(prefix="/api", tags=["trading"])


async def get_coordinator() -> TradeCoordinator:
    """Get or create trade coordinator."""
    global trade_coordinator
    if not trade_coordinator:
        trade_coordinator = TradeCoordinator(provider_manager)
        await trade_coordinator.start()
    return trade_coordinator


# REST API Endpoints

@router.post("/trade/place")
async def place_trade(
    request: PlaceTradeRequest,
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Place a new trade with risk management."""
    try:
        # Convert string side to enum
        side = OrderSide.BACK if request.side.upper() == "BACK" else OrderSide.LAY
        strategy = ExecutionStrategy[request.strategy.upper()]
        
        logger.info(f"Placing trade: market={request.market_id}, side={side}, size={request.size}")
        
        # Execute trade
        success, message, report = await coordinator.place_trade(
            market_id=request.market_id,
            selection_id=request.selection_id,
            side=side,
            size=request.size,
            price=request.price,
            strategy=strategy,
            provider=request.provider
        )
        
        response = {
            "success": success,
            "message": message
        }
        
        if report:
            response["execution_report"] = {
                "order_id": report.order_id,
                "status": report.status.value,
                "executed_size": str(report.executed_size),
                "executed_price": str(report.executed_price),
                "remaining_size": str(report.remaining_size)
            }
        
        # Broadcast update to WebSocket clients
        await connection_manager.broadcast({
            "type": "trade_update",
            "data": response
        })
        
        return response
        
    except AttributeError as e:
        logger.error(f"AttributeError in place_trade: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error placing trade: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade/cancel/{order_id}")
async def cancel_trade(
    order_id: str,
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Cancel an open order."""
    try:
        success = await coordinator.executor.cancel_order(order_id)
        
        return {
            "success": success,
            "order_id": order_id,
            "message": "Order cancelled" if success else "Failed to cancel order"
        }
        
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade/close")
async def close_position(
    request: ClosePositionRequest,
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Close a position."""
    try:
        success, message = await coordinator.close_position(
            request.position_id,
            request.size
        )
        
        response = {
            "success": success,
            "message": message,
            "position_id": request.position_id
        }
        
        # Broadcast update
        await connection_manager.broadcast({
            "type": "position_closed",
            "data": response
        })
        
        return response
        
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade/cashout")
async def cash_out(
    request: CashOutRequest,
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Cash out a position."""
    try:
        success, message, cash_value = await coordinator.cash_out_position(
            request.position_id,
            request.target_pnl
        )
        
        return {
            "success": success,
            "message": message,
            "position_id": request.position_id,
            "cash_out_value": str(cash_value)
        }
        
    except Exception as e:
        logger.error(f"Error cashing out: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade/hedge/{position_id}")
async def hedge_position(
    position_id: str,
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Hedge a position (green up)."""
    try:
        success, message = await coordinator.hedge_position(position_id)
        
        return {
            "success": success,
            "message": message,
            "position_id": position_id
        }
        
    except Exception as e:
        logger.error(f"Error hedging position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade/stoploss")
async def set_stop_loss(
    request: StopLossRequest,
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Set stop loss for a position."""
    try:
        success, message = await coordinator.set_stop_loss(
            request.position_id,
            request.stop_price
        )
        
        return {
            "success": success,
            "message": message,
            "position_id": request.position_id,
            "stop_price": str(request.stop_price)
        }
        
    except Exception as e:
        logger.error(f"Error setting stop loss: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Get all open positions."""
    try:
        positions = coordinator.get_positions()
        return {
            "positions": positions,
            "count": len(positions)
        }
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{position_id}")
async def get_position(
    position_id: str,
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Get specific position details."""
    try:
        position = coordinator.position_tracker.get_position(position_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        return coordinator._position_to_dict(position)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pnl")
async def get_pnl(
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Get P&L summary."""
    try:
        return coordinator.get_pnl_summary()
        
    except Exception as e:
        logger.error(f"Error getting P&L: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/limits")
async def get_risk_limits(
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Get risk limits and current usage."""
    try:
        return coordinator.get_risk_status()
        
    except Exception as e:
        logger.error(f"Error getting risk status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/recent")
async def get_recent_trades(
    limit: int = 50,
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Get recent trade history."""
    try:
        trades = coordinator.get_recent_trades(limit)
        return {
            "trades": trades,
            "count": len(trades)
        }
        
    except Exception as e:
        logger.error(f"Error getting recent trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats(
    coordinator: TradeCoordinator = Depends(get_coordinator)
) -> Dict[str, Any]:
    """Get trading statistics."""
    try:
        return {
            "trade_stats": coordinator.get_trade_stats(),
            "pnl": coordinator.get_pnl_summary(),
            "risk": coordinator.get_risk_status()
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket Endpoints

@router.websocket("/ws/positions")
async def websocket_positions(websocket: WebSocket):
    """WebSocket endpoint for real-time position updates."""
    await connection_manager.connect(websocket, "positions")
    coordinator = await get_coordinator()
    
    try:
        # Send initial positions
        positions = coordinator.get_positions()
        await websocket.send_json({
            "type": "positions_snapshot",
            "data": positions
        })
        
        # Keep connection alive and send updates
        while True:
            try:
                # Wait for client messages (ping/pong)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                # Send periodic position updates
                positions = coordinator.get_positions()
                await websocket.send_json({
                    "type": "positions_update",
                    "data": positions
                })
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected from positions")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)


@router.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket):
    """WebSocket endpoint for real-time trade updates."""
    await connection_manager.connect(websocket, "trades")
    coordinator = await get_coordinator()
    
    # Add callback to coordinator
    async def trade_callback(data):
        await websocket.send_json(data)
    
    coordinator.add_event_callback(trade_callback)
    
    try:
        # Send initial trade stats
        stats = coordinator.get_trade_stats()
        await websocket.send_json({
            "type": "trade_stats",
            "data": stats
        })
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        # Remove callback
        if trade_callback in coordinator.event_callbacks:
            coordinator.event_callbacks.remove(trade_callback)
        logger.info("WebSocket client disconnected from trades")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)


@router.websocket("/ws/pnl")
async def websocket_pnl(websocket: WebSocket):
    """WebSocket endpoint for real-time P&L updates."""
    await connection_manager.connect(websocket, "pnl")
    coordinator = await get_coordinator()
    
    try:
        while True:
            # Send P&L update every 5 seconds
            pnl = coordinator.get_pnl_summary()
            await websocket.send_json({
                "type": "pnl_update",
                "data": pnl,
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait or receive ping
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=5.0
                )
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                continue
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected from P&L")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)


@router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    """WebSocket endpoint for comprehensive monitoring."""
    await connection_manager.connect(websocket, "monitor")
    coordinator = await get_coordinator()
    
    try:
        while True:
            # Send comprehensive update
            monitor_data = {
                "type": "monitor_update",
                "timestamp": datetime.now().isoformat(),
                "positions": coordinator.get_positions(),
                "pnl": coordinator.get_pnl_summary(),
                "risk": coordinator.get_risk_status(),
                "stats": coordinator.get_trade_stats()
            }
            
            await websocket.send_json(monitor_data)
            
            # Wait 2 seconds between updates
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=2.0
                )
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                continue
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected from monitor")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)