from pathlib import Path

import pytest

from cloud_compute.research_revision import ResearchRevision, provenance


def test_provenance_records_both_revisions():
    revision = ResearchRevision(
        research_sha="1" * 40,
        infrastructure_sha="2" * 40,
        root=Path("/tmp/research"),
    )
    assert provenance(revision) == {
        "research_sha": "1" * 40,
        "infrastructure_sha": "2" * 40,
        "exact_research_sha_verified": True,
        "research_revision_adapter": "v1",
    }


def test_research_revision_requires_full_sha(tmp_path):
    from cloud_compute.research_revision import materialize_research_revision

    with pytest.raises(ValueError, match="40-character"):
        materialize_research_revision(
            repository_root=tmp_path,
            research_sha="abc",
            destination=tmp_path / "research",
        )
