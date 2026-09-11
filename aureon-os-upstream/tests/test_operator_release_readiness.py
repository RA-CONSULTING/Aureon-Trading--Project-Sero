"""Offline passive-readiness regressions; no provider or released effect runs."""
from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aureon.operator.release_readiness import build_operator_release_readiness


def test_report_is_strict_public_contract_and_cannot_be_mutated_between_calls():
    report = build_operator_release_readiness()
    assert report['state'] == 'held'
    assert report['release_available'] is False and report['production_ready'] is False
    assert report['source_attestation'] is None and report['configuration_attestation'] is None
    assert len(report['requirements']) == 7
    assert len(report['work_orders']) == 7
    assert len({row['id'] for row in report['requirements']}) == 7
    assert len({row['id'] for row in report['work_orders']}) == 7
    assert all(row['state'] in {'not_integrated', 'unverified', 'integrated'} for row in report['requirements'])
    integrated = {row['id'] for row in report['requirements'] if row['state'] == 'integrated'}
    assert {'terminal_receipt_service', 'capability_runtime_attestation', 'durable_release_ledger'} <= integrated
    assert all(row['id'].startswith('release:') for row in report['work_orders'])
    assert all(row['owner_surface'].startswith('/') and row['verification_route'].startswith('/') for row in report['requirements'])
    assert all(row['evidence_required'] for row in report['requirements'])
    encoded = json.dumps(report, allow_nan=False)
    for forbidden in ('private_key', 'api_key', 'tenant_id', 'observed_at', 'generated_at', 'C:\\'):
        assert forbidden not in encoded
    report['requirements'].clear()
    report['work_orders'].clear()
    report['production_ready'] = True
    assert len(build_operator_release_readiness()['requirements']) == 7
    assert len(build_operator_release_readiness()['work_orders']) == 7
    assert build_operator_release_readiness()['production_ready'] is False


def test_module_is_import_inert_and_builder_does_not_read_configuration(monkeypatch):
    module = importlib.import_module('aureon.operator.release_readiness')
    tree = ast.parse(Path(module.__file__).read_text(encoding='utf-8'))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
    for node in tree.body:
        if isinstance(node, ast.Expr):
            assert isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        elif isinstance(node, ast.Assign):
            ast.literal_eval(node.value)  # Reject any top-level call or runtime lookup.
        else:
            assert isinstance(node, ast.FunctionDef)
    def forbidden(*_args, **_kwargs):
        raise AssertionError('passive report attempted I/O')
    monkeypatch.setattr('builtins.open', forbidden)
    monkeypatch.setattr('os.getenv', forbidden)
    monkeypatch.setattr('socket.socket', forbidden)
    monkeypatch.setattr('subprocess.Popen', forbidden)
    monkeypatch.setattr('threading.Thread.start', forbidden)
    assert build_operator_release_readiness()['state'] == 'held'


@pytest.fixture
def server(monkeypatch):
    pytest.importorskip('flask')
    for name in ('AUREON_HNC_PACKET_MASTER_KEY', 'HNC_PACKET_MASTER_KEY', 'AUREON_SUPABASE_JWT_SECRET',
                 'AUREON_OPERATOR_API_KEY', 'AUREON_OPERATOR_RATE_RPS', 'AUREON_OPERATOR_RATE_BURST',
                 'AUREON_OPERATOR_HTTP_PROCESSES', 'AUREON_OPERATOR_REPLICAS'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('AUREON_OPERATOR_ENV', 'test')
    monkeypatch.setenv('AUREON_LLM_OFFLINE', '1')
    monkeypatch.setenv('AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS', '1')
    monkeypatch.setenv('AUREON_AUDIT_MODE', '1')
    return importlib.import_module('aureon.operator.operator_server')


def app_for(server):
    def forbidden(*_args, **_kwargs):
        raise AssertionError('passive report reached an effect handler')
    operator = SimpleNamespace(providers={}, bus=None, respond=forbidden, stream_events=forbidden)
    cognition = SimpleNamespace(reason=forbidden, stream_events=forbidden)
    return server.create_app(operator=operator, cognition=cognition)


def token(secret):
    def part(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b'=').decode()
    head, body = part({'alg': 'HS256', 'typ': 'JWT'}), part({'sub': 'fixture-user', 'exp': 4_102_444_800})
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), f'{head}.{body}'.encode(), hashlib.sha256).digest()).rstrip(b'=').decode()
    return f'{head}.{body}.{signature}'


def test_authenticated_read_is_safe_for_admin_and_tenant(server, monkeypatch):
    monkeypatch.setenv('AUREON_OPERATOR_API_KEY', 'fixture-admin-key')
    monkeypatch.setenv('AUREON_SUPABASE_JWT_SECRET', 'fixture-tenant-secret')
    app = app_for(server)
    client = app.test_client()
    path = '/api/operator/release-readiness'
    assert path not in ('/', '/healthz', '/readyz', '/metrics')
    assert client.get(path).status_code == 401
    assert client.get(path, headers={'Authorization': 'Bearer incorrect'}).status_code == 401
    admin = client.get(path, headers={'Authorization': 'Bearer fixture-admin-key'})
    tenant = client.get(path, headers={'Authorization': f'Bearer {token("fixture-tenant-secret")}'})
    assert admin.status_code == tenant.status_code == 200
    assert admin.get_json() == tenant.get_json() == build_operator_release_readiness()
    assert admin.headers['Cache-Control'] == 'no-store'


def test_get_does_not_admit_hnc_or_probe_provider_and_open_mode_stays_loopback(server, monkeypatch):
    app = app_for(server)
    before = app.extensions['aureon_operator_ingress_status']()
    def forbidden(*_args, **_kwargs):
        raise AssertionError('GET attempted key/provider work')
    monkeypatch.setattr(server, 'packet_master_key_from_env', forbidden)
    monkeypatch.setattr(server, '_test_provider_adapter', forbidden)
    client = app.test_client()
    assert client.get('/api/operator/release-readiness').status_code == 200
    assert app.extensions['aureon_operator_ingress_status']() == before
    assert client.get('/api/operator/release-readiness', environ_overrides={'REMOTE_ADDR': '203.0.113.8'}).status_code == 401


@pytest.mark.parametrize('has_hnc_key', [False, True])
def test_default_protected_requests_remain_503_after_readiness_read(server, monkeypatch, has_hnc_key):
    if has_hnc_key:
        monkeypatch.setenv('AUREON_HNC_PACKET_MASTER_KEY', base64.urlsafe_b64encode(b'fixture-operator-hnc-key-material').rstrip(b'=').decode())
    client = app_for(server).test_client()
    assert client.get('/api/operator/release-readiness').get_json()['production_ready'] is False
    responses = [client.post('/api/cognition/reason', json={'prompt': 'offline fixture'}),
                 client.get('/api/operator/stream?prompt=offline-fixture')]
    for response in responses:
        assert response.status_code == 503
        error = response.get_json()['error']
        assert error['handler_invoked'] is False
        assert error['reason_code'] == ('production_magic_star_release_unavailable' if has_hnc_key else 'hnc_ingress_quarantined')



def test_terminal_receipt_service_is_read_only_and_non_secret(server):
    client = app_for(server).test_client()
    response = client.get('/api/operator/terminal-receipt')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['schema'] == 'aureon.operator.terminal-receipt.v1'
    assert payload['source'] == '/api/terminal-state'
    assert payload['generated_values'] is False
    assert payload['mutation_authority'] is False
    assert len(payload.get('digest_sha256', '')) == 64
    encoded = json.dumps(payload, allow_nan=False).lower()
    for forbidden in ('private_key', 'api_key', 'secret', 'password', 'token'):
        assert forbidden not in encoded


def test_release_ledger_appends_valid_chain_rejects_secret_keys_and_detects_tamper(tmp_path):
    from aureon.operator.release_ledger import append_release_ledger_event, build_release_ledger_receipt, read_release_ledger

    path = tmp_path / 'release-ledger.jsonl'
    first = append_release_ledger_event('config_digest', {'source_hash': 'a' * 64}, actor='test', now=1_778_000_001.0, path=path)
    second = append_release_ledger_event('service_integrated', {'gate': 'durable_release_ledger'}, actor='test', now=1_778_000_002.0, path=path)
    assert first['sequence'] == 1
    assert second['sequence'] == 2
    assert second['previous_hash'] == first['current_hash']
    receipt = build_release_ledger_receipt(path=path, now=1_778_000_003.0)
    assert receipt['schema'] == 'aureon.operator.release-ledger.v1'
    assert receipt['available'] is True
    assert receipt['ledger']['chain_valid'] is True
    assert receipt['ledger']['event_count'] == 2
    assert receipt['release_authority'] is False
    assert receipt['mutation_authority'] is False
    try:
        append_release_ledger_event('config_digest', {'api_key': 'never'}, path=path)
    except ValueError as exc:
        assert 'sensitive_key' in str(exc)
    else:
        raise AssertionError('secret-bearing ledger payload was accepted')
    lines = path.read_text(encoding='utf-8').splitlines()
    lines[0] = lines[0].replace('config_digest', 'release_decision')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    assert read_release_ledger(path=path)['chain_valid'] is False


def test_ingress_custody_receipt_reports_loopback_and_auth_rate_blockers():
    from aureon.operator.ingress_custody import build_ingress_custody_receipt
    from aureon.operator.security import SecurityConfig

    payload = build_ingress_custody_receipt(
        security=SecurityConfig(environment='development', rate_rps=0.0),
        jwt_secret_set=False,
        request_view={'direct_client': '127.0.0.1', 'resolved_client': '127.0.0.1', 'identity_kind': 'open', 'is_admin': True},
        boundary_summary={'status': 'available'},
        host='127.0.0.1',
        port=8080,
        now=1_778_000_000.0,
    )
    assert payload['schema'] == 'aureon.operator.ingress-custody.v1'
    assert payload['private_ingress_custody'] is True
    assert payload['production_ingress_ready'] is False
    assert payload['controls']['auth_required'] is False
    assert payload['controls']['rate_limit_enabled'] is False
    assert {'operator_auth_not_required', 'operator_rate_limit_disabled'} <= set(payload['blockers'])
    assert payload['release_authority'] is False
    assert payload['mutation_authority'] is False
    encoded = json.dumps(payload, allow_nan=False).lower()
    for forbidden in ('private_key', 'api_key', 'secret', 'password', 'token'):
        assert forbidden not in encoded


def test_http_auth_and_rate_do_not_imply_durable_protected_custody():
    from aureon.operator.ingress_custody import build_ingress_custody_receipt
    from aureon.operator.security import SecurityConfig

    payload = build_ingress_custody_receipt(
        security=SecurityConfig(environment='production', api_key='fixture-admin-key', rate_rps=10.0, burst=20),
        jwt_secret_set=False,
        request_view={'direct_client': '127.0.0.1', 'resolved_client': '127.0.0.1', 'identity_kind': 'admin', 'is_admin': True},
        boundary_summary={'status': 'available'},
        host='127.0.0.1',
        port=8080,
        now=1_778_000_004.0,
    )
    assert payload['schema'] == 'aureon.operator.ingress-custody.v1'
    assert payload['private_ingress_custody'] is True
    assert payload['http_security_ready'] is True
    assert payload['production_ingress_ready'] is False
    assert payload['controls']['auth_required'] is True
    assert payload['controls']['rate_limit_enabled'] is True
    assert payload['blockers'] == ['protected_ingress_durable_custody_unattested']
    assert payload['release_authority'] is False
    assert payload['mutation_authority'] is False


def test_ingress_route_reports_http_security_separately_from_protected_custody(server, monkeypatch):
    monkeypatch.setenv('AUREON_OPERATOR_ENV', 'production')
    monkeypatch.setenv('AUREON_OPERATOR_API_KEY', 'fixture-admin-key')
    monkeypatch.setenv('AUREON_OPERATOR_RATE_RPS', '10')
    app = app_for(server)
    client = app.test_client()
    unauthenticated = client.get('/api/operator/ingress-custody', environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert unauthenticated.status_code == 401
    response = client.get(
        '/api/operator/ingress-custody',
        headers={'Authorization': 'Bearer fixture-admin-key'},
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    payload = response.get_json()
    assert payload['http_security_ready'] is True
    assert payload['production_ingress_ready'] is False
    assert payload['controls']['auth_required'] is True
    assert payload['controls']['rate_limit_enabled'] is True
    assert payload['blockers'] == ['protected_ingress_durable_custody_unattested']
    assert client.get(
        '/api/operator/release-readiness',
        headers={'Authorization': 'Bearer fixture-admin-key'},
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    ).get_json()['production_ready'] is False


def test_ingress_custody_route_is_no_store_and_keeps_release_held(server):
    app = app_for(server)
    client = app.test_client()
    response = client.get('/api/operator/ingress-custody', environ_base={'REMOTE_ADDR': '127.0.0.1'})
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    payload = response.get_json()
    assert payload['schema'] == 'aureon.operator.ingress-custody.v1'
    assert payload['private_ingress_custody'] is True
    assert payload['production_ingress_ready'] is False
    assert payload['controls']['ordinary_mutation_without_hnc_policy'] == 'quarantined_before_handler'
    assert client.post('/api/operator/release-ledger/events', json={'payload': {'probe': True}}).status_code == 503
    assert client.get('/api/operator/release-readiness').get_json()['production_ready'] is False


def test_executor_isolation_receipt_reports_kill_switch_and_keeps_authority_false():
    from aureon.operator.executor_isolation import build_executor_isolation_receipt

    payload = build_executor_isolation_receipt(terminal_state={
        'ok': True,
        'stale': False,
        'data_ready': True,
        'trading_ready': True,
        'exchange_action_plan': {
            'mode': 'analysis_only',
            'trade_path_state': 'runtime_clearance_pending',
            'real_orders_disabled': True,
            'exchange_mutations_disabled': True,
            'order_intent_publish_enabled': False,
            'runtime_clearances': ['real_orders_disabled', 'exchange_mutations_disabled', 'order_intent_publish_disabled'],
            'latest_execution': {'executor_enabled': False, 'trade_path_state': 'runtime_clearance_hold', 'submitted_count': 0, 'delegated_count': 0, 'guards': ['unified_order_executor_disabled']},
        },
    }, now=1_778_000_000.0)
    assert payload['schema'] == 'aureon.operator.executor-isolation.v1'
    assert payload['kill_switch_engaged'] is True
    assert payload['provider_mutation_disabled'] is True
    assert payload['production_executor_ready'] is False
    assert payload['executor_enabled'] is False
    assert payload['dry_run_order_path_proof'] is False
    assert 'unified_order_executor_disabled' in payload['blockers']
    assert payload['release_authority'] is False
    assert payload['mutation_authority'] is False


def test_executor_isolation_route_is_no_store_and_keeps_release_held(server):
    app = app_for(server)
    client = app.test_client()
    response = client.get('/api/operator/executor-isolation')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    payload = response.get_json()
    assert payload['schema'] == 'aureon.operator.executor-isolation.v1'
    assert payload['release_authority'] is False
    assert payload['mutation_authority'] is False
    assert client.get('/api/operator/release-readiness').get_json()['production_ready'] is False


def test_authority_map_and_result_binding_receipts_report_missing_production_evidence():
    from aureon.operator.authority_map import build_authority_map_receipt
    from aureon.operator.result_binding import build_result_binding_receipt

    authority = build_authority_map_receipt(now=1_778_000_000.0)
    assert authority['schema'] == 'aureon.operator.authority-map.v1'
    assert authority['distinct_authority_roles'] is True
    assert authority['signed_receipt_count'] == 0
    assert authority['independent_authorities_ready'] is False
    result = build_result_binding_receipt(
        terminal_state={'stale': False, 'exchange_action_plan': {'mode': 'analysis_only', 'trade_path_state': 'runtime_clearance_pending', 'latest_execution': {'order_lifecycle': {'active_lifecycles': []}}}},
        release_ledger={'ledger': {'recent_events': []}},
        authority_map=authority,
        now=1_778_000_001.0,
    )
    assert result['schema'] == 'aureon.operator.result-binding.v1'
    assert result['protected_result_bound'] is False
    assert result['correlation_id_available'] is False
    assert result['independent_receipts_available'] is False
    assert result['terminal_result_available'] is False
    assert result['release_authority'] is False
    assert result['mutation_authority'] is False


def test_authority_and_result_routes_are_no_store_and_keep_release_held(server):
    app = app_for(server)
    client = app.test_client()
    authority = client.get('/api/operator/authority-map')
    result = client.get('/api/operator/result-binding')
    assert authority.status_code == 200 and result.status_code == 200
    assert authority.headers['Cache-Control'] == 'no-store'
    assert result.headers['Cache-Control'] == 'no-store'
    assert authority.get_json()['release_authority'] is False
    assert result.get_json()['mutation_authority'] is False
    assert client.get('/api/operator/release-readiness').get_json()['production_ready'] is False


def test_release_ledger_route_is_read_only_and_keeps_release_held(server, monkeypatch, tmp_path):
    monkeypatch.setenv('AUREON_RELEASE_LEDGER_PATH', str(tmp_path / 'release-ledger.jsonl'))
    from aureon.operator.release_ledger import append_release_ledger_event

    append_release_ledger_event('service_integrated', {'gate': 'durable_release_ledger'}, now=1_778_000_001.0)
    app = app_for(server)
    client = app.test_client()
    response = client.get('/api/operator/release-ledger')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    payload = response.get_json()
    assert payload['schema'] == 'aureon.operator.release-ledger.v1'
    assert payload['available'] is True
    assert payload['ledger']['chain_valid'] is True
    assert payload['ledger']['event_count'] == 1
    assert payload['production_ready'] is False
    assert payload['release_authority'] is False
    assert payload['mutation_authority'] is False
    assert client.get('/api/operator/release-readiness').get_json()['production_ready'] is False


def test_capability_runtime_attestation_is_current_read_only_and_non_secret(server):
    from aureon.operator.capability_runtime_attestation import build_operator_capability_runtime_attestation

    readers = {
        'operator_status': lambda: {'truth_status': 'real_derived', 'status': 'degraded', 'product_domains': {}, 'process_observation': {'counts': {'running_verified': 1}}},
        'company_workforce': lambda: {'truth_status': 'real_derived', 'role_count': 2, 'department_count': 1, 'runtime_verification': {'read_state': 'observed'}},
        'coverage_map': lambda: {'truth_status': 'real_derived', 'all_covered': True, 'domains': [{}, {}], 'coverage_fraction': 1.0, 'uncovered': []},
        'feature_switchboard': lambda: {'groups': [{}, {}], 'summary': {'total': 3, 'enabled': 1, 'armed': 0, 'pending_restart': 0}},
        'terminal_state': lambda: {'ok': True, 'stale': False, 'data_ready': True, 'trading_ready': False, 'source': 'fixture'},
        'terminal_receipt': lambda: {'schema': 'aureon.operator.terminal-receipt.v1', 'truth_status': 'real_derived', 'available': True, 'mutation_authority': False, 'terminal': {'action_mode': 'analysis_only', 'execution_authority': False}},
        'release_readiness': build_operator_release_readiness,
        'ingress_custody': lambda: {'schema': 'aureon.operator.ingress-custody.v1', 'truth_status': 'real_derived', 'private_ingress_custody': True, 'production_ingress_ready': False, 'controls': {'auth_required': False, 'rate_limit_enabled': False, 'response_cache_policy': 'no-store', 'ordinary_mutation_without_hnc_policy': 'quarantined_before_handler'}, 'blockers': ['operator_auth_not_required']},
        'executor_isolation': lambda: {'schema': 'aureon.operator.executor-isolation.v1', 'truth_status': 'real_derived', 'production_executor_ready': False, 'kill_switch_engaged': True, 'executor_enabled': False, 'provider_mutation_disabled': True, 'evidence': {'action_mode': 'analysis_only', 'trade_path_state': 'runtime_clearance_pending'}, 'blockers': ['unified_order_executor_disabled']},
        'authority_map': lambda: {'schema': 'aureon.operator.authority-map.v1', 'truth_status': 'real_derived', 'distinct_authority_roles': True, 'signed_receipt_count': 0, 'required_signed_receipt_count': 4, 'independent_authorities_ready': False, 'blockers': ['signed_review_authority_receipt_missing']},
        'result_binding': lambda: {'schema': 'aureon.operator.result-binding.v1', 'truth_status': 'real_derived', 'protected_result_bound': False, 'correlation_id_available': False, 'independent_receipts_available': False, 'terminal_result_available': False, 'evidence': {'active_lifecycle_count': 0, 'complete_lifecycle_count': 0}, 'blockers': ['intent_to_result_correlation_missing']},
        'release_ledger': lambda: {'schema': 'aureon.operator.release-ledger.v1', 'available': True, 'append_route_mode': 'operator_only_hnc_protected', 'ledger': {'event_count': 1, 'chain_valid': True, 'latest_event_type': 'service_integrated'}},
    }
    payload = build_operator_capability_runtime_attestation(readers, now=1_778_000_000.0)
    assert payload['schema'] == 'aureon.operator.capability-runtime-attestation.v1'
    assert payload['generated_values'] is False
    assert payload['surface_count'] == payload['observed_surface_count'] == 12
    assert payload['production_ready'] is False
    assert payload['release_authority'] is False
    assert payload['mutation_authority'] is False
    assert len(payload['digest_sha256']) == 64
    routes = {row['id']: row for row in payload['routes']}
    assert routes['terminal_receipt']['summary']['terminal_action_mode'] == 'analysis_only'
    assert routes['feature_switchboard']['summary']['armed_hard_boundaries'] == 0
    assert all(row['mode'] == 'read_only' and row['mutation_authority'] is False for row in routes.values())
    encoded = json.dumps(payload, allow_nan=False).lower()
    for forbidden in ('private_key', 'api_key', 'secret', 'password', 'token'):
        assert forbidden not in encoded


def test_capability_runtime_attestation_route_is_public_read_contract_and_keeps_release_held(server, monkeypatch):
    fixture = {
        'schema': 'aureon.operator.capability-runtime-attestation.v1',
        'generated_values': False,
        'observed_at': 1_778_000_000.0,
        'observed_at_iso': '2026-05-04T13:33:20Z',
        'surface_count': 12,
        'observed_surface_count': 12,
        'unavailable_surface_count': 0,
        'all_surfaces_observed': True,
        'production_ready': False,
        'release_authority': False,
        'mutation_authority': False,
        'routes': [{'id': str(i), 'mode': 'read_only', 'mutation_authority': False} for i in range(12)],
        'digest_sha256': 'a' * 64,
        'digest_scope': 'capability_route_evidence_matrix',
    }
    monkeypatch.setattr(server, 'build_operator_capability_runtime_attestation', lambda: fixture)
    app = app_for(server)
    client = app.test_client()
    response = client.get('/api/operator/capability-runtime-attestation')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    payload = response.get_json()
    assert payload == fixture
    assert client.get('/api/operator/release-readiness').get_json()['production_ready'] is False


def test_protected_classification_and_hold_functions_match_staged_baseline():
    root = Path(__file__).resolve().parents[1]
    baseline = root / 'before/aureon/operator/operator_server.py'
    if not baseline.exists():
        pytest.skip('Staging-only baseline assertion; upstream protection suite covers integration')
    def nodes(path):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        names = {'_held_response', '_protect_control_plane_ingress', '_requires_hnc_protection'}
        return {node.name: ast.dump(node, include_attributes=False) for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name in names}
    assert nodes(root / 'aureon/operator/operator_server.py') == nodes(baseline)
