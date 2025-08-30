# Tennis Trading App

A real-time tennis trading application that integrates with Betfair's Exchange API to provide live odds streaming, automated trading capabilities, and comprehensive match analytics.

## Architecture Overview

The application follows a microservices architecture with clear separation of concerns:

- **Python Backend**: FastAPI-based server handling Betfair API integration, data processing, and trading logic
- **React Frontend**: Modern, responsive UI for monitoring matches and executing trades
- **WebSocket Communication**: Real-time bidirectional communication between frontend and backend
- **Streaming API**: Direct integration with Betfair's streaming endpoints for live data

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

2. **Set up the backend**
   ```bash
   make setup-backend
   source backend/venv/bin/activate
   cp backend/.env.example backend/.env
   # Edit backend/.env with your Betfair credentials
   ```

3. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   ```

4. **Run the application**
   ```bash
   # Terminal 1: Backend
   make run-backend
   
   # Terminal 2: Frontend
   cd frontend && npm start
   ```

## Project Structure

```
tennis-trading-app/
├── backend/                 # Python backend application
│   ├── app/                # Application source code
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Core functionality
│   │   ├── models/         # Data models
│   │   ├── services/       # Business logic
│   │   └── streaming/      # Betfair streaming integration
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
│   └── setup_backend.sh   # Backend setup automation
├── Makefile               # Common commands
└── README.md              # This file
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

- [ ] **Phase 1: Betfair Authentication**
  - [ ] Implement certificate-based authentication
  - [ ] Session management and token refresh
  - [ ] Connection pooling and retry logic

- [ ] **Phase 2: Streaming API Integration**
  - [ ] Market data streaming
  - [ ] Order stream subscription
  - [ ] Heartbeat and connection management
  - [ ] Data parsing and normalization

- [ ] **Phase 3: Backend Server Setup**
  - [ ] REST API endpoints
  - [ ] WebSocket server implementation
  - [ ] Data models and validation
  - [ ] Business logic layer

- [ ] **Phase 4: React Frontend**
  - [ ] Component architecture
  - [ ] Real-time data display
  - [ ] Trading interface
  - [ ] Performance optimization

- [ ] **Phase 5: Advanced Features**
  - [ ] Automated trading strategies
  - [ ] Backtesting framework
  - [ ] Risk management tools
  - [ ] Performance analytics

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