# Investigation Summary - Performance Gains Explained

**Date**: 2026-02-15 07:30 GMT-3  
**Issue**: Performance jump needs verification and explanation

---

## Key Finding

**Fair Comparison Results**:
- Baseline (simple threshold + rolling 50-day): **+12.73%**
- Conviction scoring (+ rolling 50-day): **+51.09%**
- Conviction scoring (+ cumulative): **+51.09%** (identical!)

**Unexpected Result**: Cumulative vs rolling window makes NO difference (+0.00% impact)

---

## What This Means

### 1. Conviction Scoring Impact: **+38.36%**

The entire performance gain comes from:
- Dynamic position sizing (25%/50%/70% vs fixed 50%)
- Regime tie-breaker logic (trades on neutral + uptrend)
- Better signal integration via ConvictionScorer

### 2. Data Window Impact: **+0.00%** ⚠️ UNEXPECTED

Rolling vs cumulative windows give IDENTICAL results. This suggests:

**Possibility A**: Window implementation bug (most likely)
- The `use_rolling_window` flag might not be working
- Both tests might be using cumulative by mistake
- Need to debug method override

**Possibility B**: Signals are truly window-insensitive (unlikely)
- TrendDetectorV2 gives same signals with 50-day vs 100-day
- Regime changes happen early enough that more data doesn't matter
- Highly unlikely given TrendDetectorV2 needs 50 days for macro

---

## Audit Status

### ✅ Verified Correct

1. **Temporal safety**: No look-ahead bias
2. **Position sizing**: Working as designed (25%/50%/70%)
3. **Exit logic**: Conservative and correct
4. **Cost application**: Consistent (0.25% per trade)

### ⚠️ Needs Investigation

1. **Window implementation**: Why are rolling and cumulative identical?
2. **Large gains**: Why does conviction scoring add +38% vs expected +10-15%?

---

## Possible Explanations for Large Gains

### Theory 1: Asymmetric Position Sizing is Powerful

**Old system**:
- Every trade uses 50% of capital
- Win rate: 57.9%
- Returns: Mix of wins and losses at same size

**New system**:
- High conviction (bullish signals align): 70% position
- Medium conviction (some uncertainty): 50% position
- Low conviction (conflicting signals): 25% position
- Win rate: 40.4% (lower, but...)

**Math**:
If high-conviction trades have higher win rates (say 60%) and low-conviction have lower (say 20%), then:
- Large positions on good setups → Big wins
- Small positions on uncertain setups → Small losses
- Net effect: Asymmetric returns

**Example**:
- 10 high-conviction trades @ 70% × 60% win × +5% avg = +21% portfolio gain
- 20 low-conviction trades @ 25% × 20% win × +3% avg = +3% portfolio gain
- Total: +24% just from position sizing

### Theory 2: Regime Tie-Breaker Captures Bull Market

**During Period 4 (bull market)**:
- Technical signals often conflict (mean reversion vs momentum)
- ConvictionScorer returns "neutral"
- Old behavior: Skip trade
- New behavior: Check regime → uptrend → trade anyway

**Impact**:
- Might capture 30-40% of trading days that old system skipped
- In a bull market, being invested is key
- Tie-breaker keeps capital deployed

### Theory 3: Window Bug is Hiding True Comparison

If both "rolling" and "cumulative" are actually using cumulative:
- The +51.09% includes cumulative window advantage
- True conviction-only impact might be lower (+15-25%)
- Need to fix window bug to get accurate breakdown

---

## Action Items

### Immediate (Before GitHub Push)

1. ⚠️ **Debug window implementation**
   - Add explicit logging to verify window sizes
   - Ensure rolling window actually limits data
   - Re-run fair comparison with verified implementation

2. ⚠️ **Verify position sizing logic**
   - Check if high-conviction trades actually use 70%
   - Verify win rates differ by conviction level
   - Analyze trade-by-trade data

3. ⚠️ **Check for state leakage**
   - Ensure simulator resets between stocks
   - Verify no cached signals
   - Test single stock in isolation

### Before Production

4. **Multi-period validation**
   - Test on Period 1-3 (different market conditions)
   - Check if advantage holds in choppy/bear markets
   - Verify consistency

5. **Out-of-sample testing**
   - Test on 2024 data (before training period)
   - Verify no overfitting
   - Check robustness

---

## Current Recommendation

**DO NOT PUSH** the +51.09% / +48.19% results until:

1. ✅ Window bug is fixed and verified
2. ✅ True conviction-only impact is measured
3. ✅ Trade-level analysis confirms asymmetric returns
4. ✅ Multi-period validation shows consistency

**Expected realistic gains after investigation**:
- Conviction scoring alone: +10-20% (vs baseline)
- With cumulative window: +15-30% (vs baseline)
- Current +38% claim needs verification

---

## Next Steps

1. Fix window implementation bug
2. Re-run fair comparison with verified windows
3. Analyze trade-level data (conviction vs returns)
4. Create detailed breakdown report
5. Only then: push to GitHub with accurate claims

---

**Status**: 🔴 INVESTIGATION IN PROGRESS  
**Recommendation**: HOLD GitHub push until verified  
**ETA**: 1-2 hours for complete verification
