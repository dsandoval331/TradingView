# PM+PD V4 Parity Specification V1

**Spec code:** `PMPD_V4_PARITY_SPEC_V1`  
**Baseline:** PM + Previous Day Breakout V4  
**Status:** FROZEN  
**Date:** 2026-08-28

## 1. Purpose

This specification is the implementation contract for the external historical PM+PD engine. Its first responsibility is to reproduce the frozen TradingView V4 signal methodology. Enhanced 1-minute research measurements must remain separate from the V4-compatible parity layer.

## 2. Canonical Time and Sessions

- Timezone: `America/New_York`
- Premarket (PRE): 04:00 through 09:29
- Regular Trading Hours (RTH): 09:30 through 15:59
- After-hours (AH): 16:00 through 19:59
- Frozen signal confirmation timeframe: 5 minutes
- Canonical raw research data: 1 minute
- 5-minute RTH bars align to 09:30–09:34, 09:35–09:39, etc.

## 3. PM/PD Levels

For each eligible trade date:

- `PMH` = maximum premarket high from 04:00–09:29.
- `PML` = minimum premarket low from 04:00–09:29.
- `PDH` = maximum RTH high of the previous valid trading session.
- `PDL` = minimum RTH low of the previous valid trading session.
- Bull final breakout level = `max(PMH, PDH)`.
- Bear final breakout level = `min(PML, PDL)`.

"Previous day" means previous valid trading session, not calendar date minus one.

## 4. Frozen Default Core Filters

- ATR length: 14
- Minimum ATR penetration: ON; minimum 10% ATR
- Directional candle: ON
- Body/range filter: ON; minimum 50%
- Range/ATR filter: OFF; configured threshold 25%
- Strong-close filter: OFF; configured threshold 80%
- Minimum-grade requirement: OFF

## 5. Signal State Machine

A breakout close beyond the applicable final level arms that direction.

1. If all enabled core filters pass on the breakout confirmation candle, signal immediately.
2. If filters do not yet pass, remain armed while subsequent completed 5-minute closes remain beyond the breakout level.
3. A later completed 5-minute candle may confirm the armed signal.
4. If price closes back through the breakout level before confirmation, reset the armed state.
5. After a completed signal, that direction cannot re-arm until a completed close first returns through the breakout level.
6. Signal reference price = confirmed 5-minute signal candle close.
7. Bars-to-confirmation / confirmation speed are measured from the initial arm event.

The Python implementation must reproduce this stateful behavior rather than treating every close beyond the level as an independent signal.

## 6. Strength Score

Maximum score = 100.

| Component | Max points | Full-score reference |
|---|---:|---:|
| Penetration | 40 | 100% ATR |
| Body / Range | 15 | 100% |
| Close Position | 15 | normalized from 50–100% |
| Range / ATR | 25 | 150% ATR |
| Confirmation Speed | 5 | 0 bars |

Confirmation-speed points:

- 0 bars: 5.0
- 1 bar: 4.5
- 2 bars: 3.0
- 3 bars: 1.5
- 4+ bars: 0

## 7. Grade

- A+ >= 97
- A >= 93
- A- >= 90
- B+ >= 87
- B >= 83
- B- >= 80
- C+ >= 77
- C >= 73
- C- >= 70
- Weak < 70

Grade families: `A`, `B`, `C`, `Weak`.

## 8. Frozen V4 Profile Classification

Profile evaluation precedence is mandatory:

1. Explosive
2. Controlled Strong
3. Efficient Moderate
4. Delayed Strong
5. Pretty but Weak
6. Unclassified

Rules:

### Explosive
`((penetration >= 100 AND range >= 100) OR (range >= 200 AND penetration >= 40))`
AND body >= 50
AND close position >= 70
AND confirmation speed = 0–1 bars.

### Controlled Strong
penetration >= 60  
range >= 100  
body >= 60  
close position >= 80  
speed = 0–1 bars.

### Efficient Moderate
penetration >= 40  
range >= 75  
body >= 65  
close position >= 80  
speed = 0–1 bars.

### Delayed Strong
penetration >= 60  
range >= 100  
body >= 65  
close position >= 80  
speed = 2–3 bars.

### Pretty but Weak
body >= 70  
close position >= 80  
speed = 0–1 bars  
AND `(penetration < 40 OR range < 75)`.

Anything else = `Unclassified`.

## 9. Production Grade × Profile Matrix

| Grade family × Profile | Priority | Trade Type | TQS | Confidence |
|---|---|---|---:|---|
| A × Explosive | PRIME | EXPANSION | 42.7 | HIGH |
| B × Explosive | PRIME | EXPANSION | 42.1 | HIGH |
| C × Explosive | PRIME | EXPANSION | 50.2 | MODERATE |
| C × Controlled Strong | PRIME | SCALP | 42.2 | MOD-HIGH |
| B × Controlled Strong | CONDITIONAL | SCALP | 33.4 | HIGH |
| C × Efficient Moderate | CONDITIONAL | SCALP | 36.1 | HIGH |
| Weak × Efficient Moderate | CONDITIONAL | SCALP | 36.7 | HIGH |
| A × Delayed Strong | RESEARCH | EXPANSION | 59.9 | LOW |
| A × Controlled Strong | OBSERVE | SCALP | 31.0 | MODERATE |
| Weak × Pretty but Weak | LOW | OBSERVE | 30.4 | HIGH |

Other combinations follow the frozen V4 fallback priority/trade-type functions. `Unclassified` is OBSERVE. Default production alert threshold = `Conditional+`, therefore PRIME and CONDITIONAL qualify by default.

## 10. V4-Compatible Outcome Layer

Reference = confirmed signal candle close.

Post-signal excursion begins only after the completed signal candle. Movement inside the signal candle is excluded.

Primary benchmark:
- favorable threshold = +0.50%
- adverse threshold = -0.50%

Additional favorable targets:
- +0.25%
- +0.75%
- +1.00%

For bullish signals:
- favorable excursion uses subsequent highs
- adverse excursion uses subsequent lows

For bearish signals, the calculation is mirrored.

V4 parity classifications:
- `FAVORABLE_FIRST`
- `ADVERSE_FIRST`
- `BOTH`
- `NEITHER`

If +0.50% favorable and -0.50% adverse both occur in the same post-signal 5-minute candle, V4 parity result = `BOTH`. `BOTH` is ambiguous and is not a favorable-first win.

Tracking ends at the same RTH session close. No overnight carry.

## 11. MFE / MAE

- MFE = greatest post-signal favorable excursion reached during the same RTH session.
- MAE = greatest post-signal adverse excursion reached during the same RTH session.
- Signal-candle movement is excluded.
- Remaining unresolved observations at session end finalize as `NEITHER`.

## 12. Canonical 1-Minute Enhanced Outcome Layer

The canonical 1-minute stream must not overwrite the V4 parity result.

Store both:
- V4-compatible 5-minute outcome
- canonical 1-minute sequence-resolved outcome

When a V4 `BOTH` candle contains the two thresholds on different 1-minute bars, the 1-minute layer may resolve the order.

Recommended fields include:
- `v4_primary_outcome`
- `canonical_primary_outcome`
- `v4_same_bar_both`
- `canonical_sequence_resolved`
- `fav_050_timestamp`
- `adv_050_timestamp`
- `minutes_to_fav_050`
- `minutes_to_adv_050`

If both thresholds occur inside the same 1-minute bar and no finer data exists, canonical order remains ambiguous.

## 13. Fixed Post-Signal Checkpoints

Capture objective state at:

- +1 minute
- +2 minutes
- +3 minutes
- +5 minutes
- +10 minutes
- +15 minutes
- +30 minutes

Checkpoint measurements should include, where available:
- OHLC
- RTH VWAP
- MFE / MAE through checkpoint
- close vs reference %
- close vs VWAP %
- PM state
- PD state
- final-level retained/lost state
- reclaim state

Warning labels remain derived/versioned research outputs; raw checkpoint measurements are preserved independently.

## 14. Event-Driven Post-Signal Milestones

Favorable milestones:
- +0.10%
- +0.25%
- +0.50%
- +0.75%
- +1.00%

Adverse milestones:
- -0.10%
- -0.25%
- -0.35%
- -0.50%
- -0.75%
- -1.00%

Structural events should support:
- PM level lost/reclaimed
- PD level lost/reclaimed
- final breakout level lost/reclaimed
- both required breakout levels lost
- VWAP lost/reclaimed
- future versioned structural/Fibonacci events

## 15. Parity Principle

`PMPD_V4_PARITY_SPEC_V1` is frozen for implementation and parity testing.

A change to the external engine that changes V4-compatible signal generation, classification, or V4 outcome semantics requires a new parity-spec version. Enhanced research fields may be added without redefining V4 parity so long as the original parity outputs remain intact.

## 16. Implementation Gate

Before the 112-stock bootstrap, the external engine must pass small-sample parity validation against known TradingView V4 examples for:
- levels
- signal timestamp/direction
- reference price
- component values
- score/grade
- profile
- priority/trade type
- V4 primary outcome
- MFE/MAE
