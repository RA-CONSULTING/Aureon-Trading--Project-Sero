"""Offline verification probes for the SOVEREIGN DOOR SYSTEM core
(door_registry.py + master_key.py — BUILD-CORE deliverable).

Every scenario runs against a TEMP state dir (per-scenario tmp workspace
slice): door state, PID files, logs, journal, and hnc_core_state.json are
redirected per scenario via module-constant seams. The gate organs are
injected fakes (conscience / capability_gate / receipts / door_activators /
organ_registry) so NOTHING here touches the live organism: zero real
trading effects, zero process kills outside our own fixture children,
zero writes outside the temp dirs (build log excepted).

Probes (each fail-closed path exercised, not just the happy path):
  1. registry table shape — 13 census doors, contract fields, honest locks
  2. registry get() known / unknown
  3. DoorState persistence round-trip + corrupt-file degrade
  4. conscience VETO            -> open() refused, no key stored
  5. conscience raises          -> fail-closed VETO
  6. coherence_gamma 0.1        -> held_incoherent
  7. hnc state missing          -> held_incoherent (fail-closed)
  8. capability missing row     -> OBSERVE mint proceeds (degraded);
                                   ACT door defers honestly
  9. capability gate raises     -> fail-closed HOLD
 10. full cycle INPROC          -> mint -> open -> close, key BURNED
 11. expired key               -> burned, re-mint refused (gamma low)
 12. locked doors              -> mint/open refuse with honest reasons
 13. one-shot subprocess stub  -> runs, output captured to door log
 14. long-run own child        -> PID file, close kills ONLY our child
 15. foreign PID file          -> close refuses (never kills what it
                                  cannot prove is ours)
 16. registry adoption         -> running organ adopted, never stopped;
                                  ours-started organ stopped via registry
 17. registry token matcher    -> real organ_registry table semantics
 18. consider()                -> silence / mint+open / waning close
 19. ELEVATE double-check      -> second conscience eval + receipt
 20. journal rotation          -> oversized journal rotated before append

Exit codes: 0 = all probes pass; 1 = at least one failed.
Usage:  python aureon_fusion/state/probe_doors_core.py [-v]
"""

import contextlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

import aureon_fusion.door_registry as dr
import aureon_fusion.master_key as mk

_py = sys.executable or "python"
_results = []
_MISSING = object()


@contextlib.contextmanager
def patched_organs(**fakes):
    """Inject fake organ modules so NOTHING reaches the live organism.
    Patches BOTH sys.modules and the aureon_fusion package attribute —
    `from aureon_fusion import X` prefers the package attribute, so a
    sys.modules-only patch is silently shadowed once the real module has
    been imported. Pass value=None to force the module absent (ImportError
    path). Restores everything on exit."""
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


def log(msg):
    print(msg)


def check(name, cond, detail=""):
    ok = bool(cond)
    _results.append((name, ok))
    mark = "PASS" if ok else "FAIL"
    log(f"  [{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))
    return ok


# ───────────────────────── fixture helpers ─────────────────────────────────

def make_door(name="stub_door", **kw):
    door = {
        "name": name,
        "title": "Stub Door",
        "module": "stub_module.py",
        "autonomy_class": "OBSERVE",
        "mode": "INPROC",
        "elevate": False,
        "locked_reason": None,
        "description": "fixture door for offline probes",
        "domain_action": "network_access:fetch_public_data",
        "command": None,
        "cwd": None,
        "value": 0.90,
        "registry_organ": None,
    }
    door.update(kw)
    return door


class StubRegistry:
    def __init__(self, doors):
        self._doors = [dict(d) for d in doors]

    def list_doors(self):
        return [dict(d) for d in self._doors]

    def get(self, name):
        for d in self._doors:
            if d["name"] == name:
                return dict(d)
        return None


def fake_module(fullname, **attrs):
    mod = types.ModuleType(fullname)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


def conscience_fake(verdict="APPROVED", reasoning="fixture", calls=None,
                    raise_exc=None):
    def evaluate(desc, context=None):
        if calls is not None:
            calls.append({"desc": desc, "context": context or {}})
        if raise_exc is not None:
            raise raise_exc
        return {"verdict": verdict, "reasoning": reasoning, "conditions": []}
    return evaluate


def gate_allow(domain_action):
    return {"gate": domain_action, "verdict": "ALLOW", "allowed": True,
            "reason": "matrix status 'active'"}


def gate_missing_row(domain_action):
    return {"gate": domain_action, "verdict": "DENY", "allowed": False,
            "reason": "no gate defined for this domain:action"}


class Harness:
    """Per-scenario temp state + module seams."""

    def __init__(self, name):
        self.name = name
        self.tmp = Path(tempfile.mkdtemp(prefix=f"doors_probe_{name}_"))
        self.state_dir = self.tmp / "state"
        self.doors_dir = self.state_dir / "doors"
        self.doors_dir.mkdir(parents=True)
        self.hnc_file = self.state_dir / "hnc_core_state.json"
        self.journal_file = self.doors_dir / "journal.jsonl"
        self.state_file = self.doors_dir / "state.json"
        self._patches = []

    def patch(self, obj, attr, value):
        old = getattr(obj, attr, None)
        setattr(obj, attr, value)
        self._patches.append((obj, attr, old))

    def patch_paths(self):
        self.patch(mk, "JOURNAL_FILE", self.journal_file)
        self.patch(mk, "HNC_STATE_FILE", self.hnc_file)
        self.patch(dr, "DOORS_STATE_FILE", self.state_file)
        self.patch(dr, "DOORS_PID_DIR", self.doors_dir / "pids")
        self.patch(dr, "DOORS_LOG_DIR", self.doors_dir / "logs")
        self.patch(mk, "JOURNAL_ROTATE_BYTES", 10 * 1024 * 1024)

    def set_gamma(self, gamma=None):
        if gamma is None:
            if self.hnc_file.exists():
                self.hnc_file.unlink()
            return
        self.hnc_file.write_text(json.dumps({
            "organ": "hnc_core", "coherence_gamma": gamma,
            "timestamp": time.time()}), encoding="utf-8")

    def make_doors(self, registry, doors):
        return mk.SovereignDoors(registry=registry,
                                 state_store=dr.DoorState(self.state_file))

    def journal_records(self):
        recs = []
        if self.journal_file.exists():
            for line in self.journal_file.read_text(
                    encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line:
                    try:
                        recs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return recs

    def restore(self):
        for obj, attr, old in reversed(self._patches):
            setattr(obj, attr, old)
        self._patches.clear()


# ───────────────────────── probes ──────────────────────────────────────────

def probe_registry_table():
    log("\n== 1. registry table shape ==")
    reg = dr.DoorRegistry()
    doors = reg.list_doors()
    check("census doors listed (13 base + expansion)",
          len(doors) >= 13, f"got {len(doors)}")
    fields = ("name", "title", "module", "autonomy_class", "mode",
              "elevate", "locked_reason", "description")
    check("every door carries the contract fields",
          all(all(k in d for k in fields) for d in doors))
    modes = {d["name"]: d["mode"] for d in doors}
    expect_modes = {
        "sero_consciousness_loop": "subprocess-oneshot",
        "planetary_switchboard": "subprocess-longrun",
        "cortex_council": "subprocess-oneshot",
        "queen_inproc_engines": "INPROC",
        "signal_lab": "subprocess-oneshot",
        "selfq_research_feed": "INPROC",
        "hnc_campaign": "subprocess-oneshot",
        "trade_journal_sweep": "subprocess-oneshot",
        "persistent_mind": "INPROC",
        "lightweight_hnc": "subprocess-longrun",
        "lineage_report": "subprocess-oneshot",
        "shield_escalation": "subprocess-oneshot",
        "casimir_cluster": "subprocess-oneshot",
    }
    check("modes match the census",
          all(modes.get(k) == v for k, v in expect_modes.items()),
          str({k: modes.get(k) for k in expect_modes
               if modes.get(k) != expect_modes[k]}))
    by_name = {d["name"]: d for d in doors}
    check("hnc_campaign ELEVATE-flagged", by_name["hnc_campaign"]["elevate"] is True)
    check("shield_escalation locked owner-review",
          by_name["shield_escalation"]["locked_reason"] == "owner-review-required")
    check("casimir_cluster locked reconstruction",
          "reconstruction-required" in
          (by_name["casimir_cluster"]["locked_reason"] or ""))
    subprocess_doors = [d for d in doors
                        if str(d["mode"]).startswith("subprocess")
                        and not d.get("locked_reason")]
    check("every runnable subprocess door carries a command",
          all(d.get("command") for d in subprocess_doors),
          str([d["name"] for d in subprocess_doors if not d.get("command")]))
    check("locked doors expose no silently-runnable command",
          all(not d.get("command")
              for d in doors if d.get("locked_reason")))


def probe_registry_get():
    log("\n== 2. registry get() ==")
    reg = dr.DoorRegistry()
    d = reg.get("planetary_switchboard")
    check("get() returns the door", isinstance(d, dict) and
          d["name"] == "planetary_switchboard")
    check("get() unknown returns None", reg.get("no_such_door") is None)
    d["name"] = "mutated"
    check("get() returns a copy (table immutable)",
          reg.get("planetary_switchboard")["name"] == "planetary_switchboard")


def probe_door_state():
    log("\n== 3. DoorState persistence ==")
    h = Harness("state")
    try:
        h.patch_paths()
        store = dr.DoorState(h.state_file)
        st = store.load()
        entry = store.door(st, "stub")
        entry.update({"state": "open", "open_count": 3,
                      "opened_at": "2026-01-01T00:00:00+00:00"})
        check("save ok", store.save(st) is True)
        st2 = store.load()
        check("round-trip preserves door state",
              st2["doors"]["stub"]["state"] == "open" and
              st2["doors"]["stub"]["open_count"] == 3)
        h.state_file.write_text("{corrupt json", encoding="utf-8")
        st3 = store.load()
        check("corrupt file degrades to fresh default",
              st3 == {"doors": {}, "keys": {}})
        check("default entry shape",
              dr.DoorState(h.state_file).door({"doors": {}, "keys": {}}, "x") ==
              {"state": "closed", "key_id": None, "opened_at": None,
               "closes_at": None, "open_count": 0})
    finally:
        h.restore()


def probe_conscience_veto():
    log("\n== 4/5. conscience VETO + raise (fail-closed) ==")
    for name, exc in (("veto", None), ("raise", RuntimeError("boom"))):
        h = Harness(f"conscience_{name}")
        try:
            h.patch_paths()
            h.set_gamma(0.60)
            calls = []
            fake = fake_module("aureon_fusion.conscience_hook",
                               evaluate=conscience_fake(
                                   verdict="VETO", calls=calls,
                                   raise_exc=exc))
            gate = fake_module("aureon_fusion.capability_gate",
                               check=gate_allow)
            door = make_door(name="victim_door",
                             domain_action="network_access:fetch_public_data")
            with patched_organs(
                    conscience_hook=fake,
                    capability_gate=gate):
                sd = h.make_doors(StubRegistry([door]), [door])
                res = sd.open("victim_door")
            check(f"conscience {name} -> refused",
                  res["action"] == "refused", res["action"])
            check(f"conscience {name} detail honest",
                  "VETO" in res["detail"], res["detail"])
            check(f"conscience {name} -> no key stored",
                  not dr.DoorState(h.state_file).load().get("keys"))
            check(f"conscience {name} journaled",
                  any(r.get("event") == "open" and r.get("action") == "refused"
                      for r in h.journal_records()))
        finally:
            h.restore()


def probe_coherence():
    log("\n== 6/7. HNC coherence fail-closed ==")
    for name, gamma in (("low", 0.10), ("missing", None)):
        h = Harness(f"gamma_{name}")
        try:
            h.patch_paths()
            h.set_gamma(gamma)
            fake = fake_module("aureon_fusion.conscience_hook",
                               evaluate=conscience_fake())
            gate = fake_module("aureon_fusion.capability_gate",
                               check=gate_allow)
            door = make_door(name="coherent_door",
                             domain_action="network_access:fetch_public_data")
            with patched_organs(
                    conscience_hook=fake,
                    capability_gate=gate):
                sd = h.make_doors(StubRegistry([door]), [door])
                res = sd.open("coherent_door")
            check(f"gamma {name} -> held_incoherent",
                  res["action"] == "refused" and
                  "held_incoherent" in res["detail"], res["detail"])
        finally:
            h.restore()


def probe_capability_rows():
    log("\n== 8/9. capability authorization ==")
    h = Harness("cap_rows")
    try:
        h.patch_paths()
        h.set_gamma(0.60)
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake())
        missing = fake_module("aureon_fusion.capability_gate",
                              check=gate_missing_row)
        observe = make_door(name="observe_door",
                            domain_action="system:activate_internal_door")
        act = make_door(name="act_door", autonomy_class="ACT",
                        domain_action="system:activate_internal_door")
        activators = fake_module(
            "aureon_fusion.door_activators",
            activate=lambda name: {"ok": True, "detail": "wired (fixture)"},
            deactivate=lambda name: {"ok": True, "detail": "unwired"})
        with patched_organs(
                conscience_hook=fake,
                capability_gate=missing,
                door_activators=activators):
            sd = h.make_doors(StubRegistry([observe, act]), [observe, act])
            res_obs = sd.open("observe_door")
            res_act = sd.open("act_door")
        check("missing row -> OBSERVE mint proceeds (degraded)",
              res_obs["action"] == "opened", f"{res_obs['action']}: {res_obs['detail']}")
        check("missing row -> ACT defers honestly",
              res_act["action"] == "refused" and "defer" in res_act["detail"],
              f"{res_act['action']}: {res_act['detail']}")

        def boom(_):
            raise RuntimeError("gate exploded")
        raising = fake_module("aureon_fusion.capability_gate", check=boom)
        raise_door = make_door(name="raise_door")
        with patched_organs(
                conscience_hook=fake,
                capability_gate=raising,
                door_activators=activators):
            sd2 = h.make_doors(StubRegistry([raise_door]), [raise_door])
            res_err = sd2.open("raise_door")
        check("gate raises -> fail-closed HOLD (refused)",
              res_err["action"] == "refused" and
              "fail-closed" in res_err["detail"], res_err["detail"])
    finally:
        h.restore()


def probe_full_cycle_inproc():
    log("\n== 10. full cycle mint -> open -> close (key BURNED) ==")
    h = Harness("cycle")
    try:
        h.patch_paths()
        h.set_gamma(0.60)
        calls = {"activate": [], "deactivate": []}
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake())
        gate = fake_module("aureon_fusion.capability_gate",
                           check=gate_allow)
        activators = fake_module(
            "aureon_fusion.door_activators",
            activate=lambda name: calls["activate"].append(name) or
                                  {"ok": True, "detail": "wired in-process"},
            deactivate=lambda name: calls["deactivate"].append(name) or
                                    {"ok": True, "detail": "unwired"})
        door = make_door(name="inproc_door")
        with patched_organs(
                conscience_hook=fake,
                capability_gate=gate,
                door_activators=activators):
            sd = h.make_doors(StubRegistry([door]), [door])
            opened = sd.open("inproc_door")
            check("open -> opened", opened["action"] == "opened",
                  f"{opened['action']}: {opened['detail']}")
            check("key id minted (uuid8-style)",
                  isinstance(opened["key_id"], str) and
                  opened["key_id"].startswith("dk_") and
                  len(opened["key_id"]) == 11, opened["key_id"])
            st = dr.DoorState(h.state_file).load()
            ent = st["doors"]["inproc_door"]
            check("state persisted open with 24h closes_at",
                  ent["state"] == "open" and ent["open_count"] == 1 and
                  ent["key_id"] == opened["key_id"] and ent["closes_at"])
            exp = datetime.fromisoformat(ent["closes_at"])
            check("closes_at ~= now+24h",
                  timedelta(hours=23) < exp - datetime.now(timezone.utc)
                  < timedelta(hours=25))
            check("key stored", st["keys"]["inproc_door"]["key_id"] == opened["key_id"])
            check("activator activated", calls["activate"] == ["inproc_door"])

            # re-open with valid key: no duplicate activation, no re-mint
            opened2 = sd.open("inproc_door")
            check("re-open already-open -> no duplicate activation",
                  opened2["action"] == "opened" and
                  "no duplicate" in opened2["detail"], opened2["detail"])
            check("re-open did not re-activate",
                  calls["activate"] == ["inproc_door"])

            closed = sd.close("inproc_door")
            check("close -> closed", closed["action"] == "closed",
                  f"{closed['action']}: {closed['detail']}")
            st2 = dr.DoorState(h.state_file).load()
            check("key BURNED (deleted from store)",
                  "inproc_door" not in st2["keys"])
            check("door state closed, key_id None",
                  st2["doors"]["inproc_door"]["state"] == "closed" and
                  st2["doors"]["inproc_door"]["key_id"] is None)
            check("deactivator called", calls["deactivate"] == ["inproc_door"])
            events = [r.get("event") for r in h.journal_records()]
            check("journal recorded mint+open+close",
                  "mint" in events and "open" in events and "close" in events,
                  str(events))
    finally:
        h.restore()


def probe_expired_key():
    log("\n== 11. expired key refused ==")
    h = Harness("expired")
    try:
        h.patch_paths()
        h.set_gamma(0.10)  # re-mint will be held incoherent
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake())
        gate = fake_module("aureon_fusion.capability_gate",
                           check=gate_allow)
        door = make_door(name="expired_door")
        store = dr.DoorState(h.state_file)
        st = store.load()
        store.door(st, "expired_door")
        st["keys"]["expired_door"] = {
            "key_id": "dk_expired00", "door": "expired_door",
            "minted_at": "2020-01-01T00:00:00+00:00",
            "expires_at": "2020-01-02T00:00:00+00:00",
            "scope": "door:expired_door", "autonomy_class": "OBSERVE"}
        store.save(st)
        with patched_organs(
                conscience_hook=fake,
                capability_gate=gate):
            sd = h.make_doors(StubRegistry([door]), [door])
            res = sd.open("expired_door")
        check("expired key -> re-mint refused (held_incoherent)",
              res["action"] == "refused" and "expired key burned" in res["detail"]
              and "held_incoherent" in res["detail"], res["detail"])
        check("expired key removed from store",
              "expired_door" not in dr.DoorState(h.state_file).load().get("keys", {}))
    finally:
        h.restore()


def probe_locked_doors():
    log("\n== 12. locked doors refuse honestly ==")
    h = Harness("locked")
    try:
        h.patch_paths()
        h.set_gamma(0.60)
        reg = dr.DoorRegistry()
        sd = h.make_doors(reg, reg.list_doors())
        for name, reason in (("shield_escalation", "owner-review-required"),
                             ("casimir_cluster", "reconstruction-required")):
            res = sd.open(name)
            check(f"{name} open -> locked",
                  res["action"] == "locked", res["action"])
            check(f"{name} honest reason",
                  reason in res["detail"], res["detail"])
        # silence the open desire so consider() exercises lock visibility
        # without touching the live gate organs for the unlocked doors.
        with mock.patch.object(mk, "MIN_DESIRE", 5.0):
            res = sd.consider()
        check("consider() never picks a locked door to open",
              res["door"] not in ("shield_escalation", "casimir_cluster"),
              str(res))
        check("no keys stored for locked doors",
              not dr.DoorState(h.state_file).load().get("keys"))
        st = sd.status()
        locked = [d for d in st["doors"] if d["locked_reason"]]
        check("status() shows locked doors honestly",
              len(locked) == 2 and all(d["state"] == "closed" and
                                       not d["key_valid"] for d in locked))
    finally:
        h.restore()


def probe_oneshot_subprocess():
    log("\n== 13. one-shot subprocess with stub command ==")
    h = Harness("oneshot")
    try:
        h.patch_paths()
        h.set_gamma(0.60)
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake())
        gate = fake_module("aureon_fusion.capability_gate",
                           check=gate_allow)
        marker = h.tmp / "oneshot_marker.txt"
        door = make_door(
            name="oneshot_door", mode="subprocess-oneshot",
            command=[_py, "-c",
                     f"open({str(marker)!r}, 'w').write('stub-organ-ran')"],
            cwd=str(h.tmp))
        with patched_organs(
                conscience_hook=fake,
                capability_gate=gate):
            sd = h.make_doors(StubRegistry([door]), [door])
            res = sd.open("oneshot_door")
        check("one-shot opened", res["action"] == "opened",
              f"{res['action']}: {res['detail']}")
        check("stub organ actually ran", marker.read_text() == "stub-organ-ran")
        log_path = dr.DoorState.log_file("oneshot_door")
        check("output captured to door log",
              log_path.exists() and "rc=0" in log_path.read_text(
                  encoding="utf-8", errors="replace"))
        closed = sd.close("oneshot_door")
        # completed one-shots auto-close and burn the key at open() time,
        # so a later close() honestly reports "none"
        check("one-shot close is a clean burn",
              closed["action"] in ("closed", "none"), closed["action"])
    finally:
        h.restore()


def probe_longrun_own_child():
    log("\n== 14/15. long-run: own child via PID file; foreign PID never killed ==")
    h = Harness("longrun")
    sleeper = None
    try:
        h.patch_paths()
        h.set_gamma(0.60)
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake())
        gate = fake_module("aureon_fusion.capability_gate",
                           check=gate_allow)
        organ_reg = fake_module("aureon_fusion.organ_registry", ORGANS={})
        door = make_door(
            name="longrun_door", mode="subprocess-longrun",
            command=[_py, "-c", "import time; time.sleep(120)"],
            cwd=str(h.tmp))
        with patched_organs(
                conscience_hook=fake,
                capability_gate=gate,
                organ_registry=organ_reg):
            sd = h.make_doors(StubRegistry([door]), [door])
            res = sd.open("longrun_door")
            check("long-run opened via subprocess (no registry organ)",
                  res["action"] == "opened" and "pid" in res["detail"],
                  f"{res['action']}: {res['detail']}")
            pid_path = dr.DoorState.pid_file("longrun_door")
            check("PID file written", pid_path.exists())
            info = json.loads(pid_path.read_text())
            check("recorded pid alive", mk._pid_alive(info["pid"]))
            st = dr.DoorState(h.state_file).load()
            check("provenance recorded as subprocess",
                  st["doors"]["longrun_door"]["provenance"]["via"] == "subprocess")

            closed = sd.close("longrun_door")
            check("close kills own child", closed["action"] == "closed",
                  f"{closed['action']}: {closed['detail']}")
            time.sleep(0.5)
            check("own child actually terminated",
                  not mk._pid_alive(info["pid"]))
            check("PID file cleaned", not pid_path.exists())
            check("key burned", "longrun_door" not in
                  dr.DoorState(h.state_file).load().get("keys", {}))

            # foreign PID: alive process we do NOT own, mismatched provenance
            sleeper = subprocess.Popen(
                [_py, "-c", "import time; time.sleep(120)"])
            foreign = make_door(name="foreign_door", mode="subprocess-longrun",
                                command=None, cwd=str(h.tmp))
            door2 = foreign
            fake_pid = {"pid": sleeper.pid, "started_at":
                        (datetime.now(timezone.utc) -
                         timedelta(hours=9)).isoformat(),
                        "cmd": ["foreign"]}
            dr.DOORS_PID_DIR.mkdir(parents=True, exist_ok=True)
            dr.DoorState.pid_file("foreign_door").write_text(
                json.dumps(fake_pid), encoding="utf-8")
            store = dr.DoorState(h.state_file)
            st = store.load()
            ent = store.door(st, "foreign_door")
            ent.update({"state": "open", "key_id": "dk_foreign0",
                        "opened_at": datetime.now(timezone.utc).isoformat(),
                        "closes_at": (datetime.now(timezone.utc) +
                                      timedelta(hours=24)).isoformat(),
                        "provenance": {"via": "subprocess",
                                       "started_at": datetime.now(
                                           timezone.utc).isoformat()}})
            st["keys"]["foreign_door"] = {"key_id": "dk_foreign0"}
            store.save(st)
            with patched_organs(
                    conscience_hook=fake,
                    capability_gate=gate,
                    organ_registry=organ_reg):
                sd2 = h.make_doors(StubRegistry([foreign]), [foreign])
                res2 = sd2.close("foreign_door")
            check("foreign/alien PID -> close refuses",
                  res2["action"] == "refused", f"{res2['action']}: {res2['detail']}")
            check("foreign process NOT killed", mk._pid_alive(sleeper.pid))
            check("key kept on refused close (fail-closed)",
                  "foreign_door" in dr.DoorState(h.state_file).load().get("keys", {}))
    finally:
        if sleeper is not None and mk._pid_alive(sleeper.pid):
            sleeper.terminate()
            try:
                sleeper.wait(timeout=5)
            except Exception:
                sleeper.kill()
        h.restore()


def probe_registry_adoption():
    log("\n== 16/17. registry adoption + token matcher ==")
    h = Harness("registry")
    try:
        h.patch_paths()
        h.set_gamma(0.60)
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake())
        gate = fake_module("aureon_fusion.capability_gate",
                           check=gate_allow)
        verb_calls = []

        def fake_verb(verb, organ):
            verb_calls.append((verb, organ))
            return {"ok": True, "detail": f"fixture {verb} {organ}", "rc": 0}

        # token matcher against the REAL organ_registry table (import-safe)
        from aureon_fusion import organ_registry as real_reg
        check("matcher: planetary_switchboard has no registry organ",
              mk._registry_organ_for({"module": "aureon_radar/planetary_switchboard.py",
                                      "registry_organ": None}) is None)
        check("matcher: hnc_core module token adopted",
              mk._registry_organ_for({"module": "aureon_fusion.hnc_core",
                                    "registry_organ": None}) == "hnc_core")
        check("matcher: explicit seat wins",
              mk._registry_organ_for({"module": "soul_protection_daemon.py → full_countermeasures.py",
                                    "registry_organ": "soul_protection_daemon"})
              == "soul_protection_daemon")

        # adoption of a RUNNING registry organ: no spawn, no stop right
        fake_organs = {"stub_organ": {"match": "stub_module"}}
        running = fake_module("aureon_fusion.organ_registry",
                              ORGANS=fake_organs,
                              status_data=lambda: {
                                  "stub_organ": {"state": "running"}})
        door = make_door(name="adopted_door", mode="subprocess-longrun",
                         module="stub_module.py", command=None)
        with patched_organs(
                conscience_hook=fake,
                capability_gate=gate,
                organ_registry=running), \
             mock.patch.object(mk, "_run_registry_verb", fake_verb):
            sd = h.make_doors(StubRegistry([door]), [door])
            res = sd.open("adopted_door")
            check("running registry organ adopted (no spawn)",
                  res["action"] == "opened" and "adopted" in res["detail"],
                  f"{res['action']}: {res['detail']}")
            check("adoption never calls registry start",
                  verb_calls == [])
            st = dr.DoorState(h.state_file).load()
            st["doors"]["adopted_door"]["provenance"] = {
                "via": "registry", "organ": "stub_organ",
                "started_by": "registry"}  # adopted, NOT started by us
            dr.DoorState(h.state_file).save(st)
            res2 = sd.close("adopted_door")
            check("adopted-only organ is NOT stopped by us",
                  res2["action"] == "refused" and
                  "ADOPTED" in res2["detail"].upper(), res2["detail"])
            check("still no registry verb issued",
                  verb_calls == [])

            # ours-started registry organ: stopped via registry only
            stopped = fake_module("aureon_fusion.organ_registry",
                                  ORGANS=fake_organs,
                                  status_data=lambda: {
                                      "stub_organ": {"state": "stopped"}})
            with patched_organs(
                    organ_registry=stopped):
                sd3 = h.make_doors(StubRegistry([door]), [door])
                st3 = dr.DoorState(h.state_file).load()
                st3["doors"].pop("adopted_door", None)
                st3["keys"].pop("adopted_door", None)
                dr.DoorState(h.state_file).save(st3)
                res3 = sd3.open("adopted_door")
            check("registry start used when organ exists but stopped",
                  res3["action"] == "opened" and
                  ("registry started" in res3["detail"]),
                  f"{res3['action']}: {res3['detail']}")
            check("start went through the registry verb",
                  ("start", "stub_organ") in verb_calls, str(verb_calls))
            res4 = sd3.close("adopted_door")
            check("ours-started organ stopped via registry",
                  res4["action"] == "closed" and
                  ("stop", "stub_organ") in verb_calls, f"{res4['action']}: {res4['detail']}")
    finally:
        h.restore()


def probe_consider():
    log("\n== 18. consider(): silence / mint+open / waning close ==")
    h = Harness("consider")
    try:
        h.patch_paths()
        h.set_gamma(0.60)
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake())
        gate = fake_module("aureon_fusion.capability_gate",
                           check=gate_allow)
        activators = fake_module(
            "aureon_fusion.door_activators",
            activate=lambda name: {"ok": True, "detail": "wired"},
            deactivate=lambda name: {"ok": True, "detail": "unwired"})
        hot = make_door(name="hot_door", value=0.95)
        mild = make_door(name="mild_door", value=0.40)
        with patched_organs(
                conscience_hook=fake,
                capability_gate=gate,
                door_activators=activators):
            sd = h.make_doors(StubRegistry([hot, mild]), [hot, mild])

            with mock.patch.object(mk, "MIN_DESIRE", 5.0):
                res = sd.consider()
            check("silence is valid (desire below threshold)",
                  res["action"] == "none", res["action"])

            res = sd.consider()
            check("consider mints+opens strongest desire",
                  res["action"] == "opened" and res["door"] == "hot_door",
                  f"{res['action']}: {res['door']} — {res['detail']}")
            check("consider result carries key_id",
                  isinstance(res["key_id"], str) and res["key_id"])

            again = sd.consider()
            check("already-open strong desire -> none (kept open)",
                  again["action"] == "none", f"{again['action']}: {again['detail']}")

            with mock.patch.object(mk, "KEEP_OPEN_DESIRE", 5.0):
                waned = sd.consider()
            check("waning desire -> organism closes the door",
                  waned["action"] == "closed", f"{waned['action']}: {waned['detail']}")
            st = dr.DoorState(h.state_file).load()
            check("waning close burned the key",
                  "hot_door" not in st.get("keys", {}) and
                  st["doors"]["hot_door"]["state"] == "closed")

            dry = sd.consider(dry_run=True)
            check("dry consider: minted but nothing persisted/spawned",
                  dry["action"] == "minted" and "[dry" in dry["detail"],
                  f"{dry['action']}: {dry['detail']}")
            check("dry consider left store untouched",
                  dr.DoorState(h.state_file).load().get("doors", {}).get(
                      "hot_door", {}).get("state") == "closed")
    finally:
        h.restore()


def probe_elevate():
    log("\n== 19. ELEVATE: conscience double-check + receipt ==")
    h = Harness("elevate")
    try:
        h.patch_paths()
        h.set_gamma(0.60)
        calls = []
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake(calls=calls))
        gate = fake_module("aureon_fusion.capability_gate",
                           check=gate_allow)
        fake_receipts = fake_module(
            "aureon_fusion.receipts",
            sign_event=lambda source, topic, payload: {
                "source": source, "topic": topic, "payload": payload,
                "receipt": {"receipt_hash": f"fixture-{topic}"}})
        marker = h.tmp / "elevate_marker.txt"
        door = make_door(name="elevate_door", elevate=True,
                         autonomy_class="ACT",
                         mode="subprocess-oneshot",
                         command=[_py, "-c",
                                  f"open({str(marker)!r}, 'w').write('elevated')"],
                         cwd=str(h.tmp),
                         domain_action="network_access:fetch_public_data")
        env_patch = mock.patch.dict(
            os.environ, {mk.SIGNING_ENABLED_ENV: "1"})
        with env_patch, patched_organs(
                conscience_hook=fake,
                capability_gate=gate,
                receipts=fake_receipts):
            sd = h.make_doors(StubRegistry([door]), [door])
            res = sd.open("elevate_door")
        check("ELEVATE door opened", res["action"] == "opened",
              f"{res['action']}: {res['detail']}")
        check("conscience evaluated TWICE (mint + open double-check)",
              len(calls) == 2, f"{len(calls)} calls")
        check("double-check carried full context",
              any((c["context"] or {}).get("phase") == "open_double_check"
                  for c in calls))
        check("receipt attached to open result",
              res.get("receipt") == "fixture-door.elevate_open", res.get("receipt"))
        journaled = [r for r in h.journal_records()
                     if r.get("door") == "elevate_door" and r.get("event") == "open"]
        check("ELEVATE open journaled with receipt",
              journaled and journaled[0].get("receipt") ==
              "fixture-door.elevate_open", str(journaled[:1]))

        # ELEVATE VETO at the double-check: mint ok, open refused
        calls.clear()
        veto_fake = fake_module("aureon_fusion.conscience_hook",
                                evaluate=conscience_fake(verdict="VETO",
                                                         calls=calls))
        # first call (mint) must pass, second (double-check) VETO:
        state = {"n": 0}

        def two_phase(desc, context=None):
            state["n"] += 1
            if state["n"] == 1:
                return {"verdict": "APPROVED", "reasoning": "mint ok",
                        "conditions": []}
            return {"verdict": "VETO", "reasoning": "second thoughts",
                    "conditions": []}
        two_phase_fake = fake_module("aureon_fusion.conscience_hook",
                                     evaluate=two_phase)
        with patched_organs(
                conscience_hook=two_phase_fake,
                capability_gate=gate,
                receipts=fake_receipts):
            sd2 = h.make_doors(StubRegistry([door]), [door])
            st = dr.DoorState(h.state_file).load()
            st["doors"].pop("elevate_door", None)
            st["keys"].pop("elevate_door", None)
            dr.DoorState(h.state_file).save(st)
            res2 = sd2.open("elevate_door")
        check("ELEVATE double-check VETO -> open refused",
              res2["action"] == "refused" and "double-check" in res2["detail"],
              f"{res2['action']}: {res2['detail']}")
        check("VETOed ELEVATE door not marked open",
              dr.DoorState(h.state_file).load()["doors"].get(
                  "elevate_door", {}).get("state", "closed") != "open")
    finally:
        h.restore()


def probe_journal_rotation():
    log("\n== 20. journal rotation ==")
    h = Harness("rotate")
    try:
        h.patch_paths()
        h.patch(mk, "JOURNAL_ROTATE_BYTES", 2048)
        h.set_gamma(0.60)
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake())
        gate = fake_module("aureon_fusion.capability_gate",
                           check=gate_allow)
        door = make_door(name="rotate_door")
        h.journal_file.parent.mkdir(parents=True, exist_ok=True)
        h.journal_file.write_text("x" * 3000, encoding="utf-8")
        with patched_organs(
                conscience_hook=fake,
                capability_gate=gate):
            sd = h.make_doors(StubRegistry([door]), [door])
            sd.open("rotate_door")
        rotated = list(h.doors_dir.glob("journal.*.jsonl"))
        check("oversized journal rotated before append",
              len(rotated) == 1, str(list(h.doors_dir.iterdir())))
        recs = h.journal_records()
        # open() with no prior key journals the mint separately, then the
        # open — two records, both for this door, nothing else.
        check("fresh journal holds exactly this open's records",
              len(recs) == 2 and all(r.get("door") == "rotate_door"
                                     for r in recs),
              str(len(recs)))
    finally:
        h.restore()


def probe_inproc_activator_unavailable():
    log("\n== 21. INPROC activator unavailable -> graceful refuse ==")
    h = Harness("noactivator")
    try:
        h.patch_paths()
        h.set_gamma(0.60)
        fake = fake_module("aureon_fusion.conscience_hook",
                           evaluate=conscience_fake())
        gate = fake_module("aureon_fusion.capability_gate",
                           check=gate_allow)
        def broken_activate(name):
            raise ImportError("fixture: activator cannot serve this door")
        broken = fake_module("aureon_fusion.door_activators",
                             activate=broken_activate,
                             deactivate=broken_activate)
        door = make_door(name="lonely_door")  # INPROC, activator broken
        with patched_organs(
                conscience_hook=fake,
                capability_gate=gate,
                door_activators=broken):
            sd = h.make_doors(StubRegistry([door]), [door])
            res = sd.open("lonely_door")
        check("activator unavailable -> graceful refuse",
              res["action"] == "refused" and "activator" in res["detail"],
              f"{res['action']}: {res['detail']}")
        check("refused mechanics left door closed",
              dr.DoorState(h.state_file).load()["doors"].get(
                  "lonely_door", {}).get("state", "closed") != "open")
    finally:
        h.restore()


# ───────────────────────── runner ──────────────────────────────────────────

def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    verbose = "-v" in (argv or sys.argv[1:])
    log("=" * 72)
    log("SOVEREIGN DOOR SYSTEM — BUILD-CORE offline probes")
    log("=" * 72)
    probes = [
        probe_registry_table,
        probe_registry_get,
        probe_door_state,
        probe_conscience_veto,
        probe_coherence,
        probe_capability_rows,
        probe_full_cycle_inproc,
        probe_expired_key,
        probe_locked_doors,
        probe_oneshot_subprocess,
        probe_longrun_own_child,
        probe_registry_adoption,
        probe_consider,
        probe_elevate,
        probe_journal_rotation,
        probe_inproc_activator_unavailable,
    ]
    for fn in probes:
        try:
            fn()
        except Exception as exc:
            check(f"{fn.__name__} (exception)", False,
                  f"{type(exc).__name__}: {exc}")
            if verbose:
                import traceback
                traceback.print_exc()
    passed = sum(1 for _, ok in _results if ok)
    failed = len(_results) - passed
    log("\n" + "=" * 72)
    log(f"PROBE RESULT: {passed}/{len(_results)} passed, {failed} failed")
    log("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
