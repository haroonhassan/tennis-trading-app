"""Main application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api import trading_router

app = FastAPI(
    title="Tennis Trading API",
    description="API for tennis betting exchange trading with risk management",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(trading_router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Tennis Trading API",
        "version": "0.2.0",
        "features": [
            "Trade execution with risk management",
            "Real-time position tracking",
            "P&L calculation",
            "WebSocket support",
            "Automated trading features"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}