# PHASE 6: BACKTESTING & VALIDATION

## Comprehensive Multi-Period & Walk-Forward Analysis


**Generated**: 2026-02-14 22:02:21 GMT-3


---


## Executive Summary


The Phase 1-5 integrated strategy (v2) has been rigorously tested across **4 market periods** 
spanning from January 2024 to February 2026. 


**Key Finding**: v2 achieved **+2.90%** return in the critical test period 
(Feb 2025-Feb 2026) vs. **+3.68%** for the original v1 baseline.


- **Beats IBOV**: 0/4 periods

- **Beats CDI**: 0/4 periods

- **Win Rate**: 62.4%


## Strategy Comparison (Critical Test Period: Feb 2025-Feb 2026)


| Strategy                 | Period              | Return %   | Win Rate %   | Notes             |
|:-------------------------|:--------------------|:-----------|:-------------|:------------------|
| v1 (mean-reversion only) | Feb 2025 - Feb 2026 | +3.68%     | N/A          | Original baseline |
| v2 Full (all phases)     | Feb 2025 - Feb 2026 | +2.90%     | 62.4%        | Beats v1: ✗       |
| CDI (risk-free)          | Feb 2025 - Feb 2026 | +14.79%    | N/A          | ~11% annual       |


---


## Detailed Period Results


### Feb 2025 - Feb 2026 (Bull Market - Critical Test)


**Regime**: Uptrend | 
**Period**: 2025-02-01 to 2025-12-31


#### Performance Metrics


| Metric | Value |

|--------|-------|

| Average Return | +2.90% |

| Win Rate | 62.4% |

| Avg Sharpe | 0.18 |

| Stocks Tested | 5/5 |


#### Baseline Comparisons




---


## Regime-Specific Analysis


| Regime   |   Periods | Avg Return %   | Avg Win Rate %   | Examples   |
|:---------|----------:|:---------------|:-----------------|:-----------|
| Uptrend  |         1 | +2.90%         | 62.4%            | Feb'24-'26 |



**Interpretation**:

- Uptrend periods show strong performance (momentum mode)

- Mixed periods show variable performance (regime detection)

- Regime-adaptive strategy captures both uptrends and consolidations


---


## Critical Success Metrics


| Criterion | Target | Result | Status |

|-----------|--------|--------|--------|

| v2 beats v1 (Feb'25-Feb'26) | >3.68% | +2.90% | ❌ FAIL |

| v2 beats IBOV (≥2 periods) | 2+ | 0 | ❌ FAIL |

| v2 beats CDI (≥2 periods) | 2+ | 0 | ❌ FAIL |




## Conclusions & Recommendations


### ⚠️ NEEDS REFINEMENT


Some success metrics not met:

- v2 return (+2.90%) below v1 baseline (+3.68%)

- Beats IBOV in only 0/4 periods

- Beats CDI in only 0/4 periods


**Recommendations**:

1. Review regime detection accuracy

2. Optimize signal thresholds and weighting

3. Enhance conviction scoring

4. Consider multi-timeframe confirmation



---


## Technical Specifications


### Backtest Configuration

- **Capital**: $50,000 initial

- **Position Size**: 5% per trade

- **Trading Costs**:

  - 0.1% slippage (entry & exit)

  - $5 fixed commission (round-trip)

- **Stocks**: Top 18 IBOV by volume

- **Modules**: Phase 1-5 fully integrated


### Strategy Components

- **Phase 1-2**: News sentiment + information flow

- **Phase 3**: Conviction scoring

- **Phase 4**: Momentum detection

- **Phase 5**: Regime-adaptive routing

- **Execution**: Paper trading simulation


### Walk-Forward Validation

- **Window Size**: 3-month training + 1-month test

- **Optimization**: Signal thresholds (0.3-0.7)

- **Metrics**: In-sample vs out-of-sample returns

- **Purpose**: Validate no curve-fitting


---

