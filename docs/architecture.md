# System Architecture

## Overview

The Tennis Trading App follows a microservices architecture pattern with clear separation between the data layer, business logic, and presentation layer.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                            │
│                    (React SPA + WebSocket)                      │
└─────────────────┬───────────────────────┬──────────────────────┘
                  │                       │
                  │ HTTP/HTTPS            │ WebSocket
                  │                       │
┌─────────────────▼───────────────────────▼──────────────────────┐
│                         API Gateway                             │
│                    (FastAPI + Uvicorn)                          │
│                         Port 8000                               │
└─────────────────┬───────────────────────┬──────────────────────┘
                  │                       │
    ┌─────────────▼──────────┐ ┌─────────▼──────────────┐
    │   REST API Endpoints   │ │  WebSocket Handler     │
    │   - Authentication     │ │  - Live odds stream    │
    │   - Market data        │ │  - Order updates       │
    │   - Order placement    │ │  - Market changes      │
    │   - Account info       │ │                        │
    └─────────────┬──────────┘ └─────────┬──────────────┘
                  │                       │
┌─────────────────▼───────────────────────▼──────────────────────┐
│                      Business Logic Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Trading    │  │   Market     │  │   Account    │        │
│  │   Engine     │  │   Analyzer   │  │   Manager    │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────┬──────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────┐
│                    Betfair Integration Layer                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Auth       │  │  Streaming   │  │   Betting    │        │
│  │   Service    │  │  API Client  │  │   API Client │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Betfair API    │
                    │   - REST API     │
                    │   - Stream API   │
                    └──────────────────┘
```

## Component Responsibilities

### Frontend (React)
- **User Interface**: Responsive web application for desktop and mobile
- **Real-time Updates**: WebSocket client for live data streaming
- **State Management**: Redux/Context API for application state
- **Data Visualization**: Charts and graphs for odds movement and P&L

### API Gateway (FastAPI)
- **Request Routing**: Direct HTTP requests to appropriate handlers
- **Authentication**: Validate user sessions and API keys
- **Rate Limiting**: Protect against abuse and ensure fair usage
- **CORS Handling**: Enable secure cross-origin requests

### Business Logic Layer
- **Trading Engine**: Execute trading strategies and manage positions
- **Market Analyzer**: Process market data and identify opportunities
- **Risk Management**: Monitor exposure and implement safety limits
- **Order Management**: Handle order lifecycle and execution

### Betfair Integration
- **Authentication Service**: Certificate-based login and session management
- **Streaming Client**: Maintain persistent connection for live data
- **API Client**: RESTful communication for account and betting operations
- **Data Parser**: Convert Betfair responses to internal format

## Data Flow

### 1. Authentication Flow
```
User Login → Frontend → API Gateway → Auth Service → Betfair SSO
    ← Session Token ← ← ← ← ← ← ← ← Session Key ←
```

### 2. Market Data Flow
```
Betfair Stream → Streaming Client → Data Parser → WebSocket → Frontend
                                         ↓
                                   Market Analyzer
                                         ↓
                                   Trading Engine
```

### 3. Order Placement Flow
```
User Action → Frontend → API Gateway → Order Validator → Betfair API
                  ↓                           ↓
            Order Status ← WebSocket ← Order Manager
```

## API Design Principles

1. **RESTful Design**: Follow REST conventions for resource operations
2. **Versioning**: API versioning through URL path (e.g., /api/v1/)
3. **Pagination**: Implement cursor-based pagination for large datasets
4. **Error Handling**: Consistent error response format with proper HTTP codes
5. **Documentation**: Auto-generated OpenAPI/Swagger documentation
6. **Idempotency**: Support idempotent operations where applicable

## WebSocket Message Format

### Client to Server
```json
{
  "type": "subscribe|unsubscribe|command",
  "action": "market|order|account",
  "data": {
    "marketId": "1.123456",
    "selectionId": 12345
  },
  "timestamp": "2024-01-01T00:00:00Z",
  "requestId": "uuid-v4"
}
```

### Server to Client
```json
{
  "type": "market_update|order_update|error",
  "data": {
    "marketId": "1.123456",
    "runners": [{
      "selectionId": 12345,
      "prices": {
        "back": [[6.0, 100.50], [5.9, 250.00]],
        "lay": [[6.2, 150.00], [6.4, 300.00]]
      }
    }]
  },
  "timestamp": "2024-01-01T00:00:00Z",
  "sequence": 1234567
}
```

## Security Considerations

1. **SSL/TLS**: All communications encrypted using HTTPS/WSS
2. **Certificate Pinning**: Validate Betfair certificates
3. **API Key Management**: Secure storage of sensitive credentials
4. **Rate Limiting**: Prevent abuse and ensure fair usage
5. **Input Validation**: Sanitize all user inputs
6. **CORS Policy**: Restrict cross-origin access
7. **Session Management**: Implement secure session handling with timeout

## Scalability Considerations

1. **Horizontal Scaling**: Stateless API design for easy scaling
2. **Connection Pooling**: Efficient database and API connection management
3. **Caching Strategy**: Redis for frequently accessed data
4. **Message Queue**: Consider RabbitMQ/Kafka for high-volume processing
5. **Load Balancing**: Distribute traffic across multiple instances
6. **Monitoring**: Comprehensive logging and metrics collection

## Performance Optimization

1. **Data Compression**: Gzip compression for API responses
2. **WebSocket Compression**: Per-message deflate for real-time data
3. **Lazy Loading**: Load data on-demand in the frontend
4. **Database Indexing**: Optimize query performance
5. **Connection Reuse**: Maintain persistent connections where possible
6. **Batch Operations**: Group multiple operations when feasible