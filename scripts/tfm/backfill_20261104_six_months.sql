with recursive bars as materialized (select symbol,trade_date,open,high,low,close,run_id,collected_at,response_sha256,'v_sector_daily_latest'::text source_view from public.v_sector_daily_latest where symbol in ('SPY','XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY') and trade_date<=date '2026-11-03' union all select symbol,trade_date,open,high,low,close,run_id,collected_at,response_sha256,'v_stock_daily_latest'::text source_view from public.v_stock_daily_latest where symbol in ('ABBV','AMAT','BAC','BRK.B','CAT','COST','CVX','GE','GEV','GOOG','GS','HD','IBM','INTC','JNJ','JPM','KLAC','KO','LIN','LLY','LRCX','MA','MCD','MRK','MS','NFLX','PEP','PG','PM','QCOM','SNDK','TSLA','TXN','UNH','V','VZ','WFC','WMT','XOM') and trade_date<=date '2026-11-03' union all select symbol,trade_date,open,high,low,close,run_id,collected_at,response_sha256,'v_tech_daily_latest'::text source_view from public.v_tech_daily_latest where symbol in ('IGV','AAPL','AMD','AMZN','ANET','AVGO','CSCO','DELL','GOOGL','HPE','HPQ','META','MRVL','MSFT','MU','NVDA','ORCL','PLTR','STX','TSM','VRT','WDC') and trade_date<=date '2026-11-03'),
 calendar(friday,target_date,cohort) as (values ('2026-05-01','2026-05-04','MONDAY'),('2026-05-08','2026-05-11','MONDAY'),('2026-05-15','2026-05-18','MONDAY'),('2026-05-22','2026-05-26','TUESDAY_HOLIDAY'),('2026-05-29','2026-06-01','MONDAY'),('2026-06-05','2026-06-08','MONDAY'),('2026-06-12','2026-06-15','MONDAY'),('2026-06-26','2026-06-29','MONDAY'),('2026-07-10','2026-07-13','MONDAY'),('2026-07-17','2026-07-20','MONDAY'),('2026-07-24','2026-07-27','MONDAY'),('2026-07-31','2026-08-03','MONDAY'),('2026-08-07','2026-08-10','MONDAY'),('2026-08-14','2026-08-17','MONDAY'),('2026-08-21','2026-08-24','MONDAY'),('2026-08-28','2026-08-31','MONDAY'),('2026-09-04','2026-09-08','TUESDAY_HOLIDAY'),('2026-09-11','2026-09-14','MONDAY'),('2026-09-18','2026-09-21','MONDAY'),('2026-09-25','2026-09-28','MONDAY'),('2026-10-02','2026-10-05','MONDAY'),('2026-10-09','2026-10-12','MONDAY'),('2026-10-16','2026-10-19','MONDAY'),('2026-10-23','2026-10-26','MONDAY'),('2026-10-30','2026-11-02','MONDAY')),
 universe(symbol) as (values ('XLB'),('XLC'),('XLE'),('XLF'),('XLI'),('XLK'),('XLP'),('XLRE'),('XLU'),('XLV'),('XLY'),('IGV'),('AAPL'),('ABBV'),('AMAT'),('AMD'),('AMZN'),('ANET'),('AVGO'),('BAC'),('BRK.B'),('CAT'),('COST'),('CSCO'),('CVX'),('DELL'),('GE'),('GEV'),('GOOG'),('GOOGL'),('GS'),('HD'),('HPE'),('HPQ'),('IBM'),('INTC'),('JNJ'),('JPM'),('KLAC'),('KO'),('LIN'),('LLY'),('LRCX'),('MA'),('MCD'),('META'),('MRK'),('MRVL'),('MS'),('MSFT'),('MU'),('NFLX'),('NVDA'),('ORCL'),('PEP'),('PG'),('PLTR'),('PM'),('QCOM'),('SNDK'),('STX'),('TSLA'),('TSM'),('TXN'),('UNH'),('V'),('VRT'),('VZ'),('WDC'),('WFC'),('WMT'),('XOM')),
 spy as (select trade_date,close,row_number() over(order by trade_date) rn from bars where symbol='SPY'),
 ema(trade_date,close,rn,value) as (
  select trade_date,close,rn,close::numeric from spy where rn=1
  union all select s.trade_date,s.close,s.rn,round((2.000000000000000000000000000000/21)*s.close+(1-2.000000000000000000000000000000/21)*e.value,28) from spy s join ema e on s.rn=e.rn+1
 ),
 triplets as (
 select u.symbol,c.friday,c.target_date,c.cohort,
 (to_jsonb(t)-'trade_date')||jsonb_build_object('trade_date',to_char(t.trade_date,'YYYY-MM-DD')) thursday_bar,(to_jsonb(f)-'trade_date')||jsonb_build_object('trade_date',to_char(f.trade_date,'YYYY-MM-DD')) friday_bar,
 case when x.symbol is null then null else (to_jsonb(x)-'trade_date')||jsonb_build_object('trade_date',to_char(x.trade_date,'YYYY-MM-DD')) end target_bar,
 (f.high<t.high) qualifies,
 case when e.rn<20 or e.rn is null then 'UNKNOWN' when e.close>=e.value then 'SPY_ABOVE_EMA20' else 'SPY_BELOW_EMA20' end market_condition,
 (x.low<f.low) hit,(x.open<f.low) gap_through,
 greatest(0,(x.open-x.low)/nullif(x.open,0)*100) mfe_pct,
 greatest(0,(x.high-x.open)/nullif(x.open,0)*100) mae_pct,
 (x.close/nullif(x.open,0)-1)*100 close_return_pct
 from calendar c cross join universe u
 join bars t on t.symbol=u.symbol and t.trade_date=c.friday::date-1
 join bars f on f.symbol=u.symbol and f.trade_date=c.friday::date
 left join bars x on x.symbol=u.symbol and x.trade_date=c.target_date::date
 left join ema e on e.trade_date=c.friday::date
 )
 select * from triplets order by friday,symbol
