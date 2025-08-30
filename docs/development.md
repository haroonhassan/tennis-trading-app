# Development Guide

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 16+
- Redis (for real-time features)
- Git

### Initial Setup

1. **Clone the repository**:
```bash
git clone <repository-url>
cd tennis-trading-app
```

2. **Set up the backend**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
```

3. **Set up the frontend**:
```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local if needed
```

4. **Start Redis** (for WebSocket support):
```bash
redis-server
```

### Running the Application

#### Development Mode

**Backend**:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Frontend**:
```bash
cd frontend
npm start
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

#### Using Make Commands

```bash
# Install all dependencies
make install

# Run both frontend and backend
make dev

# Run tests
make test

# Lint code
make lint

# Format code
make format
```

## Project Structure

```
tennis-trading-app/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── core/         # Core configuration
│   │   ├── models/       # Data models
│   │   ├── services/     # Business logic
│   │   └── utils/        # Utility functions
│   ├── tests/
│   │   ├── unit/         # Unit tests
│   │   └── integration/  # Integration tests
│   └── scripts/          # Utility scripts
├── frontend/
│   ├── public/           # Static files
│   └── src/
│       ├── components/   # React components
│       ├── services/     # API services
│       ├── utils/        # Utility functions
│       └── styles/       # CSS files
└── docs/                 # Documentation

```

## Development Workflow

### 1. Feature Development

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Push to remote
git push origin feature/your-feature-name
```

### 2. Code Style

#### Python (Backend)
- Follow PEP 8
- Use type hints
- Maximum line length: 88 characters (Black default)

```python
# Good
def calculate_profit(
    stake: float,
    odds: float,
    commission: float = 0.05
) -> float:
    """Calculate net profit from a bet."""
    gross_profit = stake * (odds - 1)
    return gross_profit * (1 - commission)
```

#### TypeScript (Frontend)
- Use functional components with hooks
- Prefer interfaces over types
- Use proper TypeScript types

```typescript
// Good
interface BetProps {
  marketId: string;
  stake: number;
  odds: number;
}

const PlaceBet: React.FC<BetProps> = ({ marketId, stake, odds }) => {
  // Component logic
};
```

### 3. Testing

#### Backend Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/unit/test_betting.py

# Run with verbose output
pytest -v
```

#### Frontend Testing

```bash
# Run tests
npm test

# Run with coverage
npm test -- --coverage

# Run in watch mode
npm test -- --watchAll
```

### 4. Database Migrations

Using Alembic for database migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "Add user table"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## API Development

### Adding a New Endpoint

1. **Define the route** in `backend/app/api/`:
```python
from fastapi import APIRouter, Depends
from app.models import Market
from app.services import betting_service

router = APIRouter()

@router.get("/markets/{market_id}")
async def get_market(market_id: str):
    return await betting_service.get_market(market_id)
```

2. **Add business logic** in `backend/app/services/`:
```python
async def get_market(market_id: str):
    # Implementation
    pass
```

3. **Create models** in `backend/app/models/`:
```python
from pydantic import BaseModel

class Market(BaseModel):
    id: str
    name: str
    odds: float
```

## Frontend Development

### Adding a New Component

1. **Create component file**:
```typescript
// frontend/src/components/MarketView.tsx
import React, { useState, useEffect } from 'react';
import { getMarket } from '../services/api';

interface MarketViewProps {
  marketId: string;
}

export const MarketView: React.FC<MarketViewProps> = ({ marketId }) => {
  const [market, setMarket] = useState(null);

  useEffect(() => {
    getMarket(marketId).then(setMarket);
  }, [marketId]);

  return (
    <div>
      {/* Component JSX */}
    </div>
  );
};
```

2. **Add API service**:
```typescript
// frontend/src/services/api.ts
export const getMarket = async (marketId: string) => {
  const response = await fetch(`/api/markets/${marketId}`);
  return response.json();
};
```

## WebSocket Development

### Backend WebSocket Handler

```python
from fastapi import WebSocket

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Process data
            await websocket.send_text(f"Message: {data}")
    except WebSocketDisconnect:
        pass
```

### Frontend WebSocket Client

```typescript
import { io } from 'socket.io-client';

const socket = io('ws://localhost:8000');

socket.on('connect', () => {
  console.log('Connected to server');
});

socket.on('market_update', (data) => {
  // Handle market updates
});
```

## Environment Variables

### Backend (.env)
```env
# Application
DEBUG=true
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:pass@localhost/dbname

# Redis
REDIS_URL=redis://localhost:6379

# Betfair
BETFAIR_USERNAME=username
BETFAIR_PASSWORD=password
BETFAIR_APP_KEY=app-key
BETFAIR_CERT_PATH=/path/to/cert
```

### Frontend (.env.local)
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
```

## Debugging

### Backend Debugging

Using VS Code:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload"],
      "jinja": true
    }
  ]
}
```

### Frontend Debugging

Chrome DevTools:
1. Add `debugger;` statements in code
2. Open Chrome DevTools
3. Use Sources tab for breakpoints

## Performance Optimization

### Backend
- Use async/await for I/O operations
- Implement caching with Redis
- Use connection pooling for database
- Profile with `cProfile`

### Frontend
- Implement React.memo for expensive components
- Use useMemo and useCallback hooks
- Lazy load components
- Optimize bundle size with code splitting

## Deployment Preparation

### Backend
```bash
# Run production server
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Frontend
```bash
# Build for production
npm run build

# Serve static files
npx serve -s build
```

## Troubleshooting

### Common Issues

1. **Port already in use**:
```bash
# Find process using port
lsof -i :8000
# Kill process
kill -9 <PID>
```

2. **Module not found**:
```bash
# Reinstall dependencies
pip install -r requirements.txt
npm install
```

3. **Database connection issues**:
- Check DATABASE_URL in .env
- Ensure database service is running
- Verify credentials

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Pytest Documentation](https://docs.pytest.org)