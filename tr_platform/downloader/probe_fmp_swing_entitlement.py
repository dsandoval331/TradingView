"""Read-only FMP Basic capability probe for SWING_10D_EDGE S1.

Prompts once for FMP_API_KEY if absent. Never stores or prints the key.
GET requests only; intentionally small requests to conserve the 250/day free quota.
"""
from __future__ import annotations
import getpass, json, os, time
import requests

BASE="https://financialmodelingprep.com/stable"

def get(key,path,**params):
    params["apikey"]=key
    try:
        r=requests.get(BASE+path,params=params,timeout=30)
        out={"status_code":r.status_code,"content_type":r.headers.get("content-type","")}
        try:
            p=r.json()
            if isinstance(p,list):
                out["result_count"]=len(p)
                if p:
                    out["sample_keys"]=list(p[0].keys())
                    out["sample"]=p[0]
            elif isinstance(p,dict):
                out["top_level_keys"]=list(p.keys())[:15]
                out["api_message"]=p.get("Error Message") or p.get("message") or p.get("error")
        except ValueError:
            out["body_prefix"]=r.text[:300]
        return out
    except Exception as e:
        return {"status_code":None,"error":type(e).__name__+": "+str(e)}

def main():
    key=os.getenv("FMP_API_KEY") or getpass.getpass("FMP API key (not stored): ")
    tests=[
      ("aapl_eod_2021","/historical-price-eod/full",{"symbol":"AAPL","from":"2021-09-01","to":"2021-09-10"}),
      ("twtr_delisted_eod_2022","/historical-price-eod/full",{"symbol":"TWTR","from":"2022-10-20","to":"2022-10-27"}),
      ("delisted_companies","/delisted-companies",{"page":0,"limit":5}),
      ("aapl_unadjusted_2024","/historical-price-eod/non-split-adjusted",{"symbol":"AAPL","from":"2024-01-02","to":"2024-01-10"}),
      ("aapl_splits","/splits",{"symbol":"AAPL"}),
      ("aapl_dividends","/dividends",{"symbol":"AAPL"}),
      ("earnings_calendar","/earnings-calendar",{"from":"2026-09-21","to":"2026-09-28"}),
    ]
    probes=[]
    for name,path,params in tests:
        item={"name":name,"path":path}; item.update(get(key,path,**params)); probes.append(item); time.sleep(0.5)
    print(json.dumps({"read_only":True,"provider":"Financial Modeling Prep","probes":probes},indent=2,default=str))

if __name__=="__main__": main()
