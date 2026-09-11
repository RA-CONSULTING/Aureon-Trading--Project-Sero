"""Offline verification probes for the QUEEN WIRING build (Phase 1+2, W1/W2/
W4/W5/W6 — the cycle-wiring deliverable).

Every scenario runs against a TEMP state dir (per-scenario tmp workspace
slice): mind state, reports, dream memory, conversation memory, the
upstream thought stream, the bus tail, HNC/trading/registry senses and the
queen_knowledge DB are redirected per scenario via module-constant seams.
The upstream faculty engines are replaced by recording stubs injected
directly into the QueenMind instance (faculty construction is bypassed),
so NOTHING here touches the live organism: zero writes outside the temp
dirs, zero process signals, zero network.

Probes:
  1.  dream facade unit   — quiet + low volatility -> dreamed=True, memory
                            file WRITTEN; high volatility / awake hours /
                            not idle -> dreamed=False (honest)
  2.  knowledge consult   — seeded queen_knowledge rows returned, ranked by
                            times_applied; empty tokens -> []; broken DB -> []
  3.  dormant engines     — activate_dormant_engines starts the cortex via
                            start() (incl. the faculty-exists retry branch)
                            and wires sentience; deactivate stops cleanly
  4.  full cycle wiring   — cycle_once with stub organs + temp state:
        a. sentience record_decision called; update_decision_outcome on
           the 5th-cycle resolution beat
        b. MindAugment absorb path invoked for the 40-event bus tail +
           propagate(cycles=1)
        c. reflection context carries conversation read-back + the last 20
           upstream thoughts
        d. report contains being_snap / world_snap
        e. qgita_calibration folded into the qgita regime product
        f. knowledge consult surfaces knowledge_applied in the report
        g. dream facade path: dreamed=True, memory file written, dreams
           counter incremented
        h. fail-closed: a RAISING sentience engine degrades the stage,
           never the cycle

Exit codes: 0 = all probes pass; 1 = at least one failed.
Usage:  python aureon_fusion/state/probe_queen_wiring.py [-v]
"""

import contextlib
import importlib
import json
import os
import sys
import tempfile
import time
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

import aureon_fusion.queen_mind as qm
import aureon_fusion.knowledge_outcomes as ko
import aureon_fusion.dream_facade as df

_py = sys.executable or "python"
_results = []
_MISSING = object()


def log(msg):
    print(msg)


def check(name, cond, detail=""):
    ok = bool(cond)
    _results.append((name, ok))
    mark = "PASS" if ok else "FAIL"
    log(f"  [{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))
    return ok


@contextlib.contextmanager
def patched_organs(**fakes):
    """Inject fake organ modules so NOTHING reaches the live organism.
    Patches BOTH sys.modules and the aureon_fusion package attribute —
    `from aureon_fusion import X` prefers the package attribute, so a
    sys.modules-only patch is silently shadowed once the real module has
    been imported. Restores everything on exit."""
    pkg = importlib.import_module("aureon_fusion")
    saved = []
    for fullname, fake in fakes.items():
        attr = fullname.split(".", 1)[1] if "." in fullname else fullname
        old_attr = getattr(pkg, attr, _MISSING)
        old_mod = sys.modules.get(fullname, _MISSING)
        if fake is None:
            if old_attr is not _MISSING:
                delattr(pkg, attr)
            sys.modules.pop(fullname, None)
        else:
            setattr(pkg, attr, fake)
            sys.modules[fullname] = fake
        saved.append((attr, old_attr, fullname, old_mod))
    try:
        yield
    finally:
        for attr, old_attr, fullname, old_mod in saved:
            if old_attr is _MISSING:
                if hasattr(pkg, attr):
                    delattr(pkg, attr)
            else:
                setattr(pkg, attr, old_attr)
            if old_mod is _MISSING:
                sys.modules.pop(fullname, None)
            else:
                sys.modules[fullname] = old_mod


def fake_module(fullname, **attrs):
    mod = types.ModuleType(fullname)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


def ns(**kw):
    return types.SimpleNamespace(**kw)


def iso_now():
    return datetime.now(timezone.utc).isoformat()


# ───────────────────────── fixture stubs ───────────────────────────────────

class StubDreamer:
    """Duck-typed EnigmaDreamer: real methods the facade calls."""

    def __init__(self):
        self.memory = ns(dreams=[], memory_file=None,
                         save=self._save)
        self.collected_wisdom = None
        self.wisdom_collector = ns(collect_all_wisdom=self._collect)
        self.saved_to = None

    def _collect(self):
        self.collected_wisdom = {
            "trades": [{"symbol": "GAMMA", "pnl": 12.5}],
            "patterns": [{"type": "winning_symbol", "count": 3,
                          "symbol": "GAMMA", "win_rate": 0.7}],
        }
        return self.collected_wisdom

    def _rem_dream(self):  # noqa: SLF001 — mirrors upstream private API
        self.memory.dreams.append(ns(dream_type="REM", content="replay",
                                     insight="fixture rem"))

    def dream_now(self, context=None):
        dream = ns(dream_type="REM", content="pattern dream",
                   insight="strongest pattern wins")
        self.memory.dreams.append(dream)
        return dream

    def _save(self):
        target = self.memory.memory_file
        if target:
            Path(target).write_text(json.dumps(
                {"dreams": len(self.memory.dreams)}), encoding="utf-8")
            self.saved_to = target


class StubScheduler:
    def __init__(self, idle_threshold_seconds=0):
        self.volatility_threshold = 0.5
        self.idle_threshold_seconds = idle_threshold_seconds
        self.last_activity_timestamp = 0.0
        self.notified = 0

    def notify_activity(self):
        self.notified += 1
        self.last_activity_timestamp = time.time()


class StubSentience:
    def __init__(self):
        self.recorded = []
        self.updated = []
        self.decision_history = {}

    def record_decision(self, decision_id, symbol, expected_outcome):
        self.recorded.append({"id": decision_id, "symbol": symbol,
                              "expected": expected_outcome})
        self.decision_history[decision_id] = {
            "symbol": symbol, "timestamp": time.time(),
            "expected_outcome": expected_outcome, "actual_outcome": None}

    def update_decision_outcome(self, decision_id, actual_outcome):
        self.updated.append({"id": decision_id, "actual": actual_outcome})
        if decision_id in self.decision_history:
            self.decision_history[decision_id]["actual_outcome"] = actual_outcome

    def get_sentience_status(self):
        return {"thinking": True, "thought_count": len(self.recorded)}


class RaisingSentience:
    def record_decision(self, *a, **kw):
        raise RuntimeError("sentience exploded")

    def get_sentience_status(self):
        raise RuntimeError("sentience exploded")


class StubCortex:
    def __init__(self):
        self._running = False
        self.started = 0
        self.stopped = 0

    def start(self):
        self._running = True
        self.started += 1

    def stop(self):
        self._running = False
        self.stopped += 1


class Harness:
    """Per-scenario temp state + module-constant seams."""

    CONSTANTS = (
        "MIND_STATE_PATH", "REPORTS_LOG", "CONSCIOUSNESS_METRICS_PATH",
        "DREAM_MEMORY_PATH", "UPSTREAM_BUS_PATH", "CONVERSATION_MEMORY_PATH",
        "CORPUS_INDEX_CACHE", "KNOWLEDGE_DATASET_PATH", "BUS_LOG",
        "REGISTRY_PATH", "HNC_STATE_PATH", "TRADING_PULSE_PATH",
        "HEARTBEAT_RESULTS_PATH",
    )

    def __init__(self, name):
        self.name = name
        self.tmp = Path(tempfile.mkdtemp(prefix=f"queen_wire_{name}_"))
        self.state = self.tmp / "state"
        self.state.mkdir(parents=True)
        self.mind_dir = self.state / "queen_mind"
        self.mind_dir.mkdir()
        self._patches = []

    def patch_constants(self):
        defaults = {
            "MIND_STATE_PATH": self.mind_dir / "mind_state.json",
            "REPORTS_LOG": self.mind_dir / "reports.jsonl",
            "CONSCIOUSNESS_METRICS_PATH": self.mind_dir / "metrics.json",
            "DREAM_MEMORY_PATH": self.mind_dir / "enigma_dream_memory.json",
            "UPSTREAM_BUS_PATH": self.mind_dir / "upstream_thoughts.jsonl",
            "CONVERSATION_MEMORY_PATH": self.mind_dir / "conversation_memory.json",
            "CORPUS_INDEX_CACHE": self.mind_dir / "research_corpus_index.json",
            "KNOWLEDGE_DATASET_PATH": self.mind_dir / "knowledge_dataset.json",
            "BUS_LOG": self.tmp / "thought_bus.jsonl",
            "REGISTRY_PATH": self.state / "organ_registry.json",
            "HNC_STATE_PATH": self.state / "hnc_core_state.json",
            "TRADING_PULSE_PATH": self.state / "trading_pulse_state.json",
            "HEARTBEAT_RESULTS_PATH": self.state / "heartbeat_last_results.json",
        }
        for name, value in defaults.items():
            self._patches.append(mock.patch.object(qm, name, value))
        for p in self._patches:
            p.start()
        return defaults

    def write_senses(self, n_bus=5, n_thoughts=25):
        now = iso_now()
        with open(self.tmp / "thought_bus.jsonl", "w", encoding="utf-8") as fh:
            for i in range(n_bus):
                fh.write(json.dumps({
                    "timestamp": now, "source": f"organ_{i}",
                    "topic": f"test.topic_{i}", "payload": {"i": i}}) + "\n")
        with open(self.mind_dir / "upstream_thoughts.jsonl", "w",
                  encoding="utf-8") as fh:
            for i in range(n_thoughts):
                fh.write(json.dumps({
                    "id": f"th_{i}", "ts": time.time(), "source": "cortex",
                    "topic": "queen.cortex", "payload": {"cycle": i}}) + "\n")
        (self.mind_dir / "conversation_memory.json").write_text(json.dumps({
            "version": 2, "threads": [{
                "peer_id": "organism",
                "turns": [{"role": "queen_mind", "text": f"cycle turn {i}"}
                          for i in range(6)]}]}), encoding="utf-8")
        (self.state / "hnc_core_state.json").write_text(json.dumps({
            "coherence_gamma": 0.8, "consciousness_psi": 0.6, "rung": 3}),
            encoding="utf-8")
        (self.state / "trading_pulse_state.json").write_text(json.dumps({
            "files": {"sweep": {"last_ts": now}}}), encoding="utf-8")
        (self.state / "organ_registry.json").write_text(json.dumps({
            "organs": {name: {"dormant": True}
                       for name in qm.ORGANS_EXPECTED_RUNNING}}),
            encoding="utf-8")
        (self.state / "heartbeat_last_results.json").write_text("{}",
                                                                encoding="utf-8")

    def restore(self):
        for p in reversed(self._patches):
            p.stop()
        self._patches.clear()


# ───────────────────────── probes ──────────────────────────────────────────

def probe_dream_facade():
    log("\n== 1. dream facade unit ==")
    h = Harness("facade")
    try:
        h.patch_constants()
        target = str(h.mind_dir / "enigma_dream_memory.json")

        res = df.run_rem_pass(StubDreamer(), quiet_hours=True, volatility=0.1,
                              scheduler=StubScheduler(), memory_path=target)
        check("quiet + low volatility -> dreamed=True",
              res.get("dreamed") is True, str(res))
        check("memory_path reported", res.get("memory_path") == target)
        check("memory file WRITTEN", Path(target).exists())

        res2 = df.run_rem_pass(StubDreamer(), quiet_hours=True, volatility=0.9,
                               scheduler=StubScheduler(), memory_path=target)
        check("high volatility -> dreamed=False", res2.get("dreamed") is False,
              str(res2))
        check("high volatility honest summary",
              "volatility" in str(res2.get("summary")))

        sched = StubScheduler()
        res3 = df.run_rem_pass(StubDreamer(), quiet_hours=False,
                               volatility=0.1, scheduler=sched,
                               memory_path=target)
        check("awake hours -> dreamed=False", res3.get("dreamed") is False)
        check("awake hours notify scheduler", sched.notified >= 1)

        res4 = df.run_rem_pass(None, quiet_hours=True, volatility=0.1)
        check("no dreamer -> dreamed=False (fail-closed)",
              res4.get("dreamed") is False)
    finally:
        h.restore()


def probe_consult():
    log("\n== 2. knowledge consult ==")
    h = Harness("consult")
    patches = []
    try:
        db_path = h.tmp / "knowledge.sqlite"
        patches.append(mock.patch.object(ko, "HISTORY_DB_PATH", db_path))
        patches.append(mock.patch.object(ko, "_CONN", None))
        for p in patches:
            p.start()
        check("DB accessor connects (temp file)", ko.get_history_db() is not None)
        check("seed row A inserted",
              ko.upsert_outcome("metacognition_lesson",
                                "metacognition coherence lesson alpha",
                                True, topic="queen_mind") is True)
        ko.upsert_outcome("metacognition_lesson",
                          "metacognition coherence lesson alpha",
                          True, topic="queen_mind")
        check("seed row B inserted",
              ko.upsert_outcome("market_lesson", "market pattern beta",
                                None, topic="trading") is True)
        rows = ko.consult(["metacognition", "queen_mind"], limit=5)
        check("consult returns the matching row", len(rows) == 1,
              f"got {len(rows)}: {rows}")
        if rows:
            check("consult row carries times_applied=2",
                  rows[0].get("times_applied") == 2, str(rows[0]))
            check("consult row carries success_rate",
                  rows[0].get("success_rate") is not None)
            check("consult row reports matched tokens",
                  "metacognition" in (rows[0].get("matched_tokens") or []))
        check("empty tokens -> []", ko.consult([], limit=5) == [])
        check("no-match tokens -> []", ko.consult(["zzz_no_match"], limit=5) == [])
        ko._CONN = False  # degraded sentinel
        check("broken DB -> [] (fail-closed)", ko.consult(["metacognition"]) == [])
    finally:
        for p in reversed(patches):
            p.stop()


def _stub_fac():
    class StubKnowledgeDataset:
        def __init__(self, path=None):
            self.path = path

        def absorb(self, pocket):
            return 1

        def find_similar(self, text, n=3):
            return []

        def get_status(self):
            return {"fragments": 3}

    class StubCorpusIndex:
        def __init__(self, **kw):
            pass

        def search(self, query, top_k=3):
            return []

    return ns(
        aureon_qgita=ns(execute_auris_loop=lambda s: s),
        aureon_qgita_framework=ns(QGITAMarketAnalyzer=object),
        qgita_calibration=ns(calibrate_qgita=lambda **kw: ns(
            phi_lattice_detected=True, calibrated=True, phi=1.618)),
        meaning_resolver=ns(get_meaning_resolver=lambda: ns(
            resolve=lambda q: ns(sources_consulted=["fixture"]))),
        knowledge_dataset=ns(KnowledgeDataset=StubKnowledgeDataset),
        research_corpus_index=ns(ResearchCorpusIndex=StubCorpusIndex),
        queen_consciousness_model=ns(BrainInput=lambda **kw: ns(**kw)),
        queen_cortex=ns(get_cortex=StubCortex),
        queen_sentience_integration=ns(get_sentience_engine=StubSentience),
    )


def _inject_engines(mind, fac, sentience):
    # SIMULATED stub auris input for wiring probe only (never live trading)
    auris = ns(time=0.0, price=1.0, high=1.0, low=1.0, volume=0.0,
               change_pct=0.0, coherenceIndex=0.5, unityIndex=0.5,
               dataIntegrity=0.5, choeranceDrift=0.0, inerchaVector=0.0,
               crystalCoherence=0.5,
               prismStatus="CLEAR", emotionalState="CALM", deerAlert=False,
               clownfishBond="STRONG", pandaHeart=0.8, hummingbirdLocked=False,
               falconSurge=False)
    mind._fac = fac
    mind._meta = ns(
        _reflect=lambda cognition: mind.__dict__.setdefault(
            "_captured_cognition", cognition) and ns(
            cycle=cognition.get("cycle"), action=cognition.get("action"),
            coherence_gamma=cognition.get("coherence_gamma"),
            consciousness_psi=cognition.get("consciousness_psi"),
            dominant_nodes=["gamma_coherence"], weakest_nodes=[],
            reasoning_summary="fixture", guidance=["hold the center"]),
        get_state=lambda: {"reflection_count": 1, "insight_count": 1},
        get_insights=lambda: [])
    mind._measure = ns(
        measure_consciousness=lambda **kw: ns(
            awakening_index=0.5, level="LOW", self_awareness=0.5,
            brain_coherence=0.5, learning_active=True,
            temporal_awareness=0.5),
        save_state=lambda: None)
    mind._consciousness = ns(perceive_input=lambda x: None,
                             synthesize_thought=lambda: None)
    mind._being = ns(snapshot=lambda: ns(to_dict=lambda: {"mood": "calm"}))
    mind._world = ns(snapshot=lambda: ns(to_dict=lambda: {"sky": "clear"}))
    mind._deep = ns(correlation_detector=ns(
        record_signal=lambda *a, **kw: None,
        detect_coincidences=lambda **kw: []),
        get_stats=lambda: {})
    mind._research = ns(run_one_cycle=lambda: {"ok": True})
    mind._dreamer = StubDreamer()
    mind._dream_scheduler = StubScheduler()
    mind._knowledge = ns(absorb=lambda p: 1, find_similar=lambda t, n=3: [],
                         get_status=lambda: {"fragments": 3})
    mind._interpreter = ns(
        interpret_entry=lambda **kw: ns(meaning="metacognition holds steady",
                                        data_type="observation",
                                        category="meta", why="fixture"),
        knowledge_dataset=None)
    mind._conversation = ns(record=lambda **kw: None)
    mind._tkb = ns(_on_event=lambda ev: None)
    mind._temporal_ground = ns(tick=lambda **kw: ns(
        current_hash="abc123", chain_length=3, forked_this_tick=False))
    mind._auris_state = auris
    mind._qgita_analyzer = ns(
        feed_price=lambda *a, **kw: None,
        analyze=lambda: {"regime": "coherent_flow",
                         "coherence": {"global_R": 0.7}, "status": "ok",
                         "stage1": {"ftcps": [1, 2]}, "stage2": {"e": 1}})
    mind._composer = ns(compose=lambda **kw: ns(
        text="The organism breathes in measured verse."))
    mind._sentience = sentience
    mind._learning_will = ns(consider_once=lambda dry_run=False: {
        "outcome": "no_intent"})
    mind._learning_will_broken = False
    mind._corpus = None
    return mind


def probe_full_cycle():
    log("\n== 3/4. full cycle wiring (temp state, stub organs) ==")
    h = Harness("cycle")
    h.patch_constants()
    h.write_senses(n_bus=5, n_thoughts=25)
    (h.mind_dir / "mind_state.json").write_text(json.dumps({"cycle": 9}),
                                                encoding="utf-8")
    ko_patches = [
        mock.patch.object(ko, "HISTORY_DB_PATH", h.tmp / "knowledge.sqlite"),
        mock.patch.object(ko, "_CONN", None),
    ]
    persona_patch = mock.patch.object(qm, "_PERSONA_ORDER", ("queen",))
    quiet_patch = mock.patch.object(qm, "QUIET_HOURS", (0, 24))
    registry_patch = mock.patch.object(
        qm.QueenMind, "_registry_status_view", staticmethod(lambda: None))
    conscience = fake_module("aureon_fusion.conscience_hook",
                             tally=lambda: {"total_checks": 10,
                                            "veto_count": 0})

    augment_calls = {"absorbed": 0, "propagated": 0}

    class FakeMindAugment:
        @property
        def available(self):
            return True

        def absorb_event(self, source, topic, payload=None):
            augment_calls["absorbed"] += 1
            return True

        def propagate(self, cycles=1):
            augment_calls["propagated"] += cycles
            return {"pathways": 4}

    sero_fake = fake_module("sero_mycelium", MindAugment=FakeMindAugment)

    try:
        for p in ko_patches:
            p.start()
        persona_patch.start()
        quiet_patch.start()
        registry_patch.start()
        ko.upsert_outcome("metacognition_lesson",
                          "metacognition coherence lesson alpha",
                          True, topic="queen_mind")
        with patched_organs(conscience_hook=conscience):
            sys.modules["sero_mycelium"] = sero_fake
            mind = qm.QueenMind()
            sentience = StubSentience()
            # one older decision still pending from a previous cycle — the
            # 5th-cycle resolution beat must resolve it with observed Γ.
            sentience.decision_history["queen_mind_cycle_9"] = {
                "symbol": "organism_gamma", "timestamp": time.time() - 120,
                "expected_outcome": 0.7, "actual_outcome": None}
            _inject_engines(mind, _stub_fac(), sentience)
            report = mind.cycle_once(publish=False)

        check("cycle completed (cycle 10)", report.get("cycle") == 10)
        sent = report.get("sentience") or {}
        check("W1: sentience record_decision called in cycle",
              len(sentience.recorded) == 1 and
              sentience.recorded[0]["id"] == "queen_mind_cycle_10",
              str(sentience.recorded))
        check("W1: report carries sentience stage",
              sent.get("recorded") is True, str(sent))
        check("W1: decision recorded against organism_gamma",
              sentience.recorded and
              sentience.recorded[0]["symbol"] == "organism_gamma")
        check("W1: update_decision_outcome resolves the older pending decision",
              len(sentience.updated) == 1 and
              sentience.updated[0]["id"] == "queen_mind_cycle_9",
              str(sentience.updated))
        check("W1: newest decision stays pending for a later cycle",
              sentience.decision_history.get(
                  "queen_mind_cycle_10", {}).get("actual_outcome") is None)
        check("W1: actual outcome = observed gamma",
              sentience.updated and
              abs(sentience.updated[0]["actual"] - 0.8) < 1e-6)

        check("W2: absorb_event invoked for the bus tail",
              augment_calls["absorbed"] == 5, str(augment_calls))
        check("W2: propagate(cycles=1) invoked",
              augment_calls["propagated"] == 1)
        ma = report.get("mind_augment") or {}
        check("W2: report carries mind_augment result",
              ma.get("available") is True and ma.get("absorbed") == 5,
              str(ma))
        check("W2: pathway count surfaced", ma.get("pathways") == 4)

        captured = mind.__dict__.get("_captured_cognition") or {}
        rc = captured.get("recent_conversation") or []
        check("W4a: conversation read-back in reflection context",
              len(rc) >= 1 and rc[-1].get("role") == "queen_mind",
              str(rc[-1:] if rc else rc))
        rt = captured.get("recent_thoughts") or []
        check("W4a: last 20 upstream thoughts in reflection context",
              len(rt) == 20 and rt[-1].get("cycle") == 24, str(len(rt)))
        rb = report.get("readback") or {}
        check("W4a: readback counts in report",
              rb.get("conversation_turns") >= 1 and
              rb.get("upstream_thoughts") == 20, str(rb))

        check("W4b: being_snap in report",
              report.get("being_snap") == {"mood": "calm"})
        check("W4b: world_snap in report",
              report.get("world_snap") == {"sky": "clear"})

        qg = (report.get("native_reasoning") or {}).get("qgita") or {}
        check("W4c: calibration folded into qgita product",
              (qg.get("calibration") or {}).get("calibrated") is True,
              str(qg))
        check("W4c: regime carries the calibration decision",
              isinstance(qg.get("regime"), dict) and
              qg["regime"].get("calibrated") is True, str(qg.get("regime")))

        kn = (report.get("native_reasoning") or {}).get("knowledge") or {}
        applied = kn.get("knowledge_applied") or []
        check("W6: knowledge_applied surfaced in report", len(applied) >= 1,
              str(kn)[:200])
        if applied:
            check("W6: applied row carries times_applied/success_rate",
                  applied[0].get("times_applied") == 1 and
                  applied[0].get("success_rate") is not None)

        dp = report.get("dream_pass") or {}
        check("W5: dream facade reports dreamed=True",
              dp.get("dreamed") is True, str(dp))
        check("W5: dream memory file written",
              Path(str(dp.get("memory_path"))).exists())
        check("W5: dreams counter incremented only on a real dream",
              (mind._state.get("dreams") or 0) == 1,
              str(mind._state.get("dreams")))
        check("W5: report persisted to the (temp) reports log",
              (h.mind_dir / "reports.jsonl").exists() and
              len((h.mind_dir / "reports.jsonl").read_text().splitlines()) == 1)

        stages = (report.get("native_reasoning") or {}).get("stages") or {}
        check("stages honest: consult stage ok",
              stages.get("knowledge_outcomes") == "ok",
              str(stages.get("knowledge_outcomes")))
        check("stages honest: calibration ran on the 10th cycle",
              stages.get("qgita_calibration") == "ok",
              str(stages.get("qgita_calibration")))

        # fail-closed: a raising sentience engine must degrade the stage,
        # never the cycle.
        mind._sentience = RaisingSentience()
        report2 = mind.cycle_once(publish=False)
        check("fail-closed: raising sentience -> cycle still completes",
              report2.get("cycle") == 11)
        check("fail-closed: sentience stage degraded honestly",
              (report2.get("sentience") or {}).get("recorded") is False and
              "raised" in str((report2.get("sentience") or {}).get("detail")),
              str(report2.get("sentience")))
    finally:
        sys.modules.pop("sero_mycelium", None)
        registry_patch.stop()
        quiet_patch.stop()
        persona_patch.stop()
        for p in reversed(ko_patches):
            p.stop()
        h.restore()


def probe_dormant_engines():
    log("\n== 5. dormant engine activation (door contract) ==")
    h = Harness("dormant")
    try:
        h.patch_constants()
        h.write_senses(n_bus=1, n_thoughts=1)
        mind = qm.QueenMind()
        mind._meta = object()          # faculty builder would be skipped
        cortex = StubCortex()
        mind._cortex = cortex
        mind._sentience = StubSentience()

        res = qm.activate_dormant_engines()
        check("activate: cortex start() invoked",
              cortex.started == 1 and cortex._running is True, str(res))
        check("activate: sentience wired ready",
              res.get("sentience_ready") is True, str(res))
        check("activate: ok + state recorded",
              res.get("ok") is True and
              qm._DORMANT_ENGINE_STATE.get("cortex_started") is True)
        check("activate: thought_count surfaced",
              qm._DORMANT_ENGINE_STATE.get("sentience_thoughts") == 0)

        # idempotent: an already-running cortex is not double-started
        res2 = qm.activate_dormant_engines()
        check("re-activate: no duplicate start",
              cortex.started == 1 and "already running" in res2.get("detail"),
              str(res2))

        res3 = qm.deactivate_dormant_engines()
        check("deactivate: cortex stop() invoked",
              cortex.stopped == 1 and cortex._running is False, str(res3))

        # faculty-exists retry branch: cortex None at boot, faculty present
        mind2 = qm.QueenMind()
        mind2._meta = object()
        mind2._cortex = None
        cortex2 = StubCortex()
        mind2._fac = ns(queen_cortex=ns(get_cortex=lambda: cortex2))
        mind2._sentience = None
        res4 = qm.activate_dormant_engines()
        check("activate retry: faculty built but cortex absent -> retried",
              cortex2.started == 1, str(res4))
        check("activate retry: no live sentience reported honestly",
              res4.get("sentience_ready") is False)

        # no live instance at all -> honest no-op
        with mock.patch.object(qm, "_LIVE_MINDS", []):
            res5 = qm.activate_dormant_engines()
        check("no live mind -> honest no-op",
              res5.get("ok") is False and "no live" in res5.get("detail"),
              str(res5))
    finally:
        h.restore()


# ───────────────────────── runner ──────────────────────────────────────────

def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    probes = (
        probe_dream_facade,
        probe_consult,
        probe_full_cycle,
        probe_dormant_engines,
    )
    only = set(a for a in (argv or sys.argv[1:]) if not a.startswith("-"))
    for probe in probes:
        if only and probe.__name__ not in only:
            continue
        try:
            probe()
        except Exception as exc:
            check(f"{probe.__name__} raised", False, repr(exc))

    total = len(_results)
    passed = sum(1 for _, ok in _results if ok)
    log(f"\n{'═' * 60}")
    log(f"QUEEN WIRING PROBES: {passed}/{total} passed")
    for name, ok in _results:
        if not ok:
            log(f"  FAILED: {name}")
    log("═" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
