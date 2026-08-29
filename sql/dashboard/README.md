# Governance Dashboard V2

This refresh moves the dashboard queries away from wide one-row output.

## Files to replace

- `01_project_dashboard.sql`
  - Now returns one row per dashboard item for each strategy.

- `06_pmpd_governance_overview.sql`
  - Replace with the same human-readable vertical format currently used by
    `07_pmpd_governance_vertical.sql`.

## Files already naturally vertical / multi-row

These do not need redesign:
- `02_pmpd_plan_status.sql`
- `03_pmpd_roadmap_summary.sql`
- `04_pmpd_full_roadmap.sql`
- `05_pmpd_open_backlog.sql`

Recommended repo location:
`sql/dashboard/`

After replacing 01 and 06, `07_pmpd_governance_vertical.sql` becomes redundant.
You can keep it temporarily or remove it after confirming 06 works.
