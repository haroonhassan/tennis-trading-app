#!/usr/bin/env python3
"""Test script for data aggregation service."""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class AggregationTestClient:
    """Test client for aggregation service."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize test client.
        
        Args:
            base_url: API base URL
        """
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def test_unified_matches(self):
        """Test unified matches endpoint."""
        print("\n" + "=" * 80)
        print("TESTING UNIFIED MATCHES")
        print("=" * 80)
        
        # Get all unified matches
        print("\n1. Getting all unified matches...")
        response = await self.client.get(f"{self.base_url}/api/unified/matches")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Found {data['total']} unified matches")
            
            # Display first few matches
            for match in data['matches'][:3]:
                print(f"\n   Match ID: {match['match_id']}")
                print(f"   Players: {match['match']['player1']} vs {match['match']['player2']}")
                print(f"   Tournament: {match['match']['tournament']}")
                print(f"   Status: {match['match']['status']}")
                
                # Show price comparison if available
                if match.get('price_comparison'):
                    pc = match['price_comparison']
                    print(f"   Best Prices:")
                    print(f"      Player 1 Back: {pc['best_back_player1']} ({pc['best_back_player1_provider']})")
                    print(f"      Player 1 Lay: {pc['best_lay_player1']} ({pc['best_lay_player1_provider']})")
                    print(f"      Player 2 Back: {pc['best_back_player2']} ({pc['best_back_player2_provider']})")
                    print(f"      Player 2 Lay: {pc['best_lay_player2']} ({pc['best_lay_player2_provider']})")
                
                # Show data quality
                if match.get('data_quality'):
                    print(f"   Data Quality:")
                    for provider, quality in match['data_quality'].items():
                        print(f"      {provider}: {quality['status']} (score: {quality['quality_score']:.2f})")
                
                # Show arbitrage opportunities
                if match.get('arbitrage_opportunities'):
                    print(f"   Arbitrage Opportunities: {len(match['arbitrage_opportunities'])}")
                    for opp in match['arbitrage_opportunities']:
                        print(f"      Type: {opp['type']}, Profit: {opp['profit_percentage']:.2f}%")
        else:
            print(f"   ❌ Error: {response.status_code}")
        
        # Get matches with arbitrage
        print("\n2. Getting matches with arbitrage opportunities...")
        response = await self.client.get(
            f"{self.base_url}/api/unified/matches",
            params={"with_arbitrage": True}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Found {data['total']} matches with arbitrage")
        else:
            print(f"   ❌ Error: {response.status_code}")
        
        # Get live matches
        print("\n3. Getting live unified matches...")
        response = await self.client.get(
            f"{self.base_url}/api/unified/matches",
            params={"status": "live"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Found {data['total']} live matches")
            return data['matches']
        else:
            print(f"   ❌ Error: {response.status_code}")
            return []
    
    async def test_unified_match_details(self, match_id: str):
        """
        Test unified match details endpoint.
        
        Args:
            match_id: Unified match ID
        """
        print("\n" + "=" * 80)
        print(f"TESTING UNIFIED MATCH DETAILS: {match_id}")
        print("=" * 80)
        
        response = await self.client.get(f"{self.base_url}/api/unified/match/{match_id}")
        
        if response.status_code == 200:
            data = response.json()
            match = data['match']
            comparison = data.get('comparison', {})
            
            print(f"\n✅ Match Details:")
            print(f"   Players: {match['match']['player1']} vs {match['match']['player2']}")
            print(f"   Tournament: {match['match']['tournament']}")
            print(f"   Status: {match['match']['status']}")
            print(f"   Surface: {match['match']['surface']}")
            
            if match.get('score'):
                print(f"   Score: {match['score']}")
            
            # Provider comparison
            if comparison:
                print(f"\n📊 Provider Comparison:")
                for provider, info in comparison.get('providers', {}).items():
                    print(f"   {provider}:")
                    print(f"      Match ID: {info['match_id']}")
                    print(f"      Has Prices: {info['has_prices']}")
                    print(f"      Has Score: {info['has_score']}")
                
                # Best prices
                if comparison.get('best_prices'):
                    print(f"\n💰 Best Prices:")
                    bp = comparison['best_prices']
                    print(f"   Player 1:")
                    print(f"      Back: {bp['player1_back']['price']} ({bp['player1_back']['provider']})")
                    print(f"      Lay: {bp['player1_lay']['price']} ({bp['player1_lay']['provider']})")
                    print(f"   Player 2:")
                    print(f"      Back: {bp['player2_back']['price']} ({bp['player2_back']['provider']})")
                    print(f"      Lay: {bp['player2_lay']['price']} ({bp['player2_lay']['provider']})")
                
                # Data quality
                if comparison.get('data_quality'):
                    print(f"\n📈 Data Quality:")
                    for provider, quality in comparison['data_quality'].items():
                        print(f"   {provider}:")
                        print(f"      Status: {quality['status']}")
                        print(f"      Latency: {quality['latency_ms']:.1f}ms")
                        print(f"      Quality Score: {quality['quality_score']:.2f}")
        else:
            print(f"❌ Error: {response.status_code}")
    
    async def test_arbitrage_opportunities(self):
        """Test arbitrage opportunities endpoint."""
        print("\n" + "=" * 80)
        print("TESTING ARBITRAGE OPPORTUNITIES")
        print("=" * 80)
        
        # Get active opportunities
        print("\n1. Getting active arbitrage opportunities...")
        response = await self.client.get(f"{self.base_url}/api/arbitrage")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Found {data['total']} active opportunities")
            
            # Display opportunities
            for opp in data['opportunities'][:5]:
                print(f"\n   Opportunity:")
                print(f"      Match ID: {opp['match_id']}")
                print(f"      Type: {opp['type']}")
                print(f"      Player: {opp['player']}")
                print(f"      Back: {opp['back_price']} @ {opp['back_provider']}")
                print(f"      Lay: {opp['lay_price']} @ {opp['lay_provider']}")
                print(f"      Profit: {opp['profit_percentage']:.2f}%")
                print(f"      Risk: {opp['risk_level']}")
                print(f"      Confidence: {opp['confidence']:.2f}")
                print(f"      Valid: {opp['is_valid']}")
        else:
            print(f"   ❌ Error: {response.status_code}")
        
        # Get historical opportunities
        print("\n2. Getting historical arbitrage opportunities...")
        response = await self.client.get(
            f"{self.base_url}/api/arbitrage",
            params={"active_only": False}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Found {data['total']} total opportunities (including historical)")
        else:
            print(f"   ❌ Error: {response.status_code}")
    
    async def test_provider_comparison(self, match_id: str):
        """
        Test provider comparison endpoint.
        
        Args:
            match_id: Unified match ID
        """
        print("\n" + "=" * 80)
        print(f"TESTING PROVIDER COMPARISON: {match_id}")
        print("=" * 80)
        
        response = await self.client.get(f"{self.base_url}/api/provider-comparison/{match_id}")
        
        if response.status_code == 200:
            comparison = response.json()
            
            print(f"\n✅ Provider Comparison:")
            
            # Providers
            print(f"\n📊 Providers:")
            for provider, info in comparison.get('providers', {}).items():
                print(f"   {provider}: Match ID {info['match_id']}")
            
            # Best prices
            if comparison.get('best_prices'):
                print(f"\n💰 Best Prices Across Providers:")
                self._display_price_comparison(comparison['best_prices'])
            
            # Arbitrage
            if comparison.get('arbitrage'):
                print(f"\n💸 Arbitrage Opportunities: {len(comparison['arbitrage'])}")
                for arb in comparison['arbitrage']:
                    print(f"   - {arb['type']}: {arb['profit_percentage']:.2f}% profit ({arb['risk_level']} risk)")
            
            # Data quality
            if comparison.get('data_quality'):
                print(f"\n📈 Data Quality Comparison:")
                for provider, quality in comparison['data_quality'].items():
                    print(f"   {provider}: {quality['status']} (latency: {quality['latency_ms']:.0f}ms, score: {quality['quality_score']:.2f})")
        else:
            print(f"❌ Error: {response.status_code}")
    
    def _display_price_comparison(self, prices: Dict[str, Any]):
        """Display price comparison in a formatted way."""
        print(f"   Player 1:")
        print(f"      Best Back: {prices['player1_back']['price']:.2f} @ {prices['player1_back']['provider']}")
        print(f"      Best Lay:  {prices['player1_lay']['price']:.2f} @ {prices['player1_lay']['provider']}")
        print(f"   Player 2:")
        print(f"      Best Back: {prices['player2_back']['price']:.2f} @ {prices['player2_back']['provider']}")
        print(f"      Best Lay:  {prices['player2_lay']['price']:.2f} @ {prices['player2_lay']['provider']}")
    
    async def run_all_tests(self):
        """Run all aggregation tests."""
        print("=" * 80)
        print("DATA AGGREGATION SERVICE TEST")
        print("=" * 80)
        print(f"Server: {self.base_url}")
        print(f"Time: {datetime.now().isoformat()}")
        
        try:
            # Test unified matches
            matches = await self.test_unified_matches()
            
            # Test match details for first match
            if matches:
                first_match_id = matches[0]['match_id']
                await self.test_unified_match_details(first_match_id)
                await self.test_provider_comparison(first_match_id)
            
            # Test arbitrage opportunities
            await self.test_arbitrage_opportunities()
            
            print("\n" + "=" * 80)
            print("✅ ALL TESTS COMPLETED")
            print("=" * 80)
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
        finally:
            await self.client.aclose()


async def main():
    """Main test function."""
    # Check if server URL is provided
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    # Create test client
    client = AggregationTestClient(server_url)
    
    # Run tests
    await client.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())