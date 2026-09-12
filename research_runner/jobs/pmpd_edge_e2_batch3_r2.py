from __future__ import annotations

import shutil
from pathlib import Path

from research_runner.jobs import pmpd_edge_e2_batch3 as b3


def run(root: Path) -> dict:
    src = root / "research_outputs" / "pmpd" / "edge" / "e2_batch2_r2" / "acceptance_state_paths.parquet"
    dst_dir = root / "research_outputs" / "pmpd" / "edge" / "e2_batch2"
    dst = dst_dir / "acceptance_state_paths.parquet"
    if not src.exists():
        raise FileNotFoundError(src)
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    result = b3.run(root)
    result["upstream_state_path"] = "PMPD-EDGE-E2-B2-R2"
    result["upstream_state_path_sha256"] = "70d6f835854bd89260c6fac994e6c66467b82ccd83875621e1736f1fb095013f"
    return result
