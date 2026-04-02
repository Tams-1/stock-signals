# Changelog

All notable documentation and operational changes are summarized here. For code history, use `git log`.

## 2026-04-02

### Documentation

- **README**: Realigned with current operations — `scripts/quick_market_monitor.py` as the default production monitor; **top 50** tickers from `data/top_50_tickers.json`; **3× daily** schedule (09:00, 14:00, 16:00 America/São Paulo) as the documented norm; clarified **two BrAPI clients** (`src/brapi_client.py` for `production_simple` / quick monitor vs `src/data/brapi_client.py` for `production_brapi` and `run_production`); updated universe size to follow `validated_tickers.json` (`total_tickers`, no fixed “214”); split **data flow** into quick monitor vs full runners; softened stale performance numbers; added link to `docs/threshold_optimization.md`.
- **Module docstrings**: `production_simple.py`, `scripts/quick_market_monitor.py`, `src/signals/trend_detector_v2.py`, `src/alerts/alert_generator.py`, `src/brapi_client.py`, `src/data/brapi_client.py`, `src/fundamentals/__init__.py` — aligned descriptions with the above architecture.

### Operations (reference)

- Quick monitor path uses **fundamentals on**, **news off** to protect news API quotas.
- Full IBOV + SMLL list maintained in `data/validated_tickers.json` (count varies with B3 updates).
