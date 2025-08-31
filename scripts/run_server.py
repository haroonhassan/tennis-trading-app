#!/usr/bin/env python3
"""Run the FastAPI server."""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Load environment variables from main folder
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    print("=" * 60)
    print("TENNIS TRADING API SERVER")
    print("=" * 60)
    print(f"Starting server on {host}:{port}")
    print(f"API docs: http://localhost:{port}/docs")
    print(f"WebSocket: ws://localhost:{port}/ws")
    print("=" * 60)
    
    # Run server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
        access_log=True
    )