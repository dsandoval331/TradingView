# PMPD V5 9H Batch 1

This batch completes the architecture for the first three 9H foundations:

- **9H-1:** outcome-blind data-quality / observability layer
- **9H-2:** reconciliation of the 205-factor PMPD-RM-1.0 roadmap into V5 dispositions plus 48 V5-native factors
- **9H-3:** frozen individual-factor testing protocol before profitability review

## Quality findings from Alpha 0.2.1

- 28,000 symbol-days total
- 26,682 complete six-level days
- 26,679 primary-inference eligible after severe price-scale guardrail
- 3 severe scale-discontinuity days: NFLX 2025-11-17, NOW 2025-12-18, TQQQ 2025-11-20
- 20 additional price-continuity review days retained for sensitivity analysis
- 6,909 complete days have sparse PM or AH observability (<=5 bars in either session); these remain eligible and are flagged rather than deleted

## Legacy roadmap reconciliation

205 legacy factors are preserved and mapped rather than overwritten:

- 154 map into 9H as carry/reframed individual-factor concepts
- 18 remain frozen V4 benchmark-only concepts for 9N
- 13 interactions defer to 9I
- 6 confirmation/latency architecture concepts defer to 9J
- 14 robustness items are retained as protocol/validation guardrails

A separate V5-native inventory adds 48 event-based factors across data quality, geometry, event structure, failure/reclaim, and timing/velocity.
