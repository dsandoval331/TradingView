from pathlib import Path
import argparse, json
import pandas as pd

PREFIX = "PMPD_PARITY_"
GRADE = {0:"Weak",1:"C-",2:"C",3:"C+",4:"B-",5:"B",6:"B+",7:"A-",8:"A",9:"A+"}
PROFILE = {0:"Controlled Strong",1:"Explosive",2:"Efficient Moderate",3:"Pretty but Weak",4:"Delayed Strong",5:"Unclassified"}
PRIORITY = {0:"OBSERVE",1:"LOW",2:"RESEARCH",3:"CONDITIONAL",4:"PRIME"}
TRADE = {0:"OBSERVE",1:"SCALP",2:"EXPANSION"}
CONF = {0:"INSUFFICIENT",1:"LOW",2:"MODERATE",3:"MOD-HIGH",4:"HIGH"}
OUTCOME = {0:"NEITHER",1:"FAVORABLE_FIRST",2:"ADVERSE_FIRST",3:"BOTH"}

def find_col(df, exact):
    matches = [c for c in df.columns if str(c).strip() == exact or str(c).strip().endswith(exact)]
    if not matches:
        raise KeyError(f"Missing CSV export column: {exact}")
    return matches[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    path = Path(args.csv)
    df = pd.read_csv(path)
    count_col = find_col(df, "PMPD_PARITY_SIGNAL_COUNT")
    seen_col = find_col(df, "PMPD_PARITY_DATE_SEEN")
    usable = df[pd.to_numeric(df[count_col], errors="coerce").notna()].copy()
    if usable.empty:
        raise SystemExit("No PMPD parity export rows found.")

    row = usable.iloc[-1]
    result = {
        "source_csv": str(path),
        "date_seen": bool(int(float(row[seen_col]))) if pd.notna(row[seen_col]) else False,
        "signal_count": int(float(row[count_col])),
    }

    names = [
        "PMPD_PARITY_DIRECTION","PMPD_PARITY_SIGNAL_TIME_MS","PMPD_PARITY_REFERENCE",
        "PMPD_PARITY_DATE_PMH","PMPD_PARITY_DATE_PML","PMPD_PARITY_DATE_PDH","PMPD_PARITY_DATE_PDL",
        "PMPD_PARITY_PMH","PMPD_PARITY_PML","PMPD_PARITY_PDH","PMPD_PARITY_PDL","PMPD_PARITY_FINAL_LEVEL",
        "PMPD_PARITY_ATR","PMPD_PARITY_PEN_PCT_ATR","PMPD_PARITY_BODY_PCT","PMPD_PARITY_RANGE_PCT_ATR",
        "PMPD_PARITY_CLOSE_POS_PCT","PMPD_PARITY_BARS_TO_CONFIRM","PMPD_PARITY_TOTAL_SCORE",
        "PMPD_PARITY_GRADE_CODE","PMPD_PARITY_PROFILE_CODE","PMPD_PARITY_PRIORITY_CODE",
        "PMPD_PARITY_TRADE_TYPE_CODE","PMPD_PARITY_TQS","PMPD_PARITY_CONFIDENCE_CODE",
        "PMPD_PARITY_DEFAULT_CONDITIONAL_PLUS_ELIGIBLE","PMPD_PARITY_CURRENT_ALERT_PASS",
        "PMPD_PARITY_PEN_SCORE","PMPD_PARITY_BODY_SCORE","PMPD_PARITY_CLOSE_SCORE",
        "PMPD_PARITY_RANGE_SCORE","PMPD_PARITY_SPEED_SCORE","PMPD_PARITY_DIRECTIONAL_PASS",
        "PMPD_PARITY_PEN_PASS","PMPD_PARITY_BODY_PASS","PMPD_PARITY_RANGE_PASS","PMPD_PARITY_CLOSE_PASS",
        "PMPD_PARITY_FIRST_OUTCOME_CODE","PMPD_PARITY_MFE_PCT","PMPD_PARITY_MAE_PCT",
    ]

    if result["signal_count"] > 0:
        for n in names:
            c = find_col(df, n)
            x = row[c]
            result[n.removeprefix(PREFIX).lower()] = None if pd.isna(x) else float(x)

        result["direction_name"] = "BULL" if result["direction"] == 1 else "BEAR"
        result["signal_timestamp_utc"] = pd.to_datetime(int(result["signal_time_ms"]), unit="ms", utc=True).isoformat()
        result["grade"] = GRADE.get(int(result["grade_code"]))
        result["profile"] = PROFILE.get(int(result["profile_code"]))
        result["priority"] = PRIORITY.get(int(result["priority_code"]))
        result["trade_type"] = TRADE.get(int(result["trade_type_code"]))
        result["confidence"] = CONF.get(int(result["confidence_code"]))
        result["first_outcome"] = OUTCOME.get(int(result["first_outcome_code"]))

    out = Path(args.out) if args.out else path.with_suffix(".parity.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print("REPORT =", out)
    print("9N_3F_CSV_PARSE_GATE=PASS")

if __name__ == "__main__":
    main()
