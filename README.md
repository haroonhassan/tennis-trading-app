# Tennis Trading App

A real-time tennis trading application with an extensible data provider architecture, currently supporting Betfair Exchange API with plans for additional betting exchanges. Provides live odds streaming, automated trading capabilities, and comprehensive match analytics.

## Architecture Overview

The application follows a microservices architecture with clear separation of concerns:

- **Abstract Data Provider Layer**: Extensible interface for multiple betting exchanges
- **Python Backend**: FastAPI-based server with pluggable provider architecture
- **React Frontend**: Modern, responsive UI for monitoring matches and executing trades
- **WebSocket Communication**: Real-time bidirectional communication between frontend and backend
- **Provider Implementations**: Currently Betfair, easily extensible for Pinnacle, Smarkets, etc.

## Prerequisites

- Python 3.9 or higher
- Node.js 16 or higher
- Betfair API access (account with API key and certificates)
- SSL certificates for Betfair API authentication

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tennis-trading-app
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Betfair credentials (username, password, app_key, cert_file)
   ```

3. **Install dependencies**
   ```bash
   make install  # Installs both backend and frontend dependencies
   ```

4. **Test Betfair connection**
   ```bash
   python scripts/test_providers.py
   ```

5. **Run live price streaming console**
   ```bash
   cd backend && source venv/bin/activate
   python ../scripts/test_streaming_simulated.py
   ```

6. **Run tennis scores service test**
   ```bash
   cd backend && source venv/bin/activate
   python ../scripts/test_tennis_scores.py
   ```

7. **Run the FastAPI server**
   ```bash
   cd backend && source venv/bin/activate
   python ../scripts/run_server.py
   # Server will run on http://localhost:8000
   # API docs available at http://localhost:8000/docs
   # WebSocket endpoint at ws://localhost:8000/ws
   ```

8. **Test WebSocket connection**
   ```bash
   # In another terminal
   cd backend && source venv/bin/activate
   python ../scripts/test_websocket.py
   ```

9. **Run the application**
   ```bash
   make dev  # Runs both backend and frontend
   
   # Or separately:
   # Terminal 1: make dev-backend
   # Terminal 2: make dev-frontend
   ```

## Project Structure

```
tennis-trading-app/
├── backend/                 # Python backend application
│   ├── app/                # Application source code
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Core functionality
│   │   ├── models/         # Data models
│   │   ├── providers/      # Data provider implementations
│   │   │   ├── base.py     # Abstract base provider
│   │   │   ├── betfair.py  # Betfair implementation
│   │   │   ├── betfair_stream.py  # Betfair streaming client
│   │   │   ├── models.py   # Universal data models
│   │   │   └── factory.py  # Provider factory
│   │   ├── services/       # Business logic
│   │   └── utils/          # Utility functions
│   ├── tests/              # Test suite
│   ├── requirements.txt    # Python dependencies
│   └── .env.example        # Environment variables template
├── frontend/               # React frontend application
│   ├── src/               # Source code
│   ├── public/            # Static assets
│   └── package.json       # Node dependencies
├── docs/                   # Documentation
│   ├── architecture.md    # System architecture details
│   ├── betfair-setup.md   # Betfair API setup guide
│   └── development.md     # Development guidelines
├── scripts/                # Utility scripts
│   ├── test_betfair_connection.py  # Betfair connection test
│   ├── test_providers.py           # Provider testing script
│   ├── test_streaming.py            # Real streaming test (requires API access)
│   └── test_streaming_simulated.py # Simulated streaming console
├── Makefile               # Common commands
└── README.md              # This file
```

## Data Provider Architecture

The application uses an abstract provider pattern to support multiple betting exchanges:

### BaseDataProvider Interface
- `authenticate()` - Handle provider authentication
- `get_live_matches()` - Fetch current live matches
- `subscribe_to_prices()` - Real-time price subscriptions
- `get_match_scores()` - Current match scores
- `get_match_stats()` - Match statistics
- `place_bet()` / `cancel_bet()` - Trading operations
- `get_account_balance()` - Account information

### Current Implementations
- **BetfairProvider**: Full integration with Betfair Exchange API
  - Non-interactive login with .pem certificate
  - Automatic session management
  - Lightweight mode for performance

### Streaming Capabilities

The system supports real-time price streaming with:

- **Live Price Updates**: Console display with real-time market prices
- **Price Movement Tracking**: Visual indicators (↑↓) for price changes
- **Provider-Agnostic Models**: Universal data format across all providers
- **Two Modes**:
  - **Real Streaming**: Full Betfair Stream API implementation (requires API approval)
  - **Simulated Streaming**: Polling-based fallback for demonstration

#### Running the Live Console
```bash
cd backend && source venv/bin/activate
python ../scripts/test_streaming_simulated.py

# Or with specific market ID
python ../scripts/test_streaming_simulated.py 1.247201095
```

### Adding New Providers
```python
from app.providers import BaseDataProvider, DataProviderFactory

class NewProvider(BaseDataProvider):
    # Implement required methods including streaming
    def connect_stream(self, config): ...
    def subscribe_market_stream(self, market_ids, callback): ...
    
# Register with factory
DataProviderFactory.register_provider("new_provider", NewProvider)
```

## Technology Stack

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **Betfairlightweight**: Official Python client for Betfair API
- **WebSockets**: Real-time communication protocol
- **Pydantic**: Data validation using Python type annotations
- **Uvicorn**: Lightning-fast ASGI server
- **Loguru**: Simplified logging with better defaults

### Frontend
- **React**: Component-based UI library
- **TypeScript**: Type-safe JavaScript
- **WebSocket Client**: Real-time server communication
- **Recharts**: Data visualization for odds charts
- **Material-UI**: Component library for consistent design

### Infrastructure
- **Docker**: Containerization for consistent deployments
- **Redis**: Caching and session management
- **PostgreSQL**: Data persistence (optional)

## Development Roadmap

### ✅ Completed
- [x] **Phase 1: Data Provider Architecture**
  - [x] Abstract BaseDataProvider interface
  - [x] Betfair provider implementation
  - [x] Provider factory pattern
  - [x] Certificate-based authentication (.pem file)
  - [x] Session management with auto keep-alive
  - [x] Connection testing and validation

- [x] **Phase 2: Streaming & Real-time Data**
  - [x] Provider-agnostic streaming methods in BaseDataProvider
  - [x] Universal data models (StreamMessage, MarketPrices, etc.)
  - [x] BetfairStreamClient implementation
  - [x] Real-time price updates with console display
  - [x] Price movement tracking and indicators
  - [x] Auto-reconnection and heartbeat management
  - [x] Polling fallback for demonstration
  - [x] WebSocket server for frontend
  - [ ] Order stream subscription (pending)

- [x] **Phase 3: Tennis Data Service**
  - [x] Comprehensive tennis data models
  - [x] Match score tracking
  - [x] Statistics aggregation
  - [x] Provider-agnostic caching layer
  - [x] Automatic update scheduler
  - [x] Match normalization across providers

- [x] **Phase 4: FastAPI Server & Multi-Provider Support**
  - [x] FastAPI REST endpoints
  - [x] WebSocket handlers with ConnectionManager
  - [x] ProviderManager for multi-source aggregation
  - [x] Provider failover and health monitoring
  - [x] Real-time broadcast to WebSocket clients
  - [x] CORS middleware configuration
  - [x] API documentation (auto-generated at /docs)
  - [x] WebSocket test client

### 🚧 In Progress

- [ ] **Phase 5: Backend API Development**
  - [ ] Trading execution layer
  - [ ] Advanced order management
  - [ ] Position tracking

### 📋 Planned
- [ ] **Phase 6: React Frontend**
  - [ ] Component architecture
  - [ ] Real-time data display
  - [ ] Trading interface
  - [ ] Performance dashboards

- [ ] **Phase 7: Additional Providers**
  - [ ] Pinnacle Sports integration
  - [ ] Smarkets provider
  - [ ] Betdaq support
  - [ ] Unified data model

- [ ] **Phase 8: Advanced Features**
  - [ ] Automated trading strategies
  - [ ] Backtesting framework
  - [ ] Risk management tools
  - [ ] ML-based predictions

## Contributing

We welcome contributions! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style
- Python: Follow PEP 8, use Black for formatting
- JavaScript/TypeScript: ESLint with Prettier
- Commit messages: Use conventional commits format

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or suggestions, please open an issue on GitHub or contact the maintainers.

## Acknowledgments

- Betfair for providing comprehensive API documentation
- The open-source community for the excellent libraries used in this project