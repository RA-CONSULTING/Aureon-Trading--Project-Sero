"""Probe: saturated-source registry + source-diversity fix in learning_will.

Verifies, inside a temp state dir (module path constants monkeypatched, the
same seam the e2e harness uses):

  1. exclusion   — a url with >= 2 current strikes is excluded from intent
                   generation; a clean sibling url wins instead
  2. strike      — a REAL consideration refused "all near-duplicates or
                   empty" increments the fetched url's strike in
                   saturated_sources.json
  3. decay       — strikes older than 24h halve: 4 strikes 2 days old ->
                   effective 1 (not excluded); a fresh strike on it -> 2
  4. fail-closed — a corrupt registry reads as empty (no exclusions, no
                   crash) and never breaks a consideration
  5. re-roll     — when every local candidate is saturated, propose()
                   falls back to breadth through the existing resolution
                   mechanisms (stubbed open_sources) and returns an intent
                   pointing at a DIFFERENT, non-saturated url, with
                   origin.saturation_reroll_from set; when nothing
                   unsaturated can be derived, propose() returns None
                   (silence is valid)
  6. wikipedia key unification — /wiki/X and /api/rest_v1/page/summary/X
                 share one registry key

Zero real network (api_communion + open_sources stubbed), zero writes
outside the temp dir. Exit 0 = all probes pass.
"""

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

FAILURES = []


def check(name, cond, info=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {info}" if info else ""))
    if not cond:
        FAILURES.append(name)


class Harness:
    PATH_ATTRS = ("JOURNAL_DIR", "JOURNAL_FILE", "INTENTS_FILE",
                  "BUILD_LOG", "HNC_STATE_FILE", "OPEN_SEARCH_SEEDS_FILE",
                  "SATURATED_FILE", "REFUSED_FILE", "VETOED_FILE",
                  "RESEARCH_THROTTLE_FILE")

    def __init__(self, tmp, lw):
        self.tmp = Path(tmp)
        self.lw = lw
        self.patches = []
        for name in self.PATH_ATTRS:
            val = getattr(self.lw, name, None)
            if isinstance(val, Path) and str(val).startswith(str(WORKSPACE)):
                self.patch(self.lw, name, self.tmp / val.name)
        self.hnc_file = self.tmp / "hnc_core_state.json"
        self.patch(self.lw, "HNC_STATE_FILE", self.hnc_file)
        (self.hnc_file.parent / "learning_will").mkdir(
            parents=True, exist_ok=True)
        self.hnc_file.write_text(json.dumps({"coherence_gamma": 0.9}),
                                 encoding="utf-8")

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value, create=True)
        p.start()
        self.patches.append(p)
        return value

    def unpatch(self):
        for p in reversed(self.patches):
            try:
                p.stop()
            except Exception:
                pass
        self.patches.clear()


class FakeKD:
    """Fragments = the intent sources; find_similar controlled per test."""

    def __init__(self, fragments, similar=None):
        self._fragments = fragments
        self._similar = similar if similar is not None else []

    def find_similar(self, text, n=3):
        return self._similar

    def absorb(self, pocket, interpretations=None):
        pass

    def save(self):
        pass


class FakeWeb:
    nodes = {}
    edges = []

    def recall(self, text):
        return []

    def remember(self, content, **kw):
        pass

    def save(self):
        pass


class FakeNet:
    domains = {}

    def get_domain_confidence(self, domain):
        return 0.1

    def feed_evidence(self, domain, signal=None, outcome=None, **kw):
        pass


def frag(text, url, dtype="question"):
    return SimpleNamespace(text=text, tags=["question", url],
                           data_type=dtype, timestamp=1.0)


def silence_other_sources(lw, hw, fragments, similar=None):
    """Inject fake organs; only the fixture fragments generate candidates."""
    lw._CACHE.clear()
    lw._CACHE["knowledge_dataset"] = FakeKD(fragments, similar)
    lw._CACHE["memory_web"] = FakeWeb()
    lw._CACHE["mycelium"] = FakeNet()
    lw._CACHE["mind_augment"] = None
    hw.patch(lw.CuriosityEngine, "_from_insight_patterns",
             lambda self_: [])


def write_registry(lw, sources):
    lw.SATURATED_FILE.write_text(json.dumps(
        {"sources": sources, "updated_at": "probe"}), encoding="utf-8")


def read_registry(lw):
    try:
        return json.loads(lw.SATURATED_FILE.read_text(
            encoding="utf-8")).get("sources") or {}
    except Exception:
        return None


URL_A = "https://en.wikipedia.org/wiki/Ethics"
URL_B = "https://fixture.example/fresh-ground"
URL_A_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/Ethics"
URL_A_ADJACENT = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
                  "Applied_ethics")


def probe(lw):
    now = time.time()

    # ── 1: exclusion — saturated url dropped, clean url wins ────────────
    print("PROBE 1: url with 2 current strikes excluded from generation")
    with tempfile.TemporaryDirectory(prefix="lw_sat_1_") as tmp:
        hw = Harness(tmp, lw)
        try:
            write_registry(lw, {lw._saturation_key(URL_A):
                                {"strikes": 2, "last_ts": now}})
            silence_other_sources(lw, hw, [
                frag("What is the ground of moral obligation in the "
                     "organism's conscience?", URL_A),
                frag("What coherence thresholds govern symbolic physics "
                     "in living systems?", URL_B),
            ])
            intent = lw.LearningWill().propose()
            check("propose returns an intent", intent is not None)
            check("saturated url excluded", (intent or {}).get("url") == URL_B,
                  f"got {(intent or {}).get('url')!r}")
            check("saturation key unifies wiki forms",
                  lw._saturation_key(URL_A) == lw._saturation_key(URL_A_SUMMARY)
                  == "wikipedia:ethics",
                  f"{lw._saturation_key(URL_A)} / "
                  f"{lw._saturation_key(URL_A_SUMMARY)}")
        finally:
            hw.unpatch()
            lw._CACHE.clear()

    # ── 2: refusal path increments strikes (real fetch, near-dup refusal) ──
    print("PROBE 2: all-near-dups refusal records a strike for the url")
    with tempfile.TemporaryDirectory(prefix="lw_sat_2_") as tmp:
        hw = Harness(tmp, lw)
        try:
            fetched = ("Ethics is the branch of philosophy concerning "
                       "systems of moral value and the rules of right "
                       "conduct that govern the choices of agents.")
            dupe = SimpleNamespace(text=fetched, tags=["learned"])
            silence_other_sources(lw, hw,
                                  [frag("What grounds moral obligation?", URL_A)],
                                  similar=[dupe])
            import aureon_fusion.conscience_hook as ch
            import aureon_fusion.capability_gate as cg
            import aureon_fusion.api_communion as ac
            hw.patch(ch, "evaluate", lambda d, c=None: {
                "verdict": "APPROVED", "reasoning": "probe", "conditions": [],
                "sls_score": 0.9})
            hw.patch(cg, "check", lambda g: {
                "gate": g, "verdict": "ALLOW", "allowed": True, "reason": "probe"})
            hw.patch(ac, "get_text", lambda url, ttl_s=60.0, timeout=10.0,
                     headers=None: fetched)
            result = lw.LearningWill().consider_once(dry_run=False)
            check("outcome refused", result.get("outcome") == "refused",
                  f"got {result.get('outcome')!r}")
            check("detail is the near-dup refusal",
                  result.get("detail") == lw._NEAR_DUP_REFUSAL_DETAIL,
                  str(result.get("detail"))[:80])
            reg = read_registry(lw) or {}
            entry = reg.get(lw._saturation_key(URL_A))
            check("strike recorded for fetched url", entry is not None,
                  f"registry: {reg}")
            check("strike count == 1",
                  entry is not None and abs(entry["strikes"] - 1.0) < 1e-6,
                  f"strikes={entry and entry['strikes']}")
        finally:
            hw.unpatch()
            lw._CACHE.clear()

    # ── 3: decay — old strikes halve per 24h ────────────────────────────
    print("PROBE 3: 24h strike decay")
    with tempfile.TemporaryDirectory(prefix="lw_sat_3_") as tmp:
        hw = Harness(tmp, lw)
        try:
            old_ts = now - 2 * 86400.0  # two full decay windows
            write_registry(lw, {lw._saturation_key(URL_A):
                                {"strikes": 4, "last_ts": old_ts}})
            check("4 strikes 48h old -> effective 1.0 (not saturated)",
                  not lw._is_saturated_url(URL_A, now),
                  f"effective={lw._saturated_effective_strikes({'strikes': 4, 'last_ts': old_ts}, now)}")
            lw._record_saturated_strike(URL_A, now)
            entry = (read_registry(lw) or {}).get(lw._saturation_key(URL_A))
            check("strike on decayed entry -> 1 + 1 = 2.0",
                  entry is not None and abs(entry["strikes"] - 2.0) < 1e-6,
                  f"strikes={entry and entry['strikes']}")
            check("2.0 fresh strikes -> now saturated",
                  lw._is_saturated_url(URL_A, now))
            # 1 strike must NOT exclude (floor is 2)
            write_registry(lw, {lw._saturation_key(URL_A):
                                {"strikes": 1, "last_ts": now}})
            check("1 fresh strike -> not excluded",
                  not lw._is_saturated_url(URL_A, now))
        finally:
            hw.unpatch()

    # ── 4: corrupt registry -> fail-closed, generation unblocked ────────
    print("PROBE 4: corrupt registry is fail-closed")
    with tempfile.TemporaryDirectory(prefix="lw_sat_4_") as tmp:
        hw = Harness(tmp, lw)
        try:
            lw.SATURATED_FILE.write_text("{not json", encoding="utf-8")
            check("_load_saturated() == {} on corrupt file",
                  lw._load_saturated() == {})
            silence_other_sources(lw, hw, [
                frag("What grounds moral obligation?", URL_A)])
            intent = lw.LearningWill().propose()
            check("generation proceeds despite corrupt registry",
                  intent is not None and intent.get("url") == URL_A,
                  f"got {(intent or {}).get('url')!r}")
            check("consider does not crash on corrupt registry",
                  lw.LearningWill().consider_once(dry_run=True).get("outcome")
                  in lw.OUTCOMES)
        finally:
            hw.unpatch()
            lw._CACHE.clear()

    # ── 5: re-roll — all local candidates saturated -> breadth fallback ──
    print("PROBE 5: saturation re-roll to a different source path")
    with tempfile.TemporaryDirectory(prefix="lw_sat_5_") as tmp:
        hw = Harness(tmp, lw)
        try:
            import aureon_fusion
            fake = SimpleNamespace(search_candidates=lambda q: ["Applied ethics"])
            hw.patch(aureon_fusion, "open_sources", fake)
            p = mock.patch.dict(sys.modules, {"aureon_fusion.open_sources": fake})
            p.start()
            hw.patches.append(p)

            write_registry(lw, {lw._saturation_key(URL_A):
                                {"strikes": 3, "last_ts": now}})
            silence_other_sources(lw, hw, [
                frag("What is the ground of moral obligation in the "
                     "organism's conscience?", URL_A)])
            intent = lw.LearningWill().propose()
            check("re-roll produced an intent", intent is not None)
            check("re-rolled to the non-saturated adjacent url",
                  (intent or {}).get("url") == URL_A_ADJACENT,
                  f"got {(intent or {}).get('url')!r}")
            check("origin carries saturation_reroll_from",
                  (intent or {}).get("origin", {}).get(
                      "saturation_reroll_from") == URL_A,
                  f"origin={((intent or {}).get('origin') or {})}")

            # nothing unsaturated derivable -> silence (never a saturated refetch).
            # Quoted theme pins the concept to the saturated page itself, so
            # every mechanism (seeds, open_sources, canonical guess) lands
            # back on blocked ground.
            fake.search_candidates = lambda q: []
            lw._CACHE.clear()
            silence_other_sources(lw, hw, [
                frag("What does 'Ethics' discipline in the organism's "
                     "conscience?", URL_A)])
            intent2 = lw.LearningWill().propose()
            check("no unsaturated target derivable -> silence (None)",
                  intent2 is None, f"got {intent2!r}")
        finally:
            hw.unpatch()
            lw._CACHE.clear()


def main():
    import aureon_fusion.learning_will as lw
    print("=" * 72)
    print("learning_will saturated-source probe — "
          f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print("=" * 72)
    try:
        probe(lw)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        FAILURES.append(f"probe crashed: {type(exc).__name__}: {exc}")
    print("=" * 72)
    if FAILURES:
        print(f"PROBE RESULT: FAIL ({len(FAILURES)}): {FAILURES}")
        return 1
    print("PROBE RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
