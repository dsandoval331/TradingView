# Governed research revision adapter

The control plane distinguishes two immutable revisions during historical research execution:

- **infrastructure SHA**: the certified revision that owns queue selection, dispatch, atomic claim, input materialization, persistence, and CCP regression tests.
- **research SHA**: `research_jobs.git_sha`, the exact governed revision from which the approved historical research module is materialized.

The adapter uses an explicit allow-list of runner IDs and module paths. It verifies the full 40-character research commit, materializes only the approved module from that commit, executes its `run(work_root)` callable against already-governed materialized inputs, and returns explicit SHA/module provenance.

The adapter must not infer arbitrary module paths from database input and must not substitute current research code for historical governed code.

PMOD-P2-B2 and IR11-P3-B2 are the initial compatibility targets. Their research modules are not modified by this adapter.
