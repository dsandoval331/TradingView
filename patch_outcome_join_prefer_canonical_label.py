from pathlib import Path

p = Path("join_and_audit_frozen_9h_outcomes.py")
s = p.read_text(encoding="utf-8")

start = s.index("# Case 1: direct favorable-first boolean.")
end = s.index("# Case 2: paired booleans", start)
replacement = '''# Case 1: skip the lossy direct favorable-first boolean when the canonical
# categorical first-reached outcome is available. FALSE cannot distinguish
# ADVERSE_FIRST from UNRESOLVED / AMBIGUOUS_SAME_BAR.
pass

'''
s = s[:start] + replacement + s[end:]

old = 'if resolution is None:\n    fav_hits = []'
new = 'if resolution is None and "outcome" not in p.columns:\n    fav_hits = []'
if old not in s:
    raise SystemExit("Expected paired-boolean fallback block not found; no changes made.")
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("OUTCOME_JOIN_CANONICAL_LABEL_PATCH_APPLIED=PASS")
