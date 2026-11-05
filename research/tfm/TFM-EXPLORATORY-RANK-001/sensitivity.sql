with raw as materialized (
select symbol,trade_date,close from public.v_stock_daily_latest where symbol in ('ABBV','AMAT','BAC','BRK.B','CAT','COST','CVX','GE','GEV','GOOG','GS','HD','IBM','INTC','JNJ','JPM','KLAC','KO','LIN','LLY','LRCX','MA','MCD','MRK','MS','NFLX','PEP','PG','PM','QCOM','SNDK','TSLA','TXN','UNH','V','VZ','WFC','WMT','XOM')
union all select symbol,trade_date,close from public.v_tech_daily_latest where symbol in ('AAPL','AMD','AMZN','ANET','AVGO','CSCO','DELL','GOOGL','HPE','HPQ','META','MRVL','MSFT','MU','NVDA','ORCL','PLTR','STX','TSM','VRT','WDC')
), ma as(select *,avg(close) over(partition by symbol order by trade_date rows 19 preceding) ma20,avg(close) over(partition by symbol order by trade_date rows 49 preceding) ma50,count(*) over(partition by symbol order by trade_date rows 49 preceding) warm from raw),
f0 as(select s.symbol,s.friday,s.target_date,s.payload->>'market_condition' market,
(s.payload#>>'{reference_bars,0,open}')::numeric th_o,(s.payload#>>'{reference_bars,0,high}')::numeric th_h,(s.payload#>>'{reference_bars,0,low}')::numeric th_l,(s.payload#>>'{reference_bars,0,close}')::numeric th_c,
(s.payload#>>'{reference_bars,1,open}')::numeric f_o,(s.payload#>>'{reference_bars,1,high}')::numeric f_h,(s.payload#>>'{reference_bars,1,low}')::numeric f_l,(s.payload#>>'{reference_bars,1,close}')::numeric f_c,
(o.payload->>'gap_through')::boolean gap,(o.payload->>'hit')::boolean hit,(o.payload->>'mfe_pct')::numeric mfe,(o.payload->>'mae_pct')::numeric mae,
case when abs(ma.close-(s.payload->>'friday_close')::numeric)<0.000001 and ma.warm>=50 then ma.ma20 end ma20,
case when abs(ma.close-(s.payload->>'friday_close')::numeric)<0.000001 and ma.warm>=50 then ma.ma50 end ma50
from public.tfm_setups s join public.tfm_outcomes o using(setup_key) left join ma on ma.symbol=s.symbol and ma.trade_date=s.friday
where s.rule_version='tfm-bearish-v2' and s.qualifies and s.payload->>'asset_class'='STOCK' and s.cohort='MONDAY'),
f as(select *,case when target_date<=date '2026-08-03' then 'DEV' when target_date<date '2026-11-02' then 'CHECK' else 'LAST_WEEK' end phase,
(hit or (mfe>=0.5 and mae>=0 and mfe>=2*mae)) win,
(not hit and mfe>=0.5 and mae>=0 and mfe>=2*mae) alt,
(f_c-f_l)/nullif(f_h-f_l,0) loc,(f_h-f_l)/nullif(th_h-th_l,0) compression,100*(f_c-f_l)/f_c distance,100*(f_h-f_l)/f_c range_pct,100*(th_h-f_h)/th_h high_drop,100*(f_o-th_c)/th_c opening_gap from f0),
buckets as(select f.*,x.feature,x.bucket from f cross join lateral(values
('Friday close location',case when loc<1.0/3 then 'LOWER THIRD' when loc<2.0/3 then 'MIDDLE THIRD' else 'UPPER THIRD' end),
('Friday candle',case when f_c<f_o then 'RED' else 'GREEN_OR_FLAT' end),
('Thursday candle',case when th_c<th_o then 'RED' else 'GREEN_OR_FLAT' end),
('Close vs Thursday',case when f_c<th_c then 'LOWER' else 'HIGHER_OR_EQUAL' end),
('Friday low',case when f_l<th_l then 'LOWER LOW' else 'INSIDE DAY' end),
('Range compression',case when compression<=0.75 then '<=0.75' when compression<=1.25 then '0.75-1.25' else '>1.25' end),
('Distance to Friday low',case when distance<=0.5 then '<=0.5%' when distance<=1.5 then '0.5-1.5%' else '>1.5%' end),
('Friday range',case when range_pct<=2 then '<=2%' when range_pct<=4 then '2-4%' else '>4%' end),
('Lower high depth',case when high_drop<=0.5 then '<=0.5%' when high_drop<=1.5 then '0.5-1.5%' else '>1.5%' end),
('Friday opening gap',case when opening_gap<=-0.5 then 'GAP DOWN >=0.5%' when opening_gap>=0.5 then 'GAP UP >=0.5%' else 'NEUTRAL' end),
('Stock SMA20',case when ma20 is null then 'UNAVAILABLE' when f_c<ma20 then 'BELOW' else 'ABOVE' end),
('Stock SMA50',case when ma50 is null then 'UNAVAILABLE' when f_c<ma50 then 'BELOW' else 'ABOVE' end),
('SPY EMA20',market),
('Combo lower-low red',case when f_l<th_l and f_c<f_o then 'YES' else 'NO' end),
('Combo SMA20 lower-third',case when ma20 is null then 'UNAVAILABLE' when f_c<ma20 and loc<1.0/3 then 'YES' else 'NO' end)
)x(feature,bucket)),
baseweek as(select phase,target_date,avg(win::int)::numeric rate from f group by 1,2),
w as(select b.feature,b.bucket,b.phase,b.target_date,avg(b.win::int)::numeric rate from buckets b group by 1,2,3,4),
wd as(select w.feature,w.bucket,w.phase,round(100*avg(w.rate-b.rate),2) weekly_lift from w join baseweek b using(phase,target_date) group by 1,2,3),
a as(select feature,bucket,phase,count(*) n,count(distinct target_date) weeks,sum(win::int) wins,sum(hit::int) hits,sum(alt::int) alts,round(100*avg(win::int),2) rate,round(avg(mfe),2) mfe,round(avg(mae),2) mae from buckets group by 1,2,3)
select case when loc<1.0/3 then 'LOWER THIRD' else 'OTHER CLOSES' end group_name,count(*) n,sum(hit::int) pattern_hits,sum(alt::int) alternates,sum(win::int) combined,sum(gap::int) gap_throughs,sum((mfe>=0.5 and mfe>=2*mae)::int) favorable_excursion_cases from f where phase<>'LAST_WEEK' group by 1 order by 1