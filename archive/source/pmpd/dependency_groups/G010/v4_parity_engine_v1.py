from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import math
import pandas as pd

NY_TZ="America/New_York"

@dataclass(frozen=True)
class V4Signal:
    symbol:str
    trade_date:str
    direction:str
    signal_timestamp_utc:str
    signal_timestamp_et:str
    signal_price:float
    final_level:float
    pm_level:float
    pd_level:float
    atr14:float
    penetration_pct_atr:float
    body_range_pct:float
    close_position_pct:float
    range_atr_pct:float
    bars_to_confirm:int
    strength_score:float
    grade:str
    grade_family:str
    profile:str

def _grade(score:float)->tuple[str,str]:
    if score>=97: return "A+","A"
    if score>=93: return "A","A"
    if score>=90: return "A-","A"
    if score>=87: return "B+","B"
    if score>=83: return "B","B"
    if score>=80: return "B-","B"
    if score>=77: return "C+","C"
    if score>=73: return "C","C"
    if score>=70: return "C-","C"
    return "Weak","Weak"

def _profile(pen, rng_atr, body, close_pos, bars):
    if (((pen>=100 and rng_atr>=100) or (rng_atr>=200 and pen>=40))
        and body>=50 and close_pos>=70 and bars<=1):
        return "Explosive"
    if pen>=60 and rng_atr>=100 and body>=60 and close_pos>=80 and bars<=1:
        return "Controlled Strong"
    if pen>=40 and rng_atr>=75 and body>=65 and close_pos>=80 and bars<=1:
        return "Efficient Moderate"
    if pen>=60 and rng_atr>=100 and body>=65 and close_pos>=80 and bars in (2,3):
        return "Delayed Strong"
    if body>=70 and close_pos>=80 and bars<=1 and (pen<40 or rng_atr<75):
        return "Pretty but Weak"
    return "Unclassified"

def _strength_score(pen, body, close_pos, rng_atr, bars):
    pen_pts=max(0.0,min(40.0,40.0*(pen/100.0)))
    body_pts=max(0.0,min(15.0,15.0*(body/100.0)))
    close_norm=max(0.0,min(1.0,(close_pos-50.0)/50.0))
    close_pts=15.0*close_norm
    range_pts=max(0.0,min(25.0,25.0*(rng_atr/150.0)))
    speed_pts={0:5.0,1:4.5,2:3.0,3:1.5}.get(int(bars),0.0)
    return pen_pts+body_pts+close_pts+range_pts+speed_pts

def _resample_5m_rth(df:pd.DataFrame)->pd.DataFrame:
    x=df.copy()
    et=pd.to_datetime(x["timestamp_et"])
    x=x.assign(_et=et)
    x=x[x["session"].eq("RTH")].copy()
    if x.empty: return x
    x=x.set_index("_et").sort_index()
    agg=x.resample("5min", origin="start_day", offset="9h30min",
                   label="left", closed="left").agg(
        open=("open","first"), high=("high","max"), low=("low","min"),
        close=("close","last"), volume=("volume","sum"),
        timestamp_utc=("timestamp_utc","last"), trade_date=("trade_date","last")
    )
    agg=agg.dropna(subset=["open","high","low","close"]).reset_index().rename(columns={"_et":"timestamp_et"})
    return agg

def _true_range(df5):
    prev_close=df5["close"].shift(1)
    tr=pd.concat([
        (df5["high"]-df5["low"]).abs(),
        (df5["high"]-prev_close).abs(),
        (df5["low"]-prev_close).abs()
    ],axis=1).max(axis=1)
    return tr

def _prior_rth_levels(raw:pd.DataFrame):
    rth=raw[raw["session"].eq("RTH")].copy()
    if rth.empty: return {}
    g=rth.groupby("trade_date").agg(PDH=("high","max"),PDL=("low","min")).sort_index()
    dates=list(g.index)
    out={}
    for i in range(1,len(dates)):
        out[str(dates[i])]=(float(g.iloc[i-1]["PDH"]),float(g.iloc[i-1]["PDL"]))
    return out

def run_v4_symbol(raw:pd.DataFrame, *, symbol:str)->pd.DataFrame:
    x=raw.copy()
    x["trade_date"]=x["trade_date"].astype(str)
    prior=_prior_rth_levels(x)
    f5=_resample_5m_rth(x)
    if f5.empty: return pd.DataFrame()

    f5["tr"]=_true_range(f5)
    f5["atr14"]=f5["tr"].rolling(14,min_periods=14).mean()

    rows=[]
    for trade_date, day5 in f5.groupby(f5["trade_date"].astype(str), sort=True):
        if trade_date not in prior: continue
        pre=x[(x["trade_date"].eq(trade_date)) & x["session"].eq("PRE")]
        if pre.empty: continue
        pmh=float(pre["high"].max()); pml=float(pre["low"].min())
        pdh,pdl=prior[trade_date]
        bull_final=max(pmh,pdh); bear_final=min(pml,pdl)

        armed={"BULL":False,"BEAR":False}
        arm_bar={"BULL":None,"BEAR":None}
        can_rearm={"BULL":True,"BEAR":True}

        for idx,bar in day5.reset_index(drop=True).iterrows():
            if pd.isna(bar["atr14"]) or float(bar["atr14"])<=0: continue
            o,h,l,c=map(float,[bar["open"],bar["high"],bar["low"],bar["close"]])
            rng=h-l
            if rng<=0: continue

            # Re-arm requires a completed close through the level after a prior signal.
            if not can_rearm["BULL"] and c<=bull_final: can_rearm["BULL"]=True
            if not can_rearm["BEAR"] and c>=bear_final: can_rearm["BEAR"]=True

            for direction,final_level,pm_level,pd_level in [
                ("BULL",bull_final,pmh,pdh),("BEAR",bear_final,pml,pdl)
            ]:
                beyond = c>final_level if direction=="BULL" else c<final_level
                reset = c<=final_level if direction=="BULL" else c>=final_level

                if armed[direction] and reset:
                    armed[direction]=False; arm_bar[direction]=None

                if (not armed[direction]) and can_rearm[direction] and beyond:
                    armed[direction]=True; arm_bar[direction]=idx

                if not armed[direction]:
                    continue

                bars_to_confirm=idx-int(arm_bar[direction])
                atr=float(bar["atr14"])
                penetration=((c-final_level)/atr*100.0) if direction=="BULL" else ((final_level-c)/atr*100.0)
                body=abs(c-o)/rng*100.0
                directional=(c>o) if direction=="BULL" else (c<o)
                close_pos=((c-l)/rng*100.0) if direction=="BULL" else ((h-c)/rng*100.0)
                rng_atr=rng/atr*100.0

                core_pass=(penetration>=10.0 and directional and body>=50.0)
                if not core_pass:
                    continue

                score=_strength_score(penetration,body,close_pos,rng_atr,bars_to_confirm)
                grade,fam=_grade(score)
                prof=_profile(penetration,rng_atr,body,close_pos,bars_to_confirm)

                rows.append(asdict(V4Signal(
                    symbol=symbol, trade_date=trade_date, direction=direction,
                    signal_timestamp_utc=str(pd.to_datetime(bar["timestamp_utc"])),
                    signal_timestamp_et=str(pd.to_datetime(bar["timestamp_et"])+pd.Timedelta(minutes=5)),
                    signal_price=c, final_level=final_level, pm_level=pm_level, pd_level=pd_level,
                    atr14=atr, penetration_pct_atr=penetration, body_range_pct=body,
                    close_position_pct=close_pos, range_atr_pct=rng_atr,
                    bars_to_confirm=bars_to_confirm, strength_score=score,
                    grade=grade, grade_family=fam, profile=prof
                )))
                armed[direction]=False
                arm_bar[direction]=None
                can_rearm[direction]=False

    return pd.DataFrame(rows)

def evaluate_v4_outcomes(raw:pd.DataFrame, signals:pd.DataFrame)->pd.DataFrame:
    if signals.empty: return signals.copy()
    x=raw.copy()
    x["trade_date"]=x["trade_date"].astype(str)
    f5=_resample_5m_rth(x)
    out=[]
    for _,s in signals.iterrows():
        day=f5[f5["trade_date"].astype(str).eq(str(s["trade_date"]))].copy()
        sig_end=pd.to_datetime(s["signal_timestamp_et"])
        future=day[pd.to_datetime(day["timestamp_et"])>=sig_end].copy()
        entry=float(s["signal_price"]); direction=s["direction"]
        fav_t=entry*(1.005 if direction=="BULL" else 0.995)
        adv_t=entry*(0.995 if direction=="BULL" else 1.005)
        outcome="NEITHER"; ff=None; fa=None; mfe=0.0; mae=0.0
        for _,b in future.iterrows():
            hi=float(b["high"]); lo=float(b["low"]); ts=str(b["timestamp_et"])
            if direction=="BULL":
                fav=hi>=fav_t; adv=lo<=adv_t
                mfe=max(mfe,(hi-entry)/entry*100.0); mae=max(mae,(entry-lo)/entry*100.0)
            else:
                fav=lo<=fav_t; adv=hi>=adv_t
                mfe=max(mfe,(entry-lo)/entry*100.0); mae=max(mae,(hi-entry)/entry*100.0)
            if fav and adv:
                outcome="BOTH"; ff=ts; fa=ts; break
            if fav:
                outcome="FAVORABLE_FIRST"; ff=ts; break
            if adv:
                outcome="ADVERSE_FIRST"; fa=ts; break
        r=dict(s)
        r.update(v4_primary_outcome=outcome, first_favorable_timestamp=ff,
                 first_adverse_timestamp=fa, mfe_pct=mfe, mae_pct=mae)
        out.append(r)
    return pd.DataFrame(out)
