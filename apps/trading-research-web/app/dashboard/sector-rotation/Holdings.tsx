import type { Group } from './model';
import snapshots from './holdings.json';
import styles from './tracker.module.css';
type Snapshot = {asOf:string;reviewedOn:string;sourceName:string;sourceUrl:string;holdings:{symbol:string;name:string;weightPct:number}[]};
const data:Record<string,Snapshot>=snapshots;
const names:Record<string,string>={AAPL:'Apple',DELL:'Dell Technologies',HPQ:'HP',HPE:'Hewlett Packard Enterprise',ANET:'Arista Networks',CSCO:'Cisco Systems',STX:'Seagate Technology',WDC:'Western Digital',NVDA:'NVIDIA',AMD:'Advanced Micro Devices',AVGO:'Broadcom',MRVL:'Marvell Technology',MU:'Micron Technology',TSM:'Taiwan Semiconductor',MSFT:'Microsoft',GOOGL:'Alphabet · Class A',AMZN:'Amazon',META:'Meta Platforms',ORCL:'Oracle',PLTR:'Palantir Technologies',VRT:'Vertiv'};
export default function Holdings({group}:{group:Group}) {
  const basket=group.kind==='basket';
  const snapshot=data[group.symbol];
  const rows=basket?(group.members??[]).map(symbol=>({symbol,name:names[symbol]??symbol,weightPct:100/group.members!.length})):snapshot?.holdings;
  if(!rows?.length) return <section className={styles.holdings}><h3>Top 5 stock holdings</h3><p>Verified holdings are unavailable for this ETF.</p></section>;
  const combined=rows.reduce((sum,row)=>sum+row.weightPct,0);
  return <section className={styles.holdings} aria-label={`${group.symbol} ${basket?'basket weights':'top five holdings'}`}>
    <h3>{basket?'Basket members & weights':'Top 5 stock holdings'}</h3>
    <p className={styles.holdingsMeta}>{basket?'Equal daily target weights · All members shown':`${group.symbol} · Fund holdings as of ${snapshot.asOf}`}</p>
    <table><caption className={styles.srOnly}>{basket?'All basket members with equal daily target weights':`Five largest stock holdings as a percentage of ${group.symbol}, dated ${snapshot.asOf}`}</caption><thead><tr><th scope="col">Stock</th><th scope="col">{basket?'Basket %':'ETF %'}</th></tr></thead><tbody>{rows.map(row=><tr key={row.symbol}><th scope="row"><strong>{row.symbol}</strong><span>{row.name}</span></th><td>{row.weightPct.toFixed(2)}%</td></tr>)}</tbody><tfoot><tr><th scope="row">{basket?'Total target weight':'Top 5 combined'}</th><td>{combined.toFixed(2)}%</td></tr></tfoot></table>
    {basket?<p className={styles.holdingsNote}>All members have the same target weight at each daily rebalance. This is a custom tracking basket.</p>:<><p className={styles.holdingsNote}>Dated issuer snapshot. Weights are percentages of the whole ETF and may change. Selecting an older price date does not change this holdings snapshot.</p><a href={snapshot.sourceUrl} target="_blank" rel="noreferrer">Source: {snapshot.sourceName} ↗</a><p className={styles.holdingsNote}>Snapshot reviewed {snapshot.reviewedOn}. Holdings snapshots are separate from overnight price updates.</p></>}
  </section>;
}
