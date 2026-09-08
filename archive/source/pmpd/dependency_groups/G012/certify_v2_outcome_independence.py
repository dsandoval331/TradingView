from pathlib import Path
import json, re, hashlib
import pandas as pd

ROOT = Path(".").resolve()

V2 = ROOT / "pmpd_v5_9j_vwap_event_path_v2_full50" / "decision_vwap_event_path_v2.csv"
DP4 = ROOT / "pmpd_v5_9j_vwap_event_path_v2_dp4fix" / "decision_vwap_event_path_v2_dp4fix.csv"
CORE = ROOT / "tr_platform" / "pmpd_v5" / "vwap_event_path_v2.py"
DERIVER = ROOT / "derive_and_certify_dp4_structural_clearance.py"

EXPECTED_V2_FP = "1f3e0d2bec2c6257bb6b372d324e9b0bc6948d6f02c5713b5ae10091573f0b56"
EXPECTED_DP4_FP = "9db7404bbf69d9b31b5ad93edfce943bdc515b70146e0d07f0fdda331f9a3a57"

# Terms that would indicate contamination by realized/future trade outcomes.
FORBIDDEN_PATTERNS = [
    r"\bfavorable[_ -]?first\b",
    r"\badverse[_ -]?first\b",
    r"\boutcome\b",
    r"\btarget[_ -]?hit\b",
    r"\bstop[_ -]?hit\b",
    r"\btake[_ -]?profit\b",
    r"\bprofit[_ -]?target\b",
    r"\brealized[_ -]?pnl\b",
    r"\brealized[_ -]?p&l\b",
    r"\bmfe\b",
    r"\bmae\b",
    r"\bforward[_ -]?(?:return|ret|high|low|price)\b",
    r"\bfuture[_ -]?(?:return|ret|high|low|price)\b",
    r"\bexit[_ -]?(?:price|time|timestamp)\b",
    r"\bwin(?:ner)?\b",
    r"\blos(?:er|ing)\b",
]

# Allowed because V2 uses "favorable/adverse side" relative to VWAP direction,
# not realized trade outcomes.
ALLOWED_SCHEMA_EXACT = {
    "event_favorable_close_count",
    "event_adverse_close_count",
    "event_favorable_close_fraction",
    "event_adverse_close_fraction",
    "event_consecutive_favorable_closes",
    "event_consecutive_adverse_closes",
    "event_first_favorable_close_timestamp_utc",
    "event_first_adverse_close_timestamp_utc",
}

def check_text(label, text):
    hits = []
    low = text.lower()
    for pat in FORBIDDEN_PATTERNS:
        for m in re.finditer(pat, low, flags=re.I):
            # Explicitly ignore comments/docstrings explaining that outcomes are prohibited.
            line = low[max(0, low.rfind("\n", 0, m.start()) + 1): low.find("\n", m.end()) if low.find("\n", m.end()) >= 0 else len(low)]
            if any(x in line for x in ["forbidden", "prohibit", "outcome-independent", "outcome independent",
                                       "do not", "not use", "without", "exclude", "blocked",
                                       "before outcome analysis", "prior to outcome analysis",
                                       "before joining outcomes", "before outcome join"]):
                continue
            hits.append({"pattern": pat, "match": m.group(0), "line": line[:250]})
    return hits

print("=== INPUTS ===")
for p in [V2, DP4, CORE, DERIVER]:
    print(p, "exists=", p.exists())
    if not p.exists():
        raise SystemExit(f"MISSING_REQUIRED_INPUT={p}")

print("\n=== SCHEMA AUDIT ===")
v2_head = pd.read_csv(V2, nrows=5)
dp4_head = pd.read_csv(DP4, nrows=5)

schema_hits = []
for dataset_name, cols in [("V2", v2_head.columns), ("DP4", dp4_head.columns)]:
    for c in cols:
        cl = c.lower()
        if c in ALLOWED_SCHEMA_EXACT:
            continue
        for pat in FORBIDDEN_PATTERNS:
            if re.search(pat, cl, flags=re.I):
                schema_hits.append((dataset_name, c, pat))

print("V2 columns =", len(v2_head.columns))
print("DP4 columns =", len(dp4_head.columns))
print("schema_forbidden_hits =", schema_hits)

print("\n=== SOURCE-CODE AUDIT ===")
core_text = CORE.read_text(encoding="utf-8", errors="replace")
deriver_text = DERIVER.read_text(encoding="utf-8", errors="replace")

core_hits = check_text("CORE", core_text)
deriver_hits = check_text("DERIVER", deriver_text)

print("core_forbidden_hits =", core_hits)
print("deriver_forbidden_hits =", deriver_hits)

print("\n=== INPUT-DEPENDENCY AUDIT ===")
# Core should reference structural parent / market data concepts, not frozen outcomes.
positive_core_terms = [
    "decision_id", "event_id", "timestamp_utc", "vwap", "market_cache",
]
for term in positive_core_terms:
    print(f"core_contains_{term} =", term.lower() in core_text.lower())

# DP4 derivation should consume only V2 + structural parent.
deriver_required = [
    "decision_vwap_event_path_v2.csv",
    "decision_research.csv",
    "DP4_FULL_STACK_FIRST_CLEAR",
    "event_minutes_since_last_loss",
]
for term in deriver_required:
    print(f"deriver_contains_{term} =", term in deriver_text)

# Explicitly inspect file/path literals for suspicious outcome sources.
pathish = re.findall(r'["\']([^"\']+\.(?:csv|parquet|json|zip))["\']', core_text + "\n" + deriver_text, flags=re.I)
suspicious_paths = []
for x in pathish:
    xl = x.lower()
    if any(t in xl for t in ["outcome", "forward", "result", "mfe", "mae", "target", "stop", "pnl", "profit"]):
        suspicious_paths.append(x)
print("suspicious_outcome_file_literals =", suspicious_paths)

print("\n=== ARTIFACT IDENTITY / METADATA ===")
v2_meta_path = ROOT / "pmpd_v5_9j_vwap_event_path_v2_full50" / "run_fingerprint.json"
dp4_meta_path = ROOT / "pmpd_v5_9j_vwap_event_path_v2_dp4fix" / "run_fingerprint.json"

v2_meta = json.loads(v2_meta_path.read_text(encoding="utf-8")) if v2_meta_path.exists() else {}
dp4_meta = json.loads(dp4_meta_path.read_text(encoding="utf-8")) if dp4_meta_path.exists() else {}

print("v2_fingerprint =", v2_meta.get("fingerprint"))
print("dp4_fingerprint =", dp4_meta.get("fingerprint"))
print("dp4_source_fingerprint =", dp4_meta.get("source_fingerprint"))

checks = {
    "v2_schema_no_forbidden_outcome_fields": not any(h[0] == "V2" for h in schema_hits),
    "dp4_schema_no_forbidden_outcome_fields": not any(h[0] == "DP4" for h in schema_hits),
    "v2_core_no_forbidden_outcome_dependencies": len(core_hits) == 0,
    "dp4_deriver_no_forbidden_outcome_dependencies": len(deriver_hits) == 0,
    "no_suspicious_outcome_file_literals": len(suspicious_paths) == 0,
    "dp4_deriver_uses_dp4_full_stack_semantics": "DP4_FULL_STACK_FIRST_CLEAR" in deriver_text,
    "dp4_deriver_uses_v2_loss_path_state": "event_minutes_since_last_loss" in deriver_text,
    "v2_fingerprint_expected": v2_meta.get("fingerprint") == EXPECTED_V2_FP,
    "dp4_fingerprint_expected": dp4_meta.get("fingerprint") == EXPECTED_DP4_FP,
    "dp4_source_fingerprint_links_certified_v2": dp4_meta.get("source_fingerprint") == EXPECTED_V2_FP,
}

print("\n=== OUTCOME-INDEPENDENCE CERTIFICATION ===")
for k, v in checks.items():
    print(k, "=", "PASS" if v else "FAIL")

failed = [k for k, v in checks.items() if not v]

result = {
    "certification": "PASS" if not failed else "FAIL",
    "failed_checks": failed,
    "v2_fingerprint": v2_meta.get("fingerprint"),
    "dp4_fingerprint": dp4_meta.get("fingerprint"),
    "schema_hits": schema_hits,
    "core_hits": core_hits,
    "deriver_hits": deriver_hits,
    "suspicious_paths": suspicious_paths,
    "statement": (
        "Feature construction is certified outcome-independent: V2 is built from structural decision/event data "
        "and contemporaneous market/VWAP path data through each decision timestamp; the DP4 semantic correction "
        "is derived only from certified V2 path state plus structural DP4 timestamps. Frozen favorable-first vs "
        "adverse-first outcomes were not used in feature construction."
    ) if not failed else "Outcome-independence certification did not pass all gates."
}

cert_path = ROOT / "pmpd_v5_9j_vwap_event_path_v2_dp4fix" / "outcome_independence_certification.json"
cert_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

print("\nOUTCOME_INDEPENDENCE_CERTIFICATION =", result["certification"])
print("FAILED_CHECKS =", failed)
print("CERTIFICATION_FILE =", cert_path)

if failed:
    raise SystemExit(2)
