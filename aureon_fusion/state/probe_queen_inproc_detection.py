"""Probe: queen_inproc_engines live-instance detection (the 157+-refusals bug).

Root cause under test: the registrar launches the organ as
``python -m aureon_fusion.queen_mind`` (organ_registry spawn line), so her
process executes queen_mind.py AS ``__main__`` and never binds
``aureon_fusion.queen_mind`` in sys.modules. The door mechanics do
``from aureon_fusion import queen_mind`` and get a SECOND, freshly executed
module with an EMPTY ``_LIVE_MINDS`` — her own cycle's door-open call was
refused with "no live queen_mind instance" even though the caller WAS the
live process.

Fix under test: ``_live_queen_mind()`` (queen_mind.py) now consults the
``__main__`` twin ONLY when ``__main__`` is provably the same source file
(resolved __file__ match). External callers (probe script as __main__) get
exactly one registry and still refuse. Fail-closed, INPROC-only.

Scenarios (single process, ordered — the refusal checks must run BEFORE any
QueenMind exists in this process):
  A. external call, no instance            -> activate + deactivate refuse
     with EXACTLY the old payload
  B. __main__-twin simulation (the
     production failure shape): same-file   -> _live_queen_mind() finds the
     __main__ with a live sentinel, local    sentinel; activate returns real
     registry empty                          state flags (no "no live..." text)
  C. twin check fail-closed: unrelated      -> _live_queen_mind() still None;
     __main__ (probe script itself)           refusal payload unchanged
  D. simulated in-process call: real        -> activate ok=True with REAL
     QueenMind via get_queen_mind() +         cortex_started/sentience_ready
     stub engines (same shape run()'s        flags; deactivate ok=True
     _engines() would set)                   and cortex actually stopped

Exit codes: 0 = all probes pass; 1 = at least one failed.
Usage:  python aureon_fusion/state/probe_queen_inproc_detection.py [-v]
"""

import os
import sys
import types
import weakref
from pathlib import Path

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from aureon_fusion import queen_mind as qm  # noqa: E402

VERBOSE = "-v" in sys.argv
failures: list = []


def check(name: str, cond: bool, evidence: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {evidence}" if evidence else ""))
    if not cond:
        failures.append(name)


class _StubCortex:
    """Same duck-type contract as the upstream ThoughtBus band-organizer:
    _running flag + start()/stop()."""
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


class _StubSentience:
    """Duck-type of the sentience engine's decision-outcome API."""
    def __init__(self, thought_count: int = 0):
        self._thought_count = thought_count

    def record_decision(self, *a, **k):
        return None

    def update_decision_outcome(self, *a, **k):
        return None

    def get_sentience_status(self):
        return {"thought_count": self._thought_count}


# ── A. external call with no live instance ──────────────────────────────────
print("─" * 72)
print("A. external call, no instance (must refuse exactly as before)")
res = qm.activate_dormant_engines()
check(
    "A1 activate refuses with the exact old payload",
    res == {"ok": False, "detail": "no live queen_mind instance",
            "cortex_started": False, "sentience_ready": False},
    f"got {res!r}",
)
res_d = qm.deactivate_dormant_engines()
check(
    "A2 deactivate refuses with the exact old payload",
    res_d == {"ok": False, "detail": "no live queen_mind instance",
              "cortex_started": False, "sentience_ready": False},
    f"got {res_d!r}",
)
check(
    "A3 _DORMANT_ENGINE_STATE untouched by the refusal",
    qm._DORMANT_ENGINE_STATE.get("detail") == "never activated",
    f"state={qm._DORMANT_ENGINE_STATE!r}",
)

# ── B. the production failure shape: __main__ twin, local registry empty ────
print("─" * 72)
print("B. __main__ twin of the SAME file holds the live instance (the bug)")
sentinel = qm.QueenMind.__new__(qm.QueenMind)  # bare object; only identity
sentinel._cortex = _StubCortex()
sentinel._sentience = _StubSentience(thought_count=7)

twin = types.ModuleType("__main__")
twin.__file__ = str(Path(qm.__file__).resolve())  # SAME source file as qm
twin._LIVE_MINDS = [weakref.ref(sentinel)]
real_main = sys.modules.get("__main__")

check(
    "B0 probe's own __main__ is NOT queen_mind.py (external shape intact)",
    Path(getattr(real_main, "__file__", "") or "").resolve()
        != Path(qm.__file__).resolve(),
)

sys.modules["__main__"] = twin
try:
    found = qm._live_queen_mind()
    check("B1 _live_queen_mind() sees the twin's live instance",
          found is sentinel, f"found={found!r}")
    res = qm.activate_dormant_engines()
    b3_ok = sentinel._cortex._running is True and sentinel._cortex.started == 1
    b4_state = dict(qm._DORMANT_ENGINE_STATE)
    res_d = qm.deactivate_dormant_engines()
finally:
    sys.modules["__main__"] = real_main

if VERBOSE:
    print(f"    activate via twin: {res!r}")
check(
    "B2 activate ok with REAL state flags (no 'no live' refusal)",
    res.get("ok") is True and res.get("detail") != "no live queen_mind instance"
        and res.get("cortex_started") is True
        and res.get("sentience_ready") is True,
    f"got {res!r}",
)
check(
    "B3 sentinel cortex was actually started through its own start()",
    b3_ok,
)
check(
    "B4 _DORMANT_ENGINE_STATE carried the real flags post-activate",
    b4_state.get("cortex_started") is True
        and b4_state.get("sentience_ready") is True
        and b4_state.get("sentience_thoughts") == 7,
    f"state={b4_state!r}",
)
check(
    "B5 deactivate ok and actually stops the twin's cortex",
    res_d.get("ok") is True and sentinel._cortex._running is False
        and sentinel._cortex.stopped == 1,
    f"got {res_d!r}",
)

# ── C. fail-closed: an unrelated __main__ must NOT unlock the door ─────────
print("─" * 72)
print("C. unrelated __main__ (probe script itself) must not satisfy detection")
# real_main IS this probe script — a different file from queen_mind.py.
check(
    "C1 _live_queen_mind() is None with the probe's own __main__",
    qm._live_queen_mind() is None,
)
res = qm.activate_dormant_engines()
check(
    "C2 activate still refuses with the exact old payload",
    res == {"ok": False, "detail": "no live queen_mind instance",
            "cortex_started": False, "sentience_ready": False},
    f"got {res!r}",
)

# ── D. simulated in-process call through the real path run() uses ───────────
print("─" * 72)
print("D. simulated in-process call (get_queen_mind + stub engines)")
mind = qm.get_queen_mind()  # same constructor + registry path as run()
mind._cortex = _StubCortex()
mind._sentience = _StubSentience(thought_count=3)
res = qm.activate_dormant_engines()
if VERBOSE:
    print(f"    activate: {res!r}")
check(
    "D1 activate ok=True with real cortex_started/sentience_ready",
    res.get("ok") is True and res.get("cortex_started") is True
        and res.get("sentience_ready") is True,
    f"got {res!r}",
)
check(
    "D2 the module registry itself (no twin needed) finds her",
    qm._live_queen_mind() is mind,
)
res_d = qm.deactivate_dormant_engines()
check(
    "D3 deactivate ok=True, cortex stopped",
    res_d.get("ok") is True and mind._cortex._running is False,
    f"got {res_d!r}",
)

# ── verdict ─────────────────────────────────────────────────────────────────
print("─" * 72)
if failures:
    print(f"PROBE FAILED — {len(failures)} check(s): {failures}")
    sys.exit(1)
print("PROBE PASSED — all checks green")
print("NOTE: her RUNNING process still holds the pre-fix code; the fix "
      "activates on her next natural restart (do NOT restart her from here).")
sys.exit(0)
