# Tennis Trading App - Backend

Python backend service for the Tennis Trading Application, providing Betfair API integration, real-time data streaming, and trading functionality.

## Features

- Certificate-based authentication with Betfair
- Real-time market data streaming
- RESTful API for frontend communication
- WebSocket server for live updates
- Automated trading strategy execution
- Comprehensive logging and error handling

## Setup

1. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your Betfair credentials
   ```

4. Place Betfair certificates in `certs/` directory

5. Run the server:
   ```bash
   python -m app.main
   ```

## Testing

Run tests with pytest:
```bash
pytest
```

## API Documentation

Once running, visit http://localhost:8000/docs for interactive API documentation.