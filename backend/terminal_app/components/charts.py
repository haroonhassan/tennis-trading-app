"""ASCII charts and visualization components."""

from decimal import Decimal
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timedelta
from collections import deque
import math

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group
from rich.layout import Layout
from rich.align import Align

from ..models import Position, Trade


class ChartType:
    """Types of charts available."""
    LINE = "line"
    BAR = "bar"
    CANDLESTICK = "candlestick"
    HISTOGRAM = "histogram"
    SCATTER = "scatter"
    HEATMAP = "heatmap"


class ASCIIChart:
    """Base class for ASCII charts."""
    
    def __init__(self, width: int = 60, height: int = 20):
        self.width = width
        self.height = height
        self.data: List[float] = []
        self.labels: List[str] = []
        self.title = ""
        self.y_label = ""
        self.x_label = ""
    
    def set_data(self, data: List[float], labels: Optional[List[str]] = None):
        """Set chart data."""
        self.data = data
        if labels:
            self.labels = labels
        else:
            self.labels = [str(i) for i in range(len(data))]
    
    def _normalize_data(self, data: List[float]) -> List[int]:
        """Normalize data to chart height."""
        if not data:
            return []
        
        min_val = min(data)
        max_val = max(data)
        
        if max_val == min_val:
            return [self.height // 2] * len(data)
        
        normalized = []
        for val in data:
            norm = int((val - min_val) / (max_val - min_val) * (self.height - 1))
            normalized.append(norm)
        
        return normalized
    
    def _create_axes(self) -> List[List[str]]:
        """Create chart axes."""
        chart = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        
        # Y-axis
        for y in range(self.height):
            chart[y][0] = '│'
        
        # X-axis
        for x in range(self.width):
            chart[self.height - 1][x] = '─'
        
        # Origin
        chart[self.height - 1][0] = '└'
        
        return chart


class LineChart(ASCIIChart):
    """ASCII line chart."""
    
    def render(self) -> Text:
        """Render the line chart."""
        if not self.data:
            return Text("No data to display", style="dim italic")
        
        chart = self._create_axes()
        normalized = self._normalize_data(self.data)
        
        # Calculate x positions
        x_step = (self.width - 2) / (len(self.data) - 1) if len(self.data) > 1 else 1
        
        # Plot points and lines
        for i in range(len(normalized)):
            x = int(1 + i * x_step)
            y = self.height - 2 - normalized[i]
            
            if 0 <= x < self.width and 0 <= y < self.height - 1:
                chart[y][x] = '●'
                
                # Draw line to next point
                if i < len(normalized) - 1:
                    next_x = int(1 + (i + 1) * x_step)
                    next_y = self.height - 2 - normalized[i + 1]
                    
                    # Simple line drawing
                    if y == next_y:
                        # Horizontal line
                        for px in range(min(x, next_x) + 1, max(x, next_x)):
                            if 0 <= px < self.width:
                                chart[y][px] = '─'
                    elif x == next_x:
                        # Vertical line
                        for py in range(min(y, next_y) + 1, max(y, next_y)):
                            if 0 <= py < self.height - 1:
                                chart[py][x] = '│'
                    else:
                        # Diagonal line
                        steps = max(abs(next_x - x), abs(next_y - y))
                        for step in range(1, steps):
                            px = x + (next_x - x) * step // steps
                            py = y + (next_y - y) * step // steps
                            if 0 <= px < self.width and 0 <= py < self.height - 1:
                                if (next_x - x) * (next_y - y) > 0:
                                    chart[py][px] = '╱'
                                else:
                                    chart[py][px] = '╲'
        
        # Add labels
        if self.data:
            min_val = min(self.data)
            max_val = max(self.data)
            
            # Y-axis labels
            for i in range(0, self.height, max(1, self.height // 5)):
                y = self.height - 1 - i
                if y >= 0 and y < self.height - 1:
                    val = min_val + (max_val - min_val) * i / (self.height - 1)
                    label = f"{val:.1f}"
                    for j, c in enumerate(label[:5]):
                        if j < self.width:
                            chart[y][j] = c
        
        # Convert to text
        text = Text()
        if self.title:
            text.append(f"{self.title}\n", style="bold")
        
        for row in chart:
            text.append(''.join(row) + '\n', style="cyan")
        
        # Add x-axis labels
        if self.labels and len(self.labels) <= 10:
            label_row = ' ' * 6  # Space for y-axis
            x_step = (self.width - 6) // len(self.labels)
            for i, label in enumerate(self.labels):
                pos = 6 + i * x_step
                label_row = label_row[:pos] + label[:x_step] + label_row[pos + len(label[:x_step]):]
            text.append(label_row, style="dim")
        
        return text


class BarChart(ASCIIChart):
    """ASCII bar chart."""
    
    def render(self) -> Text:
        """Render the bar chart."""
        if not self.data:
            return Text("No data to display", style="dim italic")
        
        # Normalize data
        max_val = max(abs(v) for v in self.data) if self.data else 1
        
        text = Text()
        if self.title:
            text.append(f"{self.title}\n\n", style="bold")
        
        # Calculate bar width
        bar_width = max(1, (self.width - 20) // len(self.data))
        
        for i, (value, label) in enumerate(zip(self.data, self.labels)):
            # Label
            text.append(f"{label[:12]:>12} ", style="white")
            
            # Value
            text.append(f"{value:>8.2f} ", style="yellow")
            
            # Bar
            bar_len = int(abs(value) / max_val * (self.width - 25))
            if value >= 0:
                bar = '█' * bar_len
                text.append(bar, style="green")
            else:
                bar = '█' * bar_len
                text.append(bar, style="red")
            
            text.append("\n")
        
        return text


class CandlestickChart(ASCIIChart):
    """ASCII candlestick chart for price data."""
    
    def __init__(self, width: int = 60, height: int = 20):
        super().__init__(width, height)
        self.ohlc_data: List[Tuple[float, float, float, float]] = []
    
    def set_ohlc_data(self, data: List[Tuple[float, float, float, float]]):
        """Set OHLC data (open, high, low, close)."""
        self.ohlc_data = data
    
    def render(self) -> Text:
        """Render the candlestick chart."""
        if not self.ohlc_data:
            return Text("No data to display", style="dim italic")
        
        chart = self._create_axes()
        
        # Get min/max for normalization
        all_values = []
        for o, h, l, c in self.ohlc_data:
            all_values.extend([o, h, l, c])
        
        min_val = min(all_values)
        max_val = max(all_values)
        
        # Calculate candle width
        candle_width = max(1, (self.width - 2) // len(self.ohlc_data))
        
        for i, (open_p, high, low, close) in enumerate(self.ohlc_data):
            x = 1 + i * candle_width + candle_width // 2
            
            # Normalize values
            high_y = self.height - 2 - int((high - min_val) / (max_val - min_val) * (self.height - 2))
            low_y = self.height - 2 - int((low - min_val) / (max_val - min_val) * (self.height - 2))
            open_y = self.height - 2 - int((open_p - min_val) / (max_val - min_val) * (self.height - 2))
            close_y = self.height - 2 - int((close - min_val) / (max_val - min_val) * (self.height - 2))
            
            # Draw wick
            for y in range(min(high_y, low_y), max(high_y, low_y) + 1):
                if 0 <= y < self.height - 1 and 0 <= x < self.width:
                    chart[y][x] = '│'
            
            # Draw body
            body_top = min(open_y, close_y)
            body_bottom = max(open_y, close_y)
            
            if close >= open_p:
                # Bullish candle (green)
                symbol = '█'
            else:
                # Bearish candle (red)
                symbol = '░'
            
            for y in range(body_top, body_bottom + 1):
                if 0 <= y < self.height - 1:
                    for dx in range(-candle_width//2, candle_width//2 + 1):
                        if 0 <= x + dx < self.width:
                            chart[y][x + dx] = symbol
        
        # Convert to text
        text = Text()
        if self.title:
            text.append(f"{self.title}\n", style="bold")
        
        for row in chart:
            line = ''.join(row)
            # Color bullish/bearish differently
            colored_line = Text()
            for char in line:
                if char == '█':
                    colored_line.append(char, style="green")
                elif char == '░':
                    colored_line.append(char, style="red")
                else:
                    colored_line.append(char, style="cyan")
            text.append(colored_line)
            text.append("\n")
        
        return text


class HeatMap:
    """ASCII heatmap for correlation or intensity data."""
    
    def __init__(self, width: int = 40, height: int = 20):
        self.width = width
        self.height = height
        self.data: List[List[float]] = []
        self.row_labels: List[str] = []
        self.col_labels: List[str] = []
        self.title = ""
    
    def set_data(self, data: List[List[float]], row_labels: List[str] = None, col_labels: List[str] = None):
        """Set heatmap data."""
        self.data = data
        self.row_labels = row_labels or [f"R{i}" for i in range(len(data))]
        self.col_labels = col_labels or ([f"C{i}" for i in range(len(data[0]))] if data else [])
    
    def render(self) -> Text:
        """Render the heatmap."""
        if not self.data:
            return Text("No data to display", style="dim italic")
        
        # Intensity characters from low to high
        intensity_chars = ' ░▒▓█'
        
        # Find min/max for normalization
        flat_data = [val for row in self.data for val in row]
        min_val = min(flat_data) if flat_data else 0
        max_val = max(flat_data) if flat_data else 1
        
        text = Text()
        if self.title:
            text.append(f"{self.title}\n\n", style="bold")
        
        # Column headers
        text.append("      ")  # Space for row labels
        for label in self.col_labels[:10]:  # Limit columns
            text.append(f"{label[:4]:^5}", style="dim")
        text.append("\n")
        
        # Data rows
        for i, row in enumerate(self.data[:self.height]):
            # Row label
            text.append(f"{self.row_labels[i][:5]:>5} ", style="dim")
            
            # Data cells
            for val in row[:10]:  # Limit columns
                # Normalize and get intensity
                if max_val > min_val:
                    normalized = (val - min_val) / (max_val - min_val)
                else:
                    normalized = 0.5
                
                intensity = int(normalized * (len(intensity_chars) - 1))
                char = intensity_chars[intensity]
                
                # Color based on value
                if normalized < 0.2:
                    style = "blue"
                elif normalized < 0.4:
                    style = "cyan"
                elif normalized < 0.6:
                    style = "yellow"
                elif normalized < 0.8:
                    style = "magenta"
                else:
                    style = "red"
                
                text.append(f"{char * 5}", style=style)
            
            text.append("\n")
        
        # Legend
        text.append("\n")
        text.append("Legend: ", style="dim")
        for i, char in enumerate(intensity_chars):
            pct = i / (len(intensity_chars) - 1) * 100
            text.append(f"{char}={pct:.0f}% ", style="dim")
        
        return text


class SparkLine:
    """Compact sparkline chart for inline display."""
    
    @staticmethod
    def render(data: List[float], width: int = 20) -> str:
        """Render a sparkline."""
        if not data:
            return ""
        
        # Unicode block characters for sparklines
        blocks = ' ▁▂▃▄▅▆▇█'
        
        # Normalize data
        min_val = min(data)
        max_val = max(data)
        
        if max_val == min_val:
            return blocks[4] * min(width, len(data))
        
        # Sample or interpolate to fit width
        if len(data) > width:
            # Sample data
            step = len(data) / width
            sampled = []
            for i in range(width):
                idx = int(i * step)
                sampled.append(data[idx])
            data = sampled
        
        # Convert to sparkline
        sparkline = ""
        for val in data:
            normalized = (val - min_val) / (max_val - min_val)
            idx = int(normalized * (len(blocks) - 1))
            sparkline += blocks[idx]
        
        return sparkline


class ChartDashboard:
    """Dashboard combining multiple charts."""
    
    def __init__(self):
        self.line_chart = LineChart(width=50, height=15)
        self.bar_chart = BarChart(width=40, height=10)
        self.candlestick = CandlestickChart(width=50, height=15)
        self.heatmap = HeatMap(width=40, height=10)
    
    def create_pnl_chart(self, trades: List[Trade]) -> Panel:
        """Create P&L over time chart."""
        if not trades:
            return Panel(Text("No trades to display", style="dim italic"), title="P&L Chart")
        
        # Calculate cumulative P&L
        cumulative_pnl = []
        current_sum = Decimal("0")
        
        for trade in sorted(trades, key=lambda t: t.executed_at):
            if trade.pnl:
                current_sum += trade.pnl
            cumulative_pnl.append(float(current_sum))
        
        # Set data
        self.line_chart.set_data(cumulative_pnl)
        self.line_chart.title = "Cumulative P&L"
        
        return Panel(self.line_chart.render(), title="📈 P&L Chart", border_style="green")
    
    def create_volume_chart(self, trades: List[Trade]) -> Panel:
        """Create volume bar chart."""
        if not trades:
            return Panel(Text("No trades to display", style="dim italic"), title="Volume Chart")
        
        # Group by hour
        volume_by_hour = {}
        for trade in trades:
            hour = trade.executed_at.hour
            if hour not in volume_by_hour:
                volume_by_hour[hour] = Decimal("0")
            volume_by_hour[hour] += trade.stake
        
        # Convert to lists
        hours = sorted(volume_by_hour.keys())
        volumes = [float(volume_by_hour[h]) for h in hours]
        labels = [f"{h:02d}:00" for h in hours]
        
        self.bar_chart.set_data(volumes, labels)
        self.bar_chart.title = "Hourly Volume"
        
        return Panel(self.bar_chart.render(), title="📊 Volume Chart", border_style="blue")
    
    def create_price_chart(self, price_history: List[Tuple[datetime, float]]) -> Panel:
        """Create price movement chart."""
        if not price_history:
            return Panel(Text("No price data", style="dim italic"), title="Price Chart")
        
        # Extract prices
        prices = [p for _, p in price_history[-50:]]  # Last 50 points
        
        self.line_chart.set_data(prices)
        self.line_chart.title = "Price Movement"
        
        # Add sparkline
        sparkline = SparkLine.render(prices, width=30)
        
        content = Group(
            self.line_chart.render(),
            Text(f"\nTrend: {sparkline}", style="yellow")
        )
        
        return Panel(content, title="💹 Price Chart", border_style="yellow")
    
    def create_position_heatmap(self, positions: List[Position]) -> Panel:
        """Create position P&L heatmap."""
        if not positions:
            return Panel(Text("No positions", style="dim italic"), title="Position Heatmap")
        
        # Group positions by selection and time
        # This is a simplified example
        selections = list(set(p.selection_name for p in positions))[:5]
        
        # Create mock heatmap data (would be real P&L data)
        data = []
        for _ in range(min(5, len(selections))):
            row = [float(p.pnl) for p in positions[:5]]
            data.append(row)
        
        self.heatmap.set_data(data, selections, ["T1", "T2", "T3", "T4", "T5"])
        self.heatmap.title = "Position P&L Heatmap"
        
        return Panel(self.heatmap.render(), title="🔥 Position Heatmap", border_style="red")
    
    def create_mini_charts(self, positions: List[Position]) -> Panel:
        """Create mini charts panel with sparklines."""
        lines = []
        
        for position in positions[:5]:
            # Generate mock price history (would be real data)
            prices = [float(position.odds) + (i - 5) * 0.01 for i in range(10)]
            sparkline = SparkLine.render(prices, width=15)
            
            line = Text()
            line.append(f"{position.selection_name[:12]:12} ", style="white")
            line.append(sparkline, style="cyan")
            line.append(f" {position.odds:.2f}", style="yellow")
            
            # P&L indicator
            if position.pnl >= 0:
                line.append(f" ▲{position.pnl:.2f}", style="green")
            else:
                line.append(f" ▼{abs(position.pnl):.2f}", style="red")
            
            lines.append(line)
        
        return Panel(
            Group(*lines) if lines else Text("No data", style="dim"),
            title="📉 Mini Charts",
            border_style="magenta"
        )