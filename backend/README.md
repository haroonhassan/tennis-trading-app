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
- **Web Dashboard**: Browser-based monitoring at `/static/monitor.html`
- **Terminal Interface**: Rich-based terminal UI for command-line trading
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
- **Web Dashboard**: http://localhost:8000/static/monitor.html
- **Health Check**: http://localhost:8000/health

### Start the Terminal Interface

#### Quick Start
```bash
# Run the complete integrated terminal
python terminal_app/app_final.py
```

#### Alternative Versions
```bash
# Basic version
python terminal_app/app.py

# Enhanced with trading grid
python terminal_app/app_v2.py

# With full keyboard navigation
python terminal_app/app_v3.py
```

### Test the Application
```bash
# Test complete integration
python test_complete_app.py

# Test individual components
python test_trading_grid.py
python test_positions_panel.py
python test_keyboard_navigation.py
python test_risk_dashboard.py
python test_live_feed.py
python test_charts.py
python test_settings.py
```

The terminal interface provides:
- Real-time market data display
- Keyboard-driven trading
- Position management
- Risk monitoring
- Live feed of trading events
- Charts and visualizations
- Settings management
- Automated trading features

## 🔴 Live Data Testing Guide

### Prerequisites for Live Data
1. **WebSocket Server**: Ensure your WebSocket server is running and accessible
2. **API Credentials**: Have your Betfair/exchange credentials configured in `.env`
3. **Network Access**: Verify connectivity to data providers
4. **Test Environment**: Use test/sandbox environment first before production

### Step 1: Configure Live Data Connection
```bash
# Edit configuration file
vim terminal_app/config.json

# Or use environment variables
export WEBSOCKET_URL="wss://your-websocket-server.com/live"
export API_BASE_URL="https://your-api-server.com/api"
```

### Step 2: Start Backend Services
```bash
# Start API server with live data providers
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal, start WebSocket relay (if needed)
python scripts/websocket_relay.py
```

### Step 3: Launch Terminal with Live Data
```bash
# Start with live WebSocket connection
python terminal_app/app_final.py --live

# Or with custom WebSocket URL
python terminal_app/app_final.py --ws-url "wss://your-server.com/live"
```

### Step 4: Verify Live Data Flow
1. **Check Connection Status**: Look for "Connected to WebSocket" message
2. **Monitor Feed Panel**: Press F5 to view live data feed
3. **Verify Price Updates**: Check trading grid (F1) for live price changes
4. **Test Match Updates**: Ensure scores and match status update in real-time

### Step 5: Test Trading Functions with Live Data
```bash
# Test order placement (paper trading mode first)
1. Navigate to a selection with arrow keys
2. Press 'b' for back bet or 'l' for lay bet
3. Select stake with number keys (1-5)
4. Confirm with 'Y'

# Test position management
1. Place a test bet
2. Press F2 to view positions
3. Press 'c' to close or 'h' to hedge
4. Monitor P&L updates in real-time
```

### Troubleshooting Live Data Issues

#### WebSocket Connection Issues
```bash
# Check WebSocket connectivity
python scripts/test_websocket.py

# Enable debug logging
export LOG_LEVEL=DEBUG
python terminal_app/app_final.py
```

#### Data Not Updating
- Check network connectivity: `ping your-server.com`
- Verify WebSocket URL in config
- Check for firewall/proxy issues
- Review logs in `terminal_app.log`

#### Authentication Failures
- Verify API credentials in `.env`
- Check certificate paths for Betfair
- Ensure API keys are active
- Test with curl: `curl -H "X-API-Key: YOUR_KEY" https://api-endpoint`

### Live Data Checklist
- [ ] WebSocket server is accessible
- [ ] API credentials are configured
- [ ] Network connectivity verified
- [ ] Test environment selected (not production)
- [ ] Logging enabled for debugging
- [ ] Paper trading mode for initial tests
- [ ] Risk limits configured appropriately
- [ ] Kill switch tested (Shift+S)
- [ ] Data feed showing in F5 view
- [ ] Prices updating in trading grid
- [ ] Positions tracking correctly
- [ ] P&L calculations accurate

### Performance Monitoring with Live Data
```bash
# Monitor system resources
top -p $(pgrep -f app_final.py)

# Check message throughput
tail -f terminal_app.log | grep "msg/s"

# Monitor WebSocket latency
python scripts/measure_latency.py
```

### Safety Features for Live Trading
1. **Paper Trading Mode**: Test without real money first
2. **Risk Limits**: Configure conservative limits initially
3. **Kill Switch**: Practice using Shift+S emergency stop
4. **Daily Loss Limit**: Set appropriate daily loss threshold
5. **Position Limits**: Start with small position counts
6. **Confirmation Dialogs**: Keep enabled for all trades
7. **Audit Logging**: Review logs regularly

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

## 💻 Terminal Interface

The Rich-based terminal interface (`terminal_app/`) provides a command-line trading experience:

### Features
- **Real-time Data**: Live market prices and score updates via WebSocket
- **Trading Grid**: Interactive table with real-time odds and positions
- **One-Click Betting**: Quick bet placement with keyboard shortcuts
- **Bet Modal**: Detailed bet confirmation with P&L calculations
- **Price Flashing**: Visual indicators for price movements (green up/red down)
- **Position Tracking**: Monitor open positions with live P&L
- **Risk Dashboard**: Visual risk metrics and exposure tracking
- **Trade Feed**: Live stream of trading events with color coding

### Trading Grid Features
- **Real-time Updates**: Prices update without screen flicker
- **Selection Highlighting**: Current row highlighted in cyan
- **Serving Indicator**: • symbol shows current server
- **Position Markers**: € symbol indicates open positions
- **P&L Display**: Color-coded profit/loss for each position
- **Volume Display**: Formatted as 1k, 2.5k for readability
- **Stale Price Detection**: Dims prices older than 5 seconds

### Position Management Features
- **Positions Table**: Sortable view of all open positions with P&L
- **P&L Ladder**: Visual chart showing profit/loss at different price points
- **Position Summary**: Total exposure, realized/unrealized P&L, best/worst trades
- **Close Position**: One-click position closure with P&L calculation
- **Hedge/Green-up**: Automatic hedge calculation for guaranteed profit
- **Stop Loss**: Set stop loss orders with max loss display
- **Multi-View Layouts**: Switch between trading, positions, split, and risk views

### Keyboard Navigation & Hotkeys (Prompt 13)

#### Comprehensive Navigation
- **Arrow Keys & Vim Keys**: Full navigation support with ↑↓←→ and hjkl
- **Page Navigation**: Page Up/Down for fast scrolling, Home/End for jump to top/bottom
- **Tab Cycling**: Tab key to switch between panels and active areas
- **Search Mode**: `/` to enter search/filter mode with real-time results

#### Input Mode Management
- **Normal Mode**: Default mode for navigation and trading
- **Search Mode**: Activated with `/` for filtering matches and selections
- **Confirm Mode**: Y/N prompts for critical actions
- **Help Mode**: `?` to show comprehensive help menu

#### Navigation & Views
- `F1` - Trading grid view
- `F2` - Positions view with P&L ladder
- `F3` - Split screen (grid + positions)
- `F4` - Risk dashboard
- `F5` - Live trading feed
- `F6` - Charts view
- `Tab` - Switch active pane/panel
- `↑/↓` or `j/k` - Navigate up/down
- `←/→` or `h/l` - Navigate left/right
- `Page Up/Down` - Fast scroll
- `Home/End` - Jump to top/bottom
- `/` - Search/filter

#### Trading Hotkeys
- `b` - Place back bet on selection
- `l` - Place lay bet on selection (context-aware with navigation)
- `1-5` - Quick stake selection (£10/25/50/100/250)
- `+/-` - Adjust stake or price
- `Enter` - Confirm action
- `Y/N` - Yes/No in confirmation dialogs
- `ESC` - Cancel/close modal

#### Position Management
- `c` - Close position at market
- `h` - Hedge position (context-aware with navigation)
- `x` - Set stop loss
- `t` - Set take profit
- `s` - Sort positions
- `o` - Toggle odds format (decimal/fractional)
- `p` - Toggle positions-only view

#### Advanced Shortcuts
- `Shift+C` - Close ALL positions (with confirmation)
- `Shift+H` - Hedge ALL positions (with confirmation)
- `Shift+S` - KILL SWITCH - Emergency stop all trading
- `Ctrl+Z` - Undo last action (maintains undo stack)

#### System Controls
- `r` - Refresh all data
- `?` - Show help menu with all shortcuts
- `q` - Quit application
- `Ctrl+C` - Force quit

#### Context-Aware Actions
- **Smart Key Conflicts**: Navigation keys (h/l) automatically switch context between navigation and trading actions
- **Mode Indicators**: Visual feedback showing current input mode
- **Quick Reference Bar**: Bottom bar showing available actions for current context
- **Help Menu**: Organized by category with visual grouping

### Risk Management Dashboard (Prompt 14)

#### Real-Time Risk Metrics
- **Exposure Tracking**: Monitor total exposure, market exposure, and position counts
- **P&L Monitoring**: Track daily P&L with warning thresholds
- **Risk Limits**: Configurable limits for position size, market exposure, and daily loss
- **Visual Indicators**: Color-coded usage bars showing risk utilization
- **Alert System**: Multi-level alerts (warning/critical) for approaching limits

#### Automated Trading Features
- **Stop Loss Orders**: Automatic stop loss at configurable percentage
- **Take Profit Orders**: Target profit levels with partial closing options
- **Trailing Stops**: Dynamic stop loss that follows favorable price movements
- **One-Cancels-Other (OCO)**: Paired stop loss and take profit orders
- **Smart Execution**: Multiple execution strategies (Market, Limit, Iceberg, TWAP, VWAP)

#### Risk Controls
- **Kill Switch**: Emergency stop for all trading activity (Shift+S)
- **Trading Freeze**: Temporary pause on new positions
- **Position Limits**: Maximum concurrent positions enforcement
- **Exposure Limits**: Per-market and total exposure caps
- **Daily Loss Limits**: Automatic freeze when daily loss threshold reached

#### Dashboard Components
- **Risk Metrics Panel**: Current vs limit with visual usage bars
- **Exposure Breakdown**: By market and selection with risk levels
- **Alerts Panel**: Active warnings and critical alerts
- **Trading Controls**: Kill switch, freeze status, auto stop-loss settings
- **Performance Metrics**: Win rate, P&L stats, best/worst trades
- **Automated Orders Panel**: Active stop loss, take profit, and trailing orders

#### Risk Dashboard View (F4)
Access the full risk management dashboard with F4 key:
- Real-time risk score and metrics
- Exposure visualization by market/selection
- P&L tracking and performance analytics
- Active alerts and warnings
- Trading controls and kill switch

### Live Data Feed (Prompt 15)

#### Live Feed Panel (F5)
Real-time streaming of all trading events:
- **Event Types**: Trade, Position, Price, Score, Match, Alert, System, Error
- **Priority System**: Critical events displayed first
- **Event Filtering**: Filter by event type
- **Pause/Resume**: Control feed streaming
- **Auto-scroll**: Automatic scrolling to latest events
- **Keyword Highlighting**: Highlight important terms

#### Specialized Feeds
- **Trade Feed**: Execution history with P&L tracking
- **Score Feed**: Live match scores and server information
- **Alert Feed**: Prioritized alerts with unread counts
- **Statistics Panel**: Message rate, uptime, connection status

#### Feed Management
- **Message Routing**: Automatic routing to appropriate feeds
- **Rate Calculation**: Real-time messages per second
- **Event History**: Configurable buffer size
- **Connection Monitoring**: Uptime and last message tracking

#### Live Dashboard Features
- Multi-panel layout with main feed and side panels
- Real-time update without screen flicker
- Color-coded events by type and priority
- Comprehensive event statistics
- WebSocket message processing

### Charts and Visualization (Prompt 16)

#### Chart Types (F6)
- **Line Charts**: Price movements and P&L trends with interpolation
- **Bar Charts**: Volume analysis with positive/negative values
- **Candlestick Charts**: OHLC price action visualization
- **Heatmaps**: Correlation matrices with intensity coloring
- **Sparklines**: Inline mini-charts for quick trends

#### Chart Features
- **ASCII Rendering**: Pure text-based charts for terminal display
- **Real-time Animation**: Live updating charts with smooth transitions
- **Normalization**: Automatic scaling to fit display area
- **Multi-panel Dashboards**: Combined chart views
- **Color Coding**: Visual distinction for bullish/bearish trends

#### Dashboard Components
- **P&L Chart**: Cumulative profit/loss over time
- **Volume Chart**: Hourly trading volume analysis
- **Price Chart**: Historical price movements with trend lines
- **Position Heatmap**: P&L intensity by selection and time
- **Mini Charts**: Sparkline-based compact visualizations

#### Visualization Features
- Responsive sizing for different terminal dimensions
- Axis labels and grid lines
- Trend indicators (up/down arrows)
- Statistical overlays
- Interactive chart updates

### Settings and Configuration (Prompt 17)

#### Configuration System
- **Persistent Settings**: JSON-based configuration storage
- **Multiple Sections**: General, Trading, Display, Risk, Automation, Keyboard, Connection
- **Type Safety**: Dataclass-based configuration with validation
- **Path-based Access**: Get/set values using dot notation
- **Import/Export**: Save and load configurations
- **Validation**: Automatic validation of settings

#### Settings Categories
- **General**: App name, version, auto-save, logging, theme
- **Trading**: Stakes, odds limits, commission, confirmations
- **Display**: Refresh rate, precision, formats, visual options
- **Risk**: Exposure limits, stop loss, take profit, kill switch
- **Automation**: Auto-hedge, auto-close, smart execution
- **Keyboard**: Shortcuts, vim mode, function keys
- **Connection**: WebSocket, API URLs, reconnection settings

#### Settings UI Features
- **Settings Panel**: Full configuration interface
- **Section Navigation**: Browse all settings categories
- **Quick Settings**: Compact view of key settings
- **Live Editing**: Modify settings on the fly
- **Reset Options**: Reset section or all to defaults
- **Validation Display**: Show configuration issues

#### Configuration Management
- Auto-save functionality
- Default values for all settings
- Section-based organization
- JSON and YAML export formats
- Configuration profiles support

### Final Integration (Prompt 18)

The complete terminal trading application brings together all components into a polished, production-ready system:

#### Integrated Features
- **Unified Application**: All components working together seamlessly
- **Complete Keyboard Control**: Full navigation and trading via keyboard
- **Real-time Updates**: Live data streaming with WebSocket integration
- **Risk Management**: Integrated limits, alerts, and kill switch
- **Automated Trading**: Stop loss, take profit, and smart execution
- **Multi-view System**: F1-F6 keys for instant view switching
- **Settings Persistence**: Configuration saved and loaded automatically
- **Session Statistics**: Real-time P&L, win rate, and performance tracking

#### Application Versions
- `app.py`: Basic terminal foundation
- `app_v2.py`: Enhanced with trading grid
- `app_v3.py`: Full keyboard navigation
- `app_final.py`: Complete integrated application

### Architecture
```
terminal_app/
├── app.py              # Main application entry
├── app_v2.py           # Enhanced app with trading grid
├── app_v3.py           # Full app with keyboard navigation
├── app_final.py        # Complete integrated application
├── models.py           # Data models (Match, Position, Trade)
├── websocket_client.py # WebSocket client with reconnection
├── keyboard_handler.py # Comprehensive keyboard input handling
├── keyboard_handler_fixed.py # Fixed version with proper filters
├── config.py           # Configuration management system
├── stores/             # Data management
│   ├── match_store.py    # Match and price data
│   ├── position_store.py # Position tracking
│   └── trade_store.py    # Trade history
└── components/         # UI components
    ├── layout.py          # Rich layout system
    ├── trading_grid.py    # Trading grid with selection
    ├── bet_modal.py       # Bet placement modal
    ├── positions_panel.py # Position management panel
    ├── position_modals.py # Close/hedge/stop-loss modals
    ├── layout_manager.py  # Multi-view layout manager
    ├── help_menu.py       # Help menu and quick reference bar
    ├── risk_dashboard.py  # Risk management dashboard
    ├── automated_trading.py # Automated orders and smart execution
    ├── live_feed.py       # Live data feed and event streaming
    ├── charts.py          # ASCII charts and visualizations
    └── settings_ui.py     # Settings UI components
```

## 📝 Logging

Logs are written to:
- `logs/app.log` - Application logs
- `logs/trades.log` - Trade execution logs
- `logs/risk.log` - Risk events
- `terminal_app.log` - Terminal interface logs

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