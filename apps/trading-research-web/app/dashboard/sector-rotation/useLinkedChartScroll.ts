'use client';
import {useCallback,useEffect,useRef} from 'react';
import type {UIEvent} from 'react';
import {syncChartScroll} from './chart-layout';
export default function useLinkedChartScroll(windowKey:string) {
 const performanceRef=useRef<HTMLDivElement>(null),priceRef=useRef<HTMLDivElement>(null);
 const onScroll=useCallback((event:UIEvent<HTMLDivElement>)=>{
  syncChartScroll(event.currentTarget,[performanceRef.current,priceRef.current]);
 },[]);
 useEffect(()=>{
  const align=()=>{const source=performanceRef.current??priceRef.current;if(source)syncChartScroll(source,[performanceRef.current,priceRef.current]);};
  align();
  if(typeof ResizeObserver==='undefined')return;
  const observer=new ResizeObserver(align);
  for(const ref of [performanceRef,priceRef])if(ref.current)observer.observe(ref.current);
  return ()=>observer.disconnect();
 },[windowKey]);
 return {performanceRef,priceRef,onScroll};
}
