import type {Group} from '../model';
import universe from './top50.json' with {type:'json'};
export const TOP_50_STOCKS:readonly Group[]=universe.constituents.map(g=>({...g,short:g.name}));
export const TOP_50_AS_OF=universe.asOf;
export const TOP_50_SOURCE=universe.source;
export const MAX_TRACKED_SYMBOLS=80;
export function normalizeStockSymbol(value:string):string|null {
 const symbol=value.trim().replace(/^\$/,'').toUpperCase();
 return /^[A-Z][A-Z0-9.-]{0,9}$/.test(symbol)?symbol:null;
}
