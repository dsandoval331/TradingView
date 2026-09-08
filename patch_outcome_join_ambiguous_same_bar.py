from pathlib import Path

p = Path("join_and_audit_frozen_9h_outcomes.py")
s = p.read_text(encoding="utf-8")

old = """        neither_pat = z.str.contains(r"neither|none|unresolved|censor|no_hit|no hit", regex=True, na=False)
        resolved.loc[fav_pat & ~adv_pat] = "FAVORABLE_FIRST"
        resolved.loc[adv_pat & ~fav_pat] = "ADVERSE_FIRST"
        resolved.loc[neither_pat & ~fav_pat & ~adv_pat] = "NEITHER_OR_UNRESOLVED"
        unknown = p[c].notna() & resolved.isna()"""

new = """        neither_pat = z.str.contains(r"neither|none|unresolved|censor|no_hit|no hit", regex=True, na=False)
        ambiguous_pat = z.eq("ambiguous_same_bar")
        resolved.loc[fav_pat & ~adv_pat] = "FAVORABLE_FIRST"
        resolved.loc[adv_pat & ~fav_pat] = "ADVERSE_FIRST"
        resolved.loc[neither_pat & ~fav_pat & ~adv_pat] = "UNRESOLVED"
        resolved.loc[ambiguous_pat] = "AMBIGUOUS_SAME_BAR"
        unknown = p[c].notna() & resolved.isna()"""

if old not in s:
    raise SystemExit("Expected categorical mapping block not found; no changes made.")

p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OUTCOME_JOIN_AMBIGUOUS_LABEL_PATCH_APPLIED=PASS")
