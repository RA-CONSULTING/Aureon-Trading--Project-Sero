"""Probe: goals_will refusal rest-memory (the goals-treadmill fix).

Bug class under test (owner decree, same spirit as learning_will): a goal
candidate refused for a persistent cause — held_incoherent (HNC state) or
deferred (authorization) — had NO memory: candidates() re-proposed the same
refused goal_text every consider cycle, and consider() only ever proposes
the top candidate, so the will treadmilled on one refusal forever.

Fix under test (aureon_fusion/goals_will.py):
  • REFUSED_FILE (state/goals/refused_goals.json) stores goal_key ->
    refuse-expiry (epoch s), capped and tmp+replace written.
  • propose() records a rest ONLY for organism_internal, non-dry
    considerations: held_incoherent -> 30 min, deferred -> 6 h.
  • GoalAspiration.candidates() filters refused keys, so the next cycle
    rotates to the next internal candidate. TTL expiry re-allows asking.
  • Gates are untouched — suppression never answers on a gate's behalf;
    a corrupt/missing registry suppresses nothing (fail-closed).
  • A conscience VETO stays permanent (vetoed_goals.json), as before.

Exit codes: 0 = all probes pass; 1 = at least one failed.
Usage:  python aureon_fusion/state/probe_goals_refusal_rest.py [-v]
"""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from aureon_fusion import goals_will as gw  # noqa: E402

VERBOSE = "-v" in sys.argv
failures: list = []


def check(name: str, cond: bool, evidence: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {evidence}" if evidence else ""))
    if not cond:
        failures.append(name)


REAL_REFUSED_FILE = gw.REFUSED_FILE
REAL_VETOED_FILE = gw.VETOED_FILE
REAL_JOURNAL = gw._journal
TMP_REFUSED = REAL_REFUSED_FILE.with_name(
    f"probe_tmp_refused_{os.getpid()}.json")
TMP_VETOED = REAL_VETOED_FILE.with_name(
    f"probe_tmp_vetoed_{os.getpid()}.json")


def use_tmp_refused():
    gw.REFUSED_FILE = TMP_REFUSED
    gw.VETOED_FILE = TMP_VETOED
    for p in (TMP_REFUSED, TMP_VETOED):
        if p.exists():
            p.unlink()


def restore():
    gw.REFUSED_FILE = REAL_REFUSED_FILE
    gw.VETOED_FILE = REAL_VETOED_FILE
    gw._journal = REAL_JOURNAL
    for p in (TMP_REFUSED, TMP_VETOED):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


# Journal lines would pollute the real goals journal: capture, don't write.
journaled: list = []
gw._journal = lambda rec: journaled.append(rec)

GOAL_HELD = "probe: raise the wheel rung to FLOWING now"
GOAL_DEFERRED = "probe: bring a capability row to owner authorization"

# ── 1. record + expiry semantics ────────────────────────────────────────────
print("─" * 72)
print("1. refusal rest-memory record / is_refused / expiry")
use_tmp_refused()
now = time.time()
gw._record_refusal(GOAL_HELD, gw._HELD_TTL_S, now=now)
gw._record_refusal(GOAL_DEFERRED, gw._REFUSED_TTL_S, now=now)
check("1a held goal refused inside its TTL",
      gw._is_refused(GOAL_HELD, now=now + 60))
check("1b deferred goal refused inside its TTL",
      gw._is_refused(GOAL_DEFERRED, now=now + 60))
check("1c held goal askable again after 30-min TTL",
      not gw._is_refused(GOAL_HELD, now=now + gw._HELD_TTL_S + 1))
check("1d deferred goal still resting at 31 min (6h TTL)",
      gw._is_refused(GOAL_DEFERRED, now=now + 1801))
check("1e deferred goal askable again after 6-h TTL",
      not gw._is_refused(GOAL_DEFERRED, now=now + gw._REFUSED_TTL_S + 1))
check("1f unrelated goal never refused",
      not gw._is_refused("probe: something else entirely", now=now + 60))
data = json.loads(TMP_REFUSED.read_text(encoding="utf-8"))
check("1g registry persisted both keys",
      len(data.get("refused") or {}) == 2, f"keys={list(data.get('refused') or {})}")

# ── 2. corrupt registry: fail-closed, nothing suppressed ────────────────────
print("─" * 72)
print("2. corrupt refused registry suppresses nothing")
TMP_REFUSED.write_text("{ not json !!", encoding="utf-8")
check("2a corrupt file -> not refused (gates still decide)",
      not gw._is_refused(GOAL_HELD))
check("2b missing file -> not refused",
      not gw._is_refused(GOAL_HELD))
TMP_REFUSED.unlink(missing_ok=True)

# ── 3. candidates() rotates away from refused internal candidates ───────────
print("─" * 72)
print("3. GoalAspiration.candidates() filters refused candidates")
use_tmp_refused()
asp = gw.GoalAspiration()
FIXED = [{
    "kind": "wheel_state", "goal_text": GOAL_HELD, "desire_score": 0.45,
    "origin": {"rung": "SPARK", "gamma": 0.5},
}, {
    "kind": "capability_opening", "goal_text": GOAL_DEFERRED,
    "desire_score": 0.35, "origin": {"open_rows": ["x:y"]},
}]
asp._from_proof_chain_gap = lambda: []
asp._from_capability_openings = lambda: [FIXED[1]]
asp._from_wheel_state = lambda: [FIXED[0]]
texts = lambda: [c["goal_text"] for c in asp.candidates()]
check("3a both candidates offered when nothing refused (gen order)",
      texts() == [GOAL_DEFERRED, GOAL_HELD], f"got={texts()}")
gw._record_refusal(GOAL_HELD, gw._HELD_TTL_S)
check("3b refused candidate excluded — rotation to the other one",
      texts() == [GOAL_DEFERRED], f"got={texts()}")
gw._record_refusal(GOAL_DEFERRED, gw._REFUSED_TTL_S)
check("3c all candidates refused -> silence (valid, no treadmill)",
      texts() == [], f"got={texts()}")

# ── 4. propose() records rest only for internal, non-dry refusals ───────────
print("─" * 72)
print("4. propose() refusal recording: internal vs external vs dry")
use_tmp_refused()
will = gw.GoalsWill()

# Stub the gate trio + risk grade: conscience APPROVED, coherence HOLD,
# authorization ALLOW — deterministic held_incoherent / accepted paths.
orig_cc, orig_coh, orig_auth, orig_risk = (
    gw._check_conscience, gw._check_coherence, gw._check_authorization,
    gw._risk_grade)
gw._check_conscience = lambda text, source: {"verdict": "APPROVED",
                                             "reasoning": "probe",
                                             "conditions": [],
                                             "sls_score": None}
gw._check_coherence = lambda: {"passed": False, "gamma": 0.1,
                               "status": "low", "age_s": 5,
                               "threshold": gw.COHERENCE_THRESHOLD,
                               "detail": "probe: held"}
gw._check_authorization = lambda: {"passed": True, "verdict": "ALLOW",
                                   "missing_row": False,
                                   "detail": "probe: allowed"}
gw._risk_grade = lambda text: {"highest": "low", "routes": [],
                               "requires_human": False}
try:
    r = will.propose(GOAL_HELD, source="organism_internal")
    check("4a internal held_incoherent -> outcome recorded",
          r.get("outcome") == "held_incoherent", f"got={r.get('outcome')}")
    check("4b internal held refusal rests 30 min",
          gw._is_refused(GOAL_HELD), "not in refused registry")
    expiry = gw._load_refused().get(gw._goal_key(GOAL_HELD))
    check("4c held expiry ~= now+1800s",
          expiry is not None and
          abs(expiry - (time.time() + gw._HELD_TTL_S)) < 5,
          f"expiry={expiry}")

    r2 = will.propose(GOAL_DEFERRED, source="operator_cli")
    check("4d external propose still answered by the gates",
          r2.get("outcome") == "held_incoherent")
    check("4e external propose records NO rest memory",
          not gw._is_refused(GOAL_DEFERRED),
          "external ask was suppressed")

    use_tmp_refused()  # reset memory; next check is dry-run discipline
    will._dry = True
    r3 = will.propose(GOAL_HELD, source="organism_internal")
    check("4f dry internal held refusal records NO memory",
          r3.get("outcome") == "held_incoherent"
          and not gw._is_refused(GOAL_HELD))
    will._dry = False

    # deferred path: authorization fails -> 6h rest
    use_tmp_refused()
    gw._check_coherence = lambda: {"passed": True, "gamma": 0.6,
                                   "status": "ok", "age_s": 5,
                                   "threshold": gw.COHERENCE_THRESHOLD}
    gw._check_authorization = lambda: {"passed": False, "verdict": "HOLD",
                                       "missing_row": False,
                                       "detail": "probe: not allowed"}
    r4 = will.propose(GOAL_DEFERRED, source="organism_internal")
    check("4g internal deferred -> recorded",
          r4.get("outcome") == "deferred", f"got={r4.get('outcome')}")
    expiry = gw._load_refused().get(gw._goal_key(GOAL_DEFERRED))
    check("4h deferred expiry ~= now+6h",
          expiry is not None and
          abs(expiry - (time.time() + gw._REFUSED_TTL_S)) < 5,
          f"expiry={expiry}")

    # success path must not record anything
    use_tmp_refused()
    gw._check_authorization = lambda: {"passed": True, "verdict": "ALLOW",
                                       "missing_row": False,
                                       "detail": "probe: allowed"}
    r5 = will.propose("probe: an acceptable goal", source="organism_internal")
    check("4i accepted goal records no rest memory",
          r5.get("outcome") == "accepted" and
          gw._load_refused() == {}, f"refused={gw._load_refused()}")

    # veto permanence untouched: VETO still lands in vetoed_goals, not refused
    gw._check_conscience = lambda text, source: {"verdict": "VETO",
                                                 "reasoning": "probe veto",
                                                 "conditions": [],
                                                 "sls_score": None}
    r6 = will.propose(GOAL_HELD, source="organism_internal")
    check("4j conscience VETO still vetoes (gate untouched)",
          r6.get("outcome") == "vetoed")
    check("4k VETO did NOT write rest memory",
          gw._load_refused() == {})
finally:
    gw._check_conscience, gw._check_coherence = orig_cc, orig_coh
    gw._check_authorization, gw._risk_grade = orig_auth, orig_risk
    restore()

check("4l real goals journal unpolluted by the probe", len(journaled) > 0)

# ── verdict ─────────────────────────────────────────────────────────────────
print("─" * 72)
if failures:
    print(f"PROBE FAILED — {len(failures)} check(s): {failures}")
    sys.exit(1)
print("PROBE PASSED — all checks green")
sys.exit(0)
