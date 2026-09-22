"""SWING_10D_EDGE S1 normalized dividend cross-provider certification.
Read-only. Fetches AAPL dividends from Massive and FMP, normalizes common fields,
matches on ex-date/date, and reports amount/date agreement. Keys are never stored/printed.
"""
from __future__ import annotations
import getpass,json,os,requests
M="https://api.massive.com"; F="https://financialmodelingprep.com/stable"
def jget(url,params):
    r=requests.get(url,params=params,timeout=30); r.raise_for_status(); return r.json()
def main():
    mk=os.getenv("MASSIVE_API_KEY") or getpass.getpass("Massive API key (not stored): ")
    fk=os.getenv("FMP_API_KEY") or getpass.getpass("FMP API key (not stored): ")
    m=jget(M+"/stocks/v1/dividends",{"ticker":"AAPL","limit":1000,"apiKey":mk}).get("results",[])
    f=jget(F+"/dividends",{"symbol":"AAPL","apikey":fk})
    mm={x.get("ex_dividend_date"):x for x in m if x.get("ex_dividend_date")}
    ff={x.get("date"):x for x in f if x.get("date")}
    common=sorted(set(mm)&set(ff))
    rows=[]
    for d in common:
        a,b=mm[d],ff[d]
        ma=a.get("split_adjusted_cash_amount")
        if ma is None: ma=a.get("cash_amount")
        fa=b.get("adjDividend")
        if fa is None: fa=b.get("dividend")
        rows.append({"date":d,"massive_amount":ma,"fmp_amount":fa,
          "amount_match": ma is not None and fa is not None and abs(float(ma)-float(fa))<1e-6,
          "record_match":a.get("record_date")==b.get("recordDate"),
          "pay_match":a.get("pay_date")==b.get("paymentDate"),
          "declaration_match":a.get("declaration_date")==b.get("declarationDate")})
    recent=[x for x in rows if x["date"]>="2013-01-01"]
    def n(k): return sum(bool(x[k]) for x in recent)
    print(json.dumps({"read_only":True,"probe":"s1_dividend_normalized_v1","symbol":"AAPL",
      "massive_count":len(m),"fmp_count":len(f),"common_ex_dates":len(common),
      "recent_common_since_2013":len(recent),
      "recent_matches":{"amount":n("amount_match"),"record_date":n("record_match"),
        "payment_date":n("pay_match"),"declaration_date":n("declaration_match")},
      "massive_only_dates":sorted(set(mm)-set(ff))[-20:],
      "fmp_only_dates":sorted(set(ff)-set(mm))[-20:],
      "mismatches":[x for x in recent if not x["amount_match"] or not x["record_match"] or not x["pay_match"]][:20]
    },indent=2))
if __name__=="__main__": main()
