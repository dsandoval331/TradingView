'use client';
import {useEffect,useRef,useState} from 'react';
import {METHOD_ONE_DEFAULTS,validateMethodOne,methodOneKey,type MethodOneConfig,type MethodOneResult} from './method-one';
import styles from './tracker.module.css';
export type MethodOneRunner=(config:MethodOneConfig)=>Promise<MethodOneResult>;
const STORAGE_KEY='multiply-method-one-settings-v1';
const selects:{key:keyof MethodOneConfig;label:string;options:readonly (readonly [string,string])[]}[]=[
 {key:'instruments',label:'Instruments',options:[['both','ETFs and stocks'],['etfs','Sector ETFs'],['stocks','Stocks']]},
 {key:'universe',label:'Stock universe',options:[['all','All tracked stocks'],['top50','Current Top 50']]},
 {key:'direction',label:'Directions',options:[['both','Longs and Shorts'],['long','Longs'],['short','Shorts']]},
 {key:'setups',label:'Setups',options:[['both','Pullbacks and breakouts'],['pullback','Pullbacks'],['breakout','Breakouts']]},
 {key:'leadership',label:'Sector leadership',options:[['both','Both conditions'],['relative','Relative performance'],['mansfield','Mansfield strength']]},
 {key:'pullback',label:'Pullback EMA',options:[['fast','Fast EMA reclaim'],['slow','Slow EMA reclaim'],['either','Either EMA reclaim']]},
 {key:'marketFilter',label:'SPY market filter',options:[['stack','Close / fast / slow EMA stack'],['slow','Close versus slow EMA'],['none','None']]},
 {key:'ranking',label:'Stock ranking',options:[['relative','Main-period strength vs sector'],['mansfield','Mansfield strength vs sector'],['shortTerm','Short-period strength vs sector']]},
 {key:'repeats',label:'Repeat signals',options:[['every','Every qualifying session'],['first','First qualifying session only']]},
];
const numbers:{key:keyof MethodOneConfig;label:string}[]=[{key:'relativePeriod',label:'Leadership lookback'},{key:'momentumPeriod',label:'Leadership improvement window'},{key:'mansfieldPeriod',label:'Mansfield average period'},{key:'fastEma',label:'Fast EMA period'},{key:'slowEma',label:'Slow EMA period'},{key:'breakoutPeriod',label:'Breakout range period'},{key:'rankPeriod',label:'Ranking main period'},{key:'tiePeriod',label:'Ranking short / tie period'},{key:'topN',label:'Stocks per sector / direction'}];
export default function MethodOnePanel({run,onResult}:{run:MethodOneRunner;onResult:(result:MethodOneResult)=>void}){
 const [draft,setDraft]=useState<MethodOneConfig>({...METHOD_ONE_DEFAULTS}),[busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<MethodOneResult|null>(null);const generation=useRef(0);
 async function apply(value:MethodOneConfig){const token=++generation.current;setBusy(true);setError('');try{const config=validateMethodOne(value);const next=await run(config);if(generation.current!==token)return;setResult(next);onResult(next);try{localStorage.setItem(STORAGE_KEY,JSON.stringify(config));}catch{ /* Browser persistence is optional. */ }}catch(e){if(generation.current===token)setError(e instanceof Error?e.message:'Method 1 screen unavailable');}finally{if(generation.current===token)setBusy(false);}}
 useEffect(()=>{let initial:MethodOneConfig={...METHOD_ONE_DEFAULTS};try{const saved=localStorage.getItem(STORAGE_KEY);if(saved)initial=validateMethodOne(JSON.parse(saved));}catch{ /* Restore valid defaults. */ }setDraft(initial);void apply(initial);return()=>{generation.current++;};
 // run is a stable server action; onResult is the parent state setter.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[run,onResult]);
 return <div className={styles.methodOnePanel}><details><summary>Method #1 settings</summary><p>Calculated retrospective screen · Defaults are configurable. Apply settings to recalculate Method #1; Method #2 saved entries remain available. Settings are remembered in this browser.</p>
 <form onSubmit={event=>{event.preventDefault();void apply(draft);}}><div className={styles.methodOneGrid}>
 {selects.map(field=><label key={field.key}>{field.label}<select value={String(draft[field.key])} onChange={event=>setDraft({...draft,[field.key]:event.target.value})}>{field.options.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>)}
 {numbers.map(field=><label key={field.key}>{field.label}<input type="number" min="1" max={field.key==='topN'?10:260} required value={String(draft[field.key])} onChange={event=>setDraft({...draft,[field.key]:Number(event.target.value)})}/></label>)}
 <label>Screen from<input type="date" required value={draft.startDate} onChange={event=>setDraft({...draft,startDate:event.target.value})}/></label></div><div className={styles.methodOneActions}><button type="submit" disabled={busy}>{busy?'Calculating…':'Apply settings'}</button><button type="button" disabled={busy} onClick={()=>{const defaults={...METHOD_ONE_DEFAULTS};setDraft(defaults);void apply(defaults);}}>Reset defaults</button></div></form>
 <p>All numeric periods count trading sessions. Relative leadership requires positive main-period performance versus SPY and a rising ratio over the improvement window; Mansfield requires strength above zero and rising over that window. Shorts use the inverse. Pullbacks require a closing cross of the selected EMA. Breakouts use prior-session highs/lows, excluding the signal session.</p>
 <p>Stocks are ranked after setup qualification, separately for each sector and direction. Up to the selected count of distinct stocks can qualify; a stock qualifying for both setups gets a row for each. Ranking ties use the short period, then ticker. Repeat counts are consecutive fully qualifying trading sessions, including rank selection; missing data or loss of qualification breaks the observed streak. Open/Close views share that signal history.</p>
 <p>Uses current tracked membership and curated sector proxies, not historical index membership. Changes to settings or historical prices can restate calculated results and Archive. This is a reference-price screen, not a validated strategy or an exit plan.</p></details>
 {busy&&<p role="status">Calculating Method #1…</p>}{error&&<p role="alert">{error}. {result?'Last successful screen retained.':'No Method #1 result is available yet.'}</p>}{result&&<p className={styles.relativeMeta}>Method #1: {result.suggestions.length} calculated matches since {result.config.startDate} · {result.stockCount} mapped stocks screened globally · Price data through {result.latestSession??'unavailable'}</p>}
 {result&&methodOneKey(draft)!==result.configKey&&<p role="status">Draft settings have not been applied. Tables show the last successful configuration.</p>}
 {result&&<p className={styles.relativeMeta}>Applied: {selects.filter(field=>['leadership','instruments','direction','setups','ranking','repeats'].includes(field.key)).map(field=>`${field.label}: ${field.options.find(([value])=>value===result.config[field.key])?.[1]}`).join(' · ')} · Top {result.config.topN}</p>}
 {result&&result.unmapped.length>0&&<p role="status">No sector mapping yet; excluded from stock ranking: {result.unmapped.join(', ')}.</p>}</div>;
}
