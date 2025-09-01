#!/usr/bin/env python3
"""Test charts and visualization functionality."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta
from rich.console import Console
from rich.layout import Layout
import random
import math

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from terminal_app.models import Trade, Position, OrderSide, PositionStatus
from terminal_app.components.charts import (
    LineChart, BarChart, CandlestickChart, HeatMap, 
    SparkLine, ChartDashboard
)


def create_sample_trades():
    """Create sample trades for testing."""
    trades = []
    now = datetime.now()
    cumulative_pnl = Decimal("0")
    
    for i in range(30):
        # Generate somewhat realistic P&L
        pnl = Decimal(str(random.uniform(-20, 30)))
        cumulative_pnl += pnl
        
        trade = Trade(
            trade_id=f"TRD_{i:03d}",
            match_id="MATCH_001",
            selection_id=f"SEL_{i % 5:03d}",
            selection_name=["Djokovic", "Nadal", "Federer", "Murray", "Zverev"][i % 5],
            side=OrderSide.BACK if i % 2 == 0 else OrderSide.LAY,
            odds=Decimal(str(1.5 + random.random() * 2)),
            stake=Decimal(str(10 + random.randint(0, 90))),
            status="MATCHED",
            executed_at=now - timedelta(hours=30-i),
            pnl=pnl
        )
        trades.append(trade)
    
    return trades


def create_sample_positions():
    """Create sample positions for testing."""
    positions = []
    
    for i in range(10):
        position = Position(
            position_id=f"POS_{i:03d}",
            match_id=f"MATCH_{i // 2:03d}",
            selection_id=f"SEL_{i:03d}",
            selection_name=["Djokovic", "Nadal", "Federer", "Murray", "Zverev", 
                          "Tsitsipas", "Medvedev", "Rublev", "Berrettini", "Ruud"][i],
            side=OrderSide.BACK if i % 2 == 0 else OrderSide.LAY,
            odds=Decimal(str(1.5 + random.random() * 2)),
            stake=Decimal(str(25 + random.randint(0, 75))),
            status=PositionStatus.OPEN,
            current_odds=Decimal(str(1.5 + random.random() * 2)),
            pnl=Decimal(str(random.uniform(-30, 50)))
        )
        positions.append(position)
    
    return positions


async def test_charts():
    """Test chart functionality."""
    console = Console()
    
    print("=" * 60)
    print("CHARTS AND VISUALIZATION TEST")
    print("=" * 60)
    
    # Test 1: Line Chart
    print("\n1. Testing Line Chart...")
    line_chart = LineChart(width=60, height=15)
    
    # Generate sine wave data
    data = [math.sin(x / 5) * 10 + 10 for x in range(30)]
    labels = [f"T{i}" for i in range(30)]
    
    line_chart.set_data(data, labels)
    line_chart.title = "Sine Wave Pattern"
    
    console.print(Panel(line_chart.render(), title="📈 Line Chart", border_style="green"))
    print("✓ Line chart rendering")
    
    # Test 2: Bar Chart
    print("\n2. Testing Bar Chart...")
    bar_chart = BarChart(width=50, height=10)
    
    bar_data = [random.uniform(-50, 50) for _ in range(8)]
    bar_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "Total"]
    
    bar_chart.set_data(bar_data, bar_labels)
    bar_chart.title = "Daily P&L"
    
    console.print(Panel(bar_chart.render(), title="📊 Bar Chart", border_style="blue"))
    print("✓ Bar chart rendering")
    
    # Test 3: Candlestick Chart
    print("\n3. Testing Candlestick Chart...")
    candlestick = CandlestickChart(width=60, height=15)
    
    # Generate OHLC data
    ohlc_data = []
    price = 2.0
    for _ in range(20):
        open_p = price
        close = price + random.uniform(-0.1, 0.1)
        high = max(open_p, close) + random.uniform(0, 0.05)
        low = min(open_p, close) - random.uniform(0, 0.05)
        ohlc_data.append((open_p, high, low, close))
        price = close
    
    candlestick.set_ohlc_data(ohlc_data)
    candlestick.title = "Price Action (OHLC)"
    
    console.print(Panel(candlestick.render(), title="🕯️ Candlestick Chart", border_style="yellow"))
    print("✓ Candlestick chart rendering")
    
    # Test 4: Heatmap
    print("\n4. Testing Heatmap...")
    heatmap = HeatMap(width=40, height=10)
    
    # Generate correlation matrix
    heat_data = []
    for i in range(5):
        row = []
        for j in range(5):
            if i == j:
                row.append(1.0)
            else:
                row.append(random.uniform(-1, 1))
        heat_data.append(row)
    
    row_labels = ["Djok", "Nadal", "Fed", "Murray", "Zver"]
    col_labels = row_labels
    
    heatmap.set_data(heat_data, row_labels, col_labels)
    heatmap.title = "Selection Correlation"
    
    console.print(Panel(heatmap.render(), title="🔥 Heatmap", border_style="red"))
    print("✓ Heatmap rendering")
    
    # Test 5: Sparklines
    print("\n5. Testing Sparklines...")
    
    sparklines_panel = Text()
    sparklines_panel.append("Market Trends:\n\n", style="bold")
    
    markets = ["Djokovic", "Nadal", "Federer", "Murray", "Zverev"]
    for market in markets:
        # Generate random price movement
        prices = [2.0 + random.uniform(-0.5, 0.5) for _ in range(30)]
        sparkline = SparkLine.render(prices, width=20)
        
        sparklines_panel.append(f"{market:12} ", style="white")
        sparklines_panel.append(sparkline, style="cyan")
        sparklines_panel.append(f" {prices[-1]:.2f}", style="yellow")
        
        # Trend indicator
        if prices[-1] > prices[0]:
            sparklines_panel.append(" ▲", style="green")
        else:
            sparklines_panel.append(" ▼", style="red")
        sparklines_panel.append("\n")
    
    console.print(Panel(sparklines_panel, title="📉 Sparklines", border_style="magenta"))
    print("✓ Sparklines rendering")
    
    # Test 6: Chart Dashboard
    print("\n6. Testing Chart Dashboard...")
    dashboard = ChartDashboard()
    
    # Create sample data
    trades = create_sample_trades()
    positions = create_sample_positions()
    
    # Create dashboard layout
    layout = Layout()
    layout.split_column(
        Layout(name="top", size=17),
        Layout(name="middle", size=12),
        Layout(name="bottom", size=8)
    )
    
    layout["top"].split_row(
        Layout(dashboard.create_pnl_chart(trades), name="pnl"),
        Layout(dashboard.create_volume_chart(trades), name="volume")
    )
    
    # Generate price history
    price_history = []
    base_price = 2.0
    now = datetime.now()
    for i in range(50):
        price = base_price + math.sin(i / 5) * 0.2 + random.uniform(-0.05, 0.05)
        price_history.append((now - timedelta(minutes=50-i), price))
    
    layout["middle"].split_row(
        Layout(dashboard.create_price_chart(price_history), name="price"),
        Layout(dashboard.create_position_heatmap(positions), name="heatmap")
    )
    
    layout["bottom"].update(dashboard.create_mini_charts(positions))
    
    console.print(layout)
    print("✓ Chart dashboard rendering")
    
    # Test 7: Animated Chart
    print("\n7. Testing Animated Chart...")
    print("   Simulating real-time price updates...")
    
    from rich.live import Live
    
    animated_chart = LineChart(width=60, height=10)
    price_data = []
    
    with Live(Panel(Text("Initializing...", style="dim"), title="⚡ Live Price"), 
              console=console, refresh_per_second=2) as live:
        
        for i in range(20):
            # Add new price point
            new_price = 2.0 + math.sin(i / 3) * 0.3 + random.uniform(-0.1, 0.1)
            price_data.append(new_price)
            
            # Keep last 30 points
            if len(price_data) > 30:
                price_data.pop(0)
            
            # Update chart
            animated_chart.set_data(price_data)
            animated_chart.title = f"Live Price (Updates: {i+1})"
            
            # Update display
            live.update(Panel(animated_chart.render(), 
                            title="⚡ Live Price", 
                            border_style="yellow"))
            
            await asyncio.sleep(0.2)
    
    print("✓ Animated chart working")
    
    # Test 8: Multi-panel Chart View
    print("\n8. Testing Multi-panel Chart View...")
    
    multi_layout = Layout()
    multi_layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", size=30)
    )
    
    multi_layout["header"].update(
        Panel(Align.center(Text("📊 CHARTS DASHBOARD 📊", style="bold white on blue")))
    )
    
    multi_layout["body"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1)
    )
    
    # Left side - price charts
    left_charts = Layout()
    left_charts.split_column(
        Layout(dashboard.create_pnl_chart(trades), size=15),
        Layout(dashboard.create_price_chart(price_history), size=15)
    )
    multi_layout["left"].update(left_charts)
    
    # Right side - analysis charts
    right_charts = Layout()
    right_charts.split_column(
        Layout(dashboard.create_volume_chart(trades), size=12),
        Layout(dashboard.create_position_heatmap(positions), size=10),
        Layout(dashboard.create_mini_charts(positions), size=8)
    )
    multi_layout["right"].update(right_charts)
    
    console.print(multi_layout)
    print("✓ Multi-panel chart view working")
    
    print("\n" + "=" * 60)
    print("ALL CHART TESTS PASSED!")
    print("=" * 60)
    
    print("\nFeatures Implemented:")
    print("✓ Line charts with interpolation")
    print("✓ Bar charts with positive/negative values")
    print("✓ Candlestick charts for OHLC data")
    print("✓ Heatmaps with intensity coloring")
    print("✓ Sparklines for inline trends")
    print("✓ Chart dashboard with multiple views")
    print("✓ P&L and volume analysis charts")
    print("✓ Real-time animated charts")
    print("✓ Multi-panel layouts")
    print("✓ Mini charts with sparklines")


if __name__ == "__main__":
    try:
        # Import Panel and Text here
        from rich.panel import Panel
        from rich.text import Text
        from rich.align import Align
        
        asyncio.run(test_charts())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()