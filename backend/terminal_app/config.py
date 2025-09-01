"""Configuration management for terminal app."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, List
from decimal import Decimal
from dataclasses import dataclass, asdict, field
from enum import Enum
import yaml


class ConfigSection(Enum):
    """Configuration sections."""
    GENERAL = "general"
    TRADING = "trading"
    DISPLAY = "display"
    RISK = "risk"
    AUTOMATION = "automation"
    KEYBOARD = "keyboard"
    CONNECTION = "connection"


@dataclass
class GeneralSettings:
    """General application settings."""
    app_name: str = "Tennis Trading Terminal"
    version: str = "1.0.0"
    auto_save: bool = True
    auto_save_interval: int = 300  # seconds
    log_level: str = "INFO"
    theme: str = "dark"
    sound_enabled: bool = False
    notifications_enabled: bool = True


@dataclass
class TradingSettings:
    """Trading configuration."""
    default_stake: Decimal = Decimal("50")
    quick_stakes: List[Decimal] = field(default_factory=lambda: [
        Decimal("10"), Decimal("25"), Decimal("50"), Decimal("100"), Decimal("250")
    ])
    stake_increment: Decimal = Decimal("5")
    min_odds: Decimal = Decimal("1.01")
    max_odds: Decimal = Decimal("1000")
    commission_rate: Decimal = Decimal("0.02")  # 2%
    one_click_betting: bool = False
    confirm_bets: bool = True
    confirm_close: bool = True
    auto_accept_price_changes: bool = False
    max_price_deviation: Decimal = Decimal("0.05")  # 5%


@dataclass
class DisplaySettings:
    """Display configuration."""
    refresh_rate: int = 1  # seconds
    show_volume: bool = True
    show_last_traded: bool = True
    show_total_matched: bool = True
    price_precision: int = 2
    stake_precision: int = 2
    show_profit_loss: bool = True
    odds_format: str = "decimal"  # decimal, fractional, american
    highlight_changes: bool = True
    flash_duration: int = 2  # seconds
    show_grid_lines: bool = True
    compact_mode: bool = False
    show_sparklines: bool = True
    chart_height: int = 15
    chart_width: int = 60


@dataclass
class RiskSettings:
    """Risk management settings."""
    max_position_size: Decimal = Decimal("100")
    max_market_exposure: Decimal = Decimal("500")
    max_total_exposure: Decimal = Decimal("1000")
    max_daily_loss: Decimal = Decimal("200")
    max_open_positions: int = 20
    stop_loss_enabled: bool = True
    default_stop_loss_pct: Decimal = Decimal("10")  # 10%
    take_profit_enabled: bool = False
    default_take_profit_pct: Decimal = Decimal("50")  # 50%
    trailing_stop_enabled: bool = False
    trailing_stop_distance: Decimal = Decimal("5")  # 5%
    kill_switch_enabled: bool = True
    freeze_on_daily_loss: bool = True
    alert_on_exposure_pct: Decimal = Decimal("75")  # Alert at 75% of limits


@dataclass
class AutomationSettings:
    """Automation settings."""
    auto_hedge_enabled: bool = False
    auto_hedge_profit_pct: Decimal = Decimal("10")  # Hedge at 10% profit
    auto_close_enabled: bool = False
    auto_close_profit_pct: Decimal = Decimal("20")  # Close at 20% profit
    auto_close_loss_pct: Decimal = Decimal("10")  # Close at 10% loss
    smart_execution_enabled: bool = True
    execution_strategy: str = "MARKET"  # MARKET, LIMIT, ICEBERG
    iceberg_chunk_size: Decimal = Decimal("10")
    retry_failed_orders: bool = True
    max_retries: int = 3
    retry_delay: int = 1  # seconds


@dataclass
class KeyboardSettings:
    """Keyboard shortcut settings."""
    enable_vim_mode: bool = True
    quick_bet_keys_enabled: bool = True
    function_keys_enabled: bool = True
    custom_shortcuts: Dict[str, str] = field(default_factory=lambda: {
        "place_back": "b",
        "place_lay": "l",
        "close_position": "c",
        "hedge_position": "h",
        "refresh": "r",
        "quit": "q",
        "help": "?",
        "search": "/",
        "undo": "ctrl+z"
    })


@dataclass
class ConnectionSettings:
    """Connection settings."""
    websocket_url: str = "ws://localhost:8000/api/ws/monitor"
    api_base_url: str = "http://localhost:8000/api"
    reconnect_enabled: bool = True
    reconnect_interval: int = 5  # seconds
    max_reconnect_attempts: int = 10
    heartbeat_interval: int = 30  # seconds
    timeout: int = 60  # seconds
    use_compression: bool = True
    buffer_size: int = 1000  # messages


@dataclass
class AppConfig:
    """Complete application configuration."""
    general: GeneralSettings = field(default_factory=GeneralSettings)
    trading: TradingSettings = field(default_factory=TradingSettings)
    display: DisplaySettings = field(default_factory=DisplaySettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    automation: AutomationSettings = field(default_factory=AutomationSettings)
    keyboard: KeyboardSettings = field(default_factory=KeyboardSettings)
    connection: ConnectionSettings = field(default_factory=ConnectionSettings)


class ConfigManager:
    """Manages application configuration."""
    
    DEFAULT_CONFIG_PATH = Path.home() / ".tennis_trading" / "config.json"
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = AppConfig()
        self._ensure_config_dir()
        self.load()
    
    def _ensure_config_dir(self):
        """Ensure config directory exists."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> AppConfig:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self._load_from_dict(data)
            except Exception as e:
                print(f"Error loading config: {e}")
                self.config = AppConfig()
        else:
            # Create default config
            self.config = AppConfig()
            self.save()
        
        return self.config
    
    def save(self):
        """Save configuration to file."""
        try:
            data = self._to_dict()
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _load_from_dict(self, data: Dict[str, Any]):
        """Load configuration from dictionary."""
        # General settings
        if "general" in data:
            self.config.general = GeneralSettings(**data["general"])
        
        # Trading settings
        if "trading" in data:
            trading_data = data["trading"].copy()
            # Convert to Decimal
            for key in ["default_stake", "stake_increment", "min_odds", "max_odds", 
                       "commission_rate", "max_price_deviation"]:
                if key in trading_data:
                    trading_data[key] = Decimal(str(trading_data[key]))
            
            if "quick_stakes" in trading_data:
                trading_data["quick_stakes"] = [
                    Decimal(str(s)) for s in trading_data["quick_stakes"]
                ]
            
            self.config.trading = TradingSettings(**trading_data)
        
        # Display settings
        if "display" in data:
            self.config.display = DisplaySettings(**data["display"])
        
        # Risk settings
        if "risk" in data:
            risk_data = data["risk"].copy()
            # Convert to Decimal
            for key in ["max_position_size", "max_market_exposure", "max_total_exposure",
                       "max_daily_loss", "default_stop_loss_pct", "default_take_profit_pct",
                       "trailing_stop_distance", "alert_on_exposure_pct"]:
                if key in risk_data:
                    risk_data[key] = Decimal(str(risk_data[key]))
            
            self.config.risk = RiskSettings(**risk_data)
        
        # Automation settings
        if "automation" in data:
            auto_data = data["automation"].copy()
            # Convert to Decimal
            for key in ["auto_hedge_profit_pct", "auto_close_profit_pct", 
                       "auto_close_loss_pct", "iceberg_chunk_size"]:
                if key in auto_data:
                    auto_data[key] = Decimal(str(auto_data[key]))
            
            self.config.automation = AutomationSettings(**auto_data)
        
        # Keyboard settings
        if "keyboard" in data:
            self.config.keyboard = KeyboardSettings(**data["keyboard"])
        
        # Connection settings
        if "connection" in data:
            self.config.connection = ConnectionSettings(**data["connection"])
    
    def _to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "general": asdict(self.config.general),
            "trading": asdict(self.config.trading),
            "display": asdict(self.config.display),
            "risk": asdict(self.config.risk),
            "automation": asdict(self.config.automation),
            "keyboard": asdict(self.config.keyboard),
            "connection": asdict(self.config.connection)
        }
    
    def get_section(self, section: ConfigSection) -> Any:
        """Get a configuration section."""
        return getattr(self.config, section.value)
    
    def update_section(self, section: ConfigSection, values: Dict[str, Any]):
        """Update a configuration section."""
        current = getattr(self.config, section.value)
        for key, value in values.items():
            if hasattr(current, key):
                setattr(current, key, value)
        self.save()
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get a configuration value by path (e.g., 'trading.default_stake')."""
        parts = path.split('.')
        value = self.config
        
        try:
            for part in parts:
                value = getattr(value, part)
            return value
        except AttributeError:
            return default
    
    def set(self, path: str, value: Any):
        """Set a configuration value by path."""
        parts = path.split('.')
        if len(parts) < 2:
            return
        
        section = parts[0]
        key = parts[-1]
        
        try:
            obj = getattr(self.config, section)
            if len(parts) == 2:
                setattr(obj, key, value)
            else:
                # Navigate to nested object
                for part in parts[1:-1]:
                    obj = getattr(obj, part)
                setattr(obj, key, value)
            
            self.save()
        except AttributeError:
            pass
    
    def reset_section(self, section: ConfigSection):
        """Reset a section to defaults."""
        if section == ConfigSection.GENERAL:
            self.config.general = GeneralSettings()
        elif section == ConfigSection.TRADING:
            self.config.trading = TradingSettings()
        elif section == ConfigSection.DISPLAY:
            self.config.display = DisplaySettings()
        elif section == ConfigSection.RISK:
            self.config.risk = RiskSettings()
        elif section == ConfigSection.AUTOMATION:
            self.config.automation = AutomationSettings()
        elif section == ConfigSection.KEYBOARD:
            self.config.keyboard = KeyboardSettings()
        elif section == ConfigSection.CONNECTION:
            self.config.connection = ConnectionSettings()
        
        self.save()
    
    def reset_all(self):
        """Reset all settings to defaults."""
        self.config = AppConfig()
        self.save()
    
    def export_config(self, path: Path, format: str = "json"):
        """Export configuration to file."""
        data = self._to_dict()
        
        if format == "json":
            with open(path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        elif format == "yaml":
            with open(path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
    
    def import_config(self, path: Path):
        """Import configuration from file."""
        if path.suffix == ".json":
            with open(path, 'r') as f:
                data = json.load(f)
        elif path.suffix in [".yaml", ".yml"]:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported format: {path.suffix}")
        
        self._load_from_dict(data)
        self.save()
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Validate trading settings
        if self.config.trading.default_stake <= 0:
            issues.append("Default stake must be positive")
        
        if self.config.trading.min_odds >= self.config.trading.max_odds:
            issues.append("Min odds must be less than max odds")
        
        # Validate risk settings
        if self.config.risk.max_position_size > self.config.risk.max_total_exposure:
            issues.append("Max position size cannot exceed total exposure limit")
        
        if self.config.risk.max_market_exposure > self.config.risk.max_total_exposure:
            issues.append("Max market exposure cannot exceed total exposure limit")
        
        # Validate display settings
        if self.config.display.refresh_rate < 0:
            issues.append("Refresh rate must be positive")
        
        # Validate connection settings
        if self.config.connection.max_reconnect_attempts < 0:
            issues.append("Max reconnect attempts must be non-negative")
        
        return issues