#!/usr/bin/env python3
"""
Quick daily fundamentals update - batches of 20 stocks with progress reporting.
Returns JSON output for cron processing.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fundamentals.fundamentus_scraper import FundamentusScraper
from src.fundamentals.scorer import FundamentalScorer, score_fundamentals


def load_monitored_tickers() -> list:
    """Load list of monitored tickers."""
    config_path = Path(__file__).parent.parent / 'data' / 'validated_tickers.json'
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    tickers = [t.replace('.SA', '') for t in config.get('all_tickers', [])]
    return tickers


def update_fundamentals_quick():
    """Update fundamental data in smaller batches with progress."""
    scraper = FundamentusScraper()
    
    # Check if cache is stale
    if not scraper.is_cache_stale():
        result = {
            'status': 'fresh',
            'message': 'Cache is fresh (less than 24 hours old)',
            'timestamp': datetime.now().isoformat()
        }
        print(json.dumps(result, indent=2))
        return result
    
    # Load tickers
    tickers = load_monitored_tickers()
    
    # Split into smaller batches
    batch_size = 20
    batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]
    
    total_scraped = 0
    failed = []
    
    print(f"Starting update of {len(tickers)} stocks in {len(batches)} batches...", flush=True)
    
    all_data = {}
    
    for i, batch in enumerate(batches, 1):
        print(f"\nBatch {i}/{len(batches)}: {len(batch)} stocks...", flush=True)
        
        for ticker in batch:
            try:
                data = scraper.scrape_ticker(ticker)
                if data:
                    all_data[ticker] = data
                    total_scraped += 1
                    if total_scraped % 5 == 0:
                        print(f"  Progress: {total_scraped}/{len(tickers)}", flush=True)
                else:
                    failed.append(ticker)
            except Exception as e:
                print(f"  Error on {ticker}: {e}", flush=True)
                failed.append(ticker)
    
    # Save to cache
    if all_data:
        scraper.save_cache(all_data)
        
        # Calculate scores
        scorer = FundamentalScorer()
        scores = score_fundamentals(all_data, scorer)
        
        # Save scores
        scores_path = scraper.cache_dir / 'fundamental_scores.json'
        scores_data = {
            'timestamp': datetime.now().isoformat(),
            'total_stocks': len(scores),
            'scores': [
                {
                    'ticker': s.ticker,
                    'composite_score': s.composite_score,
                    'grade': s.grade,
                    'value_score': s.value_score,
                    'quality_score': s.quality_score,
                    'is_value': s.is_value,
                    'is_quality': s.is_quality,
                }
                for s in scores
            ]
        }
        
        with open(scores_path, 'w', encoding='utf-8') as f:
            json.dump(scores_data, f, ensure_ascii=False, indent=2)
        
        # Top stocks for alert
        top_value = [s for s in scores if s.is_value][:5]
        top_quality = [s for s in scores if s.is_quality][:5]
        
        # Helper to get metrics from fundamental data
        def get_metrics(score_obj):
            data = all_data.get(score_obj.ticker)
            if data:
                return {
                    'pe_ratio': data.pe_ratio,
                    'roe': data.roe,
                }
            return {'pe_ratio': None, 'roe': None}
        
        result = {
            'status': 'updated',
            'timestamp': datetime.now().isoformat(),
            'stocks_updated': len(all_data),
            'stocks_failed': len(failed),
            'new_data_available': True,
            'top_value_stocks': [
                {
                    'ticker': s.ticker, 
                    'grade': s.grade, 
                    **get_metrics(s)
                }
                for s in top_value
            ],
            'top_quality_stocks': [
                {
                    'ticker': s.ticker, 
                    'grade': s.grade,
                    **get_metrics(s)
                }
                for s in top_quality
            ],
        }
        
        # Build alert message
        value_lines = []
        for s in top_value:
            m = get_metrics(s)
            if m['pe_ratio'] and m['roe']:
                value_lines.append(f"• {s.ticker} ({s.grade}) - P/E: {m['pe_ratio']:.1f}, ROE: {m['roe']:.1f}%")
            else:
                value_lines.append(f"• {s.ticker} ({s.grade})")
        
        result['alert_message'] = f"📊 Fundamentals updated: {len(all_data)} stocks scraped\n\nTop Value Stocks:\n" + "\n".join(value_lines)
        
        print(f"\n✅ Done: {len(all_data)} scraped, {len(failed)} failed", flush=True)
        print(json.dumps(result, indent=2), flush=True)
        return result
    
    else:
        result = {
            'status': 'failed',
            'message': 'No data scraped successfully',
            'timestamp': datetime.now().isoformat(),
            'new_data_available': False
        }
        print(json.dumps(result, indent=2), flush=True)
        return result


if __name__ == '__main__':
    update_fundamentals_quick()
