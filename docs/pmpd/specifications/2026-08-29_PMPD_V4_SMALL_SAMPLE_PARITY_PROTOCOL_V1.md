# PM + Previous Day Breakout
## V4 Small-Sample Parity Validation Protocol V1

**Protocol code:** `PMPD_V4_PARITY_PROTOCOL_V1`  
**Project phase:** `8H-7 — Small-Sample Parity Validation`  
**Step:** `8H-7A-1 — Materialize and Freeze the Parity Protocol`  
**Generated:** 2026-08-29  
**Status:** DRAFT_FOR_FREEZE  
**Applies to model:** `PMPD V4`  
**Authoritative strategy specification:** `2026-08-28_PMPD_V4_PARITY_SPEC_V1.md`  
**Authoritative universe:** `PMPD_112_V1`  
**Certified historical dataset:** `PMPD_112_V1 × 2025 / MARKET_CACHE_V1`

---

# 1. PURPOSE

This protocol defines how Pine/TradingView and the Python historical research implementation will be compared before PMPD historical research is allowed to scale beyond a small auditable reference sample.

The objective is **implementation parity**, not optimization.

This phase must answer:

> Does the Python implementation reproduce the frozen PMPD V4 definition and the frozen Pine V4 behavior closely enough to trust larger historical runs?

No research factor, threshold, signal rule, score weight, target, stop, confirmation rule, or sample member may be changed merely to improve parity or historical performance after results are observed.

---

# 2. AUTHORITATIVE HIERARCHY

When resolving a discrepancy, authority is evaluated in this order:

1. **Frozen V4 parity specification**
   - `docs/pmpd/specifications/2026-08-28_PMPD_V4_PARITY_SPEC_V1.md`
2. **Frozen PMPD V4 Pine implementation**
3. **Pine-generated reference evidence**
4. **Python implementation**

Python output is never considered authoritative merely because it appears reasonable.

If the written V4 specification and Pine implementation disagree, the issue is not silently resolved. It must be classified as either `PINE_IMPLEMENTATION_ISSUE` or `SPECIFICATION_AMBIGUITY` and formally resolved before that case is counted as parity-valid.

---

# 3. VALIDATION SAMPLE

The small-sample parity population must be frozen **before** broad Python results are reviewed.

Target sample size:

- **20–30 reference cases**
- multiple symbols
- multiple dates
- bullish and bearish events
- favorable-first and adverse-first outcomes
- strong and weaker qualifying V4 signals
- early and later-session breakouts
- close and widely separated PM/PD levels
- no-signal/control cases
- at least one known source-sparse case
- edge cases where available

The sample is not intended to estimate win rate. It exists only to validate implementation parity.

Once frozen, a sample member may not be removed because it causes a mismatch.

---

# 4. REQUIRED REFERENCE EVIDENCE

Each parity case must have enough Pine/TradingView evidence to determine the expected values.

At minimum, each case should identify:

- symbol
- trade date
- chart/confirmation timeframe
- expected direction or no-signal result
- PMH
- PML
- PDH
- PDL
- expected confirmation/signal bar timestamp
- V4 qualification status
- reference price when a signal exists

Where available, also capture penetration, ATR, directional candle result, body/range value, range-vs-ATR value, strong-close value, strength components, total score, grade, and outcome measurements.

Evidence may come from Pine-exported rows, Pine tables/labels, deterministic screenshots, or another frozen machine-readable Pine reference artifact.

---

# 5. PARITY LAYERS

Parity is evaluated in four layers.

## 5.1 Market / Session Layer

Compare symbol, trade date, New York session alignment, confirmation timeframe, PMH, PML, PDH, PDL, and level timestamps where applicable.

## 5.2 Signal Layer

Compare bullish/bearish/no-signal, breakout qualification, confirmation bar timestamp, penetration rule/result, directional candle condition, body/range condition, range-vs-ATR condition, strong-close condition, and every enabled/disabled frozen V4 confirmation rule.

## 5.3 Scoring Layer

Compare where exposed by frozen V4: penetration component, body component, close component, range component, speed component, total strength score, and final grade.

## 5.4 Outcome Layer

Compare reference price, +0.25% favorable-first, **+0.50% favorable before -0.50% adverse — PRIMARY**, +0.75% favorable-first, +1.00% favorable hit, adverse threshold result, MFE, MAE, favorable/adverse first-reached classification, unresolved status, and same-bar ambiguity/tie behavior.

---

# 6. EXACT PARITY FIELDS

The following are categorical/discrete and must match exactly:

- symbol
- trade date
- direction
- signal existence
- confirmation/signal bar timestamp
- filter pass/fail values
- enabled/disabled rule interpretation
- first-reached classification
- unresolved classification
- final strength grade
- same-bar classification

A mismatch in one of these fields is material unless it is explicitly explained and classified under the discrepancy taxonomy.

---

# 7. NUMERIC PARITY RULES

Numeric tolerances must be defined before individual discrepancies are reviewed.

## 7.1 Price / Level Values

For PMH, PML, PDH, PDL, reference price, and OHLC-derived comparison values:

- default absolute tolerance: **$0.01**
- if an instrument has a different minimum tick, use the instrument's actual minimum tick instead
- the tolerance is for numeric comparison only

If two numerically close values cause different V4 filter or signal decisions, the discrete decision mismatch remains material and cannot be waived merely because the prices were within tolerance.

## 7.2 Percentage / Ratio / ATR-Derived Values

For percentage, ratio, normalized penetration, and ATR-derived comparison values:

- absolute tolerance: **0.0001 in decimal units**
- equivalent to **0.01 percentage point** when expressed as a percentage

## 7.3 Strength Scores

- component score tolerance: **0.0001**
- total score tolerance: **0.0001**
- final grade must match exactly

## 7.4 MFE / MAE

- price-based MFE/MAE uses the price tolerance above
- percentage-based MFE/MAE uses the percentage tolerance above

No tolerance can be used to convert a different favorable/adverse-first classification into a parity match.

---

# 8. TIMESTAMP PARITY

Signal timestamps must match the Pine confirmation bar exactly at the frozen confirmation timeframe.

Session/date interpretation is based on **America/New_York**.

A timestamp offset caused by UTC vs ET representation is not a mismatch if both represent the exact same instant.

A one-bar shift is a material mismatch.

---

# 9. SOURCE-DATA DIFFERENCES

The certified Python research dataset is sourced from Massive and has known source-level sparse one-minute aggregate behavior for some symbols.

Known reviewed 2025 sparse-source symbols:

- MNDY
- NOW
- KLAC
- BKNG
- BLK
- AXON
- URI
- REGN

A disagreement attributable to verified source-data availability may be classified as `SOURCE_DATA_LIMITATION`.

This classification requires evidence and must not be used as a generic excuse for unexplained mismatches.

Source-data limitations remain in the parity report and are not deleted.

---

# 10. DISCREPANCY TAXONOMY

Allowed codes:

- `PARITY_MATCH`
- `LEVEL_MISMATCH`
- `SESSION_ALIGNMENT_MISMATCH`
- `TIMESTAMP_MISMATCH`
- `SIGNAL_DIRECTION_MISMATCH`
- `SIGNAL_EXISTENCE_MISMATCH`
- `FILTER_MISMATCH`
- `ATR_MISMATCH`
- `STRENGTH_SCORE_MISMATCH`
- `GRADE_MISMATCH`
- `REFERENCE_PRICE_MISMATCH`
- `OUTCOME_MISMATCH`
- `SAME_BAR_AMBIGUITY`
- `SOURCE_DATA_LIMITATION`
- `PINE_IMPLEMENTATION_ISSUE`
- `SPECIFICATION_AMBIGUITY`
- `PYTHON_IMPLEMENTATION_DEFECT`
- `UNRESOLVED`

Free-text notes may supplement but may not replace a reason code.

---

# 11. PASS / FAIL STANDARD

The small-sample parity phase is not passed based on a generic accuracy percentage alone.

Required standard:

> **100% explainable parity across the frozen sample for material V4 behavior.**

This means:

- no unexplained signal-existence mismatches
- no unexplained direction mismatches
- no unexplained confirmation-bar mismatches
- no unexplained V4 qualification/filter mismatches
- no unexplained primary ±0.50% outcome mismatches

Documented and evidenced source-data limitations may remain as explained exceptions.

A mismatch classified `PYTHON_IMPLEMENTATION_DEFECT` must be fixed and rerun.

A case classified `UNRESOLVED` prevents parity certification.

---

# 12. SAME-BAR / AMBIGUITY POLICY

If favorable and adverse thresholds can both be reached within the same one-minute bar and order cannot be known from available data:

- do not infer intrabar order
- classify according to the frozen V4 parity specification
- retain an explicit same-bar/ambiguity marker
- do not convert the case into a favorable or adverse result using hindsight

Any Pine/Python difference in this behavior is material until explained.

---

# 13. DISCREPANCY RESOLUTION RULES

Allowed during 8H-7:

- fix Python when it demonstrably violates frozen V4
- document a Pine defect
- resolve a true specification ambiguity through a formal decision
- rerun affected parity cases after a documented implementation correction

Not allowed:

- change V4 thresholds after seeing Python results
- alter weights or filters to improve parity
- remove mismatch cases from the sample
- replace difficult cases with easier cases
- change targets/stops to improve outcomes
- begin research-factor optimization
- use historical performance to decide how parity should work

A change to the authoritative V4 strategy definition requires a new version and cannot be silently absorbed into this protocol.

---

# 14. CASE-LEVEL OUTPUT SCHEMA

Each case should eventually record at least:

- parity_case_id
- sample_version
- symbol
- trade_date
- direction_expected
- direction_python
- pine_signal_exists
- python_signal_exists
- pine_signal_timestamp
- python_signal_timestamp
- pine_pmh / python_pmh
- pine_pml / python_pml
- pine_pdh / python_pdh
- pine_pdl / python_pdl
- Pine/Python filter values
- Pine/Python strength values where applicable
- pine_reference_price / python_reference_price
- pine_primary_outcome / python_primary_outcome
- numerical deltas
- discrepancy_code
- discrepancy_notes
- parity_status
- evidence_reference

---

# 15. SAMPLE-LEVEL OUTPUT

The final small-sample certification report must include:

- sample version
- protocol version
- V4 parity-spec SHA-256
- protocol SHA-256
- Python code/Git commit
- dataset/universe/cache versions
- total cases
- exact matches
- explained exceptions
- Python defects discovered
- specification ambiguities
- unresolved cases
- parity certification result

---

# 16. EXIT CRITERIA FOR 8H-7

8H-7 can be certified only when:

1. this protocol is frozen and hashed;
2. the reference sample is frozen before broad Python comparison;
3. required Pine evidence exists for every reference case;
4. every case has been compared field-by-field;
5. every mismatch has a discrepancy classification;
6. all Python implementation defects affecting parity are resolved and rerun;
7. no `UNRESOLVED` material mismatch remains;
8. the final result satisfies 100% explainable material parity;
9. the certification is stored in project governance/provenance.

Only then may full-universe PMPD historical research be unlocked.

---

# 17. CURRENT NEXT STEP

After this protocol is frozen:

**8H-7B — Define and Freeze the Small-Sample Reference Population**

No broad Python PMPD signal run should be used for strategy conclusions before 8H-7 parity certification passes.
