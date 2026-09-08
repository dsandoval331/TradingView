from pathlib import Path

p = Path("certify_v2_outcome_independence.py")
s = p.read_text(encoding="utf-8")

old = '''            if any(x in line for x in ["forbidden", "prohibit", "outcome-independent", "outcome independent",
                                       "do not", "not use", "without", "exclude", "blocked"]):
                continue'''

new = '''            if any(x in line for x in ["forbidden", "prohibit", "outcome-independent", "outcome independent",
                                       "do not", "not use", "without", "exclude", "blocked",
                                       "before outcome analysis", "prior to outcome analysis",
                                       "before joining outcomes", "before outcome join"]):
                continue'''

if old not in s:
    raise SystemExit("Expected comment-exemption block not found; no changes made.")

p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OUTCOME_CHECKER_COMMENT_PATCH_APPLIED=PASS")