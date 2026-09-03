from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# PATHS
# =============================================================================

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

RESEARCH_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_research_v1"
)

EVENTS_PATH = (
    RESEARCH_ROOT
    / "second1m_alt_entry_events_v1.parquet"
)

OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "ae2_c2_predictors_v1"
)

FEATURE_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_c2_predictor_features_v1.parquet"
)

BUCKET_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_c2_predictor_bucket_summary_v1.csv"
)

TEMPORAL_OUTPUT = (
    OUTPUT_ROOT
    / "ae2_c2_predictor_temporal_summary_v1.csv"
)


# =============================================================================
# HELPERS
# =============================================================================

def safe_pct(numer, denom):
    if denom is None or denom == 0:
        return np.nan
    return 100.0 * numer / denom


def favorable_clv(
    direction: str,
    high: float,
    low: float,
    close: float,
) -> float:

    if high <= low:
        return np.nan

    raw = 100.0 * (close - low) / (high - low)

    if direction == "BULL":
        return raw

    return 100.0 - raw


def favorable_wick(
    direction: str,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> float:

    if high <= low:
        return np.nan

    if direction == "BULL":
        wick = high - max(open_, close)
    else:
        wick = min(open_, close) - low

    return 100.0 * wick / (high - low)


def adverse_wick(
    direction: str,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> float:

    if high <= low:
        return np.nan

    if direction == "BULL":
        wick = min(open_, close) - low
    else:
        wick = high - max(open_, close)

    return 100.0 * wick / (high - low)


def favorable_body_return(
    direction: str,
    open_: float,
    close: float,
) -> float:

    if open_ <= 0:
        return np.nan

    raw = 100.0 * (close / open_ - 1.0)

    return raw if direction == "BULL" else -raw


def body_to_range(
    open_: float,
    high: float,
    low: float,
    close: float,
) -> float:

    if high <= low:
        return np.nan

    return 100.0 * abs(close - open_) / (high - low)


def directional_distance_pct(
    direction: str,
    price: float,
    reference: float,
) -> float:

    if reference <= 0:
        return np.nan

    raw = 100.0 * (price / reference - 1.0)

    return raw if direction == "BULL" else -raw


def bucket_by_quantiles(
    df: pd.DataFrame,
    feature: str,
    q: int = 5,
) -> pd.Series:

    values = df[feature]

    try:
        return pd.qcut(
            values,
            q=q,
            duplicates="drop",
        )
    except ValueError:
        return pd.Series(
            ["UNAVAILABLE"] * len(df),
            index=df.index,
        )


def summarize_target(
    df: pd.DataFrame,
    feature: str,
    bucket_col: str,
) -> pd.DataFrame:

    rows = []

    for (direction, bucket), x in df.groupby(
        ["direction", bucket_col],
        dropna=False,
    ):

        n = len(x)

        confirmed_n = int(
            x["c3_confirmed"].sum()
        )

        confirm_pct = (
            100.0 * confirmed_n / n
            if n
            else np.nan
        )

        favorable_n = int(
            (
                x["outcome"]
                == "FAVORABLE_FIRST"
            ).sum()
        )

        adverse_n = int(
            (
                x["outcome"]
                == "ADVERSE_FIRST"
            ).sum()
        )

        binary_n = favorable_n + adverse_n

        ff_pct = (
            100.0 * favorable_n / binary_n
            if binary_n
            else np.nan
        )

        rows.append(
            {
                "feature": feature,
                "direction": direction,
                "bucket": str(bucket),
                "n": n,
                "c3_confirmed_n": confirmed_n,
                "c3_confirmation_pct": confirm_pct,
                "binary_n": binary_n,
                "favorable_first_pct": ff_pct,
                "avg_feature_value": x[feature].mean(),
                "median_feature_value": x[feature].median(),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# MAIN
# =============================================================================

def main():

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    events = pd.read_parquet(
        EVENTS_PATH
    )

    events["trade_date"] = pd.to_datetime(
        events["trade_date"]
    )

    ae2 = events.loc[
        events["architecture"]
        == "AE2_RECLAIM"
    ].copy()

    ae4 = events.loc[
        events["architecture"]
        == "AE4_RECLAIM_C3"
    ].copy()

    if ae2.empty:
        raise RuntimeError(
            "AE2 population is empty."
        )

    if ae4.empty:
        raise RuntimeError(
            "AE4 population is empty."
        )

    key_cols = [
        "symbol",
        "trade_date",
        "direction",
    ]

    confirmed_keys = (
        ae4[key_cols]
        .drop_duplicates()
        .assign(c3_confirmed=True)
    )

    ae2 = ae2.merge(
        confirmed_keys,
        on=key_cols,
        how="left",
    )

    ae2["c3_confirmed"] = (
        ae2["c3_confirmed"]
        .fillna(False)
        .astype(bool)
    )

    # =========================================================================
    # C2-SAFE FEATURES
    # =========================================================================

    ae2["c1_body_to_range_pct"] = ae2.apply(
        lambda r: body_to_range(
            r["c1_open"],
            r["c1_high"],
            r["c1_low"],
            r["c1_close"],
        ),
        axis=1,
    )

    ae2["c2_body_to_range_pct"] = ae2.apply(
        lambda r: body_to_range(
            r["c2_open"],
            r["c2_high"],
            r["c2_low"],
            r["c2_close"],
        ),
        axis=1,
    )

    ae2["c1_favorable_clv_pct"] = ae2.apply(
        lambda r: favorable_clv(
            r["direction"],
            r["c1_high"],
            r["c1_low"],
            r["c1_close"],
        ),
        axis=1,
    )

    ae2["c2_favorable_clv_pct"] = ae2.apply(
        lambda r: favorable_clv(
            r["direction"],
            r["c2_high"],
            r["c2_low"],
            r["c2_close"],
        ),
        axis=1,
    )

    ae2["c1_favorable_wick_pct"] = ae2.apply(
        lambda r: favorable_wick(
            r["direction"],
            r["c1_open"],
            r["c1_high"],
            r["c1_low"],
            r["c1_close"],
        ),
        axis=1,
    )

    ae2["c2_favorable_wick_pct"] = ae2.apply(
        lambda r: favorable_wick(
            r["direction"],
            r["c2_open"],
            r["c2_high"],
            r["c2_low"],
            r["c2_close"],
        ),
        axis=1,
    )

    ae2["c1_adverse_wick_pct"] = ae2.apply(
        lambda r: adverse_wick(
            r["direction"],
            r["c1_open"],
            r["c1_high"],
            r["c1_low"],
            r["c1_close"],
        ),
        axis=1,
    )

    ae2["c2_adverse_wick_pct"] = ae2.apply(
        lambda r: adverse_wick(
            r["direction"],
            r["c2_open"],
            r["c2_high"],
            r["c2_low"],
            r["c2_close"],
        ),
        axis=1,
    )

    ae2["c1_favorable_body_return_pct"] = ae2.apply(
        lambda r: favorable_body_return(
            r["direction"],
            r["c1_open"],
            r["c1_close"],
        ),
        axis=1,
    )

    ae2["c2_favorable_body_return_pct"] = ae2.apply(
        lambda r: favorable_body_return(
            r["direction"],
            r["c2_open"],
            r["c2_close"],
        ),
        axis=1,
    )

    ae2["c1_favorable_vwap_distance_pct"] = ae2.apply(
        lambda r: directional_distance_pct(
            r["direction"],
            r["c1_close"],
            r["c1_vwap"],
        ),
        axis=1,
    )

    ae2["c2_favorable_vwap_distance_pct"] = ae2.apply(
        lambda r: directional_distance_pct(
            r["direction"],
            r["c2_close"],
            r["c2_vwap"],
        ),
        axis=1,
    )

    # Penetration into / through VWAP before reclaim.
    # Positive = deeper violation before favorable close.

    def reclaim_penetration(r):

        if r["direction"] == "BULL":
            return safe_pct(
                r["c2_vwap"] - r["c2_low"],
                r["c2_vwap"],
            )

        return safe_pct(
            r["c2_high"] - r["c2_vwap"],
            r["c2_vwap"],
        )

    ae2["c2_vwap_penetration_pct"] = (
        ae2.apply(
            reclaim_penetration,
            axis=1,
        )
    )

    # Favorable C1 -> C2 close progress.

    def c1_to_c2_progress(r):

        raw = safe_pct(
            r["c2_close"] - r["c1_close"],
            r["c1_close"],
        )

        return (
            raw
            if r["direction"] == "BULL"
            else -raw
        )

    ae2["c1_to_c2_close_progress_pct"] = (
        ae2.apply(
            c1_to_c2_progress,
            axis=1,
        )
    )

    ae2["c2_to_c1_volume_ratio"] = (
        ae2["c2_volume"]
        / ae2["c1_volume"].replace(0, np.nan)
    )

    ae2["c1_range_pct"] = (
        100.0
        * (
            ae2["c1_high"]
            - ae2["c1_low"]
        )
        / ae2["c1_open"]
    )

    ae2["c2_range_pct"] = (
        100.0
        * (
            ae2["c2_high"]
            - ae2["c2_low"]
        )
        / ae2["c2_open"]
    )

    ae2["clv_change_pp"] = (
        ae2["c2_favorable_clv_pct"]
        - ae2["c1_favorable_clv_pct"]
    )

    ae2["vwap_distance_change_pp"] = (
        ae2["c2_favorable_vwap_distance_pct"]
        - ae2["c1_favorable_vwap_distance_pct"]
    )

    # =========================================================================
    # TEMPORAL HALF
    # =========================================================================

    unique_dates = sorted(
        ae2["trade_date"]
        .dropna()
        .unique()
    )

    midpoint = pd.Timestamp(
        unique_dates[
            len(unique_dates) // 2
        ]
    )

    ae2["temporal_half"] = ae2[
        "trade_date"
    ].apply(
        lambda x:
            "OLDEST_HALF"
            if x < midpoint
            else "NEWEST_HALF"
    )

    # =========================================================================
    # FEATURE SCREEN
    # =========================================================================

    features = [
        "c1_body_to_range_pct",
        "c2_body_to_range_pct",
        "c1_favorable_clv_pct",
        "c2_favorable_clv_pct",
        "c1_favorable_wick_pct",
        "c2_favorable_wick_pct",
        "c1_adverse_wick_pct",
        "c2_adverse_wick_pct",
        "c1_favorable_body_return_pct",
        "c2_favorable_body_return_pct",
        "c1_favorable_vwap_distance_pct",
        "c2_favorable_vwap_distance_pct",
        "c2_vwap_penetration_pct",
        "c1_to_c2_close_progress_pct",
        "c2_to_c1_volume_ratio",
        "c1_range_pct",
        "c2_range_pct",
        "clv_change_pp",
        "vwap_distance_change_pp",
    ]

    bucket_frames = []

    for feature in features:

        bucket_col = (
            f"{feature}__bucket"
        )

        ae2[bucket_col] = (
            bucket_by_quantiles(
                ae2,
                feature,
                q=5,
            )
        )

        bucket_frames.append(
            summarize_target(
                ae2,
                feature,
                bucket_col,
            )
        )

    bucket_summary = pd.concat(
        bucket_frames,
        ignore_index=True,
    )

    # =========================================================================
    # TEMPORAL FEATURE SUMMARY
    # =========================================================================

    temporal_rows = []

    for feature in features:

        for temporal_half, x in ae2.groupby(
            "temporal_half"
        ):

            confirmed = x.loc[
                x["c3_confirmed"]
            ]

            not_confirmed = x.loc[
                ~x["c3_confirmed"]
            ]

            temporal_rows.append(
                {
                    "feature": feature,
                    "temporal_half": temporal_half,
                    "n": len(x),
                    "confirmed_n": len(confirmed),
                    "not_confirmed_n": len(not_confirmed),
                    "confirmed_mean":
                        confirmed[feature].mean(),
                    "not_confirmed_mean":
                        not_confirmed[feature].mean(),
                    "difference":
                        confirmed[feature].mean()
                        - not_confirmed[feature].mean(),
                }
            )

    temporal_summary = pd.DataFrame(
        temporal_rows
    )

    # =========================================================================
    # SAVE
    # =========================================================================

    ae2.to_parquet(
        FEATURE_OUTPUT,
        index=False,
    )

    bucket_summary.to_csv(
        BUCKET_OUTPUT,
        index=False,
    )

    temporal_summary.to_csv(
        TEMPORAL_OUTPUT,
        index=False,
    )

    # =========================================================================
    # PRINT
    # =========================================================================

    print("=" * 80)
    print("AE2 C2-SAFE PREDICTOR SCREEN V1")
    print("=" * 80)

    print(
        f"AE2 events:          "
        f"{len(ae2):,}"
    )

    print(
        f"C3 confirmed:        "
        f"{int(ae2['c3_confirmed'].sum()):,}"
    )

    print(
        f"No C3 confirmation:  "
        f"{int((~ae2['c3_confirmed']).sum()):,}"
    )

    print(
        f"Temporal midpoint:   "
        f"{midpoint.date()}"
    )

    print()
    print("=" * 80)
    print("MEAN DIFFERENCES: C3 CONFIRMED VS NOT CONFIRMED")
    print("=" * 80)

    overall_rows = []

    for feature in features:

        confirmed = ae2.loc[
            ae2["c3_confirmed"],
            feature,
        ]

        not_confirmed = ae2.loc[
            ~ae2["c3_confirmed"],
            feature,
        ]

        overall_rows.append(
            {
                "feature": feature,
                "confirmed_mean":
                    confirmed.mean(),
                "not_confirmed_mean":
                    not_confirmed.mean(),
                "difference":
                    confirmed.mean()
                    - not_confirmed.mean(),
            }
        )

    overall = pd.DataFrame(
        overall_rows
    )

    print(
        overall.to_string(
            index=False,
            float_format=lambda x:
                f"{x:.4f}",
        )
    )

    print()
    print("=" * 80)
    print("QUINTILE SCREEN — C3 CONFIRMATION RATE")
    print("=" * 80)

    for feature in features:

        x = bucket_summary.loc[
            bucket_summary[
                "feature"
            ]
            == feature
        ].copy()

        print()
        print(feature)
        print("-" * 80)

        print(
            x[
                [
                    "direction",
                    "bucket",
                    "n",
                    "c3_confirmation_pct",
                    "favorable_first_pct",
                    "avg_feature_value",
                ]
            ]
            .to_string(
                index=False,
                float_format=lambda z:
                    f"{z:.2f}",
            )
        )

    print()
    print("=" * 80)
    print("OUTPUTS")
    print("=" * 80)

    print(
        f"Feature events: "
        f"{FEATURE_OUTPUT}"
    )

    print(
        f"Bucket summary: "
        f"{BUCKET_OUTPUT}"
    )

    print(
        f"Temporal:       "
        f"{TEMPORAL_OUTPUT}"
    )

    print()
    print("RESULT: COMPLETE")


if __name__ == "__main__":
    main()