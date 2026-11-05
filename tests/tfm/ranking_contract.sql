-- Synthetic fixtures only. No persisted signals, reviews, rewards or research outcomes.
do $$
declare bar jsonb; th jsonb; rows jsonb; scored jsonb; reviewed jsonb;
begin
 bar:=jsonb_build_object('symbol','AAA','trade_date','2026-11-06','open',99,'high',100,'low',97,'close',97.6,'run_id','fixture','response_sha256',repeat('a',64));
 th:=bar||jsonb_build_object('trade_date','2026-11-05','high',101,'close',99);
 rows:=jsonb_build_array(jsonb_build_object('setup_key','fixture','symbol','AAA','friday','2026-11-06','qualifies',true,'payload',jsonb_build_object('reference_bars',jsonb_build_array(th,bar))));
 scored:=public.tfm_score_candidates(rows);
 if abs((scored->0->>'score')::numeric-86)>0.000001 then raise exception 'SCORE_COMPONENTS_FAILED: %',scored;end if;
 scored:=public.tfm_score_candidates(rows||jsonb_build_array(jsonb_set(rows->0,'{payload,reference_bars,1}',bar||jsonb_build_object('high',97,'low',97))));
 if scored->1->>'status'<>'UNRANKABLE' or scored->1->>'rank' is not null then raise exception 'ZERO_RANGE_FAILED';end if;
 if public.tfm_score_candidates(jsonb_build_array(jsonb_set(rows->0,'{qualifies}','false'))) <> '[]'::jsonb then raise exception 'NONQUALIFIER_FAILED';end if;
 scored:=public.tfm_score_candidates(jsonb_build_array(jsonb_set(rows->0,'{payload,reference_bars,1,response_sha256}','"bad"')));
 if scored->0->>'status'<>'UNRANKABLE' then raise exception 'PROVENANCE_FAILED';end if;
 reviewed:=public.tfm_score_review('[{"rank":1,"outcome":{"hit":false,"mfe_pct":0.1,"mae_pct":1}},{"rank":2,"outcome":{"hit":false,"mfe_pct":0.5,"mae_pct":0.25}}]');
 if abs((reviewed->>'ndcg')::numeric-63.0929753571)>0.0001 or (reviewed->>'wins')::int<>1 then raise exception 'NDCG_OR_ALTERNATE_FAILED: %',reviewed;end if;
 reviewed:=public.tfm_score_review('[{"rank":1,"outcome":null},{"rank":2,"outcome":{"hit":true}}]');
 if (reviewed->>'complete')::boolean or reviewed->>'ndcg' is not null or reviewed->>'lift' is not null then raise exception 'PENDING_REPLACEMENT_FAILED';end if;
 reviewed:=public.tfm_score_review('[{"rank":1,"outcome":{"hit":false,"mfe_pct":0.5,"mae_pct":0}}]');
 if (reviewed->>'top_rate')::numeric<>100 then raise exception 'ZERO_MAE_FAILED';end if;
 reviewed:=public.tfm_score_review('[{"rank":1,"outcome":{"hit":false,"mfe_pct":0,"mae_pct":0}}]');
 if reviewed->>'ndcg' is not null or (reviewed->>'wins')::int<>0 then raise exception 'ZERO_IDEAL_FAILED';end if;
 reviewed:=public.tfm_score_review('[]');
 if reviewed->>'ndcg' is not null or reviewed->>'top_rate' is not null then raise exception 'EMPTY_POOL_FAILED';end if;
 if has_table_privilege('authenticated','public.tfm_rank_xp','INSERT') or has_table_privilege('service_role','public.tfm_rank_snapshots','UPDATE') or has_function_privilege('anon','public.tfm_save_reflection(date,text)','EXECUTE') or has_function_privilege('authenticated','public.tfm_process_rankings(uuid)','EXECUTE') then raise exception 'PERMISSIONS_FAILED';end if;
 -- Reflection cannot mint XP without verified reviews or an allowed signed-in author.
 begin perform public.tfm_save_reflection('2026-11-09','A synthetic reflection that must not be accepted.');raise exception 'AUTH_GUARD_FAILED';
 exception when raise_exception then if SQLERRM<>'TFM_ACCESS_DENIED' then raise;end if;end;
end $$;
select 'TFM ranking contract PASS' as result;
