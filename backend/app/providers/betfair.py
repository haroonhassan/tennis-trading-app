"""Betfair data provider implementation."""

import os
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import threading
from dataclasses import dataclass

from betfairlightweight import APIClient
from betfairlightweight.exceptions import BetfairError
from betfairlightweight import filters

from .base import (
    BaseDataProvider, 
    Match, 
    PriceData, 
    Score, 
    MatchStats
)
from .models import StreamMessage, StreamConfig, StreamStatus
from .betfair_stream import BetfairStreamClient
from .tennis_models import TennisMatch, TennisScore, MatchStatistics, Player, MatchStatus
from .normalizer import MatchNormalizer


class BetfairProvider(BaseDataProvider):
    """Betfair betting exchange data provider."""
    
    TENNIS_EVENT_TYPE_ID = "2"  # Tennis sport ID in Betfair
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize Betfair provider."""
        super().__init__(logger)
        
        # Load credentials from environment
        self.username = os.getenv("BETFAIR_USERNAME")
        self.password = os.getenv("BETFAIR_PASSWORD")
        self.app_key = os.getenv("BETFAIR_APP_KEY")
        self.cert_file = os.getenv("BETFAIR_CERT_FILE")
        
        # Validate configuration
        self._validate_config()
        
        # Initialize API client
        # For a single .pem file, use cert_files parameter
        self.client = APIClient(
            username=self.username,
            password=self.password,
            app_key=self.app_key,
            cert_files=self.cert_file,  # Single .pem file
            lightweight=True
        )
        
        # Session management
        self.last_keep_alive = None
        self.keep_alive_interval = 600  # 10 minutes
        self._keep_alive_thread = None
        self._stop_keep_alive = threading.Event()
        
        # Price subscription management
        self._price_subscriptions = {}
        self._price_callback = None
        
        # Streaming
        self.stream_client = None
        self._stream_callback = None
        
        # Tennis data
        self.normalizer = MatchNormalizer(logger)
        
    def _validate_config(self):
        """Validate required configuration is present."""
        missing = []
        
        if not self.username:
            missing.append("BETFAIR_USERNAME")
        if not self.password:
            missing.append("BETFAIR_PASSWORD")
        if not self.app_key:
            missing.append("BETFAIR_APP_KEY")
        if not self.cert_file:
            missing.append("BETFAIR_CERT_FILE")
        elif not os.path.exists(self.cert_file):
            raise FileNotFoundError(f"Certificate file not found: {self.cert_file}")
            
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    def authenticate(self) -> bool:
        """
        Authenticate with Betfair using Non-Interactive login.
        
        Returns:
            bool: True if authentication successful
        """
        try:
            # Login using certificate authentication
            self.client.login()
            
            self.is_authenticated = True
            self.session_token = self.client.session_token
            self.last_keep_alive = datetime.now()
            
            # Start keep-alive thread
            self._start_keep_alive_thread()
            
            self.logger.info(f"Successfully authenticated with Betfair. Session token: {self.session_token[:20]}...")
            return True
            
        except BetfairError as e:
            self.logger.error(f"Betfair authentication failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during authentication: {e}")
            return False
    
    def _start_keep_alive_thread(self):
        """Start background thread to keep session alive."""
        if self._keep_alive_thread and self._keep_alive_thread.is_alive():
            return
            
        self._stop_keep_alive.clear()
        self._keep_alive_thread = threading.Thread(target=self._keep_alive_worker)
        self._keep_alive_thread.daemon = True
        self._keep_alive_thread.start()
    
    def _keep_alive_worker(self):
        """Background worker to maintain session."""
        while not self._stop_keep_alive.is_set():
            try:
                # Wait for interval or stop signal
                if self._stop_keep_alive.wait(self.keep_alive_interval):
                    break
                    
                # Send keep alive
                if self.is_authenticated:
                    self.keep_alive()
                    
            except Exception as e:
                self.logger.error(f"Keep-alive error: {e}")
    
    def get_live_matches(self, sport: str = "tennis") -> List[Match]:
        """
        Get list of live tennis matches.
        
        Returns:
            List of Match objects
        """
        if not self.is_authenticated:
            self.logger.error("Not authenticated")
            return []
            
        try:
            # Create filter for in-play tennis matches
            market_filter = filters.market_filter(
                event_type_ids=[self.TENNIS_EVENT_TYPE_ID],
                market_type_codes=["MATCH_ODDS"],
                in_play_only=True
            )
            
            # Get markets
            markets = self.client.betting.list_market_catalogue(
                filter=market_filter,
                market_projection=["EVENT", "MARKET_START_TIME", "RUNNER_DESCRIPTION", "COMPETITION"],
                max_results=100
            )
            
            matches = []
            for market in markets:
                # Parse player names from runners (dict format due to lightweight=True)
                runners = market.get('runners', [])
                home_player = runners[0].get('runnerName', 'Unknown') if len(runners) > 0 else "Unknown"
                away_player = runners[1].get('runnerName', 'Unknown') if len(runners) > 1 else "Unknown"
                
                event = market.get('event', {})
                competition = market.get('competition', {})
                
                match = Match(
                    id=market.get('marketId'),
                    event_name=event.get('name', 'Unknown'),
                    competition=competition.get('name', 'Unknown'),
                    market_start_time=market.get('marketStartTime'),
                    status="in-play" if market.get('inPlay') else "pre-match",
                    home_player=home_player,
                    away_player=away_player,
                    metadata={
                        "total_matched": market.get('totalMatched'),
                        "event_id": event.get('id')
                    }
                )
                matches.append(match)
                
            self.logger.info(f"Found {len(matches)} live tennis matches")
            return matches
            
        except BetfairError as e:
            self.logger.error(f"Error getting live matches: {e}")
            return []
    
    def subscribe_to_prices(
        self, 
        market_ids: List[str], 
        callback: Callable[[str, PriceData], None]
    ) -> bool:
        """
        Subscribe to price updates for markets.
        
        Note: This is a polling implementation. For real-time streaming,
        you would need to implement Betfair's Exchange Stream API.
        """
        if not self.is_authenticated:
            self.logger.error("Not authenticated")
            return False
            
        try:
            self._price_callback = callback
            
            for market_id in market_ids:
                if market_id not in self._price_subscriptions:
                    self._price_subscriptions[market_id] = True
                    self.logger.info(f"Subscribed to prices for market {market_id}")
                    
            # In a real implementation, you would start streaming here
            # For now, we'll use polling in get_market_prices
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to prices: {e}")
            return False
    
    def unsubscribe_from_prices(self, market_ids: List[str]) -> bool:
        """Unsubscribe from price updates."""
        try:
            for market_id in market_ids:
                if market_id in self._price_subscriptions:
                    del self._price_subscriptions[market_id]
                    self.logger.info(f"Unsubscribed from market {market_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error unsubscribing: {e}")
            return False
    
    def get_market_prices(self, market_id: str) -> Optional[List[PriceData]]:
        """Get current prices for a market."""
        if not self.is_authenticated:
            return None
            
        try:
            # Get market book with prices
            price_projection = filters.price_projection(
                price_data=['EX_BEST_OFFERS', 'EX_TRADED'],
                ex_best_offers_overrides=filters.ex_best_offers_overrides(
                    best_prices_depth=3
                )
            )
            
            market_books = self.client.betting.list_market_book(
                market_ids=[market_id],
                price_projection=price_projection
            )
            
            if not market_books:
                return None
                
            market_book = market_books[0]
            price_data_list = []
            
            # Handle dict format due to lightweight=True
            runners = market_book.get('runners', [])
            
            for runner in runners:
                # Extract best back and lay prices
                back_prices = []
                lay_prices = []
                
                ex = runner.get('ex', {})
                
                if ex.get('availableToBack'):
                    for price_size in ex['availableToBack']:
                        back_prices.append({
                            "price": price_size.get('price', 0),
                            "size": price_size.get('size', 0)
                        })
                        
                if ex.get('availableToLay'):
                    for price_size in ex['availableToLay']:
                        lay_prices.append({
                            "price": price_size.get('price', 0),
                            "size": price_size.get('size', 0)
                        })
                
                price_data = PriceData(
                    selection_id=str(runner.get('selectionId')),
                    selection_name=str(runner.get('selectionId')),  # Name not available in lightweight mode
                    back_prices=back_prices,
                    lay_prices=lay_prices,
                    last_price_traded=runner.get('lastPriceTraded'),
                    total_matched=runner.get('totalMatched')
                )
                price_data_list.append(price_data)
                
                # Call callback if subscribed
                if self._price_callback and market_id in self._price_subscriptions:
                    self._price_callback(market_id, price_data)
                    
            return price_data_list
            
        except BetfairError as e:
            self.logger.error(f"Error getting market prices: {e}")
            return None
    
    def get_match_scores(self, match_id: str) -> Optional[Score]:
        """
        Get current score for a match.
        
        Note: Betfair doesn't provide detailed score data through the API.
        This would typically come from a separate scores feed.
        """
        self.logger.warning("Score data not available through Betfair API")
        return None
    
    def get_match_stats(self, match_id: str) -> Optional[MatchStats]:
        """
        Get statistics for a match.
        
        Note: Betfair doesn't provide detailed stats through the API.
        """
        self.logger.warning("Stats data not available through Betfair API")
        return None
    
    def get_market_book(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed market book with prices and volumes."""
        if not self.is_authenticated:
            return None
        
        try:
            # Get market book with full price data
            market_books = self.client.betting.list_market_book(
                market_ids=[market_id],
                price_projection={
                    'priceData': ['EX_BEST_OFFERS', 'EX_TRADED'],
                    'virtualise': True
                }
            )
            
            # Return first market book (we only requested one)
            if market_books:
                if isinstance(market_books, list):
                    return market_books[0]
                else:
                    # Handle dict response
                    return market_books
            
            return None
            
        except BetfairError as e:
            self.logger.error(f"Error getting market book: {e}")
            return None
    
    def get_account_balance(self) -> Dict[str, float]:
        """Get account balance information."""
        if not self.is_authenticated:
            self.logger.error("Not authenticated")
            return {}
            
        try:
            # Get account funds
            account_funds = self.client.account.get_account_funds()
            
            # Handle dict format due to lightweight=True
            return {
                "available_balance": account_funds.get('availableToBetBalance', 0),
                "exposure": account_funds.get('exposure', 0),
                "exposure_limit": account_funds.get('exposureLimit', 0),
                "retained_commission": account_funds.get('retainedCommission', 0),
                "wallet": account_funds.get('wallet', 0)
            }
            
        except BetfairError as e:
            self.logger.error(f"Error getting account balance: {e}")
            return {}
    
    def place_back_bet(
        self,
        market_id: str,
        selection_id: str,
        price: float,
        size: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Place a back bet on Betfair."""
        return self._place_bet(market_id, selection_id, "BACK", price, size, **kwargs)
    
    def place_lay_bet(
        self,
        market_id: str,
        selection_id: str,
        price: float,
        size: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Place a lay bet on Betfair."""
        return self._place_bet(market_id, selection_id, "LAY", price, size, **kwargs)
    
    def _place_bet(
        self,
        market_id: str,
        selection_id: str,
        side: str,
        price: float,
        size: float,
        persistence_type: str = "LAPSE",
        order_type: str = "LIMIT",
        time_in_force: Optional[str] = None,
        min_fill_size: Optional[float] = None,
        bet_target_type: Optional[str] = None,
        bet_target_size: Optional[float] = None,
        customer_ref: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Internal method to place a bet on Betfair."""
        if not self.is_authenticated:
            return {"success": False, "error": "Not authenticated"}
            
        try:
            # Create limit order
            limit_order = {
                "size": size,
                "price": price,
                "persistenceType": persistence_type
            }
            
            # Add optional parameters
            if time_in_force:
                limit_order["timeInForce"] = time_in_force
            if min_fill_size:
                limit_order["minFillSize"] = min_fill_size
            if bet_target_type and bet_target_size:
                limit_order["betTargetType"] = bet_target_type
                limit_order["betTargetSize"] = bet_target_size
            
            # Create place instruction
            place_instruction = {
                "orderType": order_type,
                "selectionId": selection_id,
                "side": side,
                "limitOrder": limit_order
            }
            
            if customer_ref:
                place_instruction["customerOrderRef"] = customer_ref
            
            # Place the bet
            result = self.client.betting.place_orders(
                market_id=market_id,
                instructions=[place_instruction],
                customer_ref=customer_ref
            )
            
            # Handle dict format due to lightweight=True
            if isinstance(result, dict):
                status = result.get('status')
                if status == "SUCCESS":
                    instruction_reports = result.get('instructionReports', [])
                    if instruction_reports:
                        report = instruction_reports[0]
                        return {
                            "success": True,
                            "bet_id": report.get('betId'),
                            "placed_date": report.get('placedDate'),
                            "average_price_matched": report.get('averagePriceMatched', 0),
                            "size_matched": report.get('sizeMatched', 0),
                            "status": report.get('status'),
                            "order_status": report.get('orderStatus'),
                            "instruction": report
                        }
                else:
                    return {
                        "success": False,
                        "error": result.get('errorCode', 'Unknown error'),
                        "status": status
                    }
            else:
                # Handle object format
                if result.status == "SUCCESS":
                    instruction_report = result.instruction_reports[0]
                    return {
                        "success": True,
                        "bet_id": instruction_report.bet_id,
                        "placed_date": instruction_report.placed_date,
                        "average_price_matched": instruction_report.average_price_matched,
                        "size_matched": instruction_report.size_matched,
                        "status": instruction_report.status
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error_code,
                        "status": result.status
                    }
                
        except BetfairError as e:
            self.logger.error(f"Error placing bet: {e}")
            return {"success": False, "error": str(e)}
    
    def cancel_bet(self, bet_id: str, size_reduction: Optional[float] = None) -> bool:
        """Cancel or reduce a bet."""
        if not self.is_authenticated:
            return False
            
        try:
            # First, get the market ID for this bet
            current_orders = self.client.betting.list_current_orders(
                bet_ids=[bet_id]
            )
            
            # Extract market_id from the order
            market_id = None
            if isinstance(current_orders, dict):
                orders = current_orders.get('currentOrders', [])
                if orders:
                    market_id = orders[0].get('marketId')
            
            # Create cancel instruction
            instruction = {"betId": bet_id}
            if size_reduction:
                instruction["sizeReduction"] = size_reduction
            
            # Cancel the bet - market_id might be required
            kwargs = {"instructions": [instruction]}
            if market_id:
                kwargs["market_id"] = market_id
                
            result = self.client.betting.cancel_orders(**kwargs)
            
            # Handle dict response
            if isinstance(result, dict):
                status = result.get('status')
                if status == "SUCCESS":
                    # Check instruction reports
                    reports = result.get('instructionReports', [])
                    if reports and reports[0].get('status') == 'SUCCESS':
                        return True
                    else:
                        self.logger.error(f"Cancel failed: {reports[0] if reports else 'No report'}")
                        return False
                else:
                    self.logger.error(f"Cancel failed with status: {status}")
                    return False
            else:
                return result.status == "SUCCESS"
            
        except BetfairError as e:
            self.logger.error(f"Error cancelling bet: {e}")
            return False
    
    def update_bet(
        self,
        bet_id: str,
        new_price: Optional[float] = None,
        new_size: Optional[float] = None
    ) -> Dict[str, Any]:
        """Update bet price and/or size by replacing the bet."""
        if not self.is_authenticated:
            return {"success": False, "error": "Not authenticated"}
        
        try:
            # Betfair doesn't support direct bet updates, so we need to:
            # 1. Get current bet details
            # 2. Cancel the old bet
            # 3. Place a new bet with updated parameters
            
            # Get current order details
            current_orders = self.client.betting.list_current_orders(
                bet_ids=[bet_id]
            )
            
            if isinstance(current_orders, dict):
                orders = current_orders.get('currentOrders', [])
            else:
                orders = []
            
            if not orders:
                return {"success": False, "error": "Bet not found"}
            
            order = orders[0]
            
            # Cancel existing bet
            if not self.cancel_bet(bet_id):
                return {"success": False, "error": "Failed to cancel existing bet"}
            
            # Place new bet with updated parameters
            market_id = order.get('marketId')
            selection_id = order.get('selectionId')
            side = order.get('side')
            
            # Use new values or existing ones
            price = new_price if new_price else order.get('priceSize', {}).get('price')
            size = new_size if new_size else order.get('sizeRemaining')
            
            # Place the replacement bet
            if side == "BACK":
                return self.place_back_bet(market_id, selection_id, price, size)
            else:
                return self.place_lay_bet(market_id, selection_id, price, size)
                
        except BetfairError as e:
            self.logger.error(f"Error updating bet: {e}")
            return {"success": False, "error": str(e)}
    
    def get_open_orders(self, market_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of open/unmatched orders."""
        if not self.is_authenticated:
            return []
        
        try:
            # Build filter
            kwargs = {}
            if market_id:
                kwargs['market_ids'] = [market_id]
            
            # Get current orders
            current_orders = self.client.betting.list_current_orders(**kwargs)
            
            # Handle dict format due to lightweight=True
            orders = current_orders.get('currentOrders', []) if isinstance(current_orders, dict) else []
            
            open_orders = []
            for order in orders:
                price_size = order.get('priceSize', {})
                open_orders.append({
                    "bet_id": order.get('betId'),
                    "market_id": order.get('marketId'),
                    "selection_id": order.get('selectionId'),
                    "price": price_size.get('price', 0),
                    "size": price_size.get('size', 0),
                    "side": order.get('side'),
                    "status": order.get('status'),
                    "matched_size": order.get('sizeMatched', 0),
                    "remaining_size": order.get('sizeRemaining', 0),
                    "placed_date": order.get('placedDate'),
                    "average_price_matched": order.get('averagePriceMatched', 0)
                })
            
            return open_orders
            
        except BetfairError as e:
            self.logger.error(f"Error getting open orders: {e}")
            return []
    
    def get_matched_bets(self, market_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of matched bets."""
        if not self.is_authenticated:
            return []
        
        try:
            # Build filter
            kwargs = {'order_projection': 'EXECUTABLE'}
            if market_id:
                kwargs['market_ids'] = [market_id]
            
            # Get cleared orders (matched bets)
            cleared_orders = self.client.betting.list_cleared_orders(
                bet_status='SETTLED',
                **kwargs
            )
            
            # Handle dict format
            orders = cleared_orders.get('clearedOrders', []) if isinstance(cleared_orders, dict) else []
            
            matched_bets = []
            for order in orders:
                matched_bets.append({
                    "bet_id": order.get('betId'),
                    "market_id": order.get('marketId'),
                    "selection_id": order.get('selectionId'),
                    "price": order.get('priceMatched', 0),
                    "size": order.get('sizeSettled', 0),
                    "side": order.get('side'),
                    "placed_date": order.get('placedDate'),
                    "settled_date": order.get('settledDate'),
                    "profit": order.get('profit', 0),
                    "commission": order.get('commission', 0)
                })
            
            return matched_bets
            
        except BetfairError as e:
            self.logger.error(f"Error getting matched bets: {e}")
            return []
    
    def get_open_bets(self) -> List[Dict[str, Any]]:
        """Get list of open bets."""
        if not self.is_authenticated:
            return []
            
        try:
            # Get current orders
            current_orders = self.client.betting.list_current_orders()
            
            # Handle dict format due to lightweight=True
            orders = current_orders.get('currentOrders', []) if isinstance(current_orders, dict) else []
            
            open_bets = []
            for order in orders:
                price_size = order.get('priceSize', {})
                open_bets.append({
                    "bet_id": order.get('betId'),
                    "market_id": order.get('marketId'),
                    "selection_id": order.get('selectionId'),
                    "price": price_size.get('price', 0),
                    "size": price_size.get('size', 0),
                    "side": order.get('side'),
                    "status": order.get('status'),
                    "matched_size": order.get('sizeMatched', 0),
                    "remaining_size": order.get('sizeRemaining', 0),
                    "placed_date": order.get('placedDate')
                })
                
            return open_bets
            
        except BetfairError as e:
            self.logger.error(f"Error getting open bets: {e}")
            return []
    
    def keep_alive(self) -> bool:
        """Keep the session alive."""
        if not self.is_authenticated:
            return False
            
        try:
            # Send keep alive request
            resp = self.client.keep_alive()
            
            # Handle dict format due to lightweight=True
            if isinstance(resp, dict):
                status = resp.get('status')
            else:
                status = resp.status
            
            if status == "SUCCESS":
                self.last_keep_alive = datetime.now()
                self.logger.debug("Keep-alive successful")
                return True
            else:
                self.logger.warning(f"Keep-alive failed: {status}")
                return False
                
        except BetfairError as e:
            self.logger.error(f"Keep-alive error: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Betfair."""
        try:
            # Disconnect stream if connected
            if self.stream_client:
                self.stream_client.disconnect()
                
            # Stop keep-alive thread
            self._stop_keep_alive.set()
            if self._keep_alive_thread:
                self._keep_alive_thread.join(timeout=5)
                
            # Logout from Betfair
            if self.is_authenticated:
                self.client.logout()
                
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
        finally:
            super().disconnect()
    
    # ============== Streaming Methods ==============
    
    def connect_stream(self, config: Optional[StreamConfig] = None) -> bool:
        """
        Connect to Betfair streaming service.
        
        Args:
            config: Optional streaming configuration
            
        Returns:
            bool: True if connection successful
        """
        if not self.is_authenticated:
            self.logger.error("Must authenticate before connecting to stream")
            return False
            
        try:
            # Create stream client if not exists
            if not self.stream_client:
                self.stream_client = BetfairStreamClient(
                    session_token=self.session_token,
                    app_key=self.app_key,
                    cert_file=self.cert_file,
                    logger=self.logger
                )
            
            # Connect to stream
            return self.stream_client.connect(config)
            
        except Exception as e:
            self.logger.error(f"Failed to connect stream: {e}")
            return False
    
    def disconnect_stream(self) -> bool:
        """Disconnect from streaming service."""
        if self.stream_client:
            return self.stream_client.disconnect()
        return True
    
    def subscribe_market_stream(
        self,
        market_ids: List[str],
        callback: Callable[[StreamMessage], None],
        config: Optional[Dict] = None
    ) -> bool:
        """
        Subscribe to streaming updates for markets.
        
        Args:
            market_ids: List of market IDs to subscribe to
            callback: Function to call with stream messages
            config: Optional subscription configuration
            
        Returns:
            bool: True if subscription successful
        """
        if not self.stream_client:
            self.logger.error("Stream not connected")
            return False
            
        self._stream_callback = callback
        
        # Extract config parameters
        fields = config.get("fields") if config else None
        conflate_ms = config.get("conflate_ms") if config else None
        
        return self.stream_client.subscribe_markets(
            market_ids=market_ids,
            callback=callback,
            fields=fields,
            conflate_ms=conflate_ms
        )
    
    def unsubscribe_market_stream(self, market_ids: List[str]) -> bool:
        """Unsubscribe from market streams."""
        if self.stream_client:
            return self.stream_client.unsubscribe_markets(market_ids)
        return False
    
    def handle_stream_message(self, message: Any) -> Optional[StreamMessage]:
        """
        Handle a stream message (already handled by BetfairStreamClient).
        
        Args:
            message: Raw message from stream
            
        Returns:
            StreamMessage or None
        """
        # BetfairStreamClient already handles and normalizes messages
        # This is here for API compliance
        if isinstance(message, StreamMessage):
            return message
        return None
    
    def get_stream_status(self) -> StreamStatus:
        """Get streaming connection status."""
        if self.stream_client:
            return self.stream_client.get_status()
        return StreamStatus.DISCONNECTED
    
    # ============== Tennis Score/Stats Methods ==============
    
    def get_tennis_matches(self, status: Optional[str] = None) -> List[TennisMatch]:
        """
        Get tennis matches with normalized data.
        
        Args:
            status: Filter by status (live, upcoming, completed)
            
        Returns:
            List of normalized TennisMatch objects
        """
        if not self.is_authenticated:
            self.logger.error("Not authenticated")
            return []
        
        try:
            # Build filter based on status
            market_filter = filters.market_filter(
                event_type_ids=[self.TENNIS_EVENT_TYPE_ID],
                market_type_codes=["MATCH_ODDS"]
            )
            
            if status == "live":
                market_filter["inPlayOnly"] = True
            elif status == "upcoming":
                market_filter["inPlayOnly"] = False
                market_filter["marketStartTime"] = {
                    "from": datetime.now().isoformat(),
                    "to": (datetime.now() + timedelta(days=1)).isoformat()
                }
            
            # Get markets
            markets = self.client.betting.list_market_catalogue(
                filter=market_filter,
                market_projection=["EVENT", "MARKET_START_TIME", "RUNNER_DESCRIPTION", "COMPETITION"],
                max_results=100
            )
            
            # Get market IDs for price fetching
            market_ids = [market.get('marketId') for market in markets if market.get('marketId')]
            
            # Fetch prices for all markets in batches (max 5 per request to avoid TOO_MUCH_DATA error)
            market_prices = {}
            batch_size = 5
            for i in range(0, len(market_ids), batch_size):
                batch_ids = market_ids[i:i+batch_size]
                try:
                    # Get market book with price data
                    market_books = self.client.betting.list_market_book(
                        market_ids=batch_ids,
                        price_projection={
                            'priceData': ['EX_BEST_OFFERS', 'EX_TRADED'],
                            'virtualise': True
                        }
                    )
                    
                    # Store prices by market ID
                    for book in market_books:
                        market_id = book.get('marketId')
                        if market_id:
                            market_prices[market_id] = book
                            
                except Exception as e:
                    self.logger.warning(f"Failed to fetch prices for batch {i//batch_size}: {e}")
            
            # Normalize to TennisMatch objects with price data
            tennis_matches = []
            for market in markets:
                market_id = market.get('marketId')
                
                # Add price data to market if available
                if market_id and market_id in market_prices:
                    market['priceData'] = market_prices[market_id]
                
                match = self.normalizer.normalize_match("betfair", market)
                if match:
                    tennis_matches.append(match)
            
            self.logger.info(f"Found {len(tennis_matches)} tennis matches, {len(market_prices)} with prices")
            return tennis_matches
            
        except BetfairError as e:
            self.logger.error(f"Error getting tennis matches: {e}")
            return []
    
    def get_match_score(self, match_id: str) -> Optional[TennisScore]:
        """
        Get current tennis match score.
        
        Note: Betfair doesn't provide detailed score data through the standard API.
        This would need to be sourced from a separate scores feed or scraped.
        
        Args:
            match_id: Match identifier
            
        Returns:
            TennisScore or None
        """
        if not self.is_authenticated:
            return None
        
        try:
            # Try to get score from market data
            # In reality, Betfair doesn't provide scores through the betting API
            # This is a placeholder showing the structure
            
            # For demo purposes, create a mock score based on market odds
            market_books = self.client.betting.list_market_book(
                market_ids=[match_id.replace("betfair_", "")],
                price_projection=filters.price_projection(price_data=["EX_BEST_OFFERS"])
            )
            
            if market_books:
                market_book = market_books[0]
                
                # Get runner names from catalog
                market_filter = filters.market_filter(market_ids=[market_book.get("marketId")])
                markets = self.client.betting.list_market_catalogue(
                    filter=market_filter,
                    market_projection=["RUNNER_DESCRIPTION"],
                    max_results=1
                )
                
                if markets:
                    market = markets[0]
                    runners = market.get("runners", [])
                    
                    player1 = Player(
                        id=str(runners[0].get("selectionId")) if runners else "1",
                        name=runners[0].get("runnerName", "Player 1") if runners else "Player 1"
                    )
                    player2 = Player(
                        id=str(runners[1].get("selectionId")) if runners else "2",
                        name=runners[1].get("runnerName", "Player 2") if len(runners) > 1 else "Player 2"
                    )
                    
                    # Create basic score structure
                    score = TennisScore(
                        match_id=match_id,
                        player1=player1,
                        player2=player2,
                        match_status=MatchStatus.IN_PROGRESS if market_book.get("inplay") else MatchStatus.NOT_STARTED
                    )
                    
                    # Note: Actual score data would need to come from a different source
                    self.logger.warning(f"Score data not available from Betfair API for match {match_id}")
                    return score
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting match score: {e}")
            return None
    
    def get_match_statistics(self, match_id: str) -> Optional[MatchStatistics]:
        """
        Get tennis match statistics.
        
        Note: Betfair doesn't provide match statistics through the API.
        
        Args:
            match_id: Match identifier
            
        Returns:
            MatchStatistics or None
        """
        self.logger.warning(f"Statistics not available from Betfair API for match {match_id}")
        return None
    
    def get_serving_player(self, match_id: str) -> Optional[Player]:
        """
        Get current serving player.
        
        Note: Betfair doesn't provide serving data through the API.
        
        Args:
            match_id: Match identifier
            
        Returns:
            Player or None
        """
        # Try to get from score if available
        score = self.get_match_score(match_id)
        if score and score.server:
            return score.server
        
        self.logger.warning(f"Serving player data not available from Betfair API for match {match_id}")
        return None