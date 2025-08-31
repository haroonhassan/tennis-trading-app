#!/usr/bin/env python3
"""CLI tool for testing trade execution with the tennis trading system."""

import asyncio
import sys
import os
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import json
import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import print as rprint

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.trading.models import (
    TradeInstruction,
    OrderSide,
    OrderType,
    ExecutionStrategy,
    PersistenceType,
    RiskLimits
)
from app.trading.executor import TradeExecutor
from app.trading.audit import TradeAuditLogger, TradeEventBus
from app.server.provider_manager import ProviderManager
from app.providers.betfair import BetfairProvider
from app.config import Settings

console = Console()


class TradingCLI:
    """Interactive CLI for trade execution testing."""
    
    def __init__(self):
        """Initialize CLI."""
        self.settings = Settings()
        self.provider_manager = None
        self.executor = None
        self.audit_logger = None
        self.event_bus = None
        self.is_practice_mode = True
        
    async def initialize(self):
        """Initialize trading components."""
        console.print("[yellow]Initializing trading system...[/yellow]")
        
        # Initialize provider manager
        self.provider_manager = ProviderManager()
        
        # Initialize Betfair provider
        betfair = BetfairProvider(
            username=self.settings.BETFAIR_USERNAME,
            password=self.settings.BETFAIR_PASSWORD,
            app_key=self.settings.BETFAIR_APP_KEY,
            cert_path=self.settings.BETFAIR_CERT_PATH,
            cert_key_path=self.settings.BETFAIR_KEY_PATH
        )
        
        # Connect to Betfair
        if betfair.connect():
            self.provider_manager.add_provider("betfair", betfair, is_primary=True)
            console.print("[green]✓ Connected to Betfair[/green]")
        else:
            console.print("[red]✗ Failed to connect to Betfair[/red]")
            return False
        
        # Initialize audit logger
        self.audit_logger = TradeAuditLogger()
        
        # Initialize event bus
        self.event_bus = TradeEventBus(self.audit_logger)
        await self.event_bus.start()
        
        # Subscribe to events
        self.event_bus.subscribe("*", self.on_trade_event)
        
        # Initialize trade executor with risk limits
        risk_limits = RiskLimits(
            max_order_size=Decimal("10") if self.is_practice_mode else Decimal("100"),
            max_market_exposure=Decimal("50") if self.is_practice_mode else Decimal("1000")
        )
        
        self.executor = TradeExecutor(self.provider_manager, risk_limits)
        self.executor.add_event_callback(self.event_bus.emit)
        
        await self.executor.start_monitoring()
        
        console.print("[green]✓ Trading system initialized[/green]")
        console.print(f"[yellow]Practice mode: {self.is_practice_mode}[/yellow]")
        console.print(f"[yellow]Max order size: {risk_limits.max_order_size}[/yellow]")
        
        return True
    
    def on_trade_event(self, event):
        """Handle trade event."""
        console.print(f"[dim]{event.timestamp.strftime('%H:%M:%S')}[/dim] "
                     f"[cyan]{event.event_type}[/cyan] {event.data}")
    
    async def show_markets(self):
        """Show available markets."""
        console.print("\n[cyan]Fetching markets...[/cyan]")
        
        # Get matches from provider
        matches = await self.provider_manager.get_all_matches()
        
        if not matches:
            console.print("[red]No markets found[/red]")
            return
        
        # Create table
        table = Table(title="Available Markets")
        table.add_column("ID", style="cyan")
        table.add_column("Tournament", style="white")
        table.add_column("Match", style="yellow")
        table.add_column("Status", style="green")
        
        for i, match in enumerate(matches[:20], 1):
            table.add_row(
                str(i),
                match.tournament_name[:30],
                f"{match.player1.name} vs {match.player2.name}"[:40],
                match.status.value
            )
        
        console.print(table)
        
        # Store matches for selection
        self.current_matches = matches
    
    async def place_order(self):
        """Place a test order."""
        if not self.current_matches:
            await self.show_markets()
        
        if not self.current_matches:
            return
        
        # Select market
        market_num = Prompt.ask("Select market number", default="1")
        try:
            market_idx = int(market_num) - 1
            selected_match = self.current_matches[market_idx]
        except (ValueError, IndexError):
            console.print("[red]Invalid market selection[/red]")
            return
        
        console.print(f"\n[green]Selected:[/green] {selected_match.player1.name} vs {selected_match.player2.name}")
        
        # Get market ID and selections
        market_id = selected_match.market_id
        if not market_id:
            console.print("[red]No market ID available[/red]")
            return
        
        # For Betfair, we need runner IDs from market
        betfair = self.provider_manager.providers["betfair"].service
        market_book = betfair.get_market_book(market_id)
        
        if not market_book:
            console.print("[red]Could not fetch market details[/red]")
            return
        
        runners = market_book.get("runners", [])
        if len(runners) < 2:
            console.print("[red]Not enough runners in market[/red]")
            return
        
        # Show runners
        console.print("\n[cyan]Runners:[/cyan]")
        for i, runner in enumerate(runners, 1):
            name = runner.get("runnerName", f"Runner {i}")
            status = runner.get("status", "ACTIVE")
            console.print(f"  {i}. {name} [dim]({status})[/dim]")
        
        # Select runner
        runner_num = Prompt.ask("Select runner", default="1")
        try:
            runner_idx = int(runner_num) - 1
            selection_id = str(runners[runner_idx].get("selectionId"))
        except (ValueError, IndexError):
            console.print("[red]Invalid runner selection[/red]")
            return
        
        # Get order parameters
        side = Prompt.ask("Side", choices=["back", "lay"], default="back")
        price = Decimal(Prompt.ask("Price", default="2.0"))
        size = Decimal(Prompt.ask("Size (stake)", default="2.0"))
        
        # Select strategy
        strategy = Prompt.ask(
            "Strategy",
            choices=["aggressive", "passive", "smart"],
            default="smart"
        )
        
        strategy_map = {
            "aggressive": ExecutionStrategy.AGGRESSIVE,
            "passive": ExecutionStrategy.PASSIVE,
            "smart": ExecutionStrategy.SMART
        }
        
        # Confirm order
        console.print("\n[yellow]Order Summary:[/yellow]")
        console.print(f"  Market: {selected_match.player1.name} vs {selected_match.player2.name}")
        console.print(f"  Selection: Runner {runner_idx + 1}")
        console.print(f"  Side: {side.upper()}")
        console.print(f"  Price: {price}")
        console.print(f"  Size: {size}")
        console.print(f"  Strategy: {strategy}")
        
        if not self.is_practice_mode:
            console.print("\n[red]⚠️  REAL MONEY MODE - This will place a real bet![/red]")
        
        if not Confirm.ask("Place order?"):
            console.print("[yellow]Order cancelled[/yellow]")
            return
        
        # Create instruction
        instruction = TradeInstruction(
            market_id=market_id,
            selection_id=selection_id,
            side=OrderSide.BACK if side == "back" else OrderSide.LAY,
            size=size,
            price=price,
            order_type=OrderType.LIMIT,
            strategy=strategy_map[strategy],
            persistence=PersistenceType.LAPSE,
            client_ref=f"cli_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        # Execute order
        console.print("\n[cyan]Executing order...[/cyan]")
        
        try:
            report = await self.executor.execute_order(instruction, provider="betfair")
            
            # Show result
            if report.is_successful:
                console.print(f"[green]✓ Order executed successfully![/green]")
                console.print(f"  Order ID: {report.order_id}")
                console.print(f"  Executed: {report.executed_size} @ {report.executed_price}")
                console.print(f"  Status: {report.status.value}")
            else:
                console.print(f"[red]✗ Order failed[/red]")
                console.print(f"  Error: {report.error_message}")
                
        except Exception as e:
            console.print(f"[red]Error executing order: {e}[/red]")
    
    async def show_orders(self):
        """Show open orders."""
        orders = self.executor.get_open_orders()
        
        if not orders:
            console.print("[yellow]No open orders[/yellow]")
            return
        
        table = Table(title="Open Orders")
        table.add_column("Order ID", style="cyan")
        table.add_column("Market", style="white")
        table.add_column("Side", style="yellow")
        table.add_column("Price", style="green")
        table.add_column("Size", style="green")
        table.add_column("Matched", style="blue")
        table.add_column("Status", style="magenta")
        
        for order in orders:
            table.add_row(
                order.order_id[:8],
                order.instruction.market_id[:20] if order.instruction else "N/A",
                order.instruction.side.value if order.instruction else "N/A",
                str(order.requested_price),
                str(order.requested_size),
                str(order.matched_size),
                order.status.value
            )
        
        console.print(table)
    
    async def show_bets(self):
        """Show matched bets."""
        bets = self.executor.get_matched_bets()
        
        if not bets:
            console.print("[yellow]No matched bets[/yellow]")
            return
        
        table = Table(title="Matched Bets")
        table.add_column("Bet ID", style="cyan")
        table.add_column("Market", style="white")
        table.add_column("Side", style="yellow")
        table.add_column("Price", style="green")
        table.add_column("Size", style="green")
        table.add_column("P&L", style="red")
        
        for bet in bets:
            table.add_row(
                bet.bet_id[:8],
                bet.market_id[:20],
                bet.side.value,
                str(bet.price),
                str(bet.size),
                str(bet.profit_loss) if bet.profit_loss else "N/A"
            )
        
        console.print(table)
    
    async def cancel_order(self):
        """Cancel an order."""
        orders = self.executor.get_open_orders()
        
        if not orders:
            console.print("[yellow]No orders to cancel[/yellow]")
            return
        
        # Show orders
        await self.show_orders()
        
        # Get order ID
        order_id = Prompt.ask("Enter order ID (first 8 chars)")
        
        # Find matching order
        matching_order = None
        for order in orders:
            if order.order_id.startswith(order_id):
                matching_order = order
                break
        
        if not matching_order:
            console.print("[red]Order not found[/red]")
            return
        
        # Confirm cancellation
        if Confirm.ask(f"Cancel order {matching_order.order_id[:8]}?"):
            success = await self.executor.cancel_order(matching_order.order_id)
            if success:
                console.print("[green]✓ Order cancelled[/green]")
            else:
                console.print("[red]✗ Failed to cancel order[/red]")
    
    async def show_audit_log(self):
        """Show recent audit events."""
        events = self.audit_logger.get_recent_events(limit=20)
        
        if not events:
            console.print("[yellow]No recent events[/yellow]")
            return
        
        table = Table(title="Recent Trade Events")
        table.add_column("Time", style="dim")
        table.add_column("Type", style="cyan")
        table.add_column("Order", style="yellow")
        table.add_column("Details", style="white")
        
        for event in events:
            table.add_row(
                event.timestamp.strftime("%H:%M:%S"),
                event.event_type,
                event.order_id[:8] if event.order_id else "N/A",
                json.dumps(event.data)[:50]
            )
        
        console.print(table)
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.executor:
            await self.executor.stop_monitoring()
        
        if self.event_bus:
            await self.event_bus.stop()
        
        if self.provider_manager:
            for provider_info in self.provider_manager.providers.values():
                if provider_info.service:
                    provider_info.service.disconnect()
    
    async def run(self):
        """Run the CLI."""
        # Initialize
        if not await self.initialize():
            return
        
        # Main menu loop
        while True:
            console.print("\n" + "=" * 50)
            console.print("[bold cyan]Tennis Trading CLI[/bold cyan]")
            console.print("=" * 50)
            console.print("1. Show Markets")
            console.print("2. Place Order")
            console.print("3. Show Open Orders")
            console.print("4. Show Matched Bets")
            console.print("5. Cancel Order")
            console.print("6. Show Audit Log")
            console.print("7. Toggle Practice Mode")
            console.print("0. Exit")
            
            choice = Prompt.ask("Select option", default="1")
            
            try:
                if choice == "1":
                    await self.show_markets()
                elif choice == "2":
                    await self.place_order()
                elif choice == "3":
                    await self.show_orders()
                elif choice == "4":
                    await self.show_bets()
                elif choice == "5":
                    await self.cancel_order()
                elif choice == "6":
                    await self.show_audit_log()
                elif choice == "7":
                    self.is_practice_mode = not self.is_practice_mode
                    mode = "PRACTICE" if self.is_practice_mode else "REAL MONEY"
                    console.print(f"[yellow]Switched to {mode} mode[/yellow]")
                elif choice == "0":
                    break
                else:
                    console.print("[red]Invalid option[/red]")
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        
        # Cleanup
        console.print("\n[yellow]Shutting down...[/yellow]")
        await self.cleanup()
        console.print("[green]Goodbye![/green]")


@click.command()
@click.option('--real', is_flag=True, help='Use real money mode (dangerous!)')
def main(real):
    """Tennis Trading CLI - Test trade execution."""
    cli = TradingCLI()
    
    if real:
        console.print("[bold red]⚠️  WARNING: Real money mode enabled![/bold red]")
        if not Confirm.ask("Are you sure you want to use real money?"):
            return
        cli.is_practice_mode = False
    
    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")


if __name__ == "__main__":
    main()