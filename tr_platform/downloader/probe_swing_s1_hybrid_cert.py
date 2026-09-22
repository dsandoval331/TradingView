"""SWING_10D_EDGE S1 hybrid certification probe.
Massive: PIT ticker/universe breadth + corporate actions.
FMP: corporate-action cross-check.
Read-only; prompts once per missing key; never stores/prints keys.
"""
from __future__ import annotations
import getpass,json,os,requests,time
M="https://api.massive.com"; F="https://financialmodelingprep.com/stable"
def req(url,params):
    try:
        r=requests.get(url,params=params,timeout=30); o={"status_code":r.status_code}
        try:
            x=r.json()
            if isinstance(x,list):
                o["count"]=len(x); o["sample"]=x[:3]
            elif isinstance(x,dict):
                rows=x.get("results")
                o["status"]=x.get("status"); o["count"]=len(rows) if isinstance(rows,list) else None
                o["sample"]=rows[:3] if isinstance(rows,list) else None
                o["next_url"]=bool(x.get("next_url")); o["message"]=x.get("error") or x.get("message")
        except ValueError:o["body_prefix"]=r.text[:240]
        return o
    except Exception as e:return {"error":type(e).__name__+": "+str(e)}
def main():
    mk=os.getenv("MASSIVE_API_KEY") or getpass.getpass("Massive API key (not stored): ")
    fk=os.getenv("FMP_API_KEY") or getpass.getpass("FMP API key (not stored): ")
    out=[]
    for d in ["2019-09-10","2021-09-10","2025-09-10"]:
        p={"market":"stocks","date":d,"active":"true","limit":1000,"sort":"ticker","apiKey":mk}
        out.append({"name":"massive_active_"+d,**req(M+"/v3/reference/tickers",p)});time.sleep(.5)
    p={"market":"stocks","active":"false","limit":1000,"sort":"ticker","apiKey":mk}
    out.append({"name":"massive_delisted_sample",**req(M+"/v3/reference/tickers",p)});time.sleep(.5)
    for sym in ["AAPL","TSLA"]:
        out.append({"name":f"massive_{sym}_splits",**req(M+"/stocks/v1/splits",{"ticker":sym,"limit":100,"apiKey":mk})});time.sleep(.5)
        out.append({"name":f"fmp_{sym}_splits",**req(F+"/splits",{"symbol":sym,"apikey":fk})});time.sleep(.5)
    for sym in ["AAPL"]:
        out.append({"name":"massive_AAPL_dividends",**req(M+"/stocks/v1/dividends",{"ticker":sym,"limit":100,"apiKey":mk})});time.sleep(.5)
        out.append({"name":"fmp_AAPL_dividends",**req(F+"/dividends",{"symbol":sym,"apikey":fk})});time.sleep(.5)
    print(json.dumps({"read_only":True,"probe":"s1_hybrid_cert_v1","results":out},indent=2,default=str))
if __name__=="__main__":main()
