# Dual-SHA provenance

Required attempt metadata after production wiring:

```json
{
  "research_sha": "<research_jobs.git_sha>",
  "infrastructure_sha": "<certified Actions checkout SHA>",
  "exact_research_sha_verified": true,
  "research_revision_adapter": "v1"
}
```

The research SHA identifies research semantics. The infrastructure SHA identifies the certified orchestration/control-plane implementation.
