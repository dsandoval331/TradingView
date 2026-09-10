from __future__ import annotations

from pathlib import Path

from research_runner.jobs import pmpd_edge_e1_batch2


def run(root: Path) -> dict:
    """Execute the unchanged PMPD EDGE-E1 Batch-2 workload for CCP-10 only.

    The PMPD research module remains the source of all research logic. This
    wrapper only adapts its existing summary output to the cloud worker's
    primary-artifact contract so CCP-10 can certify real-lane execution without
    changing PMPD research behavior or governance.
    """
    result = dict(pmpd_edge_e1_batch2.run(root))
    result["artifact"] = result["summary"]
    result["ccp10_proof_of_concept_only"] = True
    return result
