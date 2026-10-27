/** Curated current sector proxies, not historical constituent membership. Unknown symbols are reported. */
export const METHOD_ONE_MAPPING_VERSION='sector-proxies-2026-10-26';
const groups:Record<string,string[]>={
 XLK:['NVDA','AAPL','MSFT','AVGO','AMD','MU','INTC','CSCO','AMAT','LRCX','PLTR','KLAC','TXN','IBM','ORCL','QCOM','SNDK','SNOW'],
 XLC:['GOOG','GOOGL','META','NFLX','VZ'],XLY:['AMZN','TSLA','HD','MCD'],
 XLF:['BRK.B','JPM','V','MA','BAC','GS','WFC','MS'],XLV:['LLY','JNJ','ABBV','UNH','MRK'],
 XLP:['WMT','COST','PG','KO','PM','PEP'],XLI:['CAT','GE','GEV'],XLE:['XOM','CVX'],XLB:['LIN'],
};
export const METHOD_ONE_SECTORS:Readonly<Record<string,string>>=Object.fromEntries(Object.entries(groups).flatMap(([sector,symbols])=>symbols.map(symbol=>[symbol,sector])));
