import type {Group} from '../model';
export const FREQUENT_STOCKS:readonly Group[]=[{symbol:'MSFT',name:'Microsoft',short:'Microsoft'},{symbol:'AAPL',name:'Apple',short:'Apple'},{symbol:'NVDA',name:'NVIDIA',short:'NVIDIA'},{symbol:'TSLA',name:'Tesla',short:'Tesla'},{symbol:'AMD',name:'Advanced Micro Devices',short:'AMD'}];
export function normalizeStockSymbol(value:string):string|null {
 const symbol=value.trim().replace(/^\$/,'').toUpperCase();
 return /^[A-Z][A-Z0-9.-]{0,9}$/.test(symbol)?symbol:null;
}
