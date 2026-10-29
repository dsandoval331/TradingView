import type {Group} from './model';
import styles from './tracker.module.css';
export default function SymbolReference({groups,title='Sector ETF reference'}:{groups:readonly Group[];title?:string}){
 return <section className={styles.symbolReference} aria-label={title}><h2>{title}</h2><dl>{groups.map(group=><div key={group.symbol}><dt>{group.symbol}</dt><dd>{group.name}</dd></div>)}</dl></section>;
}
