from __future__ import annotations

from dataclasses import dataclass, asdict
import math
import pandas as pd


@dataclass(frozen=True)
class StackGeometry:
    direction: str
    pm_level: float
    ah_level: float
    pd_level: float
    inner_level_name: str
    middle_level_name: str
    outer_level_name: str
    inner_level_price: float
    middle_level_price: float
    outer_level_price: float
    identity_order_inner_to_outer: str
    pm_ah_abs_pct: float
    pm_pd_abs_pct: float
    ah_pd_abs_pct: float
    stack_width_abs: float
    stack_width_pct: float


def _abs_pair_pct(a: float, b: float) -> float:
    mid = (a + b) / 2.0
    return abs(a - b) / mid * 100.0 if mid else math.nan


def build_stack_geometry(row: pd.Series | dict, direction: str) -> StackGeometry:
    direction = direction.upper().strip()
    if direction not in {"BULL", "BEAR"}:
        raise ValueError("direction must be BULL or BEAR")

    getter = row.get if hasattr(row, "get") else lambda k: row[k]
    if direction == "BULL":
        levels = {"PM": float(getter("pmh")), "AH": float(getter("ahh")), "PD": float(getter("pdh"))}
        ordered = sorted(levels.items(), key=lambda kv: (kv[1], kv[0]))
    else:
        levels = {"PM": float(getter("pml")), "AH": float(getter("ahl")), "PD": float(getter("pdl"))}
        ordered = sorted(levels.items(), key=lambda kv: (-kv[1], kv[0]))

    if any(pd.isna(v) for v in levels.values()):
        raise ValueError("All three directional levels are required for geometry")

    (inner_n, inner_p), (middle_n, middle_p), (outer_n, outer_p) = ordered
    lo, hi = min(levels.values()), max(levels.values())
    mid = (lo + hi) / 2.0

    return StackGeometry(
        direction=direction,
        pm_level=levels["PM"], ah_level=levels["AH"], pd_level=levels["PD"],
        inner_level_name=inner_n, middle_level_name=middle_n, outer_level_name=outer_n,
        inner_level_price=inner_p, middle_level_price=middle_p, outer_level_price=outer_p,
        identity_order_inner_to_outer=">".join(x[0] for x in ordered),
        pm_ah_abs_pct=_abs_pair_pct(levels["PM"], levels["AH"]),
        pm_pd_abs_pct=_abs_pair_pct(levels["PM"], levels["PD"]),
        ah_pd_abs_pct=_abs_pair_pct(levels["AH"], levels["PD"]),
        stack_width_abs=hi - lo,
        stack_width_pct=(hi - lo) / mid * 100.0 if mid else math.nan,
    )


def geometry_as_dict(row: pd.Series | dict, direction: str) -> dict:
    return asdict(build_stack_geometry(row, direction))
