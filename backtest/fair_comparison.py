#!/usr/bin/env python3
"""
FAIR COMPARISON: System vs Equal-Weight Portfolio

Compare pure confidence system against simple equal-weight buy&hold
of the SAME 5 tickers (not IBOV)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd

# Same tickers used in backtest
TICKERS = ["VALE3.SA", "ITUB3.SA", "KLBN11.SA", "MTRE3.SA", "ITSA4.SA"]
START = "2025-08-01"
END = "2026-02-14"
CAPITAL = 50000.0

print("="*70)
print("⚖️  COMPARAÇÃO JUSTA: Sistema vs Equal-Weight")
print("="*70)
print(f"\nPeríodo: {START} to {END}")
print(f"Capital: R$ {CAPITAL:,.2f}")
print(f"Tickers: {', '.join([t.replace('.SA', '') for t in TICKERS])}\n")

print("📥 Baixando dados...\n")

# Calculate equal-weight returns
equal_weight_returns = {}
total_ew_return = 0.0

for ticker in TICKERS:
    df = yf.download(ticker, start=START, end=END, progress=False)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if len(df) < 2:
        print(f"⚠️  {ticker}: dados insuficientes")
        continue
    
    start_price = df['Close'].iloc[0]
    end_price = df['Close'].iloc[-1]
    ticker_return = ((end_price - start_price) / start_price) * 100
    
    equal_weight_returns[ticker] = ticker_return
    total_ew_return += ticker_return
    
    print(f"  {ticker:12} R$ {start_price:7.2f} → R$ {end_price:7.2f} = {ticker_return:+6.2f}%")

avg_ew_return = total_ew_return / len(TICKERS)

print("\n" + "="*70)
print("📊 RESULTADOS")
print("="*70)

# System result (from latest backtest)
system_return = 18.51  # From pure confidence backtest

print(f"\n🤖 Sistema (Pure Confidence):")
print(f"   Return: {system_return:+.2f}%")
print(f"   Trades: 13")
print(f"   Approach: Confidence-based entry/exit com position sizing dinâmico")

print(f"\n📊 Equal-Weight Buy & Hold:")
print(f"   Return: {avg_ew_return:+.2f}%")
print(f"   Trades: 0 (buy once, hold)")
print(f"   Approach: R$ 10k por ticker, hold até o final")

print(f"\n⚖️  Comparação:")
diff = system_return - avg_ew_return
diff_pct = (diff / abs(avg_ew_return)) * 100 if avg_ew_return != 0 else 0

if diff > 0:
    print(f"   ✅ Sistema VENCEU por {diff:+.2f}pp ({diff_pct:+.1f}%)")
    print(f"   Alpha gerado: {diff:+.2f}%")
else:
    print(f"   ❌ Buy & Hold VENCEU por {-diff:+.2f}pp ({-diff_pct:+.1f}%)")
    print(f"   Sistema underperformou: {diff:+.2f}%")

print("\n" + "="*70)
print("🎯 ANÁLISE")
print("="*70)

print(f"""
Esta é a comparação JUSTA porque:
1. Mesmos 5 tickers em ambos os casos
2. Mesmo período (6 meses)
3. Mesmo capital inicial (R$ 50k)

Sistema atual ({system_return:+.2f}%) vs Equal-Weight ({avg_ew_return:+.2f}%)

Gap de {abs(diff):.2f}pp pode ser explicado por:
- Timing de entrada/saída
- Position sizing dinâmico
- Exits prematuros em algumas posições
- Trade execution costs (não incluídos em simulação)

Para bater equal-weight, sistema precisa:
- Melhorar timing de exit (trailing stops?)
- Otimizar position sizing (Kelly Criterion?)
- Reduzir trades desnecessários
""")

print("="*70)
print("💡 PRÓXIMOS PASSOS")
print("="*70)
print("""
1. Implement trailing stops (ride trends longer)
2. Kelly Criterion for optimal position sizing
3. Test with more tickers (diversification)
4. Add transaction costs to make comparison realistic
5. Walk-forward optimization of parameters
""")
print("="*70)
