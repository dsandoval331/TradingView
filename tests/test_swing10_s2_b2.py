import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tr_platform.research import swing10_s2_b2 as b2
from cloud_compute import research_revision_adapter as adapter


def gates(**changes):
    return {**dict(required_sign_pass=True, fdr_support=True, neighbor_coherence=True,
                   material_support=True, temporal_support=True, symbol_support=True), **changes}


@pytest.mark.parametrize('direction,rows,semantic,testable,expected', [
    (1, [gates()], True, True, 'ADVANCE_TO_S2_ROBUSTNESS'),
    (-1, [gates()], True, True, 'ADVANCE_TO_S2_ROBUSTNESS'),
    (0, [gates()], True, True, 'RETAIN_AS_WEAK_EVIDENCE'),
    (0, [gates(symbol_support=False)], True, True, 'RETAIN_AS_COUNTEREVIDENCE'),
    (1, [gates(temporal_support=False)], True, True, 'RETAIN_AS_WEAK_EVIDENCE'),
    (1, [gates(fdr_support=False, material_support=True)], True, True, 'RETAIN_AS_WEAK_EVIDENCE'),
    (1, [gates(fdr_support=False, material_support=False)], True, True, 'RETAIN_AS_COUNTEREVIDENCE'),
    (1, [gates(required_sign_pass=False)], True, True, 'RETAIN_AS_COUNTEREVIDENCE'),
    (1, [gates()], False, True, 'INVALID_SEMANTICS_NOT_TESTABLE'),
    (1, [gates()], True, False, 'INVALID_SEMANTICS_NOT_TESTABLE'),
])
def test_frozen_disposition_priority(direction, rows, semantic, testable, expected):
    assert b2.disposition(rows, semantic_valid=semantic, testable=testable, direction=direction) == expected


def test_temporal_no_favorable_blocks_and_concentration_gate():
    dates = pd.date_range('2025-01-01', periods=8)
    blocks = dict(zip(dates, np.repeat([1, 2, 3, 4], 2)))
    ds = pd.DataFrame({'trade_date': dates, 'spread': [1, 1, 1, 1, 1, 1, -1, -1]})
    rows, stats = b2.temporal_stats(ds, blocks, 1)
    assert len(rows) == 4 and stats['directional_blocks'] == 3 and stats['temporal_support']
    ds.spread = [10, 10, 1, 1, 1, 1, -1, -1]
    _, stats = b2.temporal_stats(ds, blocks, 1)
    assert stats['max_block_abs_effect_share'] > .5 and not stats['temporal_support']


def test_symbol_additive_decomposition_and_leave_top5_reversal():
    # Five dominant HIGH symbols supply positive effect; removing them leaves
    # a negative HIGH tail. All six LOW symbols remain; no threshold changes.
    d = pd.Timestamp('2025-01-01')
    z = pd.DataFrame({'symbol': [f'H{i}' for i in range(6)] + [f'L{i}' for i in range(6)],
                      'trade_date': d, 'is_high': [True]*6 + [False]*6,
                      'is_low': [False]*6 + [True]*6,
                      'forward_1': [1]*5 + [-.1] + [0]*6})
    rows, stats = b2.concentration_stats(z, 1, 1)
    assert sum(r['mean_spread_contribution'] for r in rows) == pytest.approx(4.9/6)
    assert stats['leave_top5_out_mean_spread'] == pytest.approx(-.1)
    assert not stats['symbol_support']
    assert sum(r['excluded_in_leave_top5'] for r in rows) == 5


def synthetic_panel():
    rng = np.random.default_rng(741)
    rows = []
    dates = pd.bdate_range('2024-01-01', periods=180)
    for i in range(12):
        close = 100 * np.exp(np.cumsum(rng.normal(.0002, .015, len(dates))))
        for j, date in enumerate(dates):
            rows.append(dict(symbol=f'S{i:02}', trade_date=date, open=close[j]*.999,
                             high=close[j]*1.02, low=close[j]*.98, close=close[j],
                             volume=float(rng.integers(100, 10000))))
    return pd.DataFrame(rows)


def test_end_to_end_synthetic_artifacts_and_exact_family(tmp_path):
    tables, blocks = b2.analyze(synthetic_panel())
    summary = tables[b2.FILES[0]]
    assert len(summary) == 42
    assert summary.primary_bh_member.sum() == 36
    assert summary.loc[~summary.primary_bh_member, 'p_fdr'].isna().all()
    assert not (summary.loc[summary.direction == 'NON_DIRECTIONAL', 'mechanical_disposition'] == 'ADVANCE_TO_S2_ROBUSTNESS').any()
    assert summary.long_short_independent_evidence.eq(False).all()
    ds = tables[b2.FILES[1]]
    for _, row in summary.iterrows():
        x = ds[(ds.factor == row.factor) & (ds.horizon_days == row.horizon_days)].spread
        assert row.standardized_effect == pytest.approx(x.mean()/x.std(ddof=1))
        symbols = tables[b2.FILES[3]]
        z = symbols[(symbols.factor == row.factor) & (symbols.horizon_days == row.horizon_days)]
        assert z.mean_spread_contribution.sum() == pytest.approx(row.mean_spread)
    ids = b2.write_outputs(tables, blocks, tmp_path, {'job_id': 'job', 'attempt_id': 'attempt'})
    assert set(p.name for p in tmp_path.iterdir()) == set(b2.FILES)
    manifest = json.loads((tmp_path / b2.FILES[-1]).read_text())
    assert manifest['fdr']['tests'] == 36 and not manifest['protected_data_access']
    assert manifest['manifest_identity']['artifact_id'] == ids[b2.FILES[-1]]
    for a in manifest['artifacts']:
        blob = (tmp_path / a['name']).read_bytes()
        assert len(blob) == a['size_bytes']
        assert hashlib.sha256(blob).hexdigest() == a['sha256']
        assert a['artifact_id'] == ids[a['name']]


def test_input_cannot_silently_regenerate(tmp_path):
    p = tmp_path / 'panel.csv'
    synthetic_panel().to_csv(p, index=False)
    with pytest.raises(ValueError, match='bytes/SHA'):
        b2.verify_input(p)


def test_adapter_materializes_both_files_at_exact_revision(monkeypatch, tmp_path):
    sha = '3'*40
    calls = []
    def materialize(repo, revision, path, destination):
        calls.append((revision, path))
        if path.endswith('_core.py'):
            destination.write_text('VALUE = 77\n')
        else:
            destination.write_text('from tr_platform.research.swing10_s2_b2_core import VALUE\ndef run(work_root):\n    return {"value": VALUE}\n')
        return destination
    monkeypatch.setattr(adapter, 'materialize_module', materialize)
    assert adapter._run_b2_bundle(tmp_path, sha, tmp_path, tmp_path) == {'value': 77}
    assert calls == [(sha, 'tr_platform/research/swing10_s2_b2.py'), (sha, 'tr_platform/research/swing10_s2_b2_core.py')]


def test_frozen_snapshot_matches_implementation():
    root = Path(__file__).resolve().parents[1]
    d = json.loads((root/'research_protocols/swing10/SW10_S2_B2_PROTOCOL_V1_SUPPLEMENT_1.persisted.json').read_text())['metadata_json']
    assert tuple(d['primary_bh_family']['members']) == b2.PRIMARY
    assert d['primary_bh_family']['tests'] == len(b2.PRIMARY)*len(b2.HORIZONS) == 36
    for f, sign in b2.DIRECTIONS.items():
        assert d['direction_registry'][f]['direction'] == {1: 'POSITIVE_HIGH_MINUS_LOW', -1: 'NEGATIVE_HIGH_MINUS_LOW', 0: 'NON_DIRECTIONAL'}[sign]
    assert all(b2.semantic_fixtures().values())


def test_artifact_id_is_preserved_in_registration(monkeypatch, tmp_path):
    from cloud_compute import control_plane_worker as worker
    from cloud_compute.control_plane import ControlPlaneConfig
    import uuid
    identity = str(uuid.uuid4())
    (tmp_path/'a.csv').write_text('a,b\n1,2\n')
    monkeypatch.setattr(worker.runner, 'WORK_ROOT', tmp_path)
    monkeypatch.setattr(worker, '_upload_object', lambda *args, **kw: None)
    monkeypatch.setattr(worker, 'create_artifact', lambda config, payload: payload)
    rows = worker._persist_result_artifacts(ControlPlaneConfig('https://example.invalid', 'fixture'), job_id='job', attempt_id='attempt', runner_job_id='SW10-S2-B2', bucket='bucket', result={'artifact':'a.csv','output_artifact_ids':{'a.csv':identity}})
    assert rows[0]['artifact_id'] == identity
    assert rows[0]['is_primary']


def test_run_declares_seven_exact_outputs(monkeypatch, tmp_path):
    context = tmp_path/'job_inputs/swing10/execution_context.json'
    context.parent.mkdir(parents=True)
    context.write_text(json.dumps({'job_id': 'job', 'attempt_id': 'attempt'}))
    panel = synthetic_panel()
    monkeypatch.setattr(b2, 'verify_input', lambda path: (panel, {'symbols':12}))
    result = b2.run(tmp_path)
    assert len(result['output_paths']) == 7 and len(result['output_artifact_ids']) == 7
    assert result['artifact'].endswith('factor_causal_summary.csv')
