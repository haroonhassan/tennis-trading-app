# Tennis Trading App - Backend

Advanced tennis betting exchange trading system with integrated risk management, real-time monitoring, and automated trading features.

## 🚀 Features

### Core Trading System
- **Trade Execution Engine**: Smart order routing with multiple execution strategies
- **Risk Management**: Pre-trade validation and position limit enforcement
- **Position Tracking**: Real-time P&L calculation with commission tracking
- **Market Data Integration**: Live odds and match data from multiple providers

### Risk Management
- **Pre-Trade Validation**: Checks against configurable risk limits before execution
- **Position Limits**: Maximum position size and open position count enforcement
- **Exposure Management**: Real-time tracking of market and total exposure
- **Daily Loss Limits**: Automatic trading freeze when loss thresholds exceeded
- **Kill Switch**: Emergency stop functionality for all trading activity

### Automated Trading
- **One-Click Hedging**: Instant green-up across all selections
- **Cash Out**: Calculate and execute optimal exit strategies
- **Stop Loss Orders**: Automatic position closure at defined loss levels
- **Smart Execution**: Adaptive order placement based on market conditions

### Real-Time Monitoring
- **WebSocket Streaming**: Live updates for positions, trades, and P&L
- **Dashboard Interface**: Web-based monitoring at `/static/monitor.html`
- **Event Logging**: Comprehensive audit trail of all trading activity
- **Performance Metrics**: Win rate, average P&L, and trade statistics

## 📋 Prerequisites

- Python 3.8+
- Betfair API credentials (for live trading)
- Tennis data API access (optional)

## 🛠️ Installation

1. **Clone and Navigate**:
   ```bash
   cd backend
   ```

2. **Create Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials:
   # - BETFAIR_USERNAME
   # - BETFAIR_PASSWORD
   # - BETFAIR_APP_KEY
   # - BETFAIR_CERT_PATH
   # - TENNIS_DATA_API_KEY (optional)
   ```

5. **Setup Certificates** (for Betfair):
   ```bash
   mkdir -p certs
   # Place your Betfair certificates in certs/
   ```

## 🚀 Running the Application

### Start the API Server
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Access Points
- **API Documentation**: http://localhost:8000/docs
- **Monitoring Dashboard**: http://localhost:8000/static/monitor.html
- **Health Check**: http://localhost:8000/health

## 📡 API Endpoints

### Trading Operations
- `POST /api/trade/place` - Place new order with risk validation
- `POST /api/trade/cancel/{order_id}` - Cancel open order
- `POST /api/trade/close` - Close position
- `POST /api/trade/cashout` - Execute cash out

### Position Management
- `GET /api/positions` - Get all open positions
- `GET /api/position/{position_id}` - Get specific position details
- `POST /api/position/hedge` - Hedge a position

### Risk Management
- `GET /api/risk/limits` - Current limits vs usage
- `GET /api/risk/status` - Real-time risk metrics
- `POST /api/risk/freeze` - Freeze/unfreeze trading

### Market Data
- `GET /api/markets` - Available markets
- `GET /api/market/{market_id}/odds` - Live odds
- `GET /api/matches` - Current matches

### WebSocket Endpoints
- `/api/ws/monitor` - Combined feed (positions, trades, P&L)
- `/api/ws/positions` - Position updates
- `/api/ws/trades` - Trade executions
- `/api/ws/pnl` - P&L updates

## 🧪 Testing

### Run All Tests
```bash
pytest
```

### Test Specific Components
```bash
# Test risk management
python test_risk_system.py

# Test trade execution cycle
python test_trade_cycle.py

# Test WebSocket connections
python test_websocket.py

# Test market data providers
python test_provider.py
```

## 🏗️ Architecture

```
backend/
├── app/
│   ├── api/              # REST & WebSocket endpoints
│   │   └── trading_api.py
│   ├── trading/          # Core trading logic
│   │   ├── coordinator.py   # Trade orchestration
│   │   ├── executor.py      # Order execution
│   │   ├── models.py        # Data models
│   │   └── position_tracker.py
│   ├── risk/             # Risk management
│   │   ├── manager.py       # Risk checks & limits
│   │   ├── models.py        # Risk data models
│   │   └── monitor.py       # Real-time monitoring
│   ├── server/           # Server infrastructure
│   │   ├── connection_manager.py
│   │   └── provider_manager.py
│   └── providers/        # External data sources
│       ├── betfair/
│       └── tennis_data/
├── static/               # Web dashboard
│   └── monitor.html
├── tests/               # Test suite
└── requirements.txt
```

## 🔧 Configuration

### Risk Limits (Configurable)
```python
RiskLimits(
    max_position_size=Decimal("100"),      # Per position
    max_market_exposure=Decimal("500"),    # Per market
    max_total_exposure=Decimal("1000"),    # Total portfolio
    max_daily_loss=Decimal("200"),         # Daily stop loss
    max_open_positions=20                  # Concurrent positions
)
```

### Execution Strategies
- `MARKET` - Immediate execution at market price
- `LIMIT` - Place at specified price
- `SMART` - Adaptive strategy based on market depth
- `ICEBERG` - Large order splitting

## 📊 Monitoring Dashboard

The web-based monitoring dashboard provides:
- Live position tracking with P&L
- Real-time trade execution feed
- Risk metric visualization
- Performance statistics
- Manual trade placement interface

Access at: http://localhost:8000/static/monitor.html

## 🔒 Security

- Certificate-based authentication for Betfair
- Environment-based credential management
- Request validation and sanitization
- Rate limiting on API endpoints
- Audit logging for compliance

## 📝 Logging

Logs are written to:
- `logs/app.log` - Application logs
- `logs/trades.log` - Trade execution logs
- `logs/risk.log` - Risk events

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational purposes. Ensure compliance with all applicable laws and exchange terms of service when using for real trading.