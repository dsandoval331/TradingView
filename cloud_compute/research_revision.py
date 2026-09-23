from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResearchRevision:
    research_sha: str
    infrastructure_sha: str
    root: Path


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True
    ).strip()


def materialize_research_revision(
    *,
    repository_root: Path,
    research_sha: str,
    destination: Path,
    infrastructure_sha: str | None = None,
) -> ResearchRevision:
    """Materialize and verify an exact governed research revision.

    The infrastructure checkout remains untouched.  Research code is exported
    into a detached git worktree so historical research can execute without
    requiring that historical revision to contain today's control-plane code.
    """
    if len(research_sha) != 40:
        raise ValueError("research_sha must be a full 40-character commit SHA")
    repository_root = repository_root.resolve()
    destination = destination.resolve()
    infrastructure_sha = infrastructure_sha or _git(repository_root, "rev-parse", "HEAD")
    if destination.exists():
        raise FileExistsError(destination)
    subprocess.run(
        ["git", "-C", str(repository_root), "worktree", "add", "--detach", str(destination), research_sha],
        check=True,
    )
    actual = _git(destination, "rev-parse", "HEAD")
    if actual != research_sha:
        raise RuntimeError(f"research revision mismatch: expected {research_sha}, got {actual}")
    return ResearchRevision(research_sha=research_sha, infrastructure_sha=infrastructure_sha, root=destination)


def remove_research_revision(*, repository_root: Path, revision: ResearchRevision) -> None:
    subprocess.run(
        ["git", "-C", str(repository_root.resolve()), "worktree", "remove", "--force", str(revision.root)],
        check=True,
    )


def provenance(revision: ResearchRevision) -> dict[str, object]:
    return {
        "research_sha": revision.research_sha,
        "infrastructure_sha": revision.infrastructure_sha,
        "exact_research_sha_verified": True,
        "research_revision_adapter": "v1",
    }
