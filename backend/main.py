"""FastAPI main application."""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.server import ProviderManager, ConnectionManager, WebSocketMessage, MessageType
from app.server.models import ProviderInfo, MatchListResponse, MatchDetailResponse
from app.config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load settings
settings = Settings()

# Global managers
provider_manager = ProviderManager(logger)
connection_manager = ConnectionManager(logger)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Tennis Trading API Server...")
    
    # Parse enabled providers from environment
    enabled_providers = os.getenv("ENABLED_PROVIDERS", "betfair").split(",")
    primary_provider = os.getenv("PRIMARY_PROVIDER", "betfair")
    
    # Initialize providers
    await provider_manager.initialize(enabled_providers, primary_provider)
    
    # Connect to all providers
    await provider_manager.connect_all()
    
    # Start monitoring
    await provider_manager.start_monitoring()
    
    # Start WebSocket ping interval
    await connection_manager.start_ping_interval()
    
    # Set up provider update callback
    async def broadcast_updates(data):
        """Broadcast provider updates to WebSocket clients."""
        if data.get("type") == "matches_update":
            message = WebSocketMessage(
                type=MessageType.MATCH_UPDATE,
                data={"matches": [m.id for m in data.get("matches", [])]},
                timestamp=datetime.now()
            )
            await connection_manager.broadcast(message)
        elif data.get("type") == "provider_failover":
            message = WebSocketMessage(
                type=MessageType.PROVIDER_STATUS,
                data=data,
                timestamp=datetime.now()
            )
            await connection_manager.broadcast(message)
    
    provider_manager.add_update_callback(broadcast_updates)
    
    logger.info("Server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Tennis Trading API Server...")
    
    # Stop monitoring
    await provider_manager.stop_monitoring()
    
    # Stop WebSocket ping
    await connection_manager.stop_ping_interval()
    
    # Disconnect all providers
    await provider_manager.disconnect_all()
    
    logger.info("Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Tennis Trading API",
    description="Real-time tennis data aggregation and trading API",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "providers": len(provider_manager.providers),
        "connections": len(connection_manager.active_connections)
    }


# Provider endpoints
@app.get("/api/providers")
async def get_providers():
    """
    Get list of available providers and their status.
    
    Returns:
        List of provider information
    """
    return {
        "providers": provider_manager.get_provider_status(),
        "primary": provider_manager.primary_provider,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/providers/{provider_name}/connect")
async def connect_provider(provider_name: str):
    """
    Connect to a specific provider.
    
    Args:
        provider_name: Name of provider to connect
        
    Returns:
        Connection status
    """
    success = await provider_manager.connect_provider(provider_name)
    if not success:
        raise HTTPException(status_code=503, detail=f"Failed to connect to {provider_name}")
    
    return {
        "status": "connected",
        "provider": provider_name,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/providers/{provider_name}/disconnect")
async def disconnect_provider(provider_name: str):
    """
    Disconnect from a specific provider.
    
    Args:
        provider_name: Name of provider to disconnect
        
    Returns:
        Disconnection status
    """
    await provider_manager.disconnect_provider(provider_name)
    
    return {
        "status": "disconnected",
        "provider": provider_name,
        "timestamp": datetime.now().isoformat()
    }


# Match endpoints
@app.get("/api/matches", response_model=MatchListResponse)
async def get_matches(
    status: Optional[str] = Query(None, description="Filter by status: live, upcoming, completed"),
    provider: Optional[str] = Query(None, description="Filter by provider")
):
    """
    Get list of all tennis matches.
    
    Args:
        status: Optional status filter
        provider: Optional provider filter
        
    Returns:
        List of matches from all providers
    """
    matches = await provider_manager.get_all_matches(status)
    
    # Filter by provider if specified
    if provider:
        matches = [m for m in matches if provider in m.metadata.get("providers", [])]
    
    # Convert to dict for response
    matches_dict = []
    for match in matches:
        match_dict = {
            "id": match.id,
            "tournament_name": match.tournament_name,
            "player1": match.player1.name,
            "player2": match.player2.name,
            "status": match.status.value,
            "surface": match.surface.value,
            "scheduled_start": match.scheduled_start.isoformat() if match.scheduled_start else None,
            "providers": match.metadata.get("providers", [])
        }
        
        # Add score if available
        if match.score:
            match_dict["score"] = match.score.get_score_string()
        
        matches_dict.append(match_dict)
    
    return MatchListResponse(
        matches=matches_dict,
        total=len(matches_dict),
        providers=list(set(p for m in matches for p in m.metadata.get("providers", []))),
        timestamp=datetime.now()
    )


@app.get("/api/match/{match_id}", response_model=MatchDetailResponse)
async def get_match_details(match_id: str):
    """
    Get detailed information for a specific match.
    
    Args:
        match_id: Match identifier
        
    Returns:
        Detailed match information including score and statistics
    """
    details = await provider_manager.get_match_details(match_id)
    
    if not details:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    
    return MatchDetailResponse(
        match=details.get("match", {}),
        score=details.get("score"),
        statistics=details.get("statistics"),
        providers=details.get("providers", []),
        timestamp=datetime.now()
    )


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Clients can:
    - Receive real-time match updates
    - Subscribe to specific matches
    - Receive provider status updates
    """
    # Generate unique client ID
    client_id = str(uuid.uuid4())
    
    try:
        # Accept connection
        connection = await connection_manager.connect(websocket, client_id)
        
        # Send initial data
        matches = await provider_manager.get_all_matches()
        await connection_manager.send_personal_message(
            client_id,
            WebSocketMessage(
                type=MessageType.MATCH_UPDATE,
                data={
                    "matches": [
                        {
                            "id": m.id,
                            "tournament": m.tournament_name,
                            "player1": m.player1.name,
                            "player2": m.player2.name,
                            "status": m.status.value
                        }
                        for m in matches[:10]  # Send first 10 matches
                    ]
                },
                timestamp=datetime.now()
            )
        )
        
        # Handle messages
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Process message
            await connection_manager.handle_client_message(client_id, data)
            
    except WebSocketDisconnect:
        await connection_manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        await connection_manager.disconnect(client_id)


# WebSocket statistics endpoint
@app.get("/api/websocket/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Returns:
        Connection statistics
    """
    return connection_manager.get_connection_stats()


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )