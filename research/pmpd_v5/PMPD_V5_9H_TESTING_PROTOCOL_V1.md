# PMPD V5 — 9H Individual-Factor Testing Protocol V1

Status: FROZEN BEFORE 9H PROFITABILITY REVIEW  
Protocol ID: `PMPD_V5_9H_FACTOR_PROTOCOL_V1`

## 1. Purpose

9H tests whether individual, pre-existing PM/AH/PD event characteristics predict subsequent price behavior. 9H is not a model-building phase. Interaction mining, composite scoring, alternative entry architecture optimization, and V4-vs-V5 comparison are reserved for later phases.

## 2. Research population

The structural population is the Alpha 0.2.1 Directional Level-Stack Encounter population built from the frozen `PMPD_112_V1` universe and certified 2025 1-minute data.

Bull identity space: PMH / AHH / PDH.  
Bear identity space: PML / AHL / PDL.

V4 signal membership is not required and must not be used to define the V5 research population.

## 3. Primary decision-point unit

For primary 9H inference, use the **first occurrence of each decision type within each parent event**. This prevents repeated DP11/DP12 or repeated transitions within the same event from being treated as independent observations.

Primary decision types:

- DP1 FIRST_CONTACT
- DP2 FIRST_LEVEL_CLEAR
- DP3 SECOND_LEVEL_CLEAR
- DP4 FULL_STACK_FIRST_CLEAR
- DP5 FIRST_COMPLETED_BAR_RETENTION
- DP9 PARTIAL_LOSS
- DP10 FULL_LOSS
- DP11 PARTIAL_RECLAIM
- DP12 FULL_RECLAIM

All-occurrence analyses are secondary and must use event/symbol clustering or be labeled descriptive.

## 4. Reference price and look-ahead rule

Decision-point reference price is the completed 1-minute bar close recorded by Alpha. Outcome evaluation begins **strictly after** the completed decision bar. No high/low from the decision bar may be used to determine post-decision success or failure.

## 5. Frozen primary outcome

Primary outcome is symmetric:

- +0.50% favorable versus -0.50% adverse from decision reference price.
- `FAVORABLE_FIRST` if the favorable threshold is reached first.
- `ADVERSE_FIRST` if the adverse threshold is reached first.
- `AMBIGUOUS_SAME_BAR` if both thresholds are first reached on the same future 1-minute bar.
- `UNRESOLVED` if neither threshold is reached before RTH ends.

Ambiguous and unresolved observations are reported separately and are not silently forced into wins/losses.

Primary favorable-first rate denominator: `FAVORABLE_FIRST + ADVERSE_FIRST` only. Ambiguous/unresolved rates are always shown beside it.

## 6. Secondary outcomes

Without changing the primary benchmark, retain:

- MFE to RTH close
- MAE to RTH close
- time to +0.25%, +0.50%, +0.75%, +1.00%
- time to adverse milestones where available
- unresolved rate
- same-bar ambiguity rate

Secondary outcomes may describe path behavior but cannot replace the frozen +0.50/-0.50 benchmark after seeing results.

## 7. Data-quality eligibility

Quality protocol: `PMPD_V5_9H_QUALITY_V1`.

Raw rows are never deleted from source outputs.

Primary-inference eligibility requires:

1. complete six-level context; and
2. no `SEVERE_DISCONTINUITY` price-scale flag.

Sparse PM/AH observability is **not** a default exclusion. It is retained as a factor/sensitivity stratum.

Severe discontinuity guardrail is outcome-blind and currently isolates three obvious 2025 scale-break symbol-days. Review-tier price-continuity rows remain in primary data but must be included in sensitivity reporting.

## 8. Frozen temporal split

No factor threshold may be selected using validation data.

- **DISCOVERY:** 2025-01-02 through 2025-04-30
- **VALIDATION_A:** 2025-05-01 through 2025-08-29
- **VALIDATION_B:** 2025-09-02 through 2025-12-31

If a market holiday means a boundary date is absent, use the next observed trading date; do not move boundaries based on outcomes.

The later 9M out-of-sample dataset remains separate and untouched by 9H threshold selection.

## 9. Direction handling

Every factor is reported:

- pooled only when directionally normalized and conceptually valid;
- BULL separately;
- BEAR separately.

A pooled effect cannot hide a material Bull/Bear sign reversal.

## 10. Continuous-factor procedure

For continuous factors:

1. Determine quintile edges using DISCOVERY only.
2. Preserve the exact numeric edges.
3. Apply those edges unchanged to VALIDATION_A and VALIDATION_B.
4. Report per-bin N, resolved N, favorable-first rate, ambiguity rate, unresolved rate, symbol count, and date coverage.
5. Report Q5-Q1 risk difference (or directionally appropriate end-bin contrast) and a standardized continuous slope where appropriate.
6. Do not scan dozens of arbitrary thresholds in validation.

If a single operational threshold is later proposed, it must be selected from discovery only and treated as a candidate requiring unchanged validation.

## 11. Categorical-factor procedure

For categorical factors, freeze category definitions before outcome review when possible. Report every materially populated category; do not merge losing categories post hoc merely to improve results.

Rare categories may be combined only for sample-size reasons using an outcome-blind rule documented before the combined result is examined.

## 12. Minimum evidence reporting

All results are displayed, but a bin/category is not eligible for a strong individual-factor claim unless it has at least:

- 200 resolved observations overall,
- 40 distinct symbols,
- 40 distinct trade dates.

Directional claims additionally require at least:

- 100 resolved observations,
- 25 distinct symbols.

These are evidence-quality gates, not optimization parameters.

## 13. Confidence and dependence

Each primary table must include a 95% binomial interval for favorable-first rate. Effect comparisons should additionally use symbol-cluster bootstrap intervals when practical so thousands of observations from a small number of symbols cannot create false precision.

Symbol concentration must be reported for apparent large effects.

## 14. Multiple comparisons

9H contains many candidate factors. Therefore:

- discovery p-values/effect screens are controlled within factor families using Benjamini-Hochberg FDR;
- validation is confirmatory for candidates selected in discovery;
- a factor is not promoted merely because one bin is nominally significant;
- interaction mining is prohibited in 9H and deferred to 9I.

## 15. Evidence classifications

A 9H factor may be classified as:

- `SUPPORTED`: discovery signal survives both validation windows with the same substantive direction and adequate sample coverage.
- `CONDITIONAL`: evidence is direction-, regime-, observability-, or decision-point-dependent and reproducible enough to retain.
- `SUGGESTIVE`: discovery/validation pattern is interesting but uncertainty remains too high for promotion.
- `NO_EVIDENCE`: no stable predictive relationship under the frozen protocol.
- `UNSTABLE`: effect materially changes sign or structure across validation windows.
- `INSUFFICIENT_N`: sample gate not met.

No factor becomes a production rule during 9H.

## 16. Initial 9H research order

1. Data quality / observability sensitivity
2. Three-level geometry and level identity
3. Current structural progression / traded-vs-retained state
4. Timing and attempts
5. Failure/loss/reclaim states
6. Legacy context families reframed to V5 decision points

V4 Grade/Profile/PRIME/CONDITIONAL/EXPANSION/SCALP remain frozen benchmark constructs and are not allowed to seed V5 discovery scoring.

## 17. Reproducibility

Every factor run must record:

- protocol ID
- code version
- dataset/universe version
- quality version
- factor code
- decision type
- direction
- discovery cutpoints/categories
- run fingerprint
- result counts
- exclusions/flags

Any methodology change after outcome review requires a new protocol version and a written project decision.
