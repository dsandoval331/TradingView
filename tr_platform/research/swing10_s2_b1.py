"""SWING_10D_EDGE S2-B1 broad factor discovery on canonical daily panel.
No optimization. Computes point-in-time-safe factor observations and forward close returns.
Outputs CSV summaries for long/short factor tails at 1,2,3,5,7,10 days.
"""
from __future__ import annotations
import argparse, pathlib
import numpy as np, pandas as pd
from sqlalchemy import create_engine
H=[1,2,3,5,7,10]
def main():
 p=argparse.ArgumentParser();p.add_argument("--db-url",required=True);p.add_argument("--out",default="research_outputs/swing10/s2_b1");a=p.parse_args()
 e=create_engine(a.db_url)
 q="select symbol,trade_date,open,high,low,close,volume from market_daily_history order by symbol,trade_date"
 d=pd.read_sql(q,e,parse_dates=["trade_date"]); g=d.groupby("symbol",group_keys=False)
 d["r1"]=g.close.pct_change(); d["mom5"]=g.close.pct_change(5); d["mom10"]=g.close.pct_change(10); d["mom20"]=g.close.pct_change(20)
 d["gap"]=d.open/g.close.shift(1)-1; d["rvol20"]=d.volume/g.volume.transform(lambda s:s/s.shift(1).rolling(20).mean())
 prev=g.close.shift(1); tr=pd.concat([(d.high-d.low),(d.high-prev).abs(),(d.low-prev).abs()],axis=1).max(axis=1)
 d["atrp14"]=tr.groupby(d.symbol).transform(lambda s:s.shift(1).rolling(14).mean())/prev
 d["high52"]=d.close/g.close.transform(lambda s:s.shift(1).rolling(252,min_periods=120).max())-1
 for h in H:d[f"f{h}"]=g.close.shift(-h)/d.close-1
 specs={"RET_MOM":"mom10","SHORT_REV":"r1","VOL_TURN":"rvol20","HIGH52":"high52","VOL_REGIME":"atrp14","GAP_OVN":"gap"}
 rows=[]
 for fac,col in specs.items():
  x=d.dropna(subset=[col]).copy()
  if len(x)<20:continue
  x["bucket"]=pd.qcut(x[col],5,labels=False,duplicates="drop")
  lo,hi=x.bucket.min(),x.bucket.max()
  for side,b in [("long_high",hi),("long_low",lo),("short_high",hi),("short_low",lo)]:
   z=x[x.bucket==b]
   for h in H:
    v=z[f"f{h}"].dropna()
    if side.startswith("short"):v=-v
    if len(v):rows.append([fac,side,h,len(v),v.mean(),v.median(),(v>0).mean(),v.quantile(.25),v.quantile(.75)])
 out=pd.DataFrame(rows,columns=["factor","side_tail","horizon_days","n","mean_return","median_return","win_rate","q25","q75"])
 path=pathlib.Path(a.out);path.mkdir(parents=True,exist_ok=True)
 out.to_csv(path/"factor_tail_summary.csv",index=False)
 print(out.to_json(orient="records"))
if __name__=="__main__":main()
