"""Settings UI component for configuration management."""

from typing import List, Optional, Dict, Any
from decimal import Decimal

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group
from rich.layout import Layout
from rich.columns import Columns
from rich.prompt import Prompt, Confirm, IntPrompt, FloatPrompt

from ..config import ConfigManager, ConfigSection, AppConfig


class SettingsPanel:
    """Settings panel for configuration management."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.current_section = ConfigSection.GENERAL
        self.is_editing = False
        self.edit_field = None
    
    def create_panel(self) -> Panel:
        """Create the settings panel."""
        layout = Layout()
        
        # Split into sections
        layout.split_row(
            Layout(self._create_menu(), name="menu", ratio=1),
            Layout(self._create_section_view(), name="content", ratio=3)
        )
        
        return Panel(
            layout,
            title="⚙️  Settings & Configuration",
            border_style="blue"
        )
    
    def _create_menu(self) -> Panel:
        """Create settings menu."""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Section", style="white")
        
        for section in ConfigSection:
            if section == self.current_section:
                table.add_row(Text(f"▶ {section.value.title()}", style="bold cyan"))
            else:
                table.add_row(Text(f"  {section.value.title()}", style="dim white"))
        
        # Add actions
        table.add_row("")
        table.add_row(Text("Actions:", style="bold yellow"))
        table.add_row(Text("  [S]ave", style="green"))
        table.add_row(Text("  [R]eset Section", style="yellow"))
        table.add_row(Text("  [E]xport", style="blue"))
        table.add_row(Text("  [I]mport", style="blue"))
        table.add_row(Text("  [V]alidate", style="magenta"))
        
        return Panel(table, title="Menu", border_style="dim")
    
    def _create_section_view(self) -> Panel:
        """Create view for current section."""
        if self.current_section == ConfigSection.GENERAL:
            return self._create_general_view()
        elif self.current_section == ConfigSection.TRADING:
            return self._create_trading_view()
        elif self.current_section == ConfigSection.DISPLAY:
            return self._create_display_view()
        elif self.current_section == ConfigSection.RISK:
            return self._create_risk_view()
        elif self.current_section == ConfigSection.AUTOMATION:
            return self._create_automation_view()
        elif self.current_section == ConfigSection.KEYBOARD:
            return self._create_keyboard_view()
        elif self.current_section == ConfigSection.CONNECTION:
            return self._create_connection_view()
    
    def _create_general_view(self) -> Panel:
        """Create general settings view."""
        config = self.config_manager.config.general
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="yellow")
        table.add_column("Description", style="dim")
        
        table.add_row("App Name", config.app_name, "Application name")
        table.add_row("Version", config.version, "Version number")
        table.add_row("Auto Save", str(config.auto_save), "Enable auto-save")
        table.add_row("Save Interval", f"{config.auto_save_interval}s", "Auto-save interval")
        table.add_row("Log Level", config.log_level, "Logging level")
        table.add_row("Theme", config.theme, "Color theme")
        table.add_row("Sound", str(config.sound_enabled), "Enable sounds")
        table.add_row("Notifications", str(config.notifications_enabled), "Enable notifications")
        
        return Panel(table, title="General Settings", border_style="cyan")
    
    def _create_trading_view(self) -> Panel:
        """Create trading settings view."""
        config = self.config_manager.config.trading
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="yellow")
        table.add_column("Description", style="dim")
        
        table.add_row("Default Stake", f"£{config.default_stake}", "Default bet amount")
        table.add_row("Quick Stakes", ", ".join(f"£{s}" for s in config.quick_stakes), "Quick bet amounts")
        table.add_row("Stake Increment", f"£{config.stake_increment}", "Stake adjustment step")
        table.add_row("Min Odds", str(config.min_odds), "Minimum acceptable odds")
        table.add_row("Max Odds", str(config.max_odds), "Maximum acceptable odds")
        table.add_row("Commission", f"{float(config.commission_rate)*100:.1f}%", "Commission rate")
        table.add_row("One-Click Betting", str(config.one_click_betting), "Skip confirmation")
        table.add_row("Confirm Bets", str(config.confirm_bets), "Require bet confirmation")
        table.add_row("Confirm Close", str(config.confirm_close), "Require close confirmation")
        table.add_row("Auto Accept Price", str(config.auto_accept_price_changes), "Auto-accept price changes")
        table.add_row("Max Price Deviation", f"{float(config.max_price_deviation)*100:.1f}%", "Max price change to accept")
        
        return Panel(table, title="Trading Settings", border_style="green")
    
    def _create_display_view(self) -> Panel:
        """Create display settings view."""
        config = self.config_manager.config.display
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="yellow")
        table.add_column("Description", style="dim")
        
        table.add_row("Refresh Rate", f"{config.refresh_rate}s", "Display update frequency")
        table.add_row("Show Volume", str(config.show_volume), "Display volume data")
        table.add_row("Show Last Traded", str(config.show_last_traded), "Show last traded price")
        table.add_row("Show Total Matched", str(config.show_total_matched), "Show total matched")
        table.add_row("Price Precision", str(config.price_precision), "Decimal places for prices")
        table.add_row("Stake Precision", str(config.stake_precision), "Decimal places for stakes")
        table.add_row("Show P&L", str(config.show_profit_loss), "Display profit/loss")
        table.add_row("Odds Format", config.odds_format, "Odds display format")
        table.add_row("Highlight Changes", str(config.highlight_changes), "Flash price changes")
        table.add_row("Flash Duration", f"{config.flash_duration}s", "Price flash duration")
        table.add_row("Grid Lines", str(config.show_grid_lines), "Show grid lines")
        table.add_row("Compact Mode", str(config.compact_mode), "Compact display")
        table.add_row("Sparklines", str(config.show_sparklines), "Show mini charts")
        table.add_row("Chart Height", str(config.chart_height), "Chart height in lines")
        table.add_row("Chart Width", str(config.chart_width), "Chart width in chars")
        
        return Panel(table, title="Display Settings", border_style="blue")
    
    def _create_risk_view(self) -> Panel:
        """Create risk settings view."""
        config = self.config_manager.config.risk
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="yellow")
        table.add_column("Description", style="dim")
        
        table.add_row("Max Position Size", f"£{config.max_position_size}", "Maximum per position")
        table.add_row("Max Market Exposure", f"£{config.max_market_exposure}", "Maximum per market")
        table.add_row("Max Total Exposure", f"£{config.max_total_exposure}", "Maximum total exposure")
        table.add_row("Max Daily Loss", f"£{config.max_daily_loss}", "Daily loss limit")
        table.add_row("Max Open Positions", str(config.max_open_positions), "Concurrent position limit")
        table.add_row("Stop Loss Enabled", str(config.stop_loss_enabled), "Auto stop-loss")
        table.add_row("Stop Loss %", f"{config.default_stop_loss_pct}%", "Default stop-loss")
        table.add_row("Take Profit Enabled", str(config.take_profit_enabled), "Auto take-profit")
        table.add_row("Take Profit %", f"{config.default_take_profit_pct}%", "Default take-profit")
        table.add_row("Trailing Stop", str(config.trailing_stop_enabled), "Enable trailing stops")
        table.add_row("Trail Distance", f"{config.trailing_stop_distance}%", "Trailing stop distance")
        table.add_row("Kill Switch", str(config.kill_switch_enabled), "Emergency stop enabled")
        table.add_row("Freeze on Loss", str(config.freeze_on_daily_loss), "Freeze on daily limit")
        table.add_row("Alert Threshold", f"{config.alert_on_exposure_pct}%", "Alert at % of limits")
        
        return Panel(table, title="Risk Settings", border_style="red")
    
    def _create_automation_view(self) -> Panel:
        """Create automation settings view."""
        config = self.config_manager.config.automation
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="yellow")
        table.add_column("Description", style="dim")
        
        table.add_row("Auto Hedge", str(config.auto_hedge_enabled), "Enable auto-hedging")
        table.add_row("Hedge at Profit", f"{config.auto_hedge_profit_pct}%", "Auto-hedge trigger")
        table.add_row("Auto Close", str(config.auto_close_enabled), "Enable auto-close")
        table.add_row("Close at Profit", f"{config.auto_close_profit_pct}%", "Auto-close profit")
        table.add_row("Close at Loss", f"{config.auto_close_loss_pct}%", "Auto-close loss")
        table.add_row("Smart Execution", str(config.smart_execution_enabled), "Smart order routing")
        table.add_row("Execution Strategy", config.execution_strategy, "Default strategy")
        table.add_row("Iceberg Size", f"£{config.iceberg_chunk_size}", "Chunk size for large orders")
        table.add_row("Retry Failed", str(config.retry_failed_orders), "Retry failed orders")
        table.add_row("Max Retries", str(config.max_retries), "Maximum retry attempts")
        table.add_row("Retry Delay", f"{config.retry_delay}s", "Delay between retries")
        
        return Panel(table, title="Automation Settings", border_style="magenta")
    
    def _create_keyboard_view(self) -> Panel:
        """Create keyboard settings view."""
        config = self.config_manager.config.keyboard
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="yellow")
        table.add_column("Description", style="dim")
        
        table.add_row("Vim Mode", str(config.enable_vim_mode), "Enable vim keybindings")
        table.add_row("Quick Bet Keys", str(config.quick_bet_keys_enabled), "Enable 1-5 stake keys")
        table.add_row("Function Keys", str(config.function_keys_enabled), "Enable F1-F6 views")
        
        table.add_row("", "", "")
        table.add_row("Custom Shortcuts:", "", "")
        
        for action, key in config.custom_shortcuts.items():
            table.add_row(f"  {action}", key, "")
        
        return Panel(table, title="Keyboard Settings", border_style="yellow")
    
    def _create_connection_view(self) -> Panel:
        """Create connection settings view."""
        config = self.config_manager.config.connection
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="yellow")
        table.add_column("Description", style="dim")
        
        table.add_row("WebSocket URL", config.websocket_url[:40], "WebSocket endpoint")
        table.add_row("API URL", config.api_base_url[:40], "API base URL")
        table.add_row("Auto Reconnect", str(config.reconnect_enabled), "Enable reconnection")
        table.add_row("Reconnect Interval", f"{config.reconnect_interval}s", "Time between attempts")
        table.add_row("Max Reconnects", str(config.max_reconnect_attempts), "Maximum attempts")
        table.add_row("Heartbeat", f"{config.heartbeat_interval}s", "Heartbeat interval")
        table.add_row("Timeout", f"{config.timeout}s", "Connection timeout")
        table.add_row("Compression", str(config.use_compression), "Use compression")
        table.add_row("Buffer Size", str(config.buffer_size), "Message buffer size")
        
        return Panel(table, title="Connection Settings", border_style="green")
    
    def navigate_section(self, direction: int):
        """Navigate between sections."""
        sections = list(ConfigSection)
        current_idx = sections.index(self.current_section)
        new_idx = (current_idx + direction) % len(sections)
        self.current_section = sections[new_idx]
    
    def edit_setting(self, field_name: str):
        """Start editing a setting."""
        self.is_editing = True
        self.edit_field = field_name
    
    def save_edit(self, value: Any):
        """Save edited value."""
        if self.edit_field:
            path = f"{self.current_section.value}.{self.edit_field}"
            self.config_manager.set(path, value)
            self.is_editing = False
            self.edit_field = None
    
    def cancel_edit(self):
        """Cancel editing."""
        self.is_editing = False
        self.edit_field = None
    
    def validate_config(self) -> List[str]:
        """Validate current configuration."""
        return self.config_manager.validate()
    
    def reset_current_section(self):
        """Reset current section to defaults."""
        self.config_manager.reset_section(self.current_section)
    
    def get_quick_settings_panel(self) -> Panel:
        """Get a compact quick settings panel."""
        config = self.config_manager.config
        
        # Key settings
        lines = []
        
        # Trading
        lines.append(Text("Trading:", style="bold yellow"))
        lines.append(Text(f"  Default Stake: £{config.trading.default_stake}", style="white"))
        lines.append(Text(f"  One-Click: {config.trading.one_click_betting}", style="white"))
        
        # Risk
        lines.append(Text("\nRisk:", style="bold red"))
        lines.append(Text(f"  Max Exposure: £{config.risk.max_total_exposure}", style="white"))
        lines.append(Text(f"  Stop Loss: {config.risk.stop_loss_enabled} ({config.risk.default_stop_loss_pct}%)", style="white"))
        
        # Display
        lines.append(Text("\nDisplay:", style="bold blue"))
        lines.append(Text(f"  Odds Format: {config.display.odds_format}", style="white"))
        lines.append(Text(f"  Compact Mode: {config.display.compact_mode}", style="white"))
        
        # Connection
        lines.append(Text("\nConnection:", style="bold green"))
        lines.append(Text(f"  Status: {'Connected' if config.connection.reconnect_enabled else 'Manual'}", style="white"))
        
        return Panel(
            Group(*lines),
            title="⚡ Quick Settings",
            border_style="cyan"
        )