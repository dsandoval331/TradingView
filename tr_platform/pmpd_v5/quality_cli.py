from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from tr_platform.pmpd_v5.quality import (
    build_session_quality_layer,
    enrich_by_session_quality,
    quality_summary,
)


def main() -> None:
    p = argparse.ArgumentParser(description="PMPD V5 9H session-quality eligibility layer")
    p.add_argument("--input-dir", default="pmpd_v5_alpha_0_2_full_universe")
    p.add_argument("--output", default="pmpd_v5_9h_quality_v1")
    args = p.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    session_levels = pd.read_csv(input_dir / "session_levels.csv")
    quality = build_session_quality_layer(session_levels)
    quality.to_csv(output_dir / "session_quality.csv", index=False)

    if (input_dir / "events.csv").exists():
        events = pd.read_csv(input_dir / "events.csv")
        enrich_by_session_quality(events, quality).to_csv(
            output_dir / "events_quality_enriched.csv", index=False
        )

    if (input_dir / "geometry.csv").exists():
        geometry = pd.read_csv(input_dir / "geometry.csv")
        enrich_by_session_quality(geometry, quality).to_csv(
            output_dir / "geometry_quality_enriched.csv", index=False
        )

    severe = quality.loc[quality["price_scale_severe_flag"]].copy()
    severe.to_csv(output_dir / "severe_scale_discontinuities.csv", index=False)

    review = quality.loc[quality["price_scale_review_flag"]].copy()
    review.to_csv(output_dir / "price_continuity_review.csv", index=False)

    symbol_obs = (
        quality.loc[quality["has_complete_six_levels"]]
        .groupby("symbol", as_index=False)
        .agg(
            six_level_days=("trade_date", "size"),
            median_pm_bars=("pm_bar_count", "median"),
            median_ah_bars=("prior_ah_bar_count", "median"),
            median_rth_bars=("prior_rth_bar_count", "median"),
            sparse_pm_days=("pm_bar_count", lambda s: int((pd.to_numeric(s, errors="coerce") <= 5).sum())),
            sparse_ah_days=("prior_ah_bar_count", lambda s: int((pd.to_numeric(s, errors="coerce") <= 5).sum())),
            severe_scale_days=("price_scale_severe_flag", "sum"),
            review_scale_days=("price_scale_review_flag", "sum"),
        )
    )
    symbol_obs["sparse_pm_pct"] = symbol_obs["sparse_pm_days"] / symbol_obs["six_level_days"]
    symbol_obs["sparse_ah_pct"] = symbol_obs["sparse_ah_days"] / symbol_obs["six_level_days"]
    symbol_obs.to_csv(output_dir / "symbol_observability.csv", index=False)

    payload = quality_summary(quality)
    (output_dir / "quality_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )

    archive = shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"Package: {archive}")


if __name__ == "__main__":
    main()
