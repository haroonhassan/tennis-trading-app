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

4. **Run the FastAPI server**
   ```bash
   python scripts/run_server.py
   # Server will run on http://localhost:8000
   # API docs available at http://localhost:8000/docs
   ```

5. **View live prices in terminal**
   ```bash
   # One-time snapshot
   python scripts/show_prices.py
   
   # Auto-refreshing console
   python scripts/basic_console.py
   
   # Rich terminal UI
   python scripts/live_console.py
   ```

6. **Test trade execution (Practice Mode)**
   ```bash
   python scripts/trade_cli.py
   # Interactive CLI for placing/cancelling bets
   
   # ⚠️ REAL MONEY MODE (use with extreme caution!)
   # python scripts/trade_cli.py --real
   ```

## Project Structure

```
tennis-trading-app/
├── backend/                 # Python backend application
│   ├── app/                # Application source code
│   │   ├── aggregator/     # Multi-provider data aggregation
│   │   ├── config.py       # Application configuration
│   │   ├── providers/      # Data provider implementations
│   │   │   ├── base.py     # Abstract base provider with trading methods
│   │   │   ├── betfair.py  # Betfair implementation (fully functional)
│   │   │   ├── normalizer.py # Data normalization
│   │   │   └── tennis_models.py # Tennis-specific models
│   │   ├── server/         # FastAPI server and WebSocket
│   │   └── trading/        # Trade execution engine
│   │       ├── models.py   # Trading data models
│   │       ├── executor.py # Trade executor with risk management
│   │       ├── strategies.py # Execution strategies (Aggressive, Passive, TWAP, etc.)
│   │       └── audit.py    # Trade event logging and compliance
│   ├── tests/              # Test suite
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend application
│   ├── src/               # Source code
│   ├── public/            # Static assets
│   └── package.json       # Node dependencies
├── docs/                   # Documentation
│   ├── architecture.md    # System architecture details
│   ├── betfair-setup.md   # Betfair API setup guide
│   └── development.md     # Development guidelines
├── scripts/                # Utility scripts
│   ├── run_server.py      # Start the FastAPI server
│   ├── show_prices.py     # Display current prices snapshot
│   ├── basic_console.py   # Auto-refreshing price console
│   ├── live_console.py    # Rich terminal UI with WebSocket
│   ├── trade_cli.py       # Interactive trading CLI
│   └── test_*.py          # Various test scripts
├── Makefile               # Common commands
└── README.md              # This file
```

## Data Provider Architecture

The application uses an abstract provider pattern to support multiple betting exchanges:

### BaseDataProvider Interface
- `authenticate()` - Handle provider authentication
- `get_tennis_matches()` - Fetch tennis matches with prices
- `place_back_bet()` / `place_lay_bet()` - Place trading orders
- `cancel_bet()` / `update_bet()` - Manage existing orders
- `get_open_orders()` / `get_matched_bets()` - Track positions
- `get_market_book()` - Detailed market prices and volumes
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

### Trade Execution Engine

The system includes a sophisticated trade execution engine with multiple features:

#### Execution Strategies
- **Aggressive**: Crosses the spread for immediate execution
- **Passive**: Joins the queue at the best available price
- **Iceberg**: Breaks large orders into smaller chunks to minimize market impact
- **TWAP**: Executes over a time period to achieve time-weighted average price
- **Smart**: Intelligently selects strategy based on market conditions

#### Risk Management
- Maximum order size limits
- Market exposure tracking
- Rate limiting per market
- Duplicate order detection
- Market suspension checks

#### Trade Event System
- Comprehensive audit logging to JSON files
- Real-time event bus for notifications
- Compliance reporting capabilities
- Suspicious activity detection

#### Usage Example
```python
from app.trading import TradeExecutor, TradeInstruction, OrderSide, ExecutionStrategy

# Create trade instruction
instruction = TradeInstruction(
    market_id="1.123456",
    selection_id="789",
    side=OrderSide.BACK,
    size=Decimal("10"),
    price=Decimal("2.5"),
    strategy=ExecutionStrategy.SMART
)

# Execute trade
report = await executor.execute_order(instruction)
```

### Adding New Providers
```python
from app.providers import BaseDataProvider, DataProviderFactory

class NewProvider(BaseDataProvider):
    # Implement required methods including trading
    def place_back_bet(self, ...): ...
    def place_lay_bet(self, ...): ...
    def cancel_bet(self, ...): ...
    
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

- [x] **Phase 5: Trade Execution Engine**
  - [x] Trading execution layer with risk management
    - [x] TradeExecutor service with validation and safeguards
    - [x] Rate limiting and duplicate detection
    - [x] Market suspension checks
  - [x] Multiple execution strategies
    - [x] Aggressive (cross the spread)
    - [x] Passive (join the queue)
    - [x] Iceberg (hide large orders)
    - [x] TWAP (time-weighted average)
    - [x] Smart routing (intelligent selection)
  - [x] Trade event system and audit logging
    - [x] Comprehensive audit trail (JSON logs)
    - [x] Event bus for real-time notifications
    - [x] Compliance reporting capabilities
  - [x] Interactive CLI for testing (`scripts/trade_cli.py`)
  - [x] Real money order placement and cancellation (tested live)

### 🚧 In Progress

- [ ] **Phase 6: Advanced Order Management**
  - [ ] Order book visualization and depth analysis
  - [ ] Complex order types (stop-loss, trailing stops, conditional orders)
  - [ ] Order modification and partial fills handling
  - [ ] Queue position estimation
  
- [ ] **Phase 7: Position Tracking & P&L**
  - [ ] Real-time position monitoring across markets
  - [ ] P&L calculation (realized and unrealized)
  - [ ] Exposure management and hedging tools
  - [ ] Position history and performance analytics
  - [ ] Multi-market portfolio view

### 📋 Planned

- [ ] **Phase 8: React Frontend**
  - [ ] Component architecture
  - [ ] Real-time data display
  - [ ] Trading interface
  - [ ] Performance dashboards

- [ ] **Phase 9: Additional Providers**
  - [ ] Pinnacle Sports integration
  - [ ] Smarkets provider
  - [ ] Betdaq support
  - [ ] Unified data model

- [ ] **Phase 10: Advanced Features**
  - [ ] Automated trading strategies
  - [ ] Backtesting framework
  - [ ] Advanced risk management
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