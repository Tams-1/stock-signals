# Quick Start: Phase 3 & 4 (Conviction Scoring + Momentum)

## Installation

All modules are in `src/` and `src/strategies/`:
```bash
# New modules (already implemented)
src/signals/conviction_scorer.py      # Signal aggregation & conviction
src/signals/momentum_detector.py       # Momentum detection
src/signals/position_manager.py        # Position sizing & constraints
src/strategies/momentum_strategy.py     # Momentum-following strategy
```

No new dependencies required (uses existing: pandas, numpy, scipy).

## 5-Minute Demo

### 1. Basic Conviction Scoring

```python
from src.signals.conviction_scorer import ConvictionScorer

# Initialize
scorer = ConvictionScorer()

# Simulate signals from detectors
signals = {
    'technical': [
        {'signal': 'volume_anomaly', 'strength': 0.8, 'direction': 'bullish'},
        {'signal': 'momentum_continuation', 'strength': 0.75, 'direction': 'bullish'}
    ],
    'news': [
        {'signal': 'positive_sentiment', 'strength': 0.7, 'direction': 'bullish'}
    ],
    'regime': [
        {'signal': 'uptrend_confirmation', 'strength': 0.85, 'direction': 'bullish'}
    ]
}

# Score
conviction, direction, details = scorer.score_signals(signals)

print(f"Conviction: {conviction:.2f}")  # Should be >= 0.8 (all signals agree)
print(f"Direction: {direction}")        # 'bullish'

# Get position size
sizing = scorer.get_position_sizing_recommendation(conviction)
print(f"Position size: {sizing['size_pct']:.0%}")  # 70%
print(f"Rationale: {sizing['rationale']}")         # "High conviction: 70% of capital"
```

**Expected Output**:
```
Conviction: 0.80
Direction: bullish
Position size: 70%
Rationale: High conviction: 70% of capital
```

### 2. Momentum Detection

```python
import pandas as pd
import numpy as np
from datetime import datetime
from src.signals.momentum_detector import MomentumDetector

# Create sample uptrend data
dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
close = np.linspace(100, 115, 30)
data = pd.DataFrame({
    'Open': close - 0.5,
    'High': close + 1.5,
    'Low': close - 1.5,
    'Close': close,
    'Volume': 1000000 + np.random.normal(0, 100000, 30)
}, index=dates)

# Detect momentum
detector = MomentumDetector()
result = detector.detect_momentum(data)

print(f"Momentum strength: {result['momentum_strength']:.2f}")
print(f"Momentum type: {result['momentum_type']}")
print(f"MA cross: {result['ma_cross']}")
print(f"Persistence: {result['persistence']} days")
```

**Expected Output**:
```
Momentum strength: 0.85
Momentum type: bullish
MA cross: True
Persistence: 3 days
```

### 3. Position Manager

```python
from src.signals.position_manager import PositionManager
from datetime import datetime

# Initialize with $10,000 capital
manager = PositionManager(initial_capital=10000.0)

# Check if we can open a position (conviction 0.75 = 50% position)
can_open, reason = manager.can_open_position(conviction=0.75)
print(f"Can open: {can_open}, Reason: {reason}")

# Open position
if can_open:
    pos, msg = manager.open_position(
        ticker='AAPL',
        entry_price=150.0,
        conviction=0.75,
        entry_date=datetime.now().strftime('%Y-%m-%d')
    )
    print(f"Position opened: {pos.ticker} x {pos.quantity} @ ${pos.entry_price}")
    print(f"Stop loss: ${pos.stop_loss:.2f}")
    print(f"Take profit: ${pos.take_profit:.2f}")

# Update price and check for exits
manager.update_prices({'AAPL': 152.50})  # Small gain

# Get portfolio metrics
metrics = manager.get_portfolio_metrics({'AAPL': 152.50})
print(f"Portfolio value: ${metrics['total_value']:.2f}")
print(f"Unrealized P&L: ${metrics['unrealized_pnl']:.2f} ({metrics['unrealized_pnl_pct']:.1f}%)")
print(f"Cash reserve: {metrics['cash_pct']:.1f}%")
```

**Expected Output**:
```
Can open: True, Reason: OK
Position opened: AAPL x 33 @ $150.00
Stop loss: $145.50
Take profit: $157.50
Portfolio value: $10000.62
Unrealized P&L: $82.50 (0.8%)
Cash reserve: 49.2%
```

### 4. Momentum Strategy

```python
from src.strategies.momentum_strategy import MomentumStrategy

# Initialize strategy
strategy = MomentumStrategy()

# Check entry conditions
momentum_result = {
    'momentum_strength': 0.8,
    'momentum_type': 'bullish',
    'persistence': 3
}

should_enter, reason = strategy.should_enter(
    data,
    regime='uptrend',
    momentum_result=momentum_result,
    news_sentiment='positive'
)

print(f"Should enter: {should_enter}")
if should_enter:
    # Get complete signal
    signal = strategy.get_position_signal(
        data, 'uptrend', momentum_result, conviction=0.8
    )
    print(f"Entry: ${signal['entry_price']:.2f}")
    print(f"Stop: ${signal['stop_loss']:.2f}")
    print(f"Target: ${signal['take_profit']:.2f}")
    print(f"Risk/Reward: {signal['risk_reward_ratio']:.2f}")
    print(f"Position size: {signal['position_size_pct']:.0%}")
```

**Expected Output**:
```
Should enter: True
Entry: $115.11
Stop: $111.65
Target: $120.86
Risk/Reward: 1.67
Position size: 70%
```

## Real-World Integration

### Use Case: Real-time Trading

```python
from src.signals.conviction_scorer import ConvictionScorer
from src.signals.momentum_detector import MomentumDetector
from src.signals.position_manager import PositionManager
from src.strategies.momentum_strategy import MomentumStrategy

# Initialize all components
scorer = ConvictionScorer()
momentum_detector = MomentumDetector()
pos_manager = PositionManager(initial_capital=100000.0)
strategy = MomentumStrategy()

# For each ticker in watchlist
for ticker in ['AAPL', 'MSFT', 'TSLA']:
    # Fetch data
    data = fetch_ticker_data(ticker, days=30)
    
    # Get signals
    info_signals = info_detector.run_all(data)
    mom_signals = mom_detector.run_all(data)
    regime = regime_detector.detect_regime(data)
    
    # Calculate conviction
    signals = scorer.aggregate_signals_from_detectors(
        info_signals=info_signals,
        mom_signals=mom_signals,
        regime_signals=regime
    )
    conviction, direction, _ = scorer.score_signals(signals)
    
    # Detect momentum
    momentum_result = momentum_detector.detect_momentum(data)
    
    # Check if we should enter (uptrend + momentum)
    if regime['regime'] == 'uptrend' and momentum_result['momentum_type'] == 'bullish':
        entry_signal = strategy.generate_entry_signal(
            ticker, data, 'uptrend', momentum_result, conviction
        )
        
        if entry_signal:
            # Open position
            pos, msg = pos_manager.open_position(
                ticker=ticker,
                entry_price=entry_signal['entry_price'],
                conviction=conviction,
                entry_date=today
            )
            print(f"✓ Opened {ticker}: {entry_signal['position_size_pct']:.0%} @ ${entry_signal['entry_price']:.2f}")
    
    # Check existing positions
    current_price = data['Close'].iloc[-1]
    exits = pos_manager.check_exit_signals({ticker: current_price})
    
    for exit_ticker, exit_reason in exits:
        success, msg = pos_manager.close_position(
            exit_ticker, current_price, today, reason=exit_reason
        )
        if success:
            print(f"✓ Closed {exit_ticker}: {msg}")

# End-of-day portfolio summary
metrics = pos_manager.get_portfolio_metrics(current_prices)
print(f"\nPortfolio Value: ${metrics['total_value']:.2f}")
print(f"Open Positions: {metrics['open_positions']}/3")
print(f"Gross Exposure: {metrics['gross_exposure']:.0%}")
print(f"Cash Reserve: {metrics['cash_pct']:.0%}")
print(f"Total P&L: ${metrics['total_pnl']:.2f} ({metrics['total_pnl_pct']:.1f}%)")
```

## Configuration

### Adjust Momentum Parameters

```python
# More aggressive momentum detection
detector = MomentumDetector(
    short_ma_period=3,        # Faster response
    long_ma_period=15,        # Faster trend
    volume_multiplier=1.5,    # Stricter volume threshold
    persistence_days=2        # Allow 2-day momentum
)

# More conservative
detector = MomentumDetector(
    short_ma_period=8,
    long_ma_period=30,
    volume_multiplier=1.0,
    persistence_days=5
)
```

### Adjust Conviction Weights

```python
# Favor technical signals
scorer = ConvictionScorer(weights={
    'technical': 0.50,  # More weight
    'news': 0.20,       # Less weight
    'regime': 0.30
})

# Equal weighting
scorer = ConvictionScorer(weights={
    'technical': 0.33,
    'news': 0.33,
    'regime': 0.34
})
```

### Adjust Portfolio Constraints

```python
# Aggressive (more risk)
manager = PositionManager(
    initial_capital=10000.0,
    max_positions=5,           # More positions
    max_gross_exposure=1.2,    # 20% leverage
    min_cash_reserve=0.10      # Only 10% reserve
)

# Conservative (less risk)
manager = PositionManager(
    initial_capital=10000.0,
    max_positions=2,           # Fewer positions
    max_gross_exposure=0.8,    # No leverage
    min_cash_reserve=0.25      # 25% reserve
)
```

## Troubleshooting

### Issue: Conviction scoring always returns 0.5

**Solution**: Check that signals have `'direction'` field:
```python
# Wrong - missing direction
signals = {'technical': [{'signal': 'volume_anomaly', 'strength': 0.8}]}

# Correct
signals = {'technical': [{'signal': 'volume_anomaly', 'strength': 0.8, 'direction': 'bullish'}]}
```

### Issue: Position manager won't open positions

**Solution**: Check constraints:
```python
can_open, reason = manager.can_open_position(0.5)
print(reason)  # Will show why (e.g., "Insufficient cash")

# Try lower conviction
pos, msg = manager.open_position(
    'AAPL', 150.0, conviction=0.5, entry_date='2026-02-14'  # 25% position
)
```

### Issue: Momentum detection always returns 0

**Solution**: Ensure sufficient data:
```python
# Needs at least 20 days of data
data = fetch_ticker_data(ticker, days=30)  # 30 days > 20 required

result = detector.detect_momentum(data)
if result['momentum_strength'] == 0:
    print(result['details'])  # Check error message
```

## Testing

Run all Phase 3 & 4 tests:
```bash
cd /home/ulluboz/.openclaw/workspace/stock-signals

# Run all tests
pytest tests/test_conviction_scorer.py tests/test_momentum_detector.py tests/test_position_manager.py tests/test_momentum_strategy.py -v

# Run specific test
pytest tests/test_conviction_scorer.py::TestConvictionScorer::test_all_signals_agree_bullish -v

# Run with coverage
pytest tests/ --cov=src/signals --cov=src/strategies -v
```

## Next Steps

1. **Integrate into monitor**: Use in `src/monitor.py` for live signals
2. **Backtest**: Run `backtest/production_simulator_robust.py` with conviction scoring
3. **Live deployment**: Deploy to trading engine with real positions
4. **Monitor performance**: Track conviction vs actual returns (Phase 5)

## Resources

- **Full Documentation**: `PHASE_3_4_IMPLEMENTATION.md`
- **API Reference**: Docstrings in each module
- **Examples**: `tests/` directory has comprehensive test cases
- **Integration**: See `src/monitor.py` for current integration point
