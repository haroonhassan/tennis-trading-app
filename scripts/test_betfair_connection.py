#!/usr/bin/env python3
"""Test Betfair API connection."""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import from backend
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


class BetfairConnectionTest:
    """Test Betfair API connection and authentication."""
    
    def __init__(self):
        """Initialize with environment variables."""
        self.username = os.getenv("BETFAIR_USERNAME")
        self.password = os.getenv("BETFAIR_PASSWORD")
        self.app_key = os.getenv("BETFAIR_APP_KEY")
        self.cert_file = os.getenv("BETFAIR_CERT_FILE")
        
        # API endpoints
        self.identity_url = "https://identitysso-cert.betfair.com/api/certlogin"
        self.api_url = "https://api.betfair.com/exchange"
        
        self.session_token = None
        
    def validate_config(self):
        """Validate that all required configuration is present."""
        print("🔍 Checking configuration...")
        
        errors = []
        
        if not self.username:
            errors.append("❌ BETFAIR_USERNAME not set")
        else:
            print(f"✅ Username: {self.username}")
            
        if not self.password:
            errors.append("❌ BETFAIR_PASSWORD not set")
        else:
            print(f"✅ Password: {'*' * len(self.password)}")
            
        if not self.app_key:
            errors.append("❌ BETFAIR_APP_KEY not set")
        else:
            print(f"✅ App Key: {self.app_key}")
            
        if not self.cert_file:
            errors.append("❌ BETFAIR_CERT_FILE not set")
        else:
            if os.path.exists(self.cert_file):
                print(f"✅ Certificate file: {self.cert_file}")
            else:
                errors.append(f"❌ Certificate file not found: {self.cert_file}")
                
        if errors:
            print("\n⚠️  Configuration errors found:")
            for error in errors:
                print(f"  {error}")
            return False
            
        print("\n✅ All configuration validated successfully!")
        return True
        
    def login(self):
        """Login to Betfair using certificate authentication."""
        print("\n🔐 Attempting to login to Betfair...")
        
        payload = {
            'username': self.username,
            'password': self.password
        }
        
        headers = {
            'X-Application': self.app_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(
                self.identity_url,
                data=payload,
                cert=self.cert_file,
                headers=headers
            )
            
            if response.status_code == 200:
                response_json = response.json()
                
                if response_json.get('loginStatus') == 'SUCCESS':
                    self.session_token = response_json.get('sessionToken')
                    print(f"✅ Login successful!")
                    print(f"   Session Token: {self.session_token[:20]}...")
                    return True
                else:
                    print(f"❌ Login failed: {response_json.get('loginStatus')}")
                    if 'error' in response_json:
                        print(f"   Error: {response_json['error']}")
                    return False
            else:
                print(f"❌ HTTP Error {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.SSLError as e:
            print(f"❌ SSL Error: {e}")
            print("   Check that your certificate file is valid")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Error: {e}")
            return False
            
    def get_account_funds(self):
        """Get account funds to verify API access."""
        print("\n💰 Getting account funds...")
        
        headers = {
            'X-Application': self.app_key,
            'X-Authentication': self.session_token,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/account/json-rpc/v1",
                json={
                    "jsonrpc": "2.0",
                    "method": "AccountAPING/v1.0/getAccountFunds",
                    "params": {},
                    "id": 1
                },
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'result' in data:
                    funds = data['result']
                    print(f"✅ Account funds retrieved successfully:")
                    print(f"   Available: £{funds.get('availableToBetBalance', 0):.2f}")
                    print(f"   Exposure: £{funds.get('exposure', 0):.2f}")
                    print(f"   Retained Commission: £{funds.get('retainedCommission', 0):.2f}")
                    return True
                elif 'error' in data:
                    print(f"❌ API Error: {data['error']}")
                    return False
            else:
                print(f"❌ HTTP Error {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Error: {e}")
            return False
            
    def list_event_types(self):
        """List available sports/event types."""
        print("\n🎾 Listing available sports...")
        
        headers = {
            'X-Application': self.app_key,
            'X-Authentication': self.session_token,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/betting/json-rpc/v1",
                json={
                    "jsonrpc": "2.0",
                    "method": "SportsAPING/v1.0/listEventTypes",
                    "params": {
                        "filter": {}
                    },
                    "id": 1
                },
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'result' in data:
                    event_types = data['result']
                    print(f"✅ Found {len(event_types)} sports:")
                    
                    # Look for Tennis specifically
                    for event_type in event_types[:10]:  # Show first 10
                        name = event_type['eventType']['name']
                        market_count = event_type.get('marketCount', 0)
                        print(f"   - {name}: {market_count} markets")
                        
                        if name == "Tennis":
                            print(f"   🎾 Tennis found with {market_count} available markets!")
                    
                    return True
                elif 'error' in data:
                    print(f"❌ API Error: {data['error']}")
                    return False
            else:
                print(f"❌ HTTP Error {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Error: {e}")
            return False
            
    def run_tests(self):
        """Run all connection tests."""
        print("=" * 60)
        print("🚀 Betfair Connection Test")
        print("=" * 60)
        
        # Validate configuration
        if not self.validate_config():
            print("\n❌ Test failed: Configuration issues")
            return False
            
        # Login
        if not self.login():
            print("\n❌ Test failed: Login failed")
            return False
            
        # Get account funds
        if not self.get_account_funds():
            print("\n❌ Test failed: Could not retrieve account funds")
            return False
            
        # List sports
        if not self.list_event_types():
            print("\n❌ Test failed: Could not list sports")
            return False
            
        print("\n" + "=" * 60)
        print("✅ All tests passed! Betfair connection working correctly.")
        print("=" * 60)
        return True


if __name__ == "__main__":
    tester = BetfairConnectionTest()
    success = tester.run_tests()
    sys.exit(0 if success else 1)