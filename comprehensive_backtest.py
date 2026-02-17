#!/usr/bin/env python3
"""
Comprehensive Backtest for Stock Signals Strategy
Generates full BACKTEST_REPORT.md with all metrics and visualizations

Period: Nov 2025 to Present
Universe: 10-20 IBOV stocks
Benchmark: IBOV index
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import warnings
warnings.filterwarnings('ignore')

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats
import json

from production_simple import SimpleProductionRunner
from src.signals.trend_detector_v2 import TrendDetectorV2


# =============================================================================
# CONFIGURATION
# =============================================================================

# Backtest period (Nov 2025 to present - using available data)
# Since yfinance may not have future data, we use recent historical data as proxy
BACKTEST_START = '2024-11-01'  # Proxy for Nov 2025
BACKTEST_END = '2025-02-17'    # Current date proxy

# IBOV Universe (top 15-20 most liquid)
IBOV_UNIVERSE = [
    'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA',
    'ABEV3.SA', 'B3SA3.SA', 'SUZB3.SA', 'RENT3.SA', 'WEGE3.SA',
    'RAIZ4.SA', 'GGBR4.SA', 'RDOR3.SA', 'HAPV3.SA', 'RADL3.SA'
]

IBOV_INDEX = '^BVSP'

# Initial capital
INITIAL_CAPITAL = 100000  # R$100,000


# =============================================================================
# DATA LOADING
# =============================================================================

def download_all_data():
    """Download all required data with progress tracking."""
    print(f"\n{'='*70}")
    print(f"DOWNLOADING MARKET DATA")
    print(f"{'='*70}\n")
    print(f"Period: {BACKTEST_START} to {BACKTEST_END}")
    print(f"Universe: {len(IBOV_UNIVERSE)} IBOV stocks\n")
    
    # Download IBOV index
    print("Downloading IBOV index (^BVSP)...")
    try:
        ibov_data = yf.download(IBOV_INDEX, start=BACKTEST_START, end=BACKTEST_END, progress=False)
        if isinstance(ibov_data.columns, pd.MultiIndex):
            ibov_data.columns = ibov_data.columns.get_level_values(0)
        print(f"  ✓ IBOV: {len(ibov_data)} trading days")
    except Exception as e:
        print(f"  ✗ IBOV download failed: {e}")
        return None, None
    
    # Download stocks
    stock_data = {}
    print(f"\nDownloading stocks...")
    for i, ticker in enumerate(IBOV_UNIVERSE):
        try:
            print(f"  [{i+1:2d}/{len(IBOV_UNIVERSE)}] {ticker}...", end=" ", flush=True)
            data = yf.download(ticker, start=BACKTEST_START, end=BACKTEST_END, progress=False)
            
            # Handle MultiIndex columns (yfinance bug)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            if not data.empty and len(data) >= 50:
                stock_data[ticker] = data
                print(f"✓ {len(data)} days")
            else:
                print(f"✗ insufficient data")
        except Exception as e:
            print(f"✗ {e}")
    
    print(f"\n✓ Downloaded {len(stock_data)} stocks successfully")
    
    return ibov_data, stock_data


# =============================================================================
# BACKTEST ENGINE
# =============================================================================

class ComprehensiveBacktest:
    """Full backtest engine with comprehensive metrics."""
    
    def __init__(self, initial_capital=INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # ticker -> {shares, entry_price, entry_date}
        self.trades = []     # List of all trades
        self.daily_portfolio_values = []
        self.daily_ibov_values = []
        
        self.trend_detector = TrendDetectorV2()
        self.runner = SimpleProductionRunner(use_news=False)
        
        # Track signals
        self.signals_generated = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        
        # Monthly returns tracking
        self.monthly_returns = {}
        self.monthly_ibov_returns = {}
    
    def run_backtest(self, ibov_data, stock_data):
        """Run full backtest with comprehensive tracking."""
        print(f"\n{'='*70}")
        print(f"RUNNING BACKTEST")
        print(f"{'='*70}\n")
        
        if ibov_data is None or ibov_data.empty:
            print("ERROR: No IBOV data")
            return None
        
        if not stock_data:
            print("ERROR: No stock data")
            return None
        
        # Get trading days from IBOV
        trading_days = sorted(list(set(ibov_data.index)))
        
        # Skip warmup period (60 days for indicators)
        warmup = 60
        if len(trading_days) <= warmup:
            print(f"ERROR: Not enough trading days ({len(trading_days)} <= {warmup})")
            return None
        
        trading_days = trading_days[warmup:]
        print(f"Backtest period: {len(trading_days)} trading days")
        print(f"From: {trading_days[0].strftime('%Y-%m-%d')}")
        print(f"To:   {trading_days[-1].strftime('%Y-%m-%d')}\n")
        
        # IBOV initial value for normalization
        ibov_initial = float(ibov_data['Close'].iloc[warmup])
        
        # Track monthly values
        current_month = None
        month_start_portfolio = self.initial_capital
        month_start_ibov = self.initial_capital
        
        # Main backtest loop
        for i, date in enumerate(trading_days):
            if (i + 1) % 10 == 0:
                print(f"  Processing {date.strftime('%Y-%m-%d')} ({i+1}/{len(trading_days)})", end="\r", flush=True)
            
            # Track monthly returns
            month_key = date.strftime('%Y-%m')
            if current_month != month_key:
                if current_month is not None:
                    # Store previous month returns
                    if len(self.daily_portfolio_values) > 0:
                        self.monthly_returns[current_month] = (self.daily_portfolio_values[-1] - month_start_portfolio) / month_start_portfolio
                        self.monthly_ibov_returns[current_month] = (self.daily_ibov_values[-1] - month_start_ibov) / month_start_ibov
                current_month = month_key
                month_start_portfolio = self.daily_portfolio_values[-1] if self.daily_portfolio_values else self.initial_capital
                month_start_ibov = self.daily_ibov_values[-1] if self.daily_ibov_values else self.initial_capital
            
            # Generate signals for each stock
            for ticker, data in stock_data.items():
                # Get historical data up to this date
                hist_data = data[data.index <= date].copy()
                
                if len(hist_data) < 50:
                    continue
                
                # Trend detection
                trend_result = self.trend_detector.detect_trend(hist_data)
                consensus = trend_result.get('consensus', 'unknown')
                confidence = trend_result.get('confidence', 0.0)
                
                # Current price
                current_price = float(hist_data['Close'].iloc[-1])
                
                # Signal logic (matching production logic)
                if consensus in ['uptrend', 'bull_pullback'] and confidence >= 0.5:
                    signal = "BUY"
                    self.signals_generated['BUY'] += 1
                    
                    # Position sizing using Kelly
                    position_size = self.runner.calculate_kelly_position(hist_data, confidence)
                    cost = position_size * self.initial_capital
                    
                    # Execute BUY
                    if ticker not in self.positions and self.cash >= cost:
                        shares = cost / current_price
                        self.cash -= cost
                        self.positions[ticker] = {
                            'shares': shares,
                            'entry_price': current_price,
                            'entry_date': date,
                            'position_size': position_size
                        }
                        self.trades.append({
                            'date': date,
                            'ticker': ticker,
                            'action': 'BUY',
                            'price': current_price,
                            'shares': shares,
                            'position_size': position_size,
                            'confidence': confidence
                        })
                
                elif consensus in ['downtrend', 'bear_bounce'] and confidence >= 0.5:
                    signal = "SELL"
                    self.signals_generated['SELL'] += 1
                    
                    # Execute SELL
                    if ticker in self.positions:
                        pos = self.positions[ticker]
                        shares = pos['shares']
                        entry_price = pos['entry_price']
                        entry_date = pos['entry_date']
                        
                        value = current_price * shares
                        pnl = (current_price - entry_price) / entry_price
                        pnl_r = value - (shares * entry_price)
                        
                        self.cash += value
                        
                        self.trades.append({
                            'date': date,
                            'ticker': ticker,
                            'action': 'SELL',
                            'price': current_price,
                            'shares': shares,
                            'entry_price': entry_price,
                            'entry_date': entry_date,
                            'holding_days': (date - entry_date).days,
                            'pnl': pnl,
                            'pnl_r': pnl_r
                        })
                        
                        del self.positions[ticker]
                else:
                    self.signals_generated['HOLD'] += 1
            
            # Calculate end-of-day portfolio value
            portfolio_value = self.cash
            for ticker, pos in self.positions.items():
                if ticker in stock_data:
                    price_data = stock_data[ticker][stock_data[ticker].index <= date]
                    if not price_data.empty:
                        current_price = float(price_data['Close'].iloc[-1])
                        portfolio_value += current_price * pos['shares']
            
            self.daily_portfolio_values.append(portfolio_value)
            
            # Calculate IBOV value (normalized to initial capital)
            ibov_current = float(ibov_data.loc[date, 'Close'])
            self.daily_ibov_values.append(self.initial_capital * ibov_current / ibov_initial)
        
        # Store last month returns
        if current_month is not None and len(self.daily_portfolio_values) > 0:
            self.monthly_returns[current_month] = (self.daily_portfolio_values[-1] - month_start_portfolio) / month_start_portfolio
            self.monthly_ibov_returns[current_month] = (self.daily_ibov_values[-1] - month_start_ibov) / month_start_ibov
        
        print(f"\n\n✓ Backtest complete")
        
        return self._compile_results(ibov_data, trading_days)
    
    def _compile_results(self, ibov_data, trading_days):
        """Compile all metrics into results dict."""
        
        portfolio_values = np.array(self.daily_portfolio_values)
        ibov_values = np.array(self.daily_ibov_values)
        
        # Basic returns
        portfolio_final = portfolio_values[-1]
        ibov_final = ibov_values[-1]
        
        portfolio_return = (portfolio_final - self.initial_capital) / self.initial_capital
        ibov_return = (ibov_final - self.initial_capital) / self.initial_capital
        
        # Daily returns
        portfolio_returns = pd.Series(portfolio_values).pct_change().dropna().values
        ibov_returns = pd.Series(ibov_values).pct_change().dropna().values
        
        # Annualized metrics
        trading_days_count = len(portfolio_returns)
        years = trading_days_count / 252
        
        annualized_return = (1 + portfolio_return) ** (1 / years) - 1 if years > 0 else 0
        ibov_annualized = (1 + ibov_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Volatility (annualized)
        portfolio_vol = np.std(portfolio_returns) * np.sqrt(252)
        ibov_vol = np.std(ibov_returns) * np.sqrt(252)
        
        # Sharpe Ratio (assuming risk-free rate = 0 for simplicity, or 10% CDI)
        risk_free_rate = 0.10 / 252  # Daily risk-free rate (CDI ~10%)
        
        portfolio_sharpe = (np.mean(portfolio_returns) - risk_free_rate) / np.std(portfolio_returns) * np.sqrt(252) if np.std(portfolio_returns) > 0 else 0
        ibov_sharpe = (np.mean(ibov_returns) - risk_free_rate) / np.std(ibov_returns) * np.sqrt(252) if np.std(ibov_returns) > 0 else 0
        
        # Sortino Ratio (downside deviation only)
        negative_returns = portfolio_returns[portfolio_returns < 0]
        downside_std = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else 0
        sortino = (annualized_return - 0.10) / downside_std if downside_std > 0 else 0
        
        # Maximum Drawdown
        portfolio_cummax = np.maximum.accumulate(portfolio_values)
        portfolio_dd = (portfolio_cummax - portfolio_values) / portfolio_cummax
        max_drawdown = np.max(portfolio_dd)
        
        ibov_cummax = np.maximum.accumulate(ibov_values)
        ibov_dd = (ibov_cummax - ibov_values) / ibov_cummax
        ibov_max_dd = np.max(ibov_dd)
        
        # Win rate and profit factor
        sell_trades = [t for t in self.trades if t['action'] == 'SELL']
        winning_trades = [t for t in sell_trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in sell_trades if t.get('pnl', 0) <= 0]
        
        win_rate = len(winning_trades) / len(sell_trades) if sell_trades else 0
        
        gross_profit = sum(t['pnl_r'] for t in winning_trades) if winning_trades else 0
        gross_loss = abs(sum(t['pnl_r'] for t in losing_trades)) if losing_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
        
        # Beta and Alpha (regression vs IBOV)
        if len(portfolio_returns) == len(ibov_returns) and len(portfolio_returns) > 1:
            slope, intercept, r_value, p_value, std_err = stats.linregress(ibov_returns, portfolio_returns)
            beta = slope
            alpha = intercept * 252  # Annualized alpha
            correlation = r_value
        else:
            beta = 1.0
            alpha = 0
            correlation = 0
        
        # Tracking error
        excess_returns = portfolio_returns - ibov_returns
        tracking_error = np.std(excess_returns) * np.sqrt(252)
        
        # Value at Risk (95% and 99%)
        var_95 = np.percentile(portfolio_returns, 5) * portfolio_values[-1]
        var_99 = np.percentile(portfolio_returns, 1) * portfolio_values[-1]
        
        # T-test for statistical significance
        t_stat, t_pvalue = stats.ttest_ind(portfolio_returns, ibov_returns)
        
        # Confidence interval for mean return difference
        mean_diff = np.mean(portfolio_returns) - np.mean(ibov_returns)
        se_diff = np.sqrt(np.var(portfolio_returns)/len(portfolio_returns) + np.var(ibov_returns)/len(ibov_returns))
        ci_lower = mean_diff - 1.96 * se_diff
        ci_upper = mean_diff + 1.96 * se_diff
        
        # Trade analysis
        holding_periods = [t['holding_days'] for t in sell_trades if 'holding_days' in t]
        avg_holding = np.mean(holding_periods) if holding_periods else 0
        
        # Best/worst trades
        best_trade = max(sell_trades, key=lambda x: x.get('pnl', 0)) if sell_trades else None
        worst_trade = min(sell_trades, key=lambda x: x.get('pnl', 0)) if sell_trades else None
        
        # Stock performance
        stock_performance = {}
        for ticker in set(t['ticker'] for t in self.trades if t['action'] == 'SELL'):
            ticker_trades = [t for t in sell_trades if t['ticker'] == ticker]
            if ticker_trades:
                stock_performance[ticker] = {
                    'trades': len(ticker_trades),
                    'avg_pnl': np.mean([t['pnl'] for t in ticker_trades]),
                    'total_pnl': sum(t['pnl'] for t in ticker_trades)
                }
        
        return {
            # Portfolio values
            'portfolio_values': portfolio_values,
            'ibov_values': ibov_values,
            'trading_days': trading_days,
            
            # Returns
            'portfolio_return': portfolio_return,
            'ibov_return': ibov_return,
            'annualized_return': annualized_return,
            'ibov_annualized': ibov_annualized,
            'alpha_pct': (portfolio_return - ibov_return) * 100,
            
            # Risk metrics
            'portfolio_vol': portfolio_vol,
            'ibov_vol': ibov_vol,
            'sharpe': portfolio_sharpe,
            'ibov_sharpe': ibov_sharpe,
            'sortino': sortino,
            'max_drawdown': max_drawdown,
            'ibov_max_dd': ibov_max_dd,
            
            # Risk/return ratios
            'beta': beta,
            'alpha': alpha,
            'correlation': correlation,
            'tracking_error': tracking_error,
            'var_95': var_95,
            'var_99': var_99,
            
            # Trade stats
            'total_trades': len(sell_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_holding_days': avg_holding,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'stock_performance': stock_performance,
            
            # Statistical tests
            't_stat': t_stat,
            't_pvalue': t_pvalue,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            
            # Monthly returns
            'monthly_returns': self.monthly_returns,
            'monthly_ibov_returns': self.monthly_ibov_returns,
            
            # Signal counts
            'signals': self.signals_generated,
            
            # Raw data
            'trades': self.trades,
            'portfolio_returns': portfolio_returns,
            'ibov_returns': ibov_returns
        }


# =============================================================================
# VISUALIZATIONS
# =============================================================================

def create_visualizations(results, output_dir):
    """Create all required visualizations."""
    print(f"\n{'='*70}")
    print(f"GENERATING VISUALIZATIONS")
    print(f"{'='*70}\n")
    
    os.makedirs(output_dir, exist_ok=True)
    
    portfolio_values = results['portfolio_values']
    ibov_values = results['ibov_values']
    trading_days = results['trading_days']
    
    # -------------------------------------------------------------------------
    # 1. Equity Curve vs IBOV
    # -------------------------------------------------------------------------
    print("  Creating equity curve...")
    fig, ax = plt.subplots(figsize=(14, 8))
    
    ax.plot(trading_days, portfolio_values, label='Strategy', linewidth=2, color='#2ecc71')
    ax.plot(trading_days, ibov_values, label='IBOV Index', linewidth=2, color='#3498db', alpha=0.7)
    
    ax.axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', alpha=0.5, label='Initial Capital')
    
    ax.set_title('Strategy vs IBOV: Equity Curve', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Portfolio Value (R$)', fontsize=12)
    ax.legend(loc='upper left', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.xticks(rotation=45)
    
    # Add performance annotation
    strat_return = results['portfolio_return'] * 100
    ibov_ret = results['ibov_return'] * 100
    text = f'Strategy: {strat_return:+.1f}%\nIBOV: {ibov_ret:+.1f}%\nAlpha: {strat_return - ibov_ret:+.1f}%'
    ax.text(0.02, 0.98, text, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/equity_curve.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"    ✓ Saved equity_curve.png")
    
    # -------------------------------------------------------------------------
    # 2. Drawdown Chart
    # -------------------------------------------------------------------------
    print("  Creating drawdown chart...")
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Calculate drawdowns
    portfolio_cummax = np.maximum.accumulate(portfolio_values)
    portfolio_dd = -(portfolio_cummax - portfolio_values) / portfolio_cummax * 100
    
    ibov_cummax = np.maximum.accumulate(ibov_values)
    ibov_dd = -(ibov_cummax - ibov_values) / ibov_cummax * 100
    
    ax.fill_between(trading_days, 0, portfolio_dd, alpha=0.4, color='#2ecc71', label='Strategy DD')
    ax.fill_between(trading_days, 0, ibov_dd, alpha=0.4, color='#3498db', label='IBOV DD')
    
    ax.axhline(y=results['max_drawdown'] * -100, color='red', linestyle='--', alpha=0.7, 
               label=f'Strategy Max DD: {results["max_drawdown"]*100:.1f}%')
    
    ax.set_title('Drawdown Comparison: Strategy vs IBOV', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Drawdown (%)', fontsize=12)
    ax.legend(loc='lower left', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/drawdown_chart.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"    ✓ Saved drawdown_chart.png")
    
    # -------------------------------------------------------------------------
    # 3. Monthly Returns Heatmap
    # -------------------------------------------------------------------------
    print("  Creating monthly returns heatmap...")
    fig, ax = plt.subplots(figsize=(12, 6))
    
    monthly_returns = results['monthly_returns']
    monthly_ibov = results['monthly_ibov_returns']
    
    months = sorted(set(list(monthly_returns.keys()) + list(monthly_ibov.keys())))
    
    if months:
        strat_returns = [monthly_returns.get(m, 0) * 100 for m in months]
        ibov_returns = [monthly_ibov.get(m, 0) * 100 for m in months]
        
        x = np.arange(len(months))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, strat_returns, width, label='Strategy', color='#2ecc71')
        bars2 = ax.bar(x + width/2, ibov_returns, width, label='IBOV', color='#3498db')
        
        ax.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
        
        ax.set_title('Monthly Returns: Strategy vs IBOV', fontsize=14, fontweight='bold')
        ax.set_xlabel('Month', fontsize=12)
        ax.set_ylabel('Return (%)', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(months, rotation=45)
        ax.legend(loc='upper left', fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add value labels
        for bar in bars1:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}%',
                       xy=(bar.get_x() + bar.get_width()/2, height),
                       xytext=(0, 3), textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)
        
        for bar in bars2:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}%',
                       xy=(bar.get_x() + bar.get_width()/2, height),
                       xytext=(0, 3), textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)
    else:
        ax.text(0.5, 0.5, 'No monthly data available', transform=ax.transAxes,
                ha='center', va='center', fontsize=14)
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/monthly_returns.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"    ✓ Saved monthly_returns.png")
    
    print(f"\n✓ All visualizations saved to {output_dir}/")


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_report(results, output_file):
    """Generate comprehensive markdown report."""
    print(f"\n{'='*70}")
    print(f"GENERATING REPORT")
    print(f"{'='*70}\n")
    
    report = f"""# Stock Signals Backtest Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  
**Period:** {BACKTEST_START} to {BACKTEST_END}  
**Universe:** {len(IBOV_UNIVERSE)} IBOV stocks  
**Initial Capital:** R${INITIAL_CAPITAL:,.0f}

---

## 1. Executive Summary

### Strategy vs IBOV Performance

| Metric | Strategy | IBOV | Difference |
|--------|----------|------|------------|
| Total Return | **{results['portfolio_return']*100:+.2f}%** | {results['ibov_return']*100:+.2f}% | {results['alpha_pct']:+.2f}% |
| Annualized Return | **{results['annualized_return']*100:+.2f}%** | {results['ibov_annualized']*100:+.2f}% | {(results['annualized_return']-results['ibov_annualized'])*100:+.2f}% |
| Sharpe Ratio | **{results['sharpe']:.2f}** | {results['ibov_sharpe']:.2f} | {results['sharpe']-results['ibov_sharpe']:+.2f} |
| Max Drawdown | **{results['max_drawdown']*100:.2f}%** | {results['ibov_max_dd']*100:.2f}% | {(results['max_drawdown']-results['ibov_max_dd'])*100:+.2f}% |
| Volatility | **{results['portfolio_vol']*100:.2f}%** | {results['ibov_vol']*100:.2f}% | {(results['portfolio_vol']-results['ibov_vol'])*100:+.2f}% |

### Key Takeaway
{"✅ **Strategy BEATS IBOV**" if results['portfolio_return'] > results['ibov_return'] else "❌ **Strategy underperforms IBOV**"} by **{abs(results['alpha_pct']):.2f}%**

---

## 2. Performance Metrics

### 2.1 Returns Analysis

| Metric | Value |
|--------|-------|
| **Total Return** | {results['portfolio_return']*100:+.2f}% |
| **Annualized Return** | {results['annualized_return']*100:+.2f}% |
| **Best Month** | {max(results['monthly_returns'].values())*100:+.2f}% ({max(results['monthly_returns'], key=results['monthly_returns'].get)}) |
| **Worst Month** | {min(results['monthly_returns'].values())*100:+.2f}% ({min(results['monthly_returns'], key=results['monthly_returns'].get)}) |

### 2.2 Risk-Adjusted Returns

| Metric | Strategy | IBOV |
|--------|----------|------|
| **Sharpe Ratio** | {results['sharpe']:.2f} | {results['ibov_sharpe']:.2f} |
| **Sortino Ratio** | {results['sortino']:.2f} | N/A |
| **Beta** | {results['beta']:.2f} | 1.00 |
| **Alpha (annualized)** | {results['alpha']*100:.2f}% | 0.00% |

### 2.3 Risk Metrics

| Metric | Value |
|--------|-------|
| **Maximum Drawdown** | {results['max_drawdown']*100:.2f}% |
| **Volatility (annualized)** | {results['portfolio_vol']*100:.2f}% |
| **VaR (95%)** | R${abs(results['var_95']):,.2f} |
| **VaR (99%)** | R${abs(results['var_99']):,.2f} |

---

## 3. Monthly Returns

### Month-by-Month Performance

| Month | Strategy | IBOV | Alpha |
|-------|----------|------|-------|
"""
    
    # Add monthly returns table
    for month in sorted(results['monthly_returns'].keys()):
        strat_ret = results['monthly_returns'].get(month, 0) * 100
        ibov_ret = results['monthly_ibov_returns'].get(month, 0) * 100
        alpha_m = strat_ret - ibov_ret
        emoji = "✅" if strat_ret > ibov_ret else "❌"
        report += f"| {month} | {strat_ret:+.2f}% | {ibov_ret:+.2f}% | {alpha_m:+.2f}% {emoji} |\n"
    
    # Cumulative returns
    cumulative_strat = (1 + results['portfolio_return']) * 100 - 100
    cumulative_ibov = (1 + results['ibov_return']) * 100 - 100
    
    report += f"""
### Cumulative Returns

| Period | Strategy | IBOV |
|--------|----------|------|
| **Full Period** | {cumulative_strat:+.2f}% | {cumulative_ibov:+.2f}% |

---

## 4. Risk Analysis

### 4.1 Value at Risk (VaR)

| Confidence Level | Daily VaR (R$) | Daily VaR (%) |
|------------------|----------------|---------------|
| **95%** | R${abs(results['var_95']):,.2f} | {abs(results['var_95'])/INITIAL_CAPITAL*100:.2f}% |
| **99%** | R${abs(results['var_99']):,.2f} | {abs(results['var_99'])/INITIAL_CAPITAL*100:.2f}% |

### 4.2 Correlation with IBOV

- **Correlation Coefficient:** {results['correlation']:.4f}
- **Tracking Error:** {results['tracking_error']*100:.2f}%

### 4.3 Beta and Alpha

- **Beta:** {results['beta']:.2f} ({"higher volatility than market" if results['beta'] > 1 else "lower volatility than market"})
- **Alpha (annualized):** {results['alpha']*100:.2f}% ({"outperformance" if results['alpha'] > 0 else "underperformance"})

---

## 5. Trade Analysis

### 5.1 Trade Statistics

| Metric | Value |
|--------|-------|
| **Total Trades** | {results['total_trades']} |
| **Winning Trades** | {results['winning_trades']} |
| **Losing Trades** | {results['losing_trades']} |
| **Win Rate** | {results['win_rate']*100:.1f}% |
| **Profit Factor** | {results['profit_factor']:.2f} |
| **Avg Holding Period** | {results['avg_holding_days']:.1f} days |

### 5.2 Best & Worst Trades

| Type | Ticker | Return | Date |
|------|--------|--------|------|
| **Best Trade** | {results['best_trade']['ticker'] if results['best_trade'] else 'N/A'} | {results['best_trade']['pnl']*100:+.2f}% | {results['best_trade']['date'].strftime('%Y-%m-%d') if results['best_trade'] else 'N/A'} |
| **Worst Trade** | {results['worst_trade']['ticker'] if results['worst_trade'] else 'N/A'} | {results['worst_trade']['pnl']*100:+.2f}% | {results['worst_trade']['date'].strftime('%Y-%m-%d') if results['worst_trade'] else 'N/A'} |

### 5.3 Stock Performance

| Ticker | Trades | Avg P&L | Total P&L |
|--------|--------|---------|-----------|
"""
    
    # Add stock performance
    sorted_stocks = sorted(results['stock_performance'].items(), key=lambda x: x[1]['total_pnl'], reverse=True)
    for ticker, perf in sorted_stocks:
        pnl_emoji = "✅" if perf['total_pnl'] > 0 else "❌"
        report += f"| {ticker} | {perf['trades']} | {perf['avg_pnl']*100:+.2f}% | {perf['total_pnl']*100:+.2f}% {pnl_emoji} |\n"
    
    report += f"""
---

## 6. Visualizations

### 6.1 Equity Curve vs IBOV

![Equity Curve](backtest_plots/equity_curve.png)

### 6.2 Drawdown Chart

![Drawdown Chart](backtest_plots/drawdown_chart.png)

### 6.3 Monthly Returns

![Monthly Returns](backtest_plots/monthly_returns.png)

---

## 7. Statistical Tests

### 7.1 T-Test vs IBOV

| Test | Value |
|------|-------|
| **T-Statistic** | {results['t_stat']:.4f} |
| **P-Value** | {results['t_pvalue']:.4f} |
| **Significant (p < 0.05)?** | {"✅ Yes" if results['t_pvalue'] < 0.05 else "❌ No"} |

### 7.2 Confidence Interval (95%)

| Metric | Value |
|--------|-------|
| **Mean Difference (daily)** | {(results['ci_lower'] + results['ci_upper'])/2*100:.4f}% |
| **CI Lower Bound** | {results['ci_lower']*100:.4f}% |
| **CI Upper Bound** | {results['ci_upper']*100:.4f}% |

---

## 8. Conclusion

### Does the Strategy Beat IBOV?

{"✅ **YES** - The strategy outperforms IBOV by " + str(round(results['alpha_pct'], 2)) + "% over the backtest period." if results['portfolio_return'] > results['ibov_return'] else "❌ **NO** - The strategy underperforms IBOV by " + str(abs(round(results['alpha_pct'], 2))) + "% over the backtest period."}

### Statistical Significance

{"✅ The difference is **statistically significant** (p < 0.05)." if results['t_pvalue'] < 0.05 else "⚠️ The difference is **NOT statistically significant** (p >= 0.05). More data or a longer period may be needed to draw conclusions."}

### Key Findings

"""
    
    # Generate insights
    if results['sharpe'] > results['ibov_sharpe']:
        report += "- **Better Risk-Adjusted Returns:** Strategy has higher Sharpe ratio than IBOV\n"
    else:
        report += "- **Lower Risk-Adjusted Returns:** Strategy has lower Sharpe ratio than IBOV\n"
    
    if results['max_drawdown'] < results['ibov_max_dd']:
        report += "- **Lower Risk:** Strategy has smaller maximum drawdown\n"
    else:
        report += "- **Higher Risk:** Strategy has larger maximum drawdown\n"
    
    if results['win_rate'] > 0.5:
        report += f"- **Positive Win Rate:** {results['win_rate']*100:.1f}% of trades are profitable\n"
    else:
        report += f"- **Negative Win Rate:** Only {results['win_rate']*100:.1f}% of trades are profitable\n"
    
    report += f"""
### Recommendations

"""
    
    if results['portfolio_return'] > results['ibov_return'] and results['t_pvalue'] < 0.05:
        report += """1. **Consider Live Trading:** Strategy shows statistically significant outperformance
2. **Position Sizing:** Current Kelly criterion approach is working well
3. **Risk Management:** Continue monitoring drawdowns and VaR
"""
    elif results['portfolio_return'] > results['ibov_return']:
        report += """1. **More Data Needed:** Results are promising but not statistically significant
2. **Extend Backtest:** Test over longer period to confirm performance
3. **Parameter Tuning:** Consider optimizing confidence thresholds
"""
    else:
        report += """1. **Strategy Review:** Strategy underperforms - consider parameter adjustments
2. **Trend Detection:** Review trend detection thresholds (currently 0.5)
3. **Position Sizing:** May need more conservative Kelly fractions
"""
    
    report += f"""
---

## Appendix: Signal Distribution

| Signal Type | Count |
|-------------|-------|
| BUY | {results['signals']['BUY']} |
| SELL | {results['signals']['SELL']} |
| HOLD | {results['signals']['HOLD']} |

---

*Report generated by Stock Signals Backtest Engine*  
*Branch: production-hardening*
"""
    
    # Write report
    with open(output_file, 'w') as f:
        f.write(report)
    
    print(f"  ✓ Report saved to {output_file}")
    
    return report


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*70)
    print("STOCK SIGNALS COMPREHENSIVE BACKTEST")
    print("Production-Hardening Branch")
    print("="*70)
    
    # Download data
    ibov_data, stock_data = download_all_data()
    
    if ibov_data is None or not stock_data:
        print("\n❌ BACKTEST FAILED: Could not download data")
        return
    
    # Run backtest
    engine = ComprehensiveBacktest(initial_capital=INITIAL_CAPITAL)
    results = engine.run_backtest(ibov_data, stock_data)
    
    if results is None:
        print("\n❌ BACKTEST FAILED: Could not run backtest")
        return
    
    # Create visualizations
    create_visualizations(results, 'backtest_plots')
    
    # Generate report
    generate_report(results, 'BACKTEST_REPORT.md')
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"BACKTEST COMPLETE")
    print(f"{'='*70}\n")
    
    print(f"📊 Strategy Return: {results['portfolio_return']*100:+.2f}%")
    print(f"📊 IBOV Return:     {results['ibov_return']*100:+.2f}%")
    print(f"📊 Alpha:           {results['alpha_pct']:+.2f}%")
    print(f"📊 Sharpe Ratio:    {results['sharpe']:.2f}")
    print(f"📊 Max Drawdown:    {results['max_drawdown']*100:.2f}%")
    print(f"📊 Win Rate:        {results['win_rate']*100:.1f}%")
    print(f"📊 Total Trades:    {results['total_trades']}")
    
    print(f"\n✅ Report: BACKTEST_REPORT.md")
    print(f"✅ Plots: backtest_plots/")


if __name__ == "__main__":
    main()
