"""Position calculator for P&L, hedging, and risk calculations."""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
import math

from app.risk.models import (
    Position, PositionSide, HedgeInstruction,
    MarketExposure, RiskMetrics
)


class PositionCalculator:
    """Calculates P&L, hedging requirements, and optimal position sizes."""
    
    def __init__(self, commission_rate: Decimal = Decimal("0.02")):
        """Initialize calculator.
        
        Args:
            commission_rate: Commission rate (default 2% for Betfair)
        """
        self.commission_rate = commission_rate
        
    def calculate_pnl(
        self,
        position: Position,
        current_price: Decimal,
        include_commission: bool = True
    ) -> Tuple[Decimal, Decimal]:
        """Calculate P&L for a position.
        
        Args:
            position: Position to calculate
            current_price: Current market price
            include_commission: Whether to include commission
            
        Returns:
            Tuple of (realized_pnl, unrealized_pnl)
        """
        # Realized P&L is already calculated
        realized_pnl = position.realized_pnl
        
        # Calculate unrealized P&L
        if position.current_size > 0:
            if position.side == PositionSide.LONG:
                gross_pnl = (current_price - position.entry_price) * position.current_size
            else:  # SHORT
                gross_pnl = (position.entry_price - current_price) * position.current_size
            
            # Apply commission on profits
            if include_commission and gross_pnl > 0:
                commission = gross_pnl * self.commission_rate
                unrealized_pnl = gross_pnl - commission
            else:
                unrealized_pnl = gross_pnl
        else:
            unrealized_pnl = Decimal("0")
        
        return realized_pnl, unrealized_pnl
        
    def calculate_hedge_requirement(
        self,
        positions: List[Position],
        target_exposure: Decimal = Decimal("0")
    ) -> Optional[HedgeInstruction]:
        """Calculate hedge requirement for a set of positions.
        
        Args:
            positions: Positions to hedge
            target_exposure: Target net exposure (0 for flat)
            
        Returns:
            Hedge instruction if hedging needed
        """
        if not positions:
            return None
        
        # Group by market and selection
        market_exposures: Dict[str, Dict[str, Decimal]] = {}
        
        for pos in positions:
            if pos.current_size == 0:
                continue
                
            if pos.market_id not in market_exposures:
                market_exposures[pos.market_id] = {}
            
            if pos.selection_id not in market_exposures[pos.market_id]:
                market_exposures[pos.market_id][pos.selection_id] = Decimal("0")
            
            # Calculate exposure
            if pos.side == PositionSide.LONG:
                exposure = pos.current_size
            else:  # SHORT
                exposure = -pos.current_size * (pos.entry_price - 1)
            
            market_exposures[pos.market_id][pos.selection_id] += exposure
        
        # Find largest imbalance
        max_imbalance = Decimal("0")
        hedge_market = None
        hedge_selection = None
        hedge_side = None
        
        for market_id, selections in market_exposures.items():
            for selection_id, exposure in selections.items():
                imbalance = abs(exposure - target_exposure)
                
                if imbalance > max_imbalance:
                    max_imbalance = imbalance
                    hedge_market = market_id
                    hedge_selection = selection_id
                    
                    # Determine hedge side
                    if exposure > target_exposure:
                        # Need to reduce exposure - lay if long, back if short
                        hedge_side = PositionSide.SHORT
                    else:
                        hedge_side = PositionSide.LONG
        
        # Only hedge if imbalance is significant
        if max_imbalance < Decimal("10"):  # Minimum hedge size
            return None
        
        # Calculate hedge size
        hedge_size = max_imbalance
        
        # Estimate hedge price (would need market data for accurate price)
        hedge_price = Decimal("2.0")  # Placeholder
        
        return HedgeInstruction(
            market_id=hedge_market,
            selection_id=hedge_selection,
            side=hedge_side,
            size=hedge_size,
            price=hedge_price,
            reason=f"Reduce exposure by {max_imbalance}",
            urgency="medium"
        )
        
    def calculate_net_position(
        self,
        positions: List[Position]
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """Calculate net position across multiple positions.
        
        Args:
            positions: Positions to net
            
        Returns:
            Tuple of (net_size, net_value, average_price)
        """
        long_size = Decimal("0")
        long_value = Decimal("0")
        short_size = Decimal("0")
        short_value = Decimal("0")
        
        for pos in positions:
            if pos.current_size > 0:
                if pos.side == PositionSide.LONG:
                    long_size += pos.current_size
                    long_value += pos.current_size * pos.entry_price
                else:
                    short_size += pos.current_size
                    short_value += pos.current_size * pos.entry_price
        
        net_size = long_size - short_size
        net_value = long_value - short_value
        
        if net_size != 0:
            average_price = abs(net_value / net_size)
        else:
            average_price = Decimal("0")
        
        return net_size, net_value, average_price
        
    def calculate_optimal_stake(
        self,
        probability: Decimal,
        odds: Decimal,
        bankroll: Decimal,
        kelly_fraction: Decimal = Decimal("0.25")
    ) -> Decimal:
        """Calculate optimal stake size using Kelly Criterion.
        
        Args:
            probability: Estimated win probability (0-1)
            odds: Decimal odds
            bankroll: Available bankroll
            kelly_fraction: Fraction of Kelly to use (default 0.25 for safety)
            
        Returns:
            Optimal stake size
        """
        if probability <= 0 or probability >= 1:
            return Decimal("0")
        
        if odds <= 1:
            return Decimal("0")
        
        # Kelly formula: f = (p * (odds - 1) - (1 - p)) / (odds - 1)
        # Simplified: f = (p * odds - 1) / (odds - 1)
        
        edge = probability * odds - 1
        
        if edge <= 0:
            return Decimal("0")
        
        kelly_full = edge / (odds - 1)
        kelly_adjusted = kelly_full * kelly_fraction
        
        # Cap at maximum percentage of bankroll
        max_stake = bankroll * Decimal("0.1")  # Max 10% per bet
        
        stake = min(bankroll * kelly_adjusted, max_stake)
        
        # Round to reasonable amount
        if stake < Decimal("2"):
            return Decimal("0")
        
        return stake.quantize(Decimal("0.01"))
        
    def calculate_break_even_price(
        self,
        position: Position,
        include_commission: bool = True
    ) -> Decimal:
        """Calculate break-even price for a position.
        
        Args:
            position: Position to calculate for
            include_commission: Whether to include commission
            
        Returns:
            Break-even price
        """
        if position.current_size == 0:
            return Decimal("0")
        
        if not include_commission:
            return position.entry_price
        
        # For back bets: break_even = entry_price / (1 - commission_rate)
        # For lay bets: break_even = entry_price * (1 - commission_rate)
        
        if position.side == PositionSide.LONG:
            break_even = position.entry_price / (1 - self.commission_rate)
        else:
            break_even = position.entry_price * (1 - self.commission_rate)
        
        return break_even.quantize(Decimal("0.01"))
        
    def calculate_risk_reward_ratio(
        self,
        entry_price: Decimal,
        target_price: Decimal,
        stop_price: Decimal,
        side: PositionSide
    ) -> Decimal:
        """Calculate risk/reward ratio for a trade.
        
        Args:
            entry_price: Entry price
            target_price: Target/take-profit price
            stop_price: Stop-loss price
            side: Position side
            
        Returns:
            Risk/reward ratio
        """
        if side == PositionSide.LONG:
            potential_profit = target_price - entry_price
            potential_loss = entry_price - stop_price
        else:
            potential_profit = entry_price - target_price
            potential_loss = stop_price - entry_price
        
        if potential_loss <= 0:
            return Decimal("0")
        
        return (potential_profit / potential_loss).quantize(Decimal("0.01"))
        
    def calculate_implied_probability(self, decimal_odds: Decimal) -> Decimal:
        """Calculate implied probability from decimal odds.
        
        Args:
            decimal_odds: Decimal odds
            
        Returns:
            Implied probability (0-1)
        """
        if decimal_odds <= 1:
            return Decimal("1")
        
        return (Decimal("1") / decimal_odds).quantize(Decimal("0.0001"))
        
    def calculate_arbitrage_opportunity(
        self,
        back_odds: Decimal,
        lay_odds: Decimal,
        commission_rate: Optional[Decimal] = None
    ) -> Tuple[bool, Decimal]:
        """Check for arbitrage opportunity between back and lay.
        
        Args:
            back_odds: Best back odds available
            lay_odds: Best lay odds available
            commission_rate: Commission rate to account for
            
        Returns:
            Tuple of (is_arbitrage, profit_percentage)
        """
        if commission_rate is None:
            commission_rate = self.commission_rate
        
        # Account for commission on winnings
        effective_back_odds = back_odds * (1 - commission_rate)
        
        # Arbitrage exists if back odds > lay odds after commission
        if effective_back_odds > lay_odds:
            # Calculate guaranteed profit percentage
            # Profit = (effective_back_odds / lay_odds - 1) * 100
            profit_pct = ((effective_back_odds / lay_odds - 1) * 100).quantize(Decimal("0.01"))
            return True, profit_pct
        
        return False, Decimal("0")
        
    def calculate_exposure_by_outcome(
        self,
        positions: List[Position]
    ) -> Dict[str, Decimal]:
        """Calculate exposure for each possible outcome.
        
        Args:
            positions: List of positions
            
        Returns:
            Dictionary of selection_id -> exposure
        """
        exposures = {}
        
        # Group positions by selection
        by_selection = {}
        for pos in positions:
            if pos.current_size == 0:
                continue
                
            if pos.selection_id not in by_selection:
                by_selection[pos.selection_id] = []
            by_selection[pos.selection_id].append(pos)
        
        # Calculate exposure for each selection winning
        for selection_id, selection_positions in by_selection.items():
            selection_pnl = Decimal("0")
            
            for pos in positions:
                if pos.current_size == 0:
                    continue
                    
                if pos.selection_id == selection_id:
                    # This selection wins
                    if pos.side == PositionSide.LONG:
                        # Back bet wins
                        pnl = (pos.entry_price - 1) * pos.current_size
                        pnl *= (1 - self.commission_rate)  # Commission on profit
                    else:
                        # Lay bet loses
                        pnl = -(pos.entry_price - 1) * pos.current_size
                else:
                    # This selection loses
                    if pos.side == PositionSide.LONG:
                        # Back bet loses
                        pnl = -pos.current_size
                    else:
                        # Lay bet wins
                        pnl = pos.current_size
                        pnl *= (1 - self.commission_rate)  # Commission on profit
                
                selection_pnl += pnl
            
            exposures[selection_id] = selection_pnl
        
        return exposures
        
    def calculate_guaranteed_profit(
        self,
        positions: List[Position]
    ) -> Tuple[bool, Decimal]:
        """Check if positions guarantee a profit regardless of outcome.
        
        Args:
            positions: List of positions
            
        Returns:
            Tuple of (is_guaranteed, min_profit)
        """
        exposures = self.calculate_exposure_by_outcome(positions)
        
        if not exposures:
            return False, Decimal("0")
        
        min_exposure = min(exposures.values())
        
        # Guaranteed profit if minimum exposure is positive
        return min_exposure > 0, min_exposure


class GreekCalculator:
    """Calculates option-like Greeks for betting positions."""
    
    def __init__(self):
        """Initialize Greek calculator."""
        pass
        
    def calculate_delta(
        self,
        position: Position,
        current_price: Decimal,
        price_range: Decimal = Decimal("0.02")
    ) -> Decimal:
        """Calculate position delta (price sensitivity).
        
        Delta = Change in P&L / Change in Price
        
        Args:
            position: Position to calculate for
            current_price: Current market price
            price_range: Price range for calculation
            
        Returns:
            Delta value
        """
        if position.current_size == 0:
            return Decimal("0")
        
        # Calculate P&L at current price
        if position.side == PositionSide.LONG:
            current_pnl = (current_price - position.entry_price) * position.current_size
            up_pnl = ((current_price + price_range) - position.entry_price) * position.current_size
        else:
            current_pnl = (position.entry_price - current_price) * position.current_size
            up_pnl = (position.entry_price - (current_price + price_range)) * position.current_size
        
        delta = (up_pnl - current_pnl) / price_range
        
        return delta.quantize(Decimal("0.01"))
        
    def calculate_gamma(
        self,
        position: Position,
        current_price: Decimal,
        price_range: Decimal = Decimal("0.02")
    ) -> Decimal:
        """Calculate position gamma (delta sensitivity).
        
        Gamma = Change in Delta / Change in Price
        
        Args:
            position: Position to calculate for
            current_price: Current market price
            price_range: Price range for calculation
            
        Returns:
            Gamma value
        """
        # For simple betting positions, gamma is typically 0
        # as delta is constant
        return Decimal("0")
        
    def calculate_theta(
        self,
        position: Position,
        time_to_event: int,
        decay_rate: Decimal = Decimal("0.01")
    ) -> Decimal:
        """Calculate position theta (time decay).
        
        For betting, this represents the opportunity cost or
        the decay in edge as the event approaches.
        
        Args:
            position: Position to calculate for
            time_to_event: Minutes until event starts
            decay_rate: Rate of decay per hour
            
        Returns:
            Theta value (P&L decay per hour)
        """
        if position.current_size == 0 or time_to_event <= 0:
            return Decimal("0")
        
        # Simple linear decay model
        hours_to_event = Decimal(time_to_event) / 60
        
        # Decay increases as we approach the event
        if hours_to_event < 1:
            decay_multiplier = Decimal("2")  # Double decay in last hour
        elif hours_to_event < 4:
            decay_multiplier = Decimal("1.5")
        else:
            decay_multiplier = Decimal("1")
        
        theta = -position.current_size * decay_rate * decay_multiplier
        
        return theta.quantize(Decimal("0.01"))
        
    def calculate_vega(
        self,
        position: Position,
        current_volatility: Decimal,
        volatility_change: Decimal = Decimal("0.01")
    ) -> Decimal:
        """Calculate position vega (volatility sensitivity).
        
        For betting, this represents sensitivity to odds volatility.
        
        Args:
            position: Position to calculate for
            current_volatility: Current price volatility
            volatility_change: Change in volatility
            
        Returns:
            Vega value
        """
        if position.current_size == 0:
            return Decimal("0")
        
        # Higher volatility generally benefits long gamma positions
        # For simple bets, we can model this as opportunity value
        
        vega = position.current_size * volatility_change * Decimal("10")
        
        if position.side == PositionSide.SHORT:
            vega = -vega  # Short positions lose from volatility
        
        return vega.quantize(Decimal("0.01"))
        
    def calculate_portfolio_greeks(
        self,
        positions: List[Position],
        market_prices: Dict[str, Decimal],
        time_to_events: Dict[str, int]
    ) -> Dict[str, Decimal]:
        """Calculate Greeks for entire portfolio.
        
        Args:
            positions: List of positions
            market_prices: Current prices by selection_id
            time_to_events: Time to event by market_id
            
        Returns:
            Dictionary of Greek values
        """
        total_delta = Decimal("0")
        total_gamma = Decimal("0")
        total_theta = Decimal("0")
        total_vega = Decimal("0")
        
        for pos in positions:
            if pos.current_size == 0:
                continue
                
            current_price = market_prices.get(pos.selection_id, pos.entry_price)
            time_to_event = time_to_events.get(pos.market_id, 60)
            
            total_delta += self.calculate_delta(pos, current_price)
            total_gamma += self.calculate_gamma(pos, current_price)
            total_theta += self.calculate_theta(pos, time_to_event)
            total_vega += self.calculate_vega(pos, Decimal("0.05"))  # Assumed volatility
        
        return {
            "delta": total_delta,
            "gamma": total_gamma,
            "theta": total_theta,
            "vega": total_vega
        }