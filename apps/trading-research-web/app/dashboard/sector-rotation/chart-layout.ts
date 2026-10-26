/** Shared plot geometry: every date has the same center in both charts. */
export function chartLayout(count:number) {
 const left=72,right=20,width=Math.max(720,left+count*24+right);
 const plotWidth=width-left-right,slot=plotWidth/Math.max(1,count);
 return {left,right,width,plotWidth,slot,bodyWidth:Math.min(14,slot*.6),labelEvery:Math.max(1,Math.ceil(70/slot))};
}
export type ScrollPane={scrollLeft:number;scrollWidth:number;clientWidth:number};
/** Absolute pixel linking, clamped to the common range; equal values do not write back. */
export function syncChartScroll(source:ScrollPane,peers:readonly (ScrollPane|null)[]):number {
 const panes=[source,...peers.filter((p):p is ScrollPane=>p!==null&&p!==source)];
 const max=Math.min(...panes.map(p=>Math.max(0,p.scrollWidth-p.clientWidth)));
 const offset=Math.max(0,Math.min(source.scrollLeft,max));
 for(const pane of panes)if(Math.abs(pane.scrollLeft-offset)>.01)pane.scrollLeft=offset;
 return offset;
}
