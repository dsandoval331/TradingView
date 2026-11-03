import Link from 'next/link';
import styles from './domains.module.css';
export const DOMAIN_SECTIONS=[
 {id:'research',name:'Research',path:'M10 3h4m-3 0v7l-6 9a1 1 0 0 0 1 2h12a1 1 0 0 0 1-2l-6-9V3M8 15h8'},
 {id:'trading-systems',name:'Trading Systems',path:'M3 19h18M5 15l4-6 4 3 6-8M15 4h4v4'},
 {id:'trading-tools',name:'Trading Tools',path:'M4 7h16M4 17h16M8 4v6M16 14v6M4 12h16'},
 {id:'osi-analysis',name:'OSI Analysis',path:'M4 20V10h4v10M10 20V4h4v16M16 20v-8h4v8'},
 {id:'trade-reviews-analysis',name:'Trade Reviews & Analysis',path:'M8 4H5v17h14V4h-3M8 3h8v4H8zM8 12l2 2 5-4M8 18h8'},
 {id:'platform-infrastructure',name:'Platform Infrastructure',path:'M4 3h16v7H4zM4 14h16v7H4zM7 6h.01M7 17h.01M11 6h6M11 17h6'},
] as const;
export default function DomainNavigation(){return <nav className={styles.row} aria-label="MULtipLY major sections">{DOMAIN_SECTIONS.map(item=><Link key={item.id} className={styles.card} href={item.id==='osi-analysis'?'/dashboard/osi-analysis':`/dashboard/sections/${item.id}`}><svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={item.path}/></svg><span>{item.name}</span></Link>)}</nav>;}
