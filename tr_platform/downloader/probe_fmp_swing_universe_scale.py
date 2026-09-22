"""FMP S1 universe-scale and cross-provider-ready certification probe.
Read-only; small free-tier request budget; never stores or prints FMP_API_KEY.
"""
from __future__ import annotations
import getpass,json,os,time,requests
BASE="https://financialmodelingprep.com/stable"
def get(k,p,**params):
    params["apikey"]=k
    try:
        r=requests.get(BASE+p,params=params,timeout=30)
        o={"status_code":r.status_code}
        try:
            x=r.json()
            if isinstance(x,list):
                o["result_count"]=len(x)
                if x:o["sample_keys"]=list(x[0].keys());o["sample"]=x[0]
            elif isinstance(x,dict):
                o["keys"]=list(x.keys())[:15];o["message"]=x.get("message") or x.get("error")
        except ValueError:o["body_prefix"]=r.text[:240]
        return o
    except Exception as e:return {"status_code":None,"error":type(e).__name__+": "+str(e)}
def main():
    k=os.getenv("FMP_API_KEY") or getpass.getpass("FMP API key (not stored): ")
    tests=[
      ("stock_list","/stock-list",{}),
      ("available_traded","/available-traded/list",{}),
      ("delisted_page0","/delisted-companies",{"page":0,"limit":100}),
      ("delisted_page1","/delisted-companies",{"page":1,"limit":100}),
      ("ge_2019_price","/historical-price-eod/non-split-adjusted",{"symbol":"GE","from":"2019-09-03","to":"2019-09-10"}),
      ("tsla_2020_split_prices","/historical-price-eod/non-split-adjusted",{"symbol":"TSLA","from":"2020-08-27","to":"2020-09-02"}),
      ("tsla_splits","/splits",{"symbol":"TSLA"}),
      ("cost_earnings_future","/earnings-calendar",{"from":"2026-09-21","to":"2026-09-28"}),
    ]
    out=[]
    for n,p,a in tests:
        z={"name":n,"path":p};z.update(get(k,p,**a));out.append(z);time.sleep(.5)
    print(json.dumps({"read_only":True,"provider":"Financial Modeling Prep","probe":"universe_scale_v1","probes":out},indent=2,default=str))
if __name__=="__main__":main()
