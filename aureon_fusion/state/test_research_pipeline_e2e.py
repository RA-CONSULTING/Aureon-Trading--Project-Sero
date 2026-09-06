"""End-to-end dry verification for the RESEARCH OUTCOMES pipeline (R4+R5).

Exercises the full outcomes path inside a temp state dir — a stubbed
research_faculty (sys.modules pattern, ZERO real network) returns a fixed
result dict; knowledge_outcomes.record_research turns it into a
queen_knowledge row with honest success semantics; consult() ranks scored
rows ahead of unscored ones; record_research_memory chains research nodes
onto a fixture sero_memory_web. Then the fail-closed edges:

  1. running mean over days: T, F, T on one topic -> success_rate 0.66
  2. idempotent re-record of the same topic+day changes nothing
  3. success=True without fragments+corroboration is downgraded to None
     (never fabricated)
  4. consult ranks a scored row ahead of a more-applied unscored row
  5. record_research_memory chains the topic node to the 2 most recent
     fixture-web nodes and never raises on a dead engine

Seams (verified against aureon_fusion/knowledge_outcomes.py on disk):
  * HISTORY_DB_PATH is a module constant consumed per call by
    get_history_db() (explicit path arg to the upstream ghdb accessor) —
    redirect it into a per-run temp dir and reset the _CONN cache.
  * The idempotency grain is _record_day(now_ms) — patch it to walk days.
  * research_faculty is a lazy import in callers (never imported by
    knowledge_outcomes), so a sys.modules stub is sufficient and no
    packets can leave the machine.
  * sero_memory_web is a lazy import inside record_research_memory, so a
    sys.modules fixture MemoryWeb captures nodes/edges without touching
    the real memory graph.

Exit codes: 0 = all scenarios pass; 1 = a scenario failed; 2 = the
knowledge_outcomes module is not importable (benchmark records PENDING).

Usage:  python aureon_fusion/state/test_research_pipeline_e2e.py [-v]
"""

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
FUSION_STATE = WORKSPACE / "aureon_fusion" / "state"
BENCHMARK_FILE = FUSION_STATE / "benchmarks" / "research_pipeline_e2e.json"

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

FIXTURE_TOPIC = "heliospheric current sheet dynamics"
FIXTURE_SUMMARY = "stubbed research result summary"
FIXTURE_RESULT = {
    "outcome": "researched",
    "topic": FIXTURE_TOPIC,
    "questions_processed": 1,
    "items_found": 4,
    "fragments_added": 2,
    "corroborated": 1,
    "mode": "topic",
    "ingester_stats": {"items_pulled": 4, "vault_ingests": 4, "errors": 0},
}
FIXTURE_FRAGMENTS = [
    "The heliospheric current sheet spirals outward from the Sun as the "
    "solar wind carries the interplanetary magnetic field past Earth.",
    "Coronal mass ejections compress the current sheet and can trigger "
    "geomagnetic storms when their magnetic orientation turns southward.",
    "In situ spacecraft observe sector boundaries as sharp reversals of "
    "the radial magnetic field component.",
]


# ---------------------------------------------------------------------------
# Recording fakes
# ---------------------------------------------------------------------------

class FixtureMemoryWeb:
    """Drop-in for sero_memory_web.MemoryWeb — captures nodes and edges."""

    def __init__(self, record, fail=False):
        self._record = record
        self._fail = fail
        self.nodes = {}
        self.edges = []
        self._seq = 0
        self._inject = list(record.get("preexisting", []))

    def _remember(self, content, node_type, connections):
        node_id = f"fx_{self._seq}"
        self._seq += 1
        self.nodes[node_id] = {"content": content, "node_type": node_type}
        for c in (connections or []):
            if c in self.nodes:
                self.edges.append((node_id, c))
        return SimpleNamespace(id=node_id)

    def remember(self, content, node_type="fact", emotional_weight=0.0,
                 intensity=0.5, tags=None, connections=None):
        if self._fail:
            raise RuntimeError("engine down")
        node = self._remember(content, node_type, connections)
        self._record["remembered"].append({
            "content": content, "node_type": node_type,
            "connections": list(connections or []),
            "node_id": node.id,
        })
        return node

    def save(self):
        self._record["saves"] = self._record.get("saves", 0) + 1

    def preload(self, n=2):
        """Simulate n previously remembered nodes (the recent tail)."""
        for _ in range(n):
            node = self._remember(f"prior memory {self._seq}", "fact", None)
            self._record.setdefault("preloaded", []).append(node.id)
        return list(self.nodes)[-2:]


def _stub_research_faculty(hw, result=None):
    """Inject a fake aureon_fusion.research_faculty module — the pipeline
    driver — returning a fixed result dict. Zero network by construction."""
    fake = SimpleNamespace(try_research=lambda intent=None: dict(result or {}),
                           ORGAN_NAME="research_faculty")
    p = mock.patch.dict(sys.modules, {"aureon_fusion.research_faculty": fake})
    p.start()
    hw.patches.append(p)
    return fake


def _stub_sero_memory_web(hw, record, fail=False):
    """Inject a fixture sero_memory_web module (lazy import target). The
    fixture serves ONE shared web instance per stub — the scenario
    preloads it with prior nodes before record_research_memory runs."""
    class _SMW:
        _web = FixtureMemoryWeb(record, fail=fail)

        @staticmethod
        def MemoryWeb():
            return _SMW._web

    p = mock.patch.dict(sys.modules, {"sero_memory_web": _SMW})
    p.start()
    hw.patches.append(p)
    return _SMW._web


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class Harness:
    """Temp state dir + DB seam redirection for one scenario run."""

    def __init__(self, tmp, ko):
        self.tmp = Path(tmp)
        self.ko = ko
        self.patches = []
        self.db_path = self.tmp / "aureon_global_history.sqlite"
        self._conn = None

    def redirect_db(self):
        self.patch(self.ko, "HISTORY_DB_PATH", self.db_path)
        self.patch(self.ko, "_CONN", None)

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value, create=True)
        p.start()
        self.patches.append(p)
        return value

    def day_seq(self, days):
        """Patch _record_day to walk a fixed sequence of days (one item
        consumed per record_research call)."""
        it = iter(days)
        self.patch(self.ko, "_record_day",
                   lambda now_ms: next(it, days[-1]))

    def query_row(self, kid):
        conn = self.ko.get_history_db()
        if conn is None:
            return None
        return conn.execute(
            "SELECT * FROM queen_knowledge WHERE knowledge_id = ?",
            (kid,)).fetchone()

    def unpatch_all(self):
        # Close the scenario's sqlite handle before Windows tries to
        # delete the temp dir (the module-level _CONN cache holds it open).
        try:
            conn = getattr(self.ko, "_CONN", None)
            if conn and conn is not False:
                conn.close()
        except Exception:
            pass
        for p in reversed(self.patches):
            try:
                p.stop()
            except Exception:
                pass
        self.patches.clear()
        try:
            self.ko._CONN = None
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def scenario_pipeline_record(ko, hw):
    """Stubbed research_faculty result -> record_research -> correct row."""
    log("── SCENARIO 1: stubbed research result lands as research_topic row ──")
    fake = _stub_research_faculty(hw, FIXTURE_RESULT)
    result = fake.try_research({"topic": FIXTURE_TOPIC})
    assert result["topic"] == FIXTURE_TOPIC, "stub result lost its topic"
    kid = ko.record_research(
        topic=result["topic"], summary=FIXTURE_SUMMARY,
        items_found=result["items_found"],
        fragments_added=result["fragments_added"],
        corroborated=result["corroborated"], success=True)
    assert kid, "record_research returned no knowledge_id"
    row = hw.query_row(kid)
    assert row is not None, "no queen_knowledge row written"
    assert row["knowledge_type"] == "research_topic"
    assert row["topic"] == FIXTURE_TOPIC
    assert row["times_applied"] == 1
    assert row["success_rate"] == 1.0, \
        f"first scored True must give rate 1.0, got {row['success_rate']}"
    for token in (f"'{FIXTURE_TOPIC}'", "items_found=4",
                  "fragments_added=2", "corroborated=1", "api_communion"):
        assert token in row["summary"], f"summary missing {token!r}"
    payload = json.loads(row["raw_json"])
    assert payload["scored_applications"] == 1
    assert payload["record_day"], "record_day grain missing"
    log(f"  row {kid}: rate=1.0 times=1 day={payload['record_day']}")
    log("  PASS: research_topic row written with structured honest summary")
    return {"row_written": True, "knowledge_id": kid}


def scenario_running_mean_and_idempotency(ko, hw):
    """T, F, T across three days -> running mean 2/3; same-day re-record
    is a no-op."""
    log("── SCENARIO 2: running mean (T,F,T -> 0.66) + same-day idempotency ──")
    hw.day_seq(["2026-09-05", "2026-09-06", "2026-09-07",
                "2026-09-07", "2026-09-07"])
    kid = None
    for success in (True, False, True):
        kid = ko.record_research(FIXTURE_TOPIC, FIXTURE_SUMMARY,
                                 items_found=4, fragments_added=2,
                                 corroborated=1, success=success)
        assert kid, f"record_research day {success} returned empty id"
    row = hw.query_row(kid)
    assert row["times_applied"] == 3, \
        f"expected 3 applications (3 distinct days), got {row['times_applied']}"
    rate = float(row["success_rate"])
    assert abs(rate - 2.0 / 3.0) < 1e-6, \
        f"running mean after T,F,T must be 0.6667, got {rate}"
    payload = json.loads(row["raw_json"])
    assert payload["scored_applications"] == 3
    log(f"  T,F,T over 3 days -> success_rate={rate:.4f} "
        f"times_applied={row['times_applied']}")

    # Same topic+day re-record: nothing moves.
    before = dict(row)
    kid2 = ko.record_research(FIXTURE_TOPIC, "a different summary same day",
                              items_found=9, fragments_added=9,
                              corroborated=9, success=True)
    assert kid2 == kid, "same topic must map to the same knowledge_id"
    row2 = hw.query_row(kid)
    assert row2["times_applied"] == before["times_applied"], \
        "same-day re-record bumped times_applied (not idempotent)"
    assert abs(float(row2["success_rate"]) - rate) < 1e-9, \
        "same-day re-record moved the running mean"
    log("  PASS: mean 0.6667 over scored days; same-day re-record no-op")
    return {"running_mean": round(rate, 4), "times_applied": 3,
            "idempotent_same_day": True}


def scenario_no_fabricated_success(ko, hw):
    """success=True with zero fragments/corroboration degrades to None;
    a bare run with no signal stays NULL, never invented."""
    log("── SCENARIO 3: no fabricated success (fail-closed honesty) ──")
    kid_force = ko.record_research("empty topic run", "nothing absorbed",
                                   items_found=0, fragments_added=0,
                                   corroborated=0, success=True)
    row = hw.query_row(kid_force)
    assert row["success_rate"] is None, \
        "True with no quality signal must be downgraded to unscored"
    assert row["times_applied"] == 1
    payload = json.loads(row["raw_json"])
    assert payload["scored_applications"] == 0
    assert payload["last_success"] is None
    log("  forced True + zero signal -> success_rate NULL (honest)")

    kid_bare = ko.record_research("signal free run", "no corroboration",
                                  items_found=3, fragments_added=1,
                                  corroborated=0, success=None)
    row = hw.query_row(kid_bare)
    assert row["success_rate"] is None, \
        "no-signal run must stay unscored, never fabricated"
    log("  PASS: True-without-signal downgraded; None stays NULL")
    return {"forced_true_downgraded": True, "null_stays_null": True}


def scenario_consult_scored_first(ko, hw):
    """When tokens match both a scored and an unscored row, the scored row
    ranks first even with fewer applications."""
    log("── SCENARIO 4: consult ranks scored rows ahead of unscored ──")
    hot = "fusion coherence heuristic"
    assert ko.upsert_outcome("research_topic",
                             f"research topic '{hot}': unscored usage row",
                             None, topic=hot), "unscored seed failed"
    for _ in range(4):  # heavily applied, still unscored
        assert ko.upsert_outcome("research_topic",
                                 f"research topic '{hot}': unscored usage row",
                                 None, topic=hot)
    assert ko.record_research(hot, "cross-checked result", items_found=5,
                              fragments_added=2, corroborated=1,
                              success=True), "scored seed failed"
    hits = ko.consult(["coherence"], limit=5)
    assert len(hits) >= 2, f"expected both rows to match, got {len(hits)}"
    first = hits[0]
    assert first["success_rate"] is not None, \
        f"unscored row ranked first: {first['knowledge_id']}"
    assert first["topic"] == hot and first["times_applied"] == 1, \
        "scored row identity wrong"
    assert any(h["success_rate"] is None for h in hits[1:]), \
        "unscored row missing from the tail"
    log(f"  scored(rate={first['success_rate']}) first despite "
        f"times_applied={first['times_applied']} vs unscored x5")
    log("  PASS: scored knowledge outranks more-applied unscored knowledge")
    return {"scored_first": True, "hits": len(hits)}


def scenario_memory_chain(ko, hw):
    """record_research_memory chains the topic node to the 2 most recent
    fixture-web nodes; fragments chain within the run; never raises."""
    log("── SCENARIO 5: memory web chaining on a fixture web ──")
    record = {"remembered": []}
    web = _stub_sero_memory_web(hw, record)
    recent = web.preload(2)
    log(f"  fixture web preloaded with recent nodes: {recent}")
    created = ko.record_research_memory(FIXTURE_TOPIC, FIXTURE_FRAGMENTS)
    assert created == 4, f"expected 4 nodes (topic+3 fragments), got {created}"
    rem = record["remembered"]
    topic_call = rem[0]
    assert topic_call["node_type"] == "research_topic"
    assert sorted(topic_call["connections"]) == sorted(recent), \
        f"topic node not connected to the 2 most recent nodes: " \
        f"{topic_call['connections']} vs {recent}"
    prev = topic_call["node_id"]
    for call in rem[1:]:
        assert call["node_type"] == "research_fragment"
        assert call["connections"] == [prev], \
            f"fragment not chained to previous node: {call['connections']}"
        prev = call["node_id"]
    assert record.get("saves", 0) >= 1, "fixture web never saved"
    ids = [r["node_id"] for r in rem]
    log(f"  nodes created: {ids}")
    log(f"  edges: {[(e[0], e[1]) for e in web.edges]}")

    # Fail-closed: a dead engine yields 0, never an exception.
    dead = {"remembered": []}
    _stub_sero_memory_web(hw, dead, fail=True)
    assert ko.record_research_memory(FIXTURE_TOPIC, FIXTURE_FRAGMENTS) == 0, \
        "dead engine must return 0"
    assert ko.record_research_memory("", FIXTURE_FRAGMENTS) == 0
    assert ko.record_research_memory(FIXTURE_TOPIC, []) == 0
    log("  PASS: 4 chained nodes; dead engine / empty inputs fail closed to 0")
    return {"nodes_created": created, "chained_to_recent": True,
            "dead_engine_zero": True}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import datetime as _dt
    ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
    log("=" * 72)
    log(f"research_pipeline e2e dry verification — {ts}")
    log("=" * 72)

    benchmark = {
        "benchmark": "research_pipeline_e2e",
        "generated_at": ts,
        "regression_baseline": True,
        "decree": "research outcomes sink (R4) + memory connections (R5): "
                  "honest success semantics (True only when fragments AND "
                  "corroboration), running mean over scored days, "
                  "idempotent per topic+day, consult scored-first, "
                  "memory-web chaining — fail-closed, zero network",
        "checks": {},
        "verdict": "PENDING",
    }

    try:
        import aureon_fusion.knowledge_outcomes as ko
    except Exception as exc:
        log(f"knowledge_outcomes not importable yet ({type(exc).__name__}: {exc})")
        benchmark["checks"]["module_available"] = {"pass": False,
                                                   "error": str(exc)[:200]}
        benchmark["verdict"] = ("PENDING — knowledge_outcomes module not "
                                "importable")
        write_benchmark(benchmark)
        return 2

    benchmark["checks"]["module_available"] = {"pass": True}

    results = {}
    exit_code = 0
    for name, fn in (("research_result_lands_as_row", scenario_pipeline_record),
                     ("running_mean_and_idempotency",
                      scenario_running_mean_and_idempotency),
                     ("no_fabricated_success", scenario_no_fabricated_success),
                     ("consult_scored_first", scenario_consult_scored_first),
                     ("memory_web_chaining", scenario_memory_chain)):
        with tempfile.TemporaryDirectory(prefix=f"rp_e2e_{name}_") as tmp:
            hw = Harness(tmp, ko)
            hw.redirect_db()
            try:
                info = fn(ko, hw)
                benchmark["checks"][name] = {"pass": True, **info}
                results[name] = True
            except AssertionError as exc:
                log(f"  FAIL: {exc}")
                benchmark["checks"][name] = {"pass": False,
                                             "error": str(exc)[:300]}
                results[name] = False
                exit_code = 1
            except Exception as exc:
                import traceback
                log(f"  ERROR: {type(exc).__name__}: {exc}")
                log(traceback.format_exc())
                benchmark["checks"][name] = {"pass": False,
                                             "error": f"{type(exc).__name__}: "
                                                      f"{exc}"[:300]}
                results[name] = False
                exit_code = 1
            finally:
                hw.unpatch_all()

    all_pass = all(results.values())
    benchmark["verdict"] = "PASS" if all_pass else "FAIL"
    log("=" * 72)
    log(f"VERDICT: {benchmark['verdict']}  "
        f"({sum(results.values())}/{len(results)} scenarios)")
    write_benchmark(benchmark)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
