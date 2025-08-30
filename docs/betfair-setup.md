# Betfair API Setup Guide

## Prerequisites

Before you begin, you'll need:
1. A Betfair account with API access
2. Application key from Betfair
3. SSL certificates for non-interactive login

## Step 1: Create a Betfair Account

1. Go to [Betfair](https://www.betfair.com) and create an account
2. Verify your identity as required by Betfair
3. Ensure your account has API access enabled

## Step 2: Obtain API Access

### Getting Your Application Key

1. Log into your Betfair account
2. Navigate to [Betfair Developer Program](https://developer.betfair.com)
3. Go to "My Account" → "Application Keys"
4. Create a new application key:
   - Choose "Delayed Application Key" for development/testing
   - Choose "Live Application Key" for production (requires approval)
5. Save your application key securely

### API Endpoints

- **UK Exchange**: `https://api.betfair.com/exchange/`
- **Australian Exchange**: `https://api-au.betfair.com/exchange/`

## Step 3: Generate SSL Certificates

For non-interactive login (recommended for automated trading):

### Generate Self-Signed Certificate

```bash
# Generate private key
openssl genrsa -out client-2048.key 2048

# Generate certificate signing request
openssl req -new -key client-2048.key -out client-2048.csr

# Generate self-signed certificate (valid for 365 days)
openssl x509 -req -days 365 -in client-2048.csr -signkey client-2048.key -out client-2048.crt
```

### Upload Certificate to Betfair

1. Log into your Betfair account
2. Go to "My Account" → "My API"
3. Upload the `client-2048.crt` file
4. Wait for confirmation (usually immediate)

## Step 4: Configure the Application

### Environment Variables

Create a `.env` file in the backend directory:

```env
# Betfair API Configuration
BETFAIR_USERNAME=your_username
BETFAIR_PASSWORD=your_password
BETFAIR_APP_KEY=your_app_key
BETFAIR_CERT_PATH=/path/to/client-2048.crt
BETFAIR_KEY_PATH=/path/to/client-2048.key

# Optional: Use different exchange
BETFAIR_EXCHANGE_URL=https://api.betfair.com/exchange/
```

### Test Connection

Run the test script to verify your setup:

```bash
cd backend
python scripts/test_betfair_connection.py
```

## Step 5: API Rate Limits

Be aware of Betfair's rate limits:

- **Data Request Limits**:
  - 200 requests per minute for most operations
  - Weight-based system for some endpoints

- **Transaction Limits**:
  - 1000 transactions per hour (Free)
  - Higher limits available with subscription

## Step 6: Market Data Access

### Navigation API
Used to retrieve market catalogues and market information:
- List available sports
- Get competitions and events
- Retrieve market types

### Betting API
Core betting operations:
- Place bets
- Cancel bets
- Update bets
- List current orders

### Account API
Account management:
- Get account funds
- View transaction history
- Transfer funds

## Best Practices

1. **Session Management**:
   - Keep sessions alive with keepAlive calls
   - Implement automatic re-login on session expiry

2. **Error Handling**:
   - Implement exponential backoff for rate limits
   - Handle network timeouts gracefully
   - Log all API errors for debugging

3. **Security**:
   - Never commit credentials to version control
   - Use environment variables for sensitive data
   - Rotate certificates periodically
   - Use IP restrictions where possible

4. **Testing**:
   - Use delayed application keys for development
   - Test with small stakes initially
   - Implement paper trading mode

## Troubleshooting

### Common Issues

1. **CERT_NOT_PROVIDED Error**:
   - Ensure certificate paths are correct
   - Check certificate hasn't expired
   - Verify certificate is uploaded to Betfair

2. **INVALID_APP_KEY Error**:
   - Verify application key is correct
   - Check key hasn't been revoked
   - Ensure using correct exchange endpoint

3. **NO_SESSION Error**:
   - Session has expired
   - Implement automatic re-login

4. **EXCEEDED_THROTTLE Error**:
   - You've hit rate limits
   - Implement request queuing
   - Consider upgrading API access

## Additional Resources

- [Betfair API Documentation](https://docs.developer.betfair.com)
- [Betfair API Forum](https://forum.developer.betfair.com)
- [API Demo Tools](https://demo.betfair.com)
- [Market Data Definitions](https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/Market+Data+Request+Definitions)

## Support

For API-specific issues:
- Email: bdp@betfair.com
- Forum: https://forum.developer.betfair.com

For account issues:
- Betfair Customer Service
- Live Chat available on website