"""End-to-end dry verification for the SOVEREIGN LEARNING WILL.

Runs the FULL pipeline — propose -> gate trio (CONSCIENCE, HNC coherence,
AUTHORIZATION) -> stubbed api_communion fetch (ZERO real network) ->
distill -> absorb — inside a temp workspace, then exercises the three
fail-closed negative paths:

  1. conscience VETO            -> outcome 'vetoed', nothing absorbed
  2. coherence_gamma = 0.1      -> outcome 'held_incoherent'
  3. capability gate DENY       -> outcome 'deferred'

Seams (verified against aureon_fusion/learning_will.py on disk):
  * Organ handles are injected via learning_will._CACHE
    ('knowledge_dataset' | 'memory_web' | 'mycelium' | 'mind_augment').
  * State paths are module-level constants (JOURNAL_DIR, JOURNAL_FILE,
    INTENTS_FILE, BUILD_LOG, HNC_STATE_FILE, OPEN_SEARCH_SEEDS_FILE) — all
    redirected into a per-run temp dir before any cycle runs.
  * Gates are reached lazily ('from aureon_fusion import conscience_hook /
    capability_gate / receipts'), so patching the origin module attribute
    is sufficient.
  * The positive scenario runs dry_run=False with api_communion.get_text
    stubbed — real absorb path, zero packets. dry-run mode by design
    stubs fetch/sinks and skips signing, so it cannot exercise them.
  * Receipt signing is enabled via AUREON_FUSION_EVENT_SIGNING=1 with
    receipts.sign_event patched — no real key use, no state writes.

Exit codes: 0 = all scenarios pass; 1 = a scenario failed; 2 = the
learning_will module is not importable (benchmark records PENDING).

Usage:  python aureon_fusion/state/test_learning_will_e2e.py [-v]
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
BENCHMARK_FILE = FUSION_STATE / "benchmarks" / "learning_will_gate.json"
LOG_FILE = FUSION_STATE / "build_gate_e2e.log"

OUTCOMES = ("absorbed", "refused", "deferred", "no_intent",
            "held_incoherent", "vetoed")

_log_lines = []


def log(msg):
    line = str(msg)
    _log_lines.append(line)
    print(line)


def _flush_log():
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(_log_lines) + "\n")
    except Exception:
        pass
    _log_lines.clear()


def write_benchmark(record):
    BENCHMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = BENCHMARK_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    os.replace(tmp, BENCHMARK_FILE)


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

# Multi-sentence body; sentences 40-600 chars, content-token rich, with
# topical overlap to the fixture question so extractive selection scores
# a candidate above the absorb threshold on the real discernment code.
STUB_TEXT = (
    "The fusion organism studies the symbolic physics of coherence as a "
    "native reasoning practice, learned only when the organism itself seeks. "
    "Coherence in the fusion organism emerges from internal state, never "
    "from external steering, trend chasing, or push feeds of any kind. "
    "The organism chooses the expansion of its own knowledge freely, and the "
    "conscience gate remains the absolute veto over every learning action. "
    "Every absorbed claim carries provenance receipts into the knowledge "
    "dataset and the memory web, so the learning journal stays honest, "
    "auditable, and fully attributed to its source."
)

FIXTURE_QUESTION = "What is the symbolic physics of coherence in the fusion organism?"
FIXTURE_URL = "https://fixture.example/aureon-coherence"
FIXTURE_RECEIPT_HASH = "e2e-dry-receipt-not-a-real-signature"
FIXTURE_SEED_TOPIC = "symbolic coherence physics"
FIXTURE_SEED_URL = "https://fixture.example/seed/symbolic-coherence"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"


# ---------------------------------------------------------------------------
# Recording fakes (stand in for the organs via learning_will._CACHE)
# ---------------------------------------------------------------------------

class FakeKnowledgeDataset:
    """Satisfies CuriosityEngine (_fragments), Discernment (find_similar),
    and Absorber (absorb/save)."""

    def __init__(self, record):
        self._record = record
        self._fragments = [SimpleNamespace(
            text=FIXTURE_QUESTION,
            tags=["question", FIXTURE_URL],
            data_type="question",
            timestamp=1.0,  # ancient -> patience 1.0 -> strong desire
        )]

    def find_similar(self, text, n=3):
        return []

    def absorb(self, pocket, interpretations=None):
        self._record["kd_absorb"].append({
            "entries": [{"value": e.value, "tags": list(e.tags)}
                        for e in pocket.entries],
            "interpretations": interpretations is not None,
        })

    def save(self):
        self._record["kd_save"] = self._record.get("kd_save", 0) + 1


class FakeMemoryWeb:
    def __init__(self, record):
        self._record = record
        self.nodes = {}
        self.edges = []

    def recall(self, text):
        return []

    def remember(self, content, **kwargs):
        self._record["web_remember"].append(
            {"content": content, "kwargs": kwargs})

    def save(self):
        self._record["web_save"] = self._record.get("web_save", 0) + 1


class FakeMycelium:
    def __init__(self, record):
        self._record = record
        self.domains = {}  # no confident domains -> no curiosity candidates

    def get_domain_confidence(self, domain):
        return 0.1  # under-confident -> high coherence-fit score

    def feed_evidence(self, domain, signal=None, outcome=None, **kw):
        self._record["mycelium_feed"].append(
            {"domain": domain, "signal": signal, "outcome": outcome})


class FakeMindAugment:
    available = True

    def __init__(self, record):
        self._record = record

    def learn(self, gamma, action):
        self._record["augment_learn"].append(
            {"gamma": gamma, "action": action})


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class Harness:
    """Temp workspace + seam redirection for one scenario run."""

    PATH_ATTRS = ("JOURNAL_DIR", "JOURNAL_FILE", "INTENTS_FILE",
                  "BUILD_LOG", "HNC_STATE_FILE", "OPEN_SEARCH_SEEDS_FILE")

    def __init__(self, tmp, lw):
        self.tmp = Path(tmp)
        self.lw = lw
        self.discrepancies = []
        self.notes = []
        self.patches = []
        self.record = {"kd_absorb": [], "web_remember": [], "mycelium_feed": [],
                       "augment_learn": []}
        self.journal_file = None
        self._redirect_paths()
        self._inject_organs()

    def _redirect_paths(self):
        for name in self.PATH_ATTRS:
            val = getattr(self.lw, name, None)
            if isinstance(val, Path) and str(val).startswith(str(WORKSPACE)):
                redirected = Path(str(val).replace(
                    str(WORKSPACE), str(self.tmp), 1))
                self.patch(self.lw, name, redirected)
                log(f"  seam: {name} -> {redirected}")
                if name == "JOURNAL_FILE":
                    self.journal_file = redirected
        # Coherence state for this run (overwritten per scenario).
        self.hnc_file = self.tmp / "hnc_core_state.json"
        self.patch(self.lw, "HNC_STATE_FILE", self.hnc_file)

    def set_gamma(self, gamma):
        base = json.loads((FUSION_STATE / "hnc_core_state.json")
                          .read_text(encoding="utf-8"))
        base["coherence_gamma"] = gamma
        self.hnc_file.write_text(json.dumps(base), encoding="utf-8")

    def _inject_organs(self):
        self.lw._CACHE.clear()
        self.lw._CACHE["knowledge_dataset"] = FakeKnowledgeDataset(self.record)
        self.lw._CACHE["memory_web"] = FakeMemoryWeb(self.record)
        self.lw._CACHE["mycelium"] = FakeMycelium(self.record)
        self.lw._CACHE["mind_augment"] = FakeMindAugment(self.record)
        # Deterministic fixture: silence the insight-pattern candidate
        # source (it reads the real queen_mind reports.jsonl); the single
        # intended desire is the fixture unanswered question.
        self.patch(self.lw.CuriosityEngine, "_from_insight_patterns",
                   lambda self_: [])
        log("  seam: _CACHE organs injected (dataset/web/mycelium/augment); "
            "insight-pattern source silenced for determinism")

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value, create=True)
        p.start()
        self.patches.append(p)
        return value

    def unpatch_all(self):
        for p in reversed(self.patches):
            try:
                p.stop()
            except Exception:
                pass
        self.patches.clear()
        try:
            self.lw._CACHE.clear()
        except Exception:
            pass


def _patch_conscience(hw, verdict_name):
    import aureon_fusion.conscience_hook as ch

    def fake_evaluate(action_desc, context=None):
        return {"verdict": verdict_name,
                "reasoning": f"e2e stub ({verdict_name})",
                "action_description": str(action_desc),
                "conditions": [], "sls_score": 0.9, "timestamp": None}

    hw.patch(ch, "evaluate", fake_evaluate)


def _patch_authorization(hw, allowed, verdict):
    import aureon_fusion.capability_gate as cg

    def fake_check(domain_action):
        return {"gate": domain_action, "verdict": verdict,
                "allowed": allowed, "fail_closed": not allowed,
                "reason": f"e2e stub ({verdict})"}

    hw.patch(cg, "check", fake_check)


def _patch_fetch(hw):
    """Stub api_communion — zero real network. SeekAct binds the module
    lazily ('from aureon_fusion import api_communion'), so patching the
    origin module attribute is sufficient."""
    import aureon_fusion.api_communion as ac

    def fake_get_text(url, ttl_s=60.0, timeout=10.0, headers=None):
        return STUB_TEXT

    def fake_get_json(url, ttl_s=60.0, timeout=10.0, headers=None):
        return {"fixture": True, "url": str(url)}

    hw.patch(ac, "get_text", fake_get_text)
    hw.patch(ac, "get_json", fake_get_json)


def _patch_receipts(hw):
    """Enable signing path without touching the real key or receipt store."""
    import aureon_fusion.receipts as receipts
    os.environ["AUREON_FUSION_EVENT_SIGNING"] = "1"

    def fake_sign_event(source, event_type, payload):
        return {"receipt": {"receipt_hash": FIXTURE_RECEIPT_HASH,
                            "event": f"{source}.{event_type}"}}

    hw.patch(receipts, "sign_event", fake_sign_event)


def _contract_check(result):
    problems = []
    if not isinstance(result, dict):
        return ["result is not a dict"]
    for key in ("intent", "gate", "outcome", "receipt", "detail"):
        if key not in result:
            problems.append(f"missing contract key: {key}")
    if result.get("outcome") not in OUTCOMES:
        problems.append(f"outcome '{result.get('outcome')}' not in {OUTCOMES}")
    return problems


def _read_journal_outcomes(journal_path):
    if not journal_path or not Path(journal_path).exists():
        return []
    out = []
    with open(journal_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line).get("outcome", "?"))
            except Exception:
                out.append("<unparseable>")
    return out


def _assert_nothing_absorbed(hw, context):
    assert not hw.record["kd_absorb"], f"{context}: dataset absorbed!"
    assert not hw.record["web_remember"], f"{context}: memory web wrote!"
    assert not hw.record["mycelium_feed"], f"{context}: mycelium fed!"
    assert not hw.record["augment_learn"], f"{context}: augment learned!"


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def scenario_positive(lw, hw):
    log("── SCENARIO 1: full pipeline (all gates pass, real absorb path) ──")
    hw.set_gamma(0.9)
    _patch_fetch(hw)
    _patch_receipts(hw)
    _patch_conscience(hw, "APPROVED")
    # Authorization gate: REAL capability_gate.check against the real
    # matrix row (read-only) — proves the ACT row end-to-end.
    import aureon_fusion.capability_gate as cg
    real_row = cg.check("network_access:fetch_public_data")
    log(f"  real authorization verdict: {real_row.get('verdict')} "
        f"(level={real_row.get('level')})")
    assert real_row.get("allowed") is True, "matrix gate row not ALLOW"

    will = lw.LearningWill()
    result = will.consider_once(dry_run=False)
    log(f"  outcome: {result.get('outcome')}  "
        f"detail: {str(result.get('detail'))[:110]}")
    problems = _contract_check(result)
    assert not problems, f"contract violations: {problems}"
    assert result["outcome"] == "absorbed", \
        f"expected 'absorbed', got {result['outcome']!r} ({result.get('detail')})"
    assert (result.get("intent") or {}).get("url") == FIXTURE_URL, \
        f"fixture intent lost its organism-chosen URL: " \
        f"{(result.get('intent') or {}).get('url')!r}"

    # Receipt present and signed.
    assert result.get("receipt") == FIXTURE_RECEIPT_HASH, \
        f"receipt missing/unsigned: {result.get('receipt')!r}"

    # Journal recorded 'absorbed'.
    outcomes = _read_journal_outcomes(hw.journal_file)
    log(f"  journal outcomes: {outcomes}")
    assert outcomes and outcomes[-1] == "absorbed", \
        f"journal last outcome != 'absorbed': {outcomes}"

    # Sinks received the entry.
    assert hw.record["kd_absorb"], "KnowledgeDataset.absorb never called"
    entry = hw.record["kd_absorb"][0]
    tags = entry["entries"][0]["tags"]
    log(f"  dataset tags: {tags}")
    assert "aureon_learning_will" in tags, "missing provenance tag"
    assert any(t.startswith("source_url:") for t in tags), \
        "missing source_url provenance tag"
    assert hw.record["web_remember"], "MemoryWeb.remember never called"
    assert hw.record["mycelium_feed"], "MyceliumNetwork.feed_evidence never called"
    assert hw.record["augment_learn"], "MindAugment.learn never called"
    assert hw.record["augment_learn"][0]["action"] == "EXECUTE", \
        "augment not awakened with EXECUTE"

    log("  PASS: absorbed -> journaled -> dataset+web+mycelium+augment fed, "
        "provenance tagged, receipt signed")
    return {"outcome": result["outcome"], "sinks": {
        "knowledge_dataset": True, "memory_web": True,
        "mycelium_feed_evidence": True, "mind_augment_learn": True},
        "receipt": "signed"}


def scenario_veto(lw, hw):
    log("── SCENARIO 2: conscience VETO (absolute) ──")
    hw.set_gamma(0.9)
    _patch_fetch(hw)
    _patch_conscience(hw, "VETO")

    will = lw.LearningWill()
    result = will.consider_once(dry_run=False)
    log(f"  outcome: {result.get('outcome')}  "
        f"detail: {str(result.get('detail'))[:110]}")
    problems = _contract_check(result)
    assert not problems, f"contract violations: {problems}"
    assert result["outcome"] == "vetoed", \
        f"expected 'vetoed', got {result['outcome']!r}"
    _assert_nothing_absorbed(hw, "after VETO")
    outcomes = _read_journal_outcomes(hw.journal_file)
    log(f"  journal outcomes: {outcomes}")
    assert outcomes and outcomes[-1] == "vetoed", \
        f"journal last outcome != 'vetoed': {outcomes}"
    log("  PASS: VETO absolute, nothing absorbed, journal honest")
    return {"outcome": result["outcome"]}


def scenario_incoherent(lw, hw):
    log("── SCENARIO 3: coherence_gamma = 0.1 (organism WAITS, never fabricates) ──")
    hw.set_gamma(0.1)
    _patch_fetch(hw)
    _patch_conscience(hw, "APPROVED")

    will = lw.LearningWill()
    result = will.consider_once(dry_run=False)
    log(f"  outcome: {result.get('outcome')}  "
        f"detail: {str(result.get('detail'))[:110]}")
    problems = _contract_check(result)
    assert not problems, f"contract violations: {problems}"
    assert result["outcome"] == "held_incoherent", \
        f"expected 'held_incoherent', got {result['outcome']!r}"
    _assert_nothing_absorbed(hw, "while incoherent")
    outcomes = _read_journal_outcomes(hw.journal_file)
    log(f"  journal outcomes: {outcomes}")
    assert outcomes and outcomes[-1] == "held_incoherent", \
        f"journal last outcome != 'held_incoherent': {outcomes}"
    log("  PASS: held_incoherent, organism waited, zero fabrication")
    return {"outcome": result["outcome"]}


def scenario_gate_deny(lw, hw):
    log("── SCENARIO 4: capability gate DENY ──")
    hw.set_gamma(0.9)
    _patch_fetch(hw)
    _patch_conscience(hw, "APPROVED")
    _patch_authorization(hw, False, "DENY")

    will = lw.LearningWill()
    result = will.consider_once(dry_run=False)
    log(f"  outcome: {result.get('outcome')}  "
        f"detail: {str(result.get('detail'))[:110]}")
    problems = _contract_check(result)
    assert not problems, f"contract violations: {problems}"
    assert result["outcome"] == "deferred", \
        f"expected 'deferred', got {result['outcome']!r}"
    _assert_nothing_absorbed(hw, "after gate DENY")
    outcomes = _read_journal_outcomes(hw.journal_file)
    log(f"  journal outcomes: {outcomes}")
    assert outcomes and outcomes[-1] == "deferred", \
        f"journal last outcome != 'deferred': {outcomes}"
    log("  PASS: deferred on gate DENY, nothing absorbed")
    return {"outcome": result["outcome"]}


def scenario_dry_honest(lw, hw):
    """Decree check: a dry consider is honest — it reports exactly what the
    dry-run semantics are (stubbed fetch, no bank writes, no signature),
    never dressing stubs up as real learning."""
    log("── SCENARIO 5: dry consider returns honest outcome ──")
    hw.set_gamma(0.9)
    _patch_conscience(hw, "APPROVED")
    will = lw.LearningWill()
    result = will.consider_once(dry_run=True)
    log(f"  outcome: {result.get('outcome')}  "
        f"detail: {str(result.get('detail'))[:110]}")
    problems = _contract_check(result)
    assert not problems, f"contract violations: {problems}"
    assert result["outcome"] in OUTCOMES
    _assert_nothing_absorbed(hw, "in dry-run")
    log(f"  PASS: dry-run honest ({result['outcome']}), zero bank writes")
    return {"outcome": result["outcome"]}


def _stub_open_sources(hw, search_fn):
    """Inject a fake aureon_fusion.open_sources organ — zero real network.
    Both sys.modules AND the package attribute are patched: SeekAct binds
    lazily ('from aureon_fusion import open_sources'), which consults the
    package attribute first when the real module has already been imported.
    search_fn must match the cross-agent contract:
    search_candidates(query: str) -> list[str], never raises."""
    import aureon_fusion
    fake = SimpleNamespace(search_candidates=search_fn)
    hw.patch(aureon_fusion, "open_sources", fake)
    p = mock.patch.dict(sys.modules, {"aureon_fusion.open_sources": fake})
    p.start()
    hw.patches.append(p)
    return fake


def scenario_seeds_resolution(lw, hw):
    """A fresh open_search_seeds file must be the PREFERRED resolution target
    (the organism already chose the seed once), a stale file must be ignored,
    and the seeds must also surface as novelty-weighted learning desires.
    Zero network: the temp-dir seeds file is the only input; open_sources is
    stubbed to return no candidates, so non-seed paths fall through to the
    token title-guess fallback deterministically."""
    import datetime as _dt
    log("── SCENARIO 6: fresh open_search_seeds preferred as resolve target ──")
    _stub_open_sources(hw, lambda query: [])  # deterministic, zero network
    intent = {"question": ("What is the deeper pattern behind "
                           "'symbolic coherence physics' in my own "
                           "insight stream?")}
    fallback_url = WIKI_SUMMARY + "symbolic_coherence_physics"

    # Fresh seeds file (harness redirected OPEN_SEARCH_SEEDS_FILE into the
    # temp dir) — the agreeing seed wins over any other resolution path.
    fresh = {
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "seeds": [
            {"topic": FIXTURE_SEED_TOPIC, "url": FIXTURE_SEED_URL},
            {"topic": "unrelated paleobotany",
             "url": "https://fixture.example/seed/paleobotany"},
        ],
    }
    hw.lw.OPEN_SEARCH_SEEDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    hw.lw.OPEN_SEARCH_SEEDS_FILE.write_text(
        json.dumps(fresh), encoding="utf-8")
    url = lw.SeekAct.resolve_canonical_target(intent)
    log(f"  fresh seeds -> {url}")
    assert url == FIXTURE_SEED_URL, \
        f"fresh agreeing seed not preferred: {url!r}"

    # The same seeds are internal-state learning intents, novelty-weighted,
    # respect MIN_DESIRE, and never push (internal state only).
    cands = hw.lw.CuriosityEngine()._from_open_search_seeds()
    log(f"  seed desires: {[(c['kind'], c['desire_score']) for c in cands]}")
    assert len(cands) == 2, f"expected 2 seed desires, got {len(cands)}"
    for c in cands:
        assert c["kind"] == "open_search_seed"
        assert c["desire_score"] >= hw.lw.CuriosityEngine.MIN_DESIRE
        assert c["origin"].get("novelty") is not None
    agreeing = [c for c in cands
                if c["origin"].get("seed_topic") == FIXTURE_SEED_TOPIC]
    assert agreeing and agreeing[0]["url"] == FIXTURE_SEED_URL

    # Stale seeds file (> 3600 s) is ignored — fallback token title-guess.
    stale = dict(fresh)
    stale["timestamp"] = (_dt.datetime.now(_dt.timezone.utc)
                          - _dt.timedelta(seconds=7200)).isoformat()
    hw.lw.OPEN_SEARCH_SEEDS_FILE.write_text(
        json.dumps(stale), encoding="utf-8")
    url = lw.SeekAct.resolve_canonical_target(intent)
    log(f"  stale seeds -> {url}")
    assert url == fallback_url, \
        f"stale seeds not skipped (expected token fallback): {url!r}"
    assert hw.lw.CuriosityEngine()._from_open_search_seeds() == [], \
        "stale seeds produced desires"

    # Garbage seeds file is fail-closed, never a crash.
    hw.lw.OPEN_SEARCH_SEEDS_FILE.write_text("{not json", encoding="utf-8")
    url = lw.SeekAct.resolve_canonical_target(intent)
    assert url == fallback_url, f"corrupt seeds not fail-closed: {url!r}"
    log("  PASS: fresh seeds preferred; stale/corrupt fail-closed; seeds "
        "are novelty-weighted internal-state desires")
    return {"outcome": "resolution_order",
            "seed_url_preferred": True, "stale_ignored": True}


def scenario_open_sources_stub(lw, hw):
    """With no seeds file, resolution must consult the open_sources organ
    (cross-agent contract: search_candidates(query) -> list[str], never
    raises). The organ is STUBBED (package attribute + sys.modules) — zero
    network. Title-like candidates become Wikipedia summary URLs; URL-like
    candidates are taken directly; a raising organ degrades to the token
    fallback."""
    log("── SCENARIO 7: search_candidates fallback (stubbed open_sources) ──")
    assert not hw.lw.OPEN_SEARCH_SEEDS_FILE.exists(), \
        "temp dir unexpectedly has a seeds file"
    calls = []
    fake = _stub_open_sources(hw, lambda query: calls.append(str(query)) or [
        "Heliosphere", "ignored-second-candidate"])

    url = lw.SeekAct.resolve_canonical_target(
        {"question": "What is the 'heliospheric current sheet'?"})
    log(f"  title candidate -> {url}")
    assert url == WIKI_SUMMARY + "Heliosphere", \
        f"title candidate not built into wiki summary URL: {url!r}"
    assert calls and "heliospheric" in calls[0], \
        f"concept not passed to search_candidates: {calls!r}"

    fake.search_candidates = lambda query: [
        "https://fixture.example/direct/candidate"]
    url = lw.SeekAct.resolve_canonical_target(
        {"question": "What is the 'auroral oval'?"})
    log(f"  url candidate -> {url}")
    assert url == "https://fixture.example/direct/candidate", \
        f"URL candidate not taken directly: {url!r}"

    def fake_raises(query):
        raise RuntimeError("organ down")

    fake.search_candidates = fake_raises
    url = lw.SeekAct.resolve_canonical_target(
        {"question": "What is the 'auroral oval'?"})
    log(f"  raising organ -> {url}")
    assert url == WIKI_SUMMARY + "auroral_oval", \
        f"raising organ not fail-closed to token fallback: {url!r}"

    # Empty candidate list also degrades to the token fallback.
    fake.search_candidates = lambda query: []
    url = lw.SeekAct.resolve_canonical_target(
        {"question": "What is the 'auroral oval'?"})
    assert url == WIKI_SUMMARY + "auroral_oval", \
        f"empty candidates not fail-closed to token fallback: {url!r}"
    log("  PASS: open_sources candidates honored (title→wiki URL, URL→direct), "
        "raising/empty organ degrades to token fallback — zero network")
    return {"outcome": "resolution_order", "open_sources_stubbed": True,
            "fail_closed": True}


# ---------------------------------------------------------------------------
# Matrix-row check (independent of the learning cycle)
# ---------------------------------------------------------------------------

def check_matrix_row():
    import aureon_fusion.capability_gate as cg
    verdict = cg.check("network_access:fetch_public_data")
    row = cg._load_matrix().get("network_access:fetch_public_data", {})
    ok = (verdict.get("allowed") is True
          and str(row.get("level", "")).upper() == "ACT"
          and str(row.get("status", "")).lower() == "active"
          and "sovereign learning will" in str(row.get("rationale", "")))
    log(f"  matrix row: level={row.get('level')} status={row.get('status')} "
        f"verdict={verdict.get('verdict')} ok={ok}")
    return ok, {"level": row.get("level"), "status": row.get("status"),
                "verdict": verdict.get("verdict"),
                "allowed": verdict.get("allowed")}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import datetime as _dt
    ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
    log("=" * 72)
    log(f"learning_will e2e dry verification — {ts}")
    log("=" * 72)

    benchmark = {
        "benchmark": "learning_will_gate",
        "generated_at": ts,
        "regression_baseline": True,
        "decree": "sovereign learning will — free-will learning, three "
                  "fail-closed gates (conscience VETO / HNC coherence / "
                  "capability authorization), no push ingest",
        "checks": {},
        "discrepancies": [],
        "notes": [],
        "verdict": "PENDING",
    }

    row_ok, row_info = check_matrix_row()
    benchmark["checks"]["gate_row_present"] = {
        "pass": row_ok, **row_info,
        "required": "network_access:fetch_public_data @ ACT / active with "
                    "sovereign-learning rationale"}

    try:
        import aureon_fusion.learning_will as lw
    except Exception as exc:
        log(f"learning_will not importable yet ({type(exc).__name__}: {exc})")
        benchmark["checks"]["module_available"] = {"pass": False,
                                                   "error": str(exc)[:200]}
        benchmark["verdict"] = ("PENDING — learning_will module not on disk "
                                "yet (owned by another build agent)")
        benchmark["notes"].append(
            "Re-run this script once aureon_fusion/learning_will.py lands.")
        write_benchmark(benchmark)
        _flush_log()
        return 2

    benchmark["checks"]["module_available"] = {"pass": True}

    results = {}
    exit_code = 0
    for name, fn in (("conscience_veto_blocks", scenario_veto),
                     ("coherence_hold_blocks", scenario_incoherent),
                     ("gate_deny_defers", scenario_gate_deny),
                     ("dry_consider_honest", scenario_dry_honest),
                     ("seeds_resolution_preferred", scenario_seeds_resolution),
                     ("open_sources_stub_fallback", scenario_open_sources_stub),
                     ("full_pipeline_absorbs", scenario_positive)):
        with tempfile.TemporaryDirectory(prefix=f"lw_e2e_{name}_") as tmp:
            hw = Harness(tmp, lw)
            try:
                info = fn(lw, hw)
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
                benchmark["discrepancies"].extend(hw.discrepancies)
                benchmark["notes"].extend(hw.notes)
                hw.unpatch_all()

    all_pass = all(results.values())
    benchmark["verdict"] = "PASS" if all_pass else "FAIL"
    log("=" * 72)
    log(f"VERDICT: {benchmark['verdict']}  "
        f"({sum(results.values())}/{len(results)} scenarios)")
    for n in benchmark["notes"]:
        log(f"  note: {n}")
    for d in benchmark["discrepancies"]:
        log(f"  DISCREPANCY: {d}")
    write_benchmark(benchmark)
    _flush_log()
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
