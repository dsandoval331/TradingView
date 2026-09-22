"""FMP Basic S1 depth/scale/semantics probe for SWING_10D_EDGE.
Read-only, small request budget, never stores/prints FMP_API_KEY.
"""
from __future__ import annotations
import getpass,json,os,time,requests
BASE="https://financialmodelingprep.com/stable"
def get(key,path,**params):
    params["apikey"]=key
    try:
        r=requests.get(BASE+path,params=params,timeout=30)
        o={"status_code":r.status_code}
        try:
            p=r.json()
            if isinstance(p,list):
                o["result_count"]=len(p)
                if p:
                    o["sample_keys"]=list(p[0].keys()); o["first"]=p[-1] if "date" in p[0] else p[0]; o["last"]=p[0]
            elif isinstance(p,dict):
                o["keys"]=list(p.keys())[:15]; o["message"]=p.get("message") or p.get("error")
        except ValueError:o["body_prefix"]=r.text[:240]
        return o
    except Exception as e:return {"status_code":None,"error":type(e).__name__+": "+str(e)}
def main():
    k=os.getenv("FMP_API_KEY") or getpass.getpass("FMP API key (not stored): ")
    tests=[
      ("aapl_2020_depth","/historical-price-eod/full",{"symbol":"AAPL","from":"2020-09-01","to":"2020-09-10"}),
      ("aapl_2019_depth","/historical-price-eod/full",{"symbol":"AAPL","from":"2019-09-01","to":"2019-09-10"}),
      ("twtr_2019_delisted","/historical-price-eod/full",{"symbol":"TWTR","from":"2019-09-03","to":"2019-09-10"}),
      ("fb_meta_2021_old_ticker","/historical-price-eod/full",{"symbol":"FB","from":"2021-09-01","to":"2021-09-10"}),
      ("aapl_full_split_week","/historical-price-eod/full",{"symbol":"AAPL","from":"2020-08-27","to":"2020-09-02"}),
      ("aapl_non_split_week","/historical-price-eod/non-split-adjusted",{"symbol":"AAPL","from":"2020-08-27","to":"2020-09-02"}),
      ("aapl_split_record","/splits",{"symbol":"AAPL"}),
      ("earnings_past_window","/earnings-calendar",{"from":"2025-09-20","to":"2025-09-27"}),
      ("earnings_future_window","/earnings-calendar",{"from":"2026-09-21","to":"2026-09-28"}),
    ]
    out=[]
    for n,p,a in tests:
        x={"name":n,"path":p};x.update(get(k,p,**a));out.append(x);time.sleep(.5)
    print(json.dumps({"read_only":True,"provider":"Financial Modeling Prep","probe":"depth_scale_semantics_v1","probes":out},indent=2,default=str))
if __name__=="__main__":main()
