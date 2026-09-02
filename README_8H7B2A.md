# 8H-7B-2A — Temporary Pine V4 Parity Classification Capture

This is an **additive patch**, not a replacement PMPD indicator.

It is designed for the current frozen V4 validation build
`PM_Previous_Day_Breakout_Monitor_V3_4A6_V4_Grade_Profile_TQS_Capture.pine`.

The existing V4 build already exposes the state-machine alerts, confirmation
time, PM/PD levels, ATR-normalized penetration, component scores, grade, and
debug values needed for reference capture. The patch reads those existing
values; it does not redefine the frozen signal logic.

## Why a patch instead of a rewritten indicator?

Parity truth must come from the same frozen Pine state machine we are validating.
Duplicating V4 logic into a separate classifier would create a second
implementation and weaken the reference truth.

## Installation

1. Open the frozen V4 Pine source.
2. Locate the end of the existing:
   `ARM -> CONFIRM -> SCORE -> ALERT`
   state-machine section.
3. Insert the entire contents of:
   `PMPD_8H7B2A_PARITY_CLASSIFICATION_PATCH.pine`
   immediately **after the state machine** and **before** the existing
   historical signal-capture/finalization sections.
4. Save as a new temporary research copy. Do not overwrite the frozen source.
   Suggested name:
   `PM_PD_Breakout_V4_8H7_Parity_Capture`
5. Compile before collecting any evidence.

## Use

For each row in:
`docs/pmpd/parity/PMPD_V4_PARITY_SAMPLE_CANDIDATES_V1.csv`

- load the candidate symbol
- set `Candidate ID`
- set `Candidate Trade Date`
- enable `Enable Parity Candidate Capture`
- keep the frozen V4 signal settings unchanged
- capture a screenshot showing both parity tables

The summary panel records:
- candidate id
- target date
- PMH/PDH/PML/PDL
- signal count
- direction
- signal timestamp
- reference price
- grade
- proposed/frozen V4 profile
- V4-compatible ±0.50% primary outcome
- MFE / MAE

The detail panel records the exact components and filter results for a selected
signal.

## No-signal controls

If the candidate date is loaded and V4 emits no signal, the panel shows:
`NO_SIGNAL`.

`DATE_NOT_LOADED` is **not** a no-signal result. It means TradingView did not
load the selected historical date and the case cannot be classified from that
chart session.

## Important TradingView bar-history rule

Do not classify `DATE_NOT_LOADED` as `NO_SIGNAL`. If your plan's chart-history
limit prevents a 2025 candidate date from loading, stop and report the candidate
IDs that show `DATE_NOT_LOADED`. We will handle accessibility systematically
before freezing the final 24-case sample.

## Outcome semantics

The patch:
- uses the frozen 5-minute confirmation stream
- sets reference = signal candle close
- excludes signal-candle movement
- tracks only subsequent 5-minute bars on the same target session
- uses symmetric +0.50% favorable / -0.50% adverse
- returns FAVORABLE_FIRST, ADVERSE_FIRST, BOTH, or NEITHER

This matches `PMPD_V4_PARITY_SPEC_V1` outcome semantics.

## Scope

This patch is temporary evidence tooling for 8H-7. It must not become a new
production PMPD model version.
