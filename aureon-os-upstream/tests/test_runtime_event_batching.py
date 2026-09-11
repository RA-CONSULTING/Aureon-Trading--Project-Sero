from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fabric = _load(
    "aureon.trading.live_trade_signal_fabric",
    ROOT / "aureon" / "trading" / "live_trade_signal_fabric.py",
)
lifecycle = _load(
    "staged_order_lifecycle",
    ROOT / "aureon" / "trading" / "order_lifecycle.py",
)


def _fabric_event(index: int, *, identity: str | None = None) -> dict:
    return {
        "schema_version": fabric.SCHEMA_VERSION,
        "event_id": f"event-{index}",
        "phase": "signal_generated",
        "generated_at": 1_700_000_000 + index,
        "dedupe_identity": identity or f"identity-{index}",
        "trace_id": f"trace-{index}",
    }


def test_signal_batch_scans_and_serializes_state_once(tmp_path, monkeypatch):
    reads: list[int] = []
    original_read = fabric._tail_jsonl_records

    def read_once(path, limit):
        reads.append(limit)
        return original_read(path, limit)

    writes: list[str | None] = []
    original_write = fabric._write_json_atomic

    def record_write(path, payload, *, serialized=None):
        writes.append(serialized)
        original_write(path, payload, serialized=serialized)

    monkeypatch.setattr(fabric, "_tail_jsonl_records", read_once)
    monkeypatch.setattr(fabric, "_write_json_atomic", record_write)
    events = [_fabric_event(index) for index in range(20)]

    state = fabric.write_trade_flow_event_batch(events, root=tmp_path)

    assert reads == [1000]
    assert len((tmp_path / fabric.LOG_PATH).read_text(encoding="utf-8").splitlines()) == 20
    assert state["summary"]["event_count"] == 20
    assert state["summary"]["dedupe_applied_count"] == 0
    assert all(event["dedupe_applied"] is False for event in events)
    assert len(writes) == 2 and writes[0] is writes[1]
    assert (tmp_path / fabric.STATE_PATH).read_bytes() == (tmp_path / fabric.PUBLIC_PATH).read_bytes()


def test_signal_batch_deduplicates_against_disk_and_within_batch(tmp_path):
    first = _fabric_event(0, identity="same")
    fabric.write_trade_flow_event_batch([first], root=tmp_path)
    second = _fabric_event(1, identity="same")
    third = _fabric_event(2, identity="new")
    fourth = _fabric_event(3, identity="new")

    state = fabric.write_trade_flow_event_batch([second, third, fourth], root=tmp_path)

    rows = [json.loads(line) for line in (tmp_path / fabric.LOG_PATH).read_text(encoding="utf-8").splitlines()]
    assert [row["event_id"] for row in rows] == ["event-0", "event-2"]
    assert [second["dedupe_applied"], third["dedupe_applied"], fourth["dedupe_applied"]] == [True, False, True]
    assert state["summary"]["dedupe_applied_count"] == 2
    assert state["summary"]["dedupe_last_identity"] == "new"


def test_signal_batch_uses_same_rolling_physical_window_as_sequential_writes(tmp_path):
    seeded = [_fabric_event(index) for index in range(fabric.DEDUPLICATION_SCAN_LIMIT)]
    fabric.write_trade_flow_event_batch(seeded, root=tmp_path)
    newest = _fabric_event(10_000, identity="newest")
    aged_out = _fabric_event(10_001, identity="identity-0")

    fabric.write_trade_flow_event_batch([newest, aged_out], root=tmp_path)

    rows = [json.loads(line) for line in (tmp_path / fabric.LOG_PATH).read_text(encoding="utf-8").splitlines()]
    assert len(rows) == fabric.DEDUPLICATION_SCAN_LIMIT + 2
    assert [row["event_id"] for row in rows[-2:]] == ["event-10000", "event-10001"]
    assert newest["dedupe_applied"] is False
    assert aged_out["dedupe_applied"] is False


def test_signal_batch_rolls_window_across_malformed_physical_record(tmp_path):
    log_path = tmp_path / fabric.LOG_PATH
    log_path.parent.mkdir(parents=True)
    rows = [_fabric_event(0), None, *[_fabric_event(index) for index in range(1, 499)]]
    with log_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write((json.dumps(row) if row is not None else "not-json") + "\n")
    newest = _fabric_event(10_000, identity="newest")
    aged_out = _fabric_event(10_001, identity="identity-0")

    fabric.write_trade_flow_event_batch([newest, aged_out], root=tmp_path)

    parsed = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line != "not-json"
    ]
    assert [row["event_id"] for row in parsed[-2:]] == ["event-10000", "event-10001"]
    assert aged_out["dedupe_applied"] is False


def test_signal_batch_duplicate_final_event_matches_sequential_500_record_state(tmp_path):
    fabric.write_trade_flow_event_batch([_fabric_event(index) for index in range(600)], root=tmp_path)
    duplicate = _fabric_event(10_000, identity="identity-599")

    state = fabric.write_trade_flow_event_batch([duplicate], root=tmp_path)

    assert duplicate["dedupe_applied"] is True
    assert state["summary"]["event_count"] == fabric.DEDUPLICATION_SCAN_LIMIT


def test_signal_batch_rereads_a_concurrent_append(tmp_path, monkeypatch):
    log_path = tmp_path / fabric.LOG_PATH
    log_path.parent.mkdir(parents=True)
    log_path.write_text('{"event_id":"initial","generated_at":1}\n', encoding="utf-8")
    original_read = fabric._tail_jsonl_records
    reads: list[int] = []

    def append_during_read(path, limit):
        rows = original_read(path, limit)
        reads.append(limit)
        if len(reads) == 1:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write('{"event_id":"concurrent","generated_at":2}\n')
        return rows

    monkeypatch.setattr(fabric, "_tail_jsonl_records", append_during_read)
    state = fabric.write_trade_flow_event_batch([_fabric_event(3)], root=tmp_path)

    assert reads == [1000, 1000]
    assert [row["event_id"] for row in state["events"]] == ["initial", "concurrent", "event-3"]


def test_lifecycle_batch_rebuilds_both_ledgers_once(tmp_path, monkeypatch):
    lifecycle_reads: list[int] = []
    lifecycle_writes: list[int] = []
    published: list[dict] = []
    fabric_batches: list[list[dict]] = []
    original_tail = lifecycle._tail_jsonl
    original_write = lifecycle._write_state

    def read_once(path, limit=500):
        lifecycle_reads.append(limit)
        return original_tail(path, limit)

    def write_once(state, root):
        lifecycle_writes.append(state["event_count"])
        return original_write(state, root)

    def publish(event, **kwargs):
        assert kwargs["write_artifacts"] is False
        published.append(dict(event))
        return _fabric_event(len(published))

    def write_fabric(events, **kwargs):
        fabric_batches.append(list(events))
        return {}

    monkeypatch.setattr(lifecycle, "_tail_jsonl", read_once)
    monkeypatch.setattr(lifecycle, "_write_state", write_once)
    monkeypatch.setattr(lifecycle, "publish_lifecycle_event", publish)
    monkeypatch.setattr(lifecycle, "write_trade_flow_event_batch", write_fabric)
    specs = [
        {
            "event_type": "candidate_ready",
            "status": "candidate_ready",
            "lifecycle_id": f"life-{index}",
            "candidate_id": f"candidate-{index}",
            "route_key": f"kraken:spot:ASSET{index}:BUY",
            "symbol": f"ASSET{index}",
            "side": "BUY",
        }
        for index in range(20)
    ]

    events = lifecycle.append_events(specs, root=tmp_path)

    assert len(events) == 20
    assert lifecycle_reads == [500]
    assert lifecycle_writes == [20]
    assert len(published) == 20
    assert len(fabric_batches) == 1 and len(fabric_batches[0]) == 20
    assert len((tmp_path / lifecycle.LOG_PATH).read_text(encoding="utf-8").splitlines()) == 20
    assert (tmp_path / lifecycle.STATE_PATH).read_bytes() == (tmp_path / lifecycle.PUBLIC_PATH).read_bytes()


def test_lifecycle_batch_preserves_active_row_outside_tail(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "publish_lifecycle_event", None)
    monkeypatch.setattr(lifecycle, "write_trade_flow_event_batch", None)
    active_id = "active-position"
    lifecycle.append_event(
        root=tmp_path,
        event_type="position_recovered",
        status="position_open",
        lifecycle_id=active_id,
        route_key="capital:cfd:GOLD:BUY",
        venue="capital",
        symbol="GOLD",
        side="BUY",
    )
    specs = [
        {
            "event_type": "candidate_ready",
            "status": "candidate_ready",
            "lifecycle_id": f"candidate-life-{index}",
            "route_key": f"binance:spot:A{index}:BUY",
            "symbol": f"A{index}",
            "side": "BUY",
        }
        for index in range(520)
    ]

    lifecycle.append_events(specs, root=tmp_path)
    state = lifecycle.load_state(tmp_path)

    assert state["event_count"] == 500
    assert [row["lifecycle_id"] for row in state["active_lifecycles"]] == [active_id]
    assert state["active_lifecycles"][0]["preserved_from_previous_snapshot"] is True


def test_lifecycle_batch_preserves_active_transition_from_its_own_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "publish_lifecycle_event", None)
    monkeypatch.setattr(lifecycle, "write_trade_flow_event_batch", None)
    active_id = "batch-prefix-position"
    specs = [
        {
            "event_type": "position_recovered",
            "status": "position_open",
            "lifecycle_id": active_id,
            "route_key": "capital:cfd:GOLD:BUY",
            "venue": "capital",
            "symbol": "GOLD",
            "side": "BUY",
        },
        *[
            {
                "event_type": "candidate_ready",
                "status": "candidate_ready",
                "lifecycle_id": f"candidate-life-{index}",
                "route_key": f"binance:spot:A{index}:BUY",
                "symbol": f"A{index}",
                "side": "BUY",
            }
            for index in range(520)
        ],
    ]

    lifecycle.append_events(specs, root=tmp_path)
    state = lifecycle.load_state(tmp_path)

    assert state["event_count"] == 500
    assert [row["lifecycle_id"] for row in state["active_lifecycles"]] == [active_id]
    assert state["active_lifecycles"][0]["preserved_from_previous_snapshot"] is True


def test_lifecycle_batch_prefers_newer_prefix_update_over_previous_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "publish_lifecycle_event", None)
    monkeypatch.setattr(lifecycle, "write_trade_flow_event_batch", None)
    active_id = "updated-position"
    lifecycle.append_event(
        root=tmp_path,
        event_type="broker_fill",
        status="position_open",
        lifecycle_id=active_id,
        route_key="capital:cfd:GOLD:BUY",
        venue="capital",
        symbol="GOLD",
        side="BUY",
        filled_qty=1,
        generated_at="2026-09-08T18:00:00+00:00",
    )
    specs = [
        {
            "event_type": "broker_fill",
            "status": "position_open",
            "lifecycle_id": active_id,
            "route_key": "capital:cfd:GOLD:BUY",
            "venue": "capital",
            "symbol": "GOLD",
            "side": "BUY",
            "filled_qty": 2,
            "generated_at": "2026-09-08T18:02:00+00:00",
        },
        *[
            {
                "event_type": "candidate_ready",
                "status": "candidate_ready",
                "lifecycle_id": f"candidate-life-{index}",
                "route_key": f"binance:spot:A{index}:BUY",
                "symbol": f"A{index}",
                "side": "BUY",
            }
            for index in range(520)
        ],
    ]

    lifecycle.append_events(specs, root=tmp_path)
    state = lifecycle.load_state(tmp_path)

    assert len(state["active_lifecycles"]) == 1
    assert state["active_lifecycles"][0]["lifecycle_id"] == active_id
    assert state["active_lifecycles"][0]["filled_qty"] == 2
    assert state["active_lifecycles"][0]["updated_at"] == "2026-09-08T18:02:00+00:00"
