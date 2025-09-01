"""Risk management dashboard component."""

from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.progress import Progress, BarColumn, TextColumn
from rich.console import Group
from rich.align import Align
from rich.layout import Layout

from ..models import Position, Trade, PositionStatus


class RiskDashboard:
    """Risk management dashboard with real-time metrics."""
    
    def __init__(self):
        self.risk_limits = {
            'max_position_size': Decimal('100'),
            'max_market_exposure': Decimal('500'),
            'max_total_exposure': Decimal('1000'),
            'max_daily_loss': Decimal('200'),
            'max_open_positions': 20,
            'stop_loss_percentage': Decimal('10')
        }
        self.alert_thresholds = {
            'exposure_warning': Decimal('0.75'),  # 75% of limit
            'exposure_critical': Decimal('0.90'),  # 90% of limit
            'daily_loss_warning': Decimal('0.50'),  # 50% of daily limit
            'daily_loss_critical': Decimal('0.75')  # 75% of daily limit
        }
        self.kill_switch_active = False
        self.trading_frozen = False
        
    def create_dashboard(self, positions: List[Position], trades: List[Trade]) -> Layout:
        """Create the complete risk dashboard layout."""
        layout = Layout()
        
        # Create main sections
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="metrics", size=10),
            Layout(name="exposure", size=12),
            Layout(name="alerts", size=8),
            Layout(name="controls", size=5)
        )
        
        # Populate sections
        layout["header"].update(self._create_header())
        layout["metrics"].update(self._create_risk_metrics(positions, trades))
        layout["exposure"].update(self._create_exposure_panel(positions))
        layout["alerts"].update(self._create_alerts_panel(positions, trades))
        layout["controls"].update(self._create_controls_panel())
        
        return layout
    
    def _create_header(self) -> Panel:
        """Create dashboard header."""
        status = "🔴 KILL SWITCH ACTIVE" if self.kill_switch_active else (
            "🟡 TRADING FROZEN" if self.trading_frozen else "🟢 TRADING ACTIVE"
        )
        
        header = Text()
        header.append("⚠️  RISK MANAGEMENT DASHBOARD  ⚠️", style="bold white on red")
        header.append("\n")
        header.append(f"Status: {status}", style="bold")
        
        return Panel(
            Align.center(header),
            border_style="red" if self.kill_switch_active else "yellow" if self.trading_frozen else "green"
        )
    
    def _create_risk_metrics(self, positions: List[Position], trades: List[Trade]) -> Panel:
        """Create risk metrics panel."""
        # Calculate metrics
        total_exposure = sum(abs(p.stake) for p in positions if p.status == PositionStatus.OPEN)
        market_exposures = self._calculate_market_exposures(positions)
        daily_pnl = self._calculate_daily_pnl(trades)
        open_positions = len([p for p in positions if p.status == PositionStatus.OPEN])
        
        # Create metrics table
        table = Table(show_header=True, box=None, padding=0)
        table.add_column("Metric", style="bold cyan", width=25)
        table.add_column("Current", justify="right", width=15)
        table.add_column("Limit", justify="right", width=15)
        table.add_column("Usage", justify="center", width=30)
        
        # Add rows with progress bars
        metrics = [
            ("Total Exposure", total_exposure, self.risk_limits['max_total_exposure']),
            ("Max Market Exposure", max(market_exposures.values()) if market_exposures else Decimal('0'), 
             self.risk_limits['max_market_exposure']),
            ("Daily Loss", abs(daily_pnl) if daily_pnl < 0 else Decimal('0'), 
             self.risk_limits['max_daily_loss']),
            ("Open Positions", Decimal(open_positions), Decimal(self.risk_limits['max_open_positions']))
        ]
        
        for metric_name, current, limit in metrics:
            usage_pct = (current / limit * 100) if limit > 0 else 0
            
            # Create usage bar
            bar = self._create_usage_bar(usage_pct)
            
            # Style based on threshold
            value_style = self._get_risk_style(usage_pct)
            
            table.add_row(
                metric_name,
                f"£{current:.2f}" if metric_name != "Open Positions" else str(int(current)),
                f"£{limit:.2f}" if metric_name != "Open Positions" else str(int(limit)),
                bar
            )
        
        return Panel(table, title="📊 Risk Metrics", border_style="cyan")
    
    def _create_exposure_panel(self, positions: List[Position]) -> Panel:
        """Create exposure breakdown panel."""
        market_exposures = self._calculate_market_exposures(positions)
        selection_exposures = self._calculate_selection_exposures(positions)
        
        # Create exposure tables
        left_table = self._create_market_exposure_table(market_exposures)
        right_table = self._create_selection_exposure_table(selection_exposures)
        
        columns = Columns([left_table, right_table], padding=2, expand=True)
        
        return Panel(columns, title="💰 Exposure Breakdown", border_style="yellow")
    
    def _create_market_exposure_table(self, exposures: Dict[str, Decimal]) -> Panel:
        """Create market exposure table."""
        table = Table(show_header=True, box=None)
        table.add_column("Market", style="white", width=20)
        table.add_column("Exposure", justify="right", style="yellow")
        table.add_column("Risk", justify="center", width=10)
        
        # Sort by exposure
        sorted_exposures = sorted(exposures.items(), key=lambda x: x[1], reverse=True)
        
        for market, exposure in sorted_exposures[:10]:  # Top 10
            risk_level = self._get_exposure_risk_level(exposure, self.risk_limits['max_market_exposure'])
            table.add_row(
                market[:20],  # Truncate long names
                f"£{exposure:.2f}",
                risk_level
            )
        
        return Panel(table, title="By Market", border_style="dim")
    
    def _create_selection_exposure_table(self, exposures: Dict[str, Decimal]) -> Panel:
        """Create selection exposure table."""
        table = Table(show_header=True, box=None)
        table.add_column("Selection", style="white", width=20)
        table.add_column("Exposure", justify="right", style="yellow")
        table.add_column("Positions", justify="center", width=10)
        
        # Sort by exposure
        sorted_exposures = sorted(exposures.items(), key=lambda x: x[1]['exposure'], reverse=True)
        
        for selection, data in sorted_exposures[:10]:  # Top 10
            table.add_row(
                selection[:20],  # Truncate long names
                f"£{data['exposure']:.2f}",
                str(data['count'])
            )
        
        return Panel(table, title="By Selection", border_style="dim")
    
    def _create_alerts_panel(self, positions: List[Position], trades: List[Trade]) -> Panel:
        """Create alerts and warnings panel."""
        alerts = []
        
        # Check exposure alerts
        total_exposure = sum(abs(p.stake) for p in positions if p.status == PositionStatus.OPEN)
        exposure_pct = total_exposure / self.risk_limits['max_total_exposure']
        
        if exposure_pct >= self.alert_thresholds['exposure_critical']:
            alerts.append(("🔴 CRITICAL", f"Total exposure at {exposure_pct:.0%} of limit", "red"))
        elif exposure_pct >= self.alert_thresholds['exposure_warning']:
            alerts.append(("🟡 WARNING", f"Total exposure at {exposure_pct:.0%} of limit", "yellow"))
        
        # Check daily loss alerts
        daily_pnl = self._calculate_daily_pnl(trades)
        if daily_pnl < 0:
            loss_pct = abs(daily_pnl) / self.risk_limits['max_daily_loss']
            if loss_pct >= self.alert_thresholds['daily_loss_critical']:
                alerts.append(("🔴 CRITICAL", f"Daily loss at {loss_pct:.0%} of limit", "red"))
            elif loss_pct >= self.alert_thresholds['daily_loss_warning']:
                alerts.append(("🟡 WARNING", f"Daily loss at {loss_pct:.0%} of limit", "yellow"))
        
        # Check position count
        open_positions = len([p for p in positions if p.status == PositionStatus.OPEN])
        if open_positions >= self.risk_limits['max_open_positions'] * 0.9:
            alerts.append(("🟡 WARNING", f"{open_positions} open positions (limit: {self.risk_limits['max_open_positions']})", "yellow"))
        
        # Check for positions without stop loss
        no_stop_loss = [p for p in positions if p.status == PositionStatus.OPEN and not hasattr(p, 'stop_loss')]
        if no_stop_loss:
            alerts.append(("⚠️  INFO", f"{len(no_stop_loss)} positions without stop loss", "cyan"))
        
        # Create alerts display
        if alerts:
            alert_text = Text()
            for level, message, color in alerts:
                alert_text.append(f"{level} ", style=f"bold {color}")
                alert_text.append(f"{message}\n", style=color)
        else:
            alert_text = Text("✅ No active alerts", style="green")
        
        return Panel(alert_text, title="🚨 Alerts & Warnings", border_style="red" if alerts else "green")
    
    def _create_controls_panel(self) -> Panel:
        """Create trading controls panel."""
        controls = Table(show_header=False, box=None)
        controls.add_column("Control", style="bold white")
        controls.add_column("Status", justify="center")
        controls.add_column("Action", style="dim")
        
        controls.add_row(
            "Kill Switch",
            "🔴 ACTIVE" if self.kill_switch_active else "⭕ INACTIVE",
            "Press Shift+S to toggle"
        )
        controls.add_row(
            "Trading Freeze",
            "🟡 FROZEN" if self.trading_frozen else "🟢 ACTIVE",
            "Press F to toggle freeze"
        )
        controls.add_row(
            "Auto Stop Loss",
            "✅ ENABLED",
            "10% of position size"
        )
        
        return Panel(controls, title="🎮 Trading Controls", border_style="magenta")
    
    def _calculate_market_exposures(self, positions: List[Position]) -> Dict[str, Decimal]:
        """Calculate exposure by market."""
        exposures = defaultdict(Decimal)
        for position in positions:
            if position.status == PositionStatus.OPEN:
                exposures[position.match_id] += abs(position.stake)
        return dict(exposures)
    
    def _calculate_selection_exposures(self, positions: List[Position]) -> Dict[str, Dict]:
        """Calculate exposure by selection."""
        exposures = defaultdict(lambda: {'exposure': Decimal('0'), 'count': 0})
        for position in positions:
            if position.status == PositionStatus.OPEN:
                selection = position.selection_name or 'Unknown'
                exposures[selection]['exposure'] += abs(position.stake)
                exposures[selection]['count'] += 1
        return dict(exposures)
    
    def _calculate_daily_pnl(self, trades: List[Trade]) -> Decimal:
        """Calculate today's P&L."""
        today = datetime.now().date()
        daily_pnl = Decimal('0')
        
        for trade in trades:
            if trade.executed_at.date() == today:
                # Calculate trade P&L based on side
                if trade.side == 'BACK':
                    # Back bet P&L
                    daily_pnl += trade.pnl if hasattr(trade, 'pnl') else Decimal('0')
                else:
                    # Lay bet P&L
                    daily_pnl += trade.pnl if hasattr(trade, 'pnl') else Decimal('0')
        
        return daily_pnl
    
    def _create_usage_bar(self, percentage: float) -> Text:
        """Create a visual usage bar."""
        bar_width = 20
        filled = int(percentage / 100 * bar_width)
        
        # Determine color based on percentage
        if percentage >= 90:
            color = "red"
        elif percentage >= 75:
            color = "yellow"
        else:
            color = "green"
        
        bar = Text()
        bar.append("█" * filled, style=color)
        bar.append("░" * (bar_width - filled), style="dim white")
        bar.append(f" {percentage:.0f}%", style=color)
        
        return bar
    
    def _get_risk_style(self, usage_pct: float) -> str:
        """Get style based on risk level."""
        if usage_pct >= 90:
            return "bold red"
        elif usage_pct >= 75:
            return "bold yellow"
        else:
            return "green"
    
    def _get_exposure_risk_level(self, exposure: Decimal, limit: Decimal) -> str:
        """Get risk level indicator for exposure."""
        pct = (exposure / limit * 100) if limit > 0 else 0
        if pct >= 90:
            return "🔴 HIGH"
        elif pct >= 75:
            return "🟡 MED"
        else:
            return "🟢 LOW"
    
    def activate_kill_switch(self):
        """Activate the kill switch."""
        self.kill_switch_active = True
        self.trading_frozen = True
    
    def deactivate_kill_switch(self):
        """Deactivate the kill switch."""
        self.kill_switch_active = False
        self.trading_frozen = False
    
    def toggle_trading_freeze(self):
        """Toggle trading freeze status."""
        if not self.kill_switch_active:
            self.trading_frozen = not self.trading_frozen
    
    def check_risk_limits(self, positions: List[Position], new_position_size: Decimal = Decimal('0')) -> tuple[bool, str]:
        """Check if risk limits would be breached."""
        # Check total exposure
        total_exposure = sum(abs(p.stake) for p in positions if p.status == PositionStatus.OPEN) + new_position_size
        if total_exposure > self.risk_limits['max_total_exposure']:
            return False, f"Would exceed total exposure limit (£{self.risk_limits['max_total_exposure']})"
        
        # Check position count
        open_positions = len([p for p in positions if p.status == PositionStatus.OPEN])
        if new_position_size > 0 and open_positions >= self.risk_limits['max_open_positions']:
            return False, f"Maximum open positions reached ({self.risk_limits['max_open_positions']})"
        
        # Check if trading is frozen
        if self.trading_frozen:
            return False, "Trading is currently frozen"
        
        # Check if kill switch is active
        if self.kill_switch_active:
            return False, "Kill switch is active - all trading disabled"
        
        return True, "OK"


class PerformanceMetrics:
    """Track and display trading performance metrics."""
    
    def __init__(self):
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': Decimal('0'),
            'best_trade': Decimal('0'),
            'worst_trade': Decimal('0'),
            'average_win': Decimal('0'),
            'average_loss': Decimal('0'),
            'win_rate': Decimal('0'),
            'sharpe_ratio': Decimal('0')
        }
    
    def update_metrics(self, trades: List[Trade]):
        """Update performance metrics from trades."""
        if not trades:
            return
        
        winning_trades = [t for t in trades if hasattr(t, 'pnl') and t.pnl > 0]
        losing_trades = [t for t in trades if hasattr(t, 'pnl') and t.pnl < 0]
        
        self.metrics['total_trades'] = len(trades)
        self.metrics['winning_trades'] = len(winning_trades)
        self.metrics['losing_trades'] = len(losing_trades)
        
        if trades:
            pnls = [t.pnl for t in trades if hasattr(t, 'pnl')]
            if pnls:
                self.metrics['total_pnl'] = sum(pnls)
                self.metrics['best_trade'] = max(pnls)
                self.metrics['worst_trade'] = min(pnls)
        
        if winning_trades:
            self.metrics['average_win'] = sum(t.pnl for t in winning_trades) / len(winning_trades)
        
        if losing_trades:
            self.metrics['average_loss'] = sum(t.pnl for t in losing_trades) / len(losing_trades)
        
        if self.metrics['total_trades'] > 0:
            self.metrics['win_rate'] = Decimal(self.metrics['winning_trades']) / Decimal(self.metrics['total_trades']) * 100
    
    def create_panel(self) -> Panel:
        """Create performance metrics panel."""
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", justify="right")
        
        # Win/Loss stats
        table.add_row("Total Trades", str(self.metrics['total_trades']))
        table.add_row("Win Rate", f"{self.metrics['win_rate']:.1f}%")
        table.add_row("Winning Trades", str(self.metrics['winning_trades']))
        table.add_row("Losing Trades", str(self.metrics['losing_trades']))
        
        table.add_row("", "")  # Spacer
        
        # P&L stats
        pnl_style = "green" if self.metrics['total_pnl'] >= 0 else "red"
        table.add_row("Total P&L", Text(f"£{self.metrics['total_pnl']:.2f}", style=pnl_style))
        table.add_row("Best Trade", Text(f"£{self.metrics['best_trade']:.2f}", style="green"))
        table.add_row("Worst Trade", Text(f"£{self.metrics['worst_trade']:.2f}", style="red"))
        table.add_row("Avg Win", Text(f"£{self.metrics['average_win']:.2f}", style="green"))
        table.add_row("Avg Loss", Text(f"£{self.metrics['average_loss']:.2f}", style="red"))
        
        return Panel(table, title="📈 Performance", border_style="blue")