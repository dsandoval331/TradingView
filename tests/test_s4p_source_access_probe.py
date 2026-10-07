import io,json,urllib.error
from cloud_compute.s4p_source_access_probe import probe,summarize
class Response:
 def __init__(self,body):self.body=body
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read(self,n):return self.body[:n]
def test_missing_no_requests():
 def forbidden(*a,**k):raise AssertionError()
 r=probe({},forbidden)
 assert r["FMP"]["status"]=="CREDENTIAL_NOT_MAPPED_OR_NOT_CONFIGURED"
def test_success_never_publishes_outcomes_secret_or_values():
 secret="syntheticSecret"
 def open_(req,**kwargs):
  assert req.full_url.startswith("https://financialmodelingprep.com/stable/earnings-calendar?")
  return Response(json.dumps([{"symbol":"AAPL","date":"synthetic-date","time":"amc","epsActual":999,"secret":secret}]).encode())
 r=probe({"FMP_API_KEY":secret},open_);text=json.dumps(r)
 assert secret not in text and "epsActual" not in text and "synthetic-date" not in text
 assert r["FMP"]["universe_record_count"]==1 and not r["coverage_certified"]
def test_http_body_not_logged():
 def open_(*a,**k):raise urllib.error.HTTPError("secret-url",403,"secret-msg",{},io.BytesIO(b"secret"))
 r=probe({"FMP_API_KEY":"private"},open_)
 assert r["FMP"]["status"]=="HTTP_403" and "secret" not in json.dumps(r)
def test_transport_url_not_logged():
 def open_(*a,**k):raise RuntimeError("private-url-credential")
 r=probe({"FMP_API_KEY":"private"},open_)
 assert "private" not in json.dumps(r)
def test_oversize_fail_closed():
 r=probe({"FMP_API_KEY":"x"},lambda *a,**k:Response(b"x"*2000001))
 assert r["FMP"]["status"]=="TRANSPORT_OR_SCHEMA_FAILURE"
def test_nonlist_or_empty_does_not_certify_absence():
 assert not summarize({"error":"credential"},set())["schema_valid"]
 assert not summarize([],{"AAPL"})["coverage_certified"]
def test_broker_credentials_do_not_enable_requests():
 r=probe({"ETRADE_CONSUMER_KEY":"private"},lambda *a,**k: (_ for _ in ()).throw(AssertionError()))
 assert r["broker_account_requests"]==0 and r["price_requests"]==0
