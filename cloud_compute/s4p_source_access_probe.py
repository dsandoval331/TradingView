"""One-time metadata-only access probe. Never reads prices/accounts or prints credentials."""
import datetime as dt, hashlib, json, os, urllib.request, urllib.error
BASE="https://financialmodelingprep.com/stable/earnings-calendar"
ALLOWED={"symbol","date","time","lastUpdated","updated","fiscalDateEnding"}
def summarize(payload, universe):
    if not isinstance(payload,list):
        return {"schema_valid":False,"reason":"NON_LIST_NO_BODY_RETAINED","coverage_certified":False}
    records=[x for x in payload if isinstance(x,dict) and x.get("symbol") in universe]
    return {"schema_valid":True,"provider_record_count":len(payload),"universe_record_count":len(records),
            "observed_metadata_fields":sorted({k for x in records for k in x if k in ALLOWED}),
            "coverage_certified":False,"reason":"SINGLE_SNAPSHOT_NOT_COMPLETENESS_CERTIFICATION"}
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def probe(env,opener=None):
    opener=opener or urllib.request.build_opener(NoRedirect()).open
    out={"mode":"METADATA_ONLY_ENTITLEMENT_PROBE","checked_at":dt.datetime.now(dt.timezone.utc).isoformat(),
         "credentials_present":{"FMP_API_KEY":bool(env.get("FMP_API_KEY")),"TR_FMP_API_KEY":bool(env.get("TR_FMP_API_KEY")),
         "ETRADE_CONSUMER_KEY":bool(env.get("ETRADE_CONSUMER_KEY")),"ETRADE_API_KEY":bool(env.get("ETRADE_API_KEY"))},
         "price_requests":0,"broker_account_requests":0,"coverage_certified":False}
    key=env.get("FMP_API_KEY") or env.get("TR_FMP_API_KEY")
    if not key:
        out["FMP"]={"status":"CREDENTIAL_NOT_MAPPED_OR_NOT_CONFIGURED"}; return out
    from urllib.parse import urlencode
    today=dt.datetime.now(dt.timezone.utc).date()
    req=urllib.request.Request(BASE+"?"+urlencode({"from":today.isoformat(),"to":(today+dt.timedelta(days=42)).isoformat(),"apikey":key}),
                               headers={"User-Agent":"MULtipLY-S4P-metadata-probe"})
    try:
        with opener(req,timeout=30) as response:
            raw=response.read(2000001)
            if len(raw)>2000000: raise ValueError("oversized")
            payload=json.loads(raw)
            from tr_platform.research.swing11_s4p import ARCHIVE_SYMBOLS
            out["FMP"]={"status":"HTTP_200","wire_sha256":hashlib.sha256(raw).hexdigest(),"wire_bytes":len(raw),
                        **summarize(payload,set(FROZEN_SYMBOLS))}
    except urllib.error.HTTPError as e:
        out["FMP"]={"status":"HTTP_"+str(e.code),"response_body_retained":False}
    except Exception:
        out["FMP"]={"status":"TRANSPORT_OR_SCHEMA_FAILURE","response_body_retained":False}
    return out
if __name__=="__main__":
    result=probe(os.environ)
    with open("s4p-source-access-probe.json","w",encoding="utf-8") as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps(result,sort_keys=True))
