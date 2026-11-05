"""Read-only scoring contract checks against deployed RPCs. Synthetic prices only."""
def validate_ranking_api(db):
    bar={'symbol':'FIXTURE','trade_date':'2026-11-06','open':99,'high':100,'low':97,'close':97.6,'run_id':'fixture','response_sha256':'a'*64}
    th={**bar,'trade_date':'2026-11-05','high':101,'close':99}
    row={'setup_key':'fixture','symbol':'FIXTURE','friday':'2026-11-06','qualifies':True,'payload':{'reference_bars':[th,bar]}}
    scored=db('rpc/tfm_score_candidates','POST',{'p_rows':[row]})
    if len(scored)!=1 or abs(scored[0]['score']-86)>1e-8 or scored[0]['rank']!=1:raise ValueError('RANK_SCORE_CONTRACT_FAILED')
    pending=db('rpc/tfm_score_review','POST',{'p_rows':[{'rank':1,'outcome':None},{'rank':2,'outcome':{'hit':True}}]})
    if pending['complete'] or pending['ndcg'] is not None or pending['lift'] is not None:raise ValueError('RANK_PENDING_CONTRACT_FAILED')
    reviewed=db('rpc/tfm_score_review','POST',{'p_rows':[{'rank':1,'outcome':{'hit':False,'mfe_pct':.1,'mae_pct':1}},{'rank':2,'outcome':{'hit':False,'mfe_pct':.5,'mae_pct':.25}}]})
    if abs(reviewed['ndcg']-63.0929753571)>.0001 or reviewed['wins']!=1:raise ValueError('RANK_REVIEW_CONTRACT_FAILED')
    return 'PASS'
