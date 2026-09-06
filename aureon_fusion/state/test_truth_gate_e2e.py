"""End-to-end dry verification for the KUNDALINI / MATH-ANGLE TRUTH GATE wiring.

Two halves, both ZERO network:

A. Gate half (aureon_fusion.truth_gate over the REAL pure upstream gate —
   imported, never run; the gate itself performs no I/O):
     1. well-grounded fresh claim            -> READY_FOR_AURIS
     2. same claim, stale fetched_at         -> STALE_OR_LINEAGE @ Sacral
                                                (verified against the real
                                                KUNDALINI_BLOCKERS table)
     3. claim with no provenance             -> MISSING_GROUNDING @ Root
     4. batch of two contradicting claims    -> CROSS_CLAIM_CONFLICT @ Third Eye
     5. gate forced unavailable              -> GATE_UNAVAILABLE, never raises

B. Faculty wiring half (aureon_fusion.research_faculty run_topic /
   run_questions with stubbed seams — the test_research_pipeline_e2e
   sys.modules idiom):
     6. stubbed truth_gate fixed split (1 ready / 1 contested): the ready
        item crystallizes with 'truth:aris', the contested item lands in
        truth_contested.jsonl and NOT in the dataset, result counts correct
     7. same for run_questions
     8. gate unavailable -> fragments 'truth_unchecked', research still
        succeeds, honest truth_gate_available=false

Seams (verified against aureon_fusion/research_faculty.py on disk):
  * Gates/throttle are module functions (_run_gate_trio / _throttle_check /
    _throttle_record) — patched, never burned.
  * _topic_pull / _novelty_filter / _mark_questions_researched are module
    functions — stubbed with fixture entries (ZERO network).
  * truth_gate is a lazy guarded import inside _truth_layer; the stub is
    injected via sys.modules AND the package attribute (learning_will
    e2e idiom).
  * FusionKnowledgeDatasetAdapter is patched to a fixture recorder so no
    real dataset file is touched; TRUTH_CONTESTED_FILE is redirected into
    the per-run temp dir; events.publish_event is stubbed.

Writes benchmarks/truth_gate_e2e.json (verdict PASS/FAIL/PENDING).

Exit codes: 0 = all scenarios pass; 1 = a scenario failed; 2 = the
truth_gate module is not importable (benchmark records PENDING).

Usage:  python aureon_fusion/state/test_truth_gate_e2e.py [-v]
"""

import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
FUSION_STATE = WORKSPACE / "aureon_fusion" / "state"
BENCHMARK_FILE = FUSION_STATE / "benchmarks" / "truth_gate_e2e.json"

_log_lines = []


def log(msg):
    line = str(msg)
    _log_lines.append(line)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(line)


def write_benchmark(record):
    BENCHMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = BENCHMARK_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    os.replace(tmp, BENCHMARK_FILE)


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

CLAIM_FRESH = "solar wind is a stream of charged particles"
CLAIM_CONTRADICTED = "solar wind is not a stream of charged particles"
FIXTURE_URL = "https://en.wikipedia.org/wiki/Solar_wind"
STALE_AGE_S = 48.0 * 3600.0  # older than STALE_AFTER_S, inside MAX_AGE_S

FIXTURE_ENTRIES = [
    {
        "item": SimpleNamespace(
            source="wiki", category="knowledge", title="Solar wind",
            text=CLAIM_FRESH, url=FIXTURE_URL, fetched_at=time.time()),
        "sources": ["wiki"],
        "corroboration_count": 1,
        "dump_text": f"Solar wind: {CLAIM_FRESH}",
    },
    {
        "item": SimpleNamespace(
            source="blog", category="knowledge", title="Contrarian take",
            text=CLAIM_CONTRADICTED, url="https://example.org/contrarian",
            fetched_at=time.time()),
        "sources": ["blog"],
        "corroboration_count": 1,
        "dump_text": f"Contrarian take: {CLAIM_CONTRADICTED}",
    },
]


# ---------------------------------------------------------------------------
# Fakes / stubs
# ---------------------------------------------------------------------------


class FixtureDataset:
    """Recorder standing in for FusionKnowledgeDatasetAdapter: captures
    every crystallized pocket entry (value + tags), counts nothing real."""

    def __init__(self, record):
        self._record = record

    def absorb_pocket(self, pocket):
        entries = []
        for e in list(getattr(pocket, "entries", []) or []):
            entries.append({"value": e.value, "tags": list(e.tags)})
        self._record.setdefault("pockets", []).append(entries)
        return len(entries)


def _read_contested(path):
    out = []
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def _stub_truth_gate(hw, *, available=True, results=None):
    """Inject a fake aureon_fusion.truth_gate (package attr + sys.modules —
    the learning_will e2e stub idiom). check_batch returns the fixed
    results list; gate_available is the availability switch."""
    import aureon_fusion
    calls = []

    def fake_check_batch(items, *, now=None):
        calls.append(list(items or []))
        return list(results or [])

    avail_calls = []

    def fake_gate_available():
        avail_calls.append(1)
        return available

    fake = SimpleNamespace(
        gate_available=fake_gate_available,
        check_batch=fake_check_batch,
        check_claim=lambda text, provenance=None, *, now=None:
            (results or [{}])[0],
        _calls=calls,
        _avail_calls=avail_calls,
    )
    hw.patch(aureon_fusion, "truth_gate", fake)
    p = mock.patch.dict(sys.modules, {"aureon_fusion.truth_gate": fake})
    p.start()
    hw.patches.append(p)
    return fake


def _patch_faculty_seams(hw, rf, entries):
    """Stub every seam between the gate trio and crystallization so
    run_topic/run_questions execute with ZERO network and ZERO live state:
    gates pass, throttle allows (never records), the pull returns fixture
    entries, novelty keeps them, the dataset records them."""
    hw.patch(rf, "_run_gate_trio",
             lambda: {"passed": True, "gamma": {"gamma": 0.9}})
    hw.patch(rf, "_throttle_check",
             lambda now, mode="proactive": {"allowed": True,
                                            "retry_in_s": 0.0,
                                            "last_run_at": 0.0,
                                            "mode": mode})
    hw.patch(rf, "_throttle_record", lambda now, mode, result: None)
    hw.patch(rf, "_topic_pull", lambda ingester, topic, sources=None, cap=6:
             [dict(e) for e in entries])
    hw.patch(rf, "_novelty_filter",
             lambda entries_: (list(entries_), 0, "fixture", 0))
    hw.patch(rf, "_mark_questions_researched", lambda texts: 0)
    hw.patch(rf, "FusionKnowledgeDatasetAdapter",
             lambda *a, **k: hw.dataset)
    hw.patch(rf, "events", SimpleNamespace(
        publish_event=lambda *a, **k: hw.events.append({"args": a, "kw": k})))
    hw.patch(rf, "TRUTH_CONTESTED_FILE", hw.contested_file)


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class Harness:
    """Per-scenario temp state + seam redirection."""

    def __init__(self, tmp, rf):
        self.tmp = Path(tmp)
        self.rf = rf
        self.patches = []
        self.record = {"pockets": []}
        self.dataset = FixtureDataset(self.record)
        self.contested_file = self.tmp / "truth_contested.jsonl"
        self.events = []

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value, create=True)
        p.start()
        self.patches.append(p)
        return value

    def crystallized_tags(self):
        tags = []
        for pocket in self.record["pockets"]:
            for ent in pocket:
                tags.append(list(ent["tags"]))
        return tags

    def crystallized_texts(self):
        texts = []
        for pocket in self.record["pockets"]:
            for ent in pocket:
                texts.append(ent["value"])
        return texts

    def unpatch_all(self):
        for p in reversed(self.patches):
            try:
                p.stop()
            except Exception:
                pass
        self.patches.clear()


# ---------------------------------------------------------------------------
# Scenarios — gate half (real upstream, pure)
# ---------------------------------------------------------------------------


def scenario_fresh_claim_ready(tg):
    log("── SCENARIO 1: well-grounded fresh claim -> READY_FOR_AURIS ──")
    now = time.time()
    res = tg.check_claim(
        CLAIM_FRESH,
        {"url": FIXTURE_URL, "source": "wikipedia", "fetched_at": now},
        now=now)
    log(f"  verdict={res['verdict']} ready={res['ready_for_aris']} "
        f"blocker={res['blocker']} status={res['status']}")
    assert res["verdict"] == "READY_FOR_AURIS", res
    assert res["ready_for_aris"] is True
    assert res["blocker"] is None
    assert res["failure_kind"] is None
    assert res["reason"] == "grounding_supported_diagnostics_linked", \
        res["reason"]
    for key in ("qgita_diagnostic", "math_angle_diagnostic",
                "schema_versions", "receipt_id"):
        assert res.get(key), f"missing compact field: {key}"
    assert res["receipt_id"].startswith("truth-gate:qgita-kundalini:")
    log("  PASS: fresh grounded claim reaches the Crown (READY_FOR_AURIS)")
    return {"verdict": res["verdict"], "reason": res["reason"]}


def scenario_stale_claim_blocked(tg, mods):
    log("── SCENARIO 2: stale fetched_at -> STALE_OR_LINEAGE @ Sacral ──")
    now = time.time()
    res = tg.check_claim(
        CLAIM_FRESH,
        {"url": FIXTURE_URL, "source": "wikipedia",
         "fetched_at": now - STALE_AGE_S},
        now=now)
    log(f"  verdict={res['verdict']} blocker={res['blocker']} "
        f"status={res['status']} reason={res['reason']}")
    expected = dict(mods.gate.KUNDALINI_BLOCKERS).get("Sacral")
    assert expected == "STALE_OR_LINEAGE", \
        f"upstream table drifted: Sacral -> {expected}"
    assert res["verdict"] == "STALE_OR_LINEAGE", res
    assert res["ready_for_aris"] is False
    assert res["blocker"] == "Sacral", res["blocker"]
    assert res["status"] == "CORRECTION_REQUIRED", res["status"]
    directive_next = None
    log("  PASS: stale provenance binds the Sacral blocker per the real "
        "KUNDALINI_BLOCKERS table")
    return {"verdict": res["verdict"], "blocker": res["blocker"],
            "table_verified": True}


def scenario_missing_grounding(tg, mods):
    log("── SCENARIO 3: no provenance -> MISSING_GROUNDING @ Root ──")
    res = tg.check_claim(CLAIM_FRESH)
    log(f"  verdict={res['verdict']} blocker={res['blocker']}")
    expected = dict(mods.gate.KUNDALINI_BLOCKERS).get("Root")
    assert expected == "MISSING_GROUNDING", \
        f"upstream table drifted: Root -> {expected}"
    assert res["verdict"] == "MISSING_GROUNDING", res
    assert res["ready_for_aris"] is False
    assert res["blocker"] == "Root", res["blocker"]
    log("  PASS: absent provenance is honestly ungrounded (never fabricated)")
    return {"verdict": res["verdict"], "blocker": res["blocker"]}


def scenario_cross_claim_conflict(tg, mods):
    log("── SCENARIO 4: contradicting batch -> CROSS_CLAIM_CONFLICT ──")
    now = time.time()
    prov = {"url": FIXTURE_URL, "fetched_at": now}
    results = tg.check_batch([
        {"text": CLAIM_FRESH, "provenance": prov},
        {"text": CLAIM_CONTRADICTED,
         "provenance": {"url": "https://example.org/x", "fetched_at": now}},
    ], now=now)
    assert len(results) == 2, f"expected 2 results, got {len(results)}"
    expected = dict(mods.gate.KUNDALINI_BLOCKERS).get("Third Eye")
    assert expected == "CROSS_CLAIM_CONFLICT", \
        f"upstream table drifted: Third Eye -> {expected}"
    for res in results:
        log(f"  verdict={res['verdict']} blocker={res['blocker']}")
        assert res["verdict"] == "CROSS_CLAIM_CONFLICT", res
        assert res["ready_for_aris"] is False
        assert res["blocker"] == "Third Eye", res["blocker"]
    # And the same claims pass individually when checked alone.
    solo = tg.check_claim(CLAIM_FRESH, prov, now=now)
    assert solo["ready_for_aris"] is True, \
        "contradiction-only failure must not poison a solo re-check"
    log("  PASS: batch catches the BETWEEN-items contradiction that solo "
        "checks cannot see; solo re-check stays clean")
    return {"verdict": "CROSS_CLAIM_CONFLICT", "blocker": "Third Eye",
            "solo_recheck_ready": True}


def scenario_gate_unavailable(tg):
    log("── SCENARIO 5: gate unavailable -> GATE_UNAVAILABLE, never raises ──")
    with mock.patch.object(tg, "_load_gate", return_value=None), \
         mock.patch.object(tg, "_probe_cache",
                           {"probed": False, "modules": None}):
        res = tg.check_claim(CLAIM_FRESH, {"url": FIXTURE_URL})
        assert res["verdict"] == "GATE_UNAVAILABLE", res
        assert res["ready_for_aris"] is False
        batch = tg.check_batch([{"text": CLAIM_FRESH},
                                {"text": CLAIM_CONTRADICTED}])
        assert len(batch) == 2 and all(
            b["verdict"] == "GATE_UNAVAILABLE" for b in batch), batch
    log("  PASS: fail-closed GATE_UNAVAILABLE on every public surface")
    return {"verdict": "GATE_UNAVAILABLE", "fail_closed": True}


# ---------------------------------------------------------------------------
# Scenarios — faculty wiring half (stubbed truth_gate, zero network)
# ---------------------------------------------------------------------------

READY_RES = {"verdict": "READY_FOR_AURIS", "ready_for_aris": True,
             "failure_kind": None, "blocker": None}
CONTESTED_RES = {"verdict": "STALE_OR_LINEAGE", "ready_for_aris": False,
                 "failure_kind": "STALE_OR_LINEAGE", "blocker": "Sacral"}


def _assert_split_result(result, hw, expect_gated=True):
    """Shared assertions for the stubbed-split wiring runs."""
    assert result.get("outcome") == "researched", result
    assert result.get("truth_gate_available") is True, result
    assert result.get("truth_gated") is expect_gated, result
    assert result.get("truth_ready") == 1, result
    assert result.get("truth_contested") == 1, result
    # Ready item crystallized WITH 'truth:aris'; contested did NOT.
    tags = hw.crystallized_tags()
    texts = hw.crystallized_texts()
    flat = [t for ent_tags in tags for t in ent_tags]
    assert "truth:aris" in flat, f"missing truth:aris tag: {tags}"
    assert "truth_unchecked" not in flat, f"unexpected unchecked tag: {tags}"
    ready_text = FIXTURE_ENTRIES[0]["dump_text"]
    contested_text = FIXTURE_ENTRIES[1]["dump_text"]
    assert any(ready_text in t for t in texts), \
        f"ready item not crystallized: {texts}"
    assert not any(contested_text in t for t in texts), \
        "contested item crystallized into the dataset!"
    # Contested item landed in the ledger, tagged, exactly once.
    ledger = _read_contested(hw.contested_file)
    assert len(ledger) == 1, f"expected 1 contested record, got {ledger}"
    rec = ledger[0]
    assert rec["verdict"] == "STALE_OR_LINEAGE", rec
    assert rec["blocker"] == "Sacral", rec
    assert rec["failure_kind"] == "STALE_OR_LINEAGE", rec
    assert contested_text == rec["text"], rec
    assert rec.get("provenance", {}).get("url"), rec
    assert rec.get("ts"), rec


def scenario_faculty_run_topic(rf):
    log("── SCENARIO 6: run_topic wiring (1 ready / 1 contested) ──")
    with tempfile.TemporaryDirectory(prefix="tg_e2e_topic_") as tmp:
        hw = Harness(tmp, rf)
        try:
            _patch_faculty_seams(hw, rf, FIXTURE_ENTRIES)
            _stub_truth_gate(hw, results=[READY_RES, CONTESTED_RES])
            result = rf.run_topic("solar wind")
            log(f"  outcome={result.get('outcome')} ready="
                f"{result.get('truth_ready')} contested="
                f"{result.get('truth_contested')}")
            _assert_split_result(result, hw)
            log("  PASS: ready item crystallized 'truth:aris'; contested "
                "item ledgered, never absorbed; counts honest")
            return {"outcome": result["outcome"],
                    "truth_ready": result["truth_ready"],
                    "truth_contested": result["truth_contested"],
                    "ledger_records": 1}
        finally:
            hw.unpatch_all()


def scenario_faculty_run_questions(rf):
    log("── SCENARIO 7: run_questions wiring (1 ready / 1 contested) ──")
    with tempfile.TemporaryDirectory(prefix="tg_e2e_questions_") as tmp:
        hw = Harness(tmp, rf)
        try:
            _patch_faculty_seams(hw, rf, FIXTURE_ENTRIES)
            hw.patch(rf, "_question_fragments", lambda max_n: [
                "what is the solar wind made of?"])
            _stub_truth_gate(hw, results=[READY_RES, CONTESTED_RES])
            result = rf.run_questions(max_questions=1)
            log(f"  outcome={result.get('outcome')} ready="
                f"{result.get('truth_ready')} contested="
                f"{result.get('truth_contested')}")
            _assert_split_result(result, hw)
            log("  PASS: questions mode honors the same truth layer")
            return {"outcome": result["outcome"],
                    "truth_ready": result["truth_ready"],
                    "truth_contested": result["truth_contested"],
                    "ledger_records": 1}
        finally:
            hw.unpatch_all()


def scenario_faculty_gate_unavailable(rf):
    log("── SCENARIO 8: gate unavailable -> honest degradation ──")
    with tempfile.TemporaryDirectory(prefix="tg_e2e_down_") as tmp:
        hw = Harness(tmp, rf)
        try:
            _patch_faculty_seams(hw, rf, FIXTURE_ENTRIES)
            fake = _stub_truth_gate(hw, available=False)
            result = rf.run_topic("solar wind")
            log(f"  outcome={result.get('outcome')} gated="
                f"{result.get('truth_gated')} available="
                f"{result.get('truth_gate_available')}")
            assert result.get("outcome") == "researched", result
            assert result.get("truth_gate_available") is False, result
            assert result.get("truth_gated") is False, result
            assert result.get("truth_ready") == 0, result
            assert result.get("truth_contested") == 0, result
            # Both fragments crystallized, tagged 'truth_unchecked'.
            tags = hw.crystallized_tags()
            flat = [t for ent_tags in tags for t in ent_tags]
            assert "truth_unchecked" in flat, f"missing degrade tag: {tags}"
            assert "truth:aris" not in flat, "truth:aris without a gate pass!"
            texts = hw.crystallized_texts()
            assert any(FIXTURE_ENTRIES[0]["dump_text"] in t for t in texts)
            assert any(FIXTURE_ENTRIES[1]["dump_text"] in t for t in texts)
            # Nothing contested, nothing ledgered; journal note fired once.
            assert _read_contested(hw.contested_file) == [], \
                "unavailable gate must not contest items"
            notes = [e for e in hw.events
                     if e["args"] and "truth_gate_unavailable" in str(
                         e["args"][1])]
            assert len(notes) == 1, f"journal/blog note missing: {hw.events}"
            assert fake._avail_calls, "stubbed gate was never probed"
            assert not fake._calls, \
                "unavailable gate must never receive batch checks"
            log("  PASS: research continues; fragments 'truth_unchecked'; "
                "journal/blog noted once; metrics distinguish")
            return {"outcome": result["outcome"],
                    "degraded_honestly": True,
                    "journal_noted": True}
        finally:
            hw.unpatch_all()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    import datetime as _dt
    ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
    log("=" * 72)
    log(f"truth_gate e2e dry verification — {ts}")
    log("=" * 72)

    benchmark = {
        "benchmark": "truth_gate_e2e",
        "generated_at": ts,
        "regression_baseline": True,
        "decree": "Kundalini/math-angle truth gate wired over the research "
                  "thread: grounded fresh claims -> READY_FOR_AURIS "
                  "(truth:aris tag), missing provenance -> MISSING_GROUNDING "
                  "(Root), stale provenance -> STALE_OR_LINEAGE (Sacral), "
                  "batch contradictions -> CROSS_CLAIM_CONFLICT (Third Eye); "
                  "contested material ledgered (truth_contested.jsonl), "
                  "never absorbed; gate unavailable -> honest "
                  "truth_unchecked degradation — zero network, fail-closed",
        "checks": {},
        "verdict": "PENDING",
    }

    try:
        import aureon_fusion.truth_gate as tg
    except Exception as exc:
        log(f"truth_gate not importable yet ({type(exc).__name__}: {exc})")
        benchmark["checks"]["module_available"] = {"pass": False,
                                                   "error": str(exc)[:200]}
        benchmark["verdict"] = ("PENDING — truth_gate module not importable")
        write_benchmark(benchmark)
        return 2

    mods = tg._load_gate()
    if mods is None:
        log("upstream truth gate not constructible under suppression env")
        benchmark["checks"]["module_available"] = {
            "pass": False, "error": "upstream gate unavailable"}
        benchmark["verdict"] = "PENDING — upstream gate unavailable"
        write_benchmark(benchmark)
        return 2

    benchmark["checks"]["module_available"] = {
        "pass": True,
        "gate_available": True,
        "kundalini_blockers": [list(b) for b in mods.gate.KUNDALINI_BLOCKERS],
    }

    import aureon_fusion.research_faculty as rf

    results = {}
    for name, fn in (
            ("fresh_claim_ready_for_aris", scenario_fresh_claim_ready),
            ("stale_claim_blocked_sacral",
             lambda tg_: scenario_stale_claim_blocked(tg_, mods)),
            ("missing_grounding_root",
             lambda tg_: scenario_missing_grounding(tg_, mods)),
            ("cross_claim_conflict_third_eye",
             lambda tg_: scenario_cross_claim_conflict(tg_, mods)),
            ("gate_unavailable_fail_closed", scenario_gate_unavailable),
            ("faculty_run_topic_truth_layer",
             lambda _: scenario_faculty_run_topic(rf)),
            ("faculty_run_questions_truth_layer",
             lambda _: scenario_faculty_run_questions(rf)),
            ("faculty_gate_unavailable_degrades",
             lambda _: scenario_faculty_gate_unavailable(rf)),
    ):
        try:
            info = fn(tg)
            benchmark["checks"][name] = {"pass": True, **info}
            results[name] = True
        except AssertionError as exc:
            log(f"  FAIL: {exc}")
            benchmark["checks"][name] = {"pass": False,
                                         "error": str(exc)[:300]}
            results[name] = False
        except Exception as exc:
            import traceback
            log(f"  ERROR: {type(exc).__name__}: {exc}")
            log(traceback.format_exc())
            benchmark["checks"][name] = {"pass": False,
                                         "error": f"{type(exc).__name__}: "
                                                  f"{exc}"[:300]}
            results[name] = False

    all_pass = all(results.values())
    benchmark["verdict"] = "PASS" if all_pass else "FAIL"
    log("=" * 72)
    log(f"VERDICT: {benchmark['verdict']}  "
        f"({sum(results.values())}/{len(results)} scenarios)")
    write_benchmark(benchmark)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
