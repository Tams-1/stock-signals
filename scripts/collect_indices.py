#!/usr/bin/env python3
"""
Collect complete ticker lists for Brazilian indices
IBOV, SMLL, IDIV, IFNC, UTIL, etc.
"""

import yfinance as yf
import pandas as pd
import json
from typing import List, Dict


def get_ibov_constituents() -> List[str]:
    """
    Get IBOV constituents
    Source: Wikipedia or B3 website
    """
    # Full IBOV list (87 stocks as of 2024)
    # Source: https://en.wikipedia.org/wiki/Bovespa_Index
    tickers = [
        # Top 20 by weight
        "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA",
        "ABEV3.SA", "B3SA3.SA", "SUZB3.SA", "RENT3.SA", "WEGE3.SA",
        "MGLU3.SA", "PCAR3.SA", "LREN3.SA", "RAIZ4.SA", "GGBR4.SA",
        "ASAI3.SA", "JBSS3.SA", "RDOR3.SA", "HAPV3.SA", "RAIL3.SA",
        
        # Next 20
        "VBBR3.SA", "CSAN3.SA", "EMBR3.SA", "ELET3.SA", "ELET6.SA",
        "CMIG4.SA", "CPFE3.SA", "CPLE6.SA", "EQTL3.SA", "GGBR3.SA",
        "GOAU4.SA", "IGTI11.SA", "ITSA4.SA", "KLBN11.SA", "LWSA3.SA",
        "MRFG3.SA", "MRVE3.SA", "MULT3.SA", "PETZ3.SA", "RADL3.SA",
        
        # Next 20
        "RRRP3.SA", "SANB11.SA", "SBSP3.SA", "SUZANO.SA", "TAEE11.SA",
        "TOTS3.SA", "UGPA3.SA", "USIM5.SA", "VIVT3.SA", "WEGE3.SA",
        "YDUQ3.SA", "AZUL4.SA", "BEEF3.SA", "BRFS3.SA", "BRKM5.SA",
        "CCRO3.SA", "CIEL3.SA", "COGN3.SA", "CPLE6.SA", "CRFB3.SA",
        
        # Next 20
        "CVCB3.SA", "CYRE3.SA", "ECOR3.SA", "EGIE3.SA", "ENBR3.SA",
        "ENEV3.SA", "ENGI11.SA", "EZTC3.SA", "FLRY3.SA", "GOLL4.SA",
        "HYPE3.SA", "IRBR3.SA", "JHSF3.SA", "KLBN11.SA", "LAME4.SA",
        "LIGT3.SA", "LOGG3.SA", "MDIA3.SA", "MTRE3.SA", "NTCO3.SA",
        
        # Final 7
        "POMO4.SA", "POSI3.SA", "PRIO3.SA", "QUAL3.SA", "RECV3.SA",
        "SLCE3.SA", "SOMA3.SA",
    ]
    
    return sorted(list(set(tickers)))


def get_smll_constituents() -> List[str]:
    """
    Get SMLL (Small Caps) constituents
    """
    tickers = [
        "ALPA4.SA", "ALPK3.SA", "AMAR3.SA", "AMBP3.SA", "ANIM3.SA",
        "ARZZ3.SA", "AURE3.SA", "BLAU3.SA", "BMOB3.SA", "BRML3.SA",
        "BSLI4.SA", "CASH3.SA", "CBAV3.SA", "CMIN3.SA", "COCE5.SA",
        "CSMG3.SA", "CURY3.SA", "DEXP3.SA", "DIRR3.SA", "DMMO3.SA",
        "DXCO3.SA", "ESPA3.SA", "EVEN3.SA", "EZTC3.SA", "FESA4.SA",
        "GBIO33.SA", "GMAT3.SA", "GOGL34.SA", "GRND3.SA", "GUAR3.SA",
        "HBOR3.SA", "HETA4.SA", "HGTX3.SA", "HYPE3.SA", "IFIX11.SA",
        "JALL3.SA", "JHSF3.SA", "KEPL3.SA", "LAVV3.SA", "LEVE3.SA",
        "LIGT3.SA", "LJQQ3.SA", "LLIS3.SA", "LOGN3.SA", "LOGG3.SA",
        "LWSA3.SA", "MATD3.SA", "MDIA3.SA", "MEAL3.SA", "MEGA3.SA",
        "MELK3.SA", "MILS3.SA", "MOVI3.SA", "MRVE3.SA", "MTRE3.SA",
        "MULT3.SA", "NINJ3.SA", "NTCO3.SA", "ODPV3.SA", "ONCO3.SA",
        "ORVR3.SA", "PARD3.SA", "PDGR3.SA", "PETZ3.SA", "PGMN3.SA",
        "PLPL3.SA", "PNVL3.SA", "POMO4.SA", "PORT3.SA", "POSI3.SA",
        "PSSA3.SA", "PTBL3.SA", "QUAL3.SA", "RAPT4.SA", "RCSL3.SA",
        "RECV3.SA", "REDE3.SA", "RENT3.SA", "RSID3.SA", "SAPR11.SA",
        "SEQL3.SA", "SHOW3.SA", "SIMH3.SA", "SLCE3.SA", "SMFT3.SA",
        "SMTO3.SA", "SOMA3.SA", "SOND6.SA", "SQIA3.SA", "STBP3.SA",
        "SYNE3.SA", "TECN3.SA", "TEND3.SA", "TFCO4.SA", "TGMA3.SA",
        "TIMS3.SA", "TPIS3.SA", "TRAD3.SA", "TRIS3.SA", "TUPY3.SA",
        "UNIP6.SA", "VAMO3.SA", "VIVA3.SA", "VLID3.SA", "VULC3.SA",
        "WEST3.SA", "WLMM4.SA", "WIZC3.SA", "YDUQ3.SA", "ZAMP3.SA",
    ]
    
    return sorted(list(set(tickers)))


def get_idiv_constituents() -> List[str]:
    """
    Get IDIV (Dividendos) constituents
    High dividend payers
    """
    tickers = [
        "BBSE3.SA", "TAEE11.SA", "TRPL4.SA", "CPLE6.SA", "ITSA4.SA",
        "BBDC4.SA", "ITUB4.SA", "BBAS3.SA", "GGBR4.SA", "VALE3.SA",
        "PETR4.SA", "CMIG4.SA", "ELET6.SA", "CPFE3.SA", "ENBR3.SA",
        "ENGI11.SA", "SAPR11.SA", "CSAN3.SA", "UGPA3.SA", "BEEF3.SA",
        "VIVT3.SA", "SBSP3.SA", "SANB11.SA", "BPAC11.SA", "CYRE3.SA",
    ]
    
    return sorted(list(set(tickers)))


def get_ifnc_constituents() -> List[str]:
    """
    Get IFNC (Financeiro) constituents
    Banks and financial institutions
    """
    tickers = [
        "ITUB4.SA", "BBDC4.SA", "BBAS3.SA", "SANB11.SA", "BPAC11.SA",
        "B3SA3.SA", "BBSE3.SA", "BPAN4.SA", "BMGB4.SA", "PINE4.SA",
        "CIEL3.SA", "PAGS34.SA", "SULA11.SA", "BRSR6.SA", "WIZC3.SA",
        "CXSE3.SA", "STBP3.SA", "CASH3.SA", "BGIP4.SA", "PNVL3.SA",
    ]
    
    return sorted(list(set(tickers)))


def get_util_constituents() -> List[str]:
    """
    Get UTIL (Utilidade Pública) constituents
    Utilities (energy, water, gas)
    """
    tickers = [
        "ELET3.SA", "ELET6.SA", "CMIG4.SA", "CPFE3.SA", "CPLE6.SA",
        "TAEE11.SA", "ENBR3.SA", "ENGI11.SA", "EQTL3.SA", "EGIE3.SA",
        "SAPR11.SA", "SBSP3.SA", "CGAS5.SA", "NEOE3.SA", "TRPL4.SA",
        "ENEV3.SA", "AURE3.SA", "MEGA3.SA", "LIGT3.SA", "AESB3.SA",
    ]
    
    return sorted(list(set(tickers)))


def check_liquidity(ticker: str, min_volume_brl: float = 5_000_000) -> Dict:
    """
    Check if ticker meets minimum liquidity requirements
    
    Args:
        ticker: Stock ticker
        min_volume_brl: Minimum daily volume in BRL (default 5M)
        
    Returns:
        Dict with ticker, avg_volume, avg_volume_brl, meets_requirement
    """
    try:
        data = yf.download(ticker, period="30d", progress=False)
        
        if len(data) == 0:
            return {
                'ticker': ticker,
                'avg_volume': 0,
                'avg_volume_brl': 0,
                'meets_requirement': False,
                'error': 'No data',
            }
        
        # Handle MultiIndex columns (flatten if needed)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] if col[1] == '' else f"{col[0]}_{ticker}" for col in data.columns]
        
        # Calculate average volume in shares
        avg_volume = data['Volume'].mean()
        if hasattr(avg_volume, 'item'):
            avg_volume = avg_volume.item()
        avg_volume = float(avg_volume)
        
        # Calculate average daily volume in BRL
        avg_price = data['Close'].mean()
        if hasattr(avg_price, 'item'):
            avg_price = avg_price.item()
        avg_price = float(avg_price)
        
        avg_volume_brl = avg_volume * avg_price
        
        meets_requirement = avg_volume_brl >= min_volume_brl
        
        return {
            'ticker': ticker,
            'avg_volume': int(avg_volume),
            'avg_volume_brl': float(avg_volume_brl),
            'meets_requirement': meets_requirement,
        }
        
    except Exception as e:
        return {
            'ticker': ticker,
            'avg_volume': 0,
            'avg_volume_brl': 0,
            'meets_requirement': False,
            'error': str(e),
        }


def main():
    """Collect and save all indices"""
    print("📊 Collecting Brazilian Stock Indices\n")
    
    # Collect all indices
    indices = {
        'IBOV': get_ibov_constituents(),
        'SMLL': get_smll_constituents(),
        'IDIV': get_idiv_constituents(),
        'IFNC': get_ifnc_constituents(),
        'UTIL': get_util_constituents(),
    }
    
    # Print summary
    print(f"{'Index':<10} {'Count':<10}")
    print(f"{'-'*20}")
    for index_name, tickers in indices.items():
        print(f"{index_name:<10} {len(tickers):<10}")
    
    # Get all unique tickers
    all_tickers = set()
    for tickers in indices.values():
        all_tickers.update(tickers)
    
    print(f"\nTotal unique tickers: {len(all_tickers)}")
    
    # Check liquidity for all tickers
    print(f"\n🔍 Checking liquidity (min R$5M daily volume)...")
    
    liquidity_results = []
    for i, ticker in enumerate(sorted(all_tickers), 1):
        print(f"  {i}/{len(all_tickers)} {ticker}...", end=" ", flush=True)
        result = check_liquidity(ticker)
        liquidity_results.append(result)
        
        if result['meets_requirement']:
            print(f"✓ R${result['avg_volume_brl']:,.0f}")
        else:
            error = result.get('error', 'Low liquidity')
            print(f"✗ {error}")
    
    # Filter by liquidity
    liquid_tickers = [r['ticker'] for r in liquidity_results if r['meets_requirement']]
    
    print(f"\n📊 Summary:")
    print(f"   Total tickers: {len(all_tickers)}")
    print(f"   Liquid (>R$5M/day): {len(liquid_tickers)} ({len(liquid_tickers)/len(all_tickers)*100:.1f}%)")
    print(f"   Illiquid: {len(all_tickers) - len(liquid_tickers)}")
    
    # Save results
    output = {
        'indices': indices,
        'all_tickers': sorted(list(all_tickers)),
        'liquid_tickers': sorted(liquid_tickers),
        'liquidity_results': sorted(liquidity_results, key=lambda x: x['avg_volume_brl'], reverse=True),
        'generated_at': pd.Timestamp.now().isoformat(),
    }
    
    output_file = "data/brazilian_indices.json"
    import os
    os.makedirs("data", exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Saved to {output_file}")
    
    # Print top 10 most liquid
    print(f"\n🏆 Top 10 Most Liquid Stocks:")
    for i, result in enumerate(liquidity_results[:10], 1):
        print(f"   {i}. {result['ticker']:<12} R${result['avg_volume_brl']:>12,.0f}/day")


if __name__ == "__main__":
    main()
