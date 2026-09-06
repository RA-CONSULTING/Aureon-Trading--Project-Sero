#!/usr/bin/env python3
"""Probe: orca goal-state candidate order + micro-momentum fail-closed/auth.

No network calls (requests.get is stubbed), no real workspace state touched.
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

WORKSPACE = Path(r"C:\Users\user\.kimi_openclaw\workspace")
sys.path.insert(0, str(WORKSPACE / "aureon-os-upstream"))
sys.path.insert(0, str(WORKSPACE / "aureon_radar" / "bots"))

failures = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


# ═══ 1. orca_fire_trade._load_goal_distance candidate order ═══
import orca_fire_trade as orca

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)

    # (a) no state file anywhere → graceful 999999 fallback
    os.environ["SERO_WORKSPACE"] = str(tmp / "ws_empty")
    os.environ.pop("QUANTUM_GOAL_STATE", None)
    dist = orca.FireTrader._load_goal_distance(None)
    check("missing state file -> 999999 fallback", dist == 999999.0, repr(dist))
    dist = orca.FireTrader._load_goal_distance(None)  # second call still fine
    check("fallback stable on repeat call", dist == 999999.0, repr(dist))

    # (b) anchored workspace path is read (aureon_fusion/state/goals/)
    goals_dir = tmp / "ws_a" / "aureon_fusion" / "state" / "goals"
    goals_dir.mkdir(parents=True)
    (goals_dir / "quantum_goal_engine_state.json").write_text(json.dumps(
        {"active_goals": [{"target_value": 500, "current_value": 100}]}), encoding="utf-8")
    os.environ["SERO_WORKSPACE"] = str(tmp / "ws_a")
    dist = orca.FireTrader._load_goal_distance(None)
    check("anchored aureon_fusion/state/goals path read (dist=400)", dist == 400.0, repr(dist))

    # (c) QUANTUM_GOAL_STATE env wins over anchored path
    env_file = tmp / "env_state.json"
    env_file.write_text(json.dumps(
        {"active_goals": [{"target_value": 50, "current_value": 10}]}), encoding="utf-8")
    os.environ["QUANTUM_GOAL_STATE"] = str(env_file)
    dist = orca.FireTrader._load_goal_distance(None)
    check("QUANTUM_GOAL_STATE env override wins (dist=40)", dist == 40.0, repr(dist))
    os.environ.pop("QUANTUM_GOAL_STATE", None)
    os.environ.pop("SERO_WORKSPACE", None)

# ═══ 2. aureon_micro_momentum_goal ═══
import requests
from aureon.conversion import aureon_micro_momentum_goal as mom


class FakeResp:
    def __init__(self, status_code):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def json(self):
        return {"bars": {}}


# (a) fail-closed: no creds resolvable → no HTTP request at all, empty result
os.environ.pop("APCA_API_KEY_ID", None)
os.environ.pop("APCA_API_SECRET_KEY", None)
mom._ALPACA_CREDS_LOADED = False
mom._ALPACA_CREDS = None
called = []


def _boom(*a, **k):
    called.append(1)
    raise AssertionError("request must not be sent without credentials")


mom.requests.get = _boom
real_loader = mom._load_alpaca_creds
mom._load_alpaca_creds = lambda: None  # simulate: no env, no .env entries
scanner = mom.MicroMomentumScanner()
result = scanner._fetch_1min_bars(["BTC/USD"])
check("no creds -> fail-closed (no request, empty dict)", result == {} and not called)
mom._load_alpaca_creds = real_loader

# (b) creds from env -> authenticated request; HTTP 401 logged once, empty result
os.environ["APCA_API_KEY_ID"] = "PROBE_KEY"
os.environ["APCA_API_SECRET_KEY"] = "PROBE_SECRET"
mom._ALPACA_CREDS_LOADED = False
mom._ALPACA_CREDS = None
seen_headers = []


def _fake_get(url, params=None, headers=None, timeout=None):
    seen_headers.append(headers)
    return FakeResp(401)


mom.requests.get = _fake_get
result = scanner._fetch_1min_bars(["BTC/USD"])
check("HTTP 401 -> empty dict (fail-closed, no signals)", result == {})
check("auth headers sent to Alpaca",
      seen_headers and seen_headers[0].get("APCA-API-KEY-ID") == "PROBE_KEY"
      and seen_headers[0].get("APCA-API-SECRET-KEY") == "PROBE_SECRET",
      repr(seen_headers))
os.environ.pop("APCA_API_KEY_ID", None)
os.environ.pop("APCA_API_SECRET_KEY", None)

# (c) success path caches bars
mom._load_alpaca_creds = lambda: ("K", "S")


class FakeOk(FakeResp):
    def json(self):
        return {"bars": {"BTC/USD": [{"c": "65000"}, {"c": "64900"}]}}


mom.requests.get = lambda *a, **k: FakeOk(200)
ok = scanner._fetch_1min_bars(["BTC/USD"])
check("HTTP 200 -> bars fetched and cached",
      ok.get("BTC/USD") == [{"c": "65000"}, {"c": "64900"}]
      and "BTC/USD" in scanner._bar_cache)
mom.requests.get = _boom
mom._load_alpaca_creds = real_loader

# (d) ADVISORY line carries conviction + cost math, never bare EXECUTE
sig = mom.MomentumSignal(
    symbol="BTC/USD", exchange="alpaca", tier=mom.MomentumTier.TIER_1_HOT,
    current_price=65000.0, price_1m_ago=64800.0, price_5m_ago=64500.0,
    momentum_1m_pct=0.31, momentum_5m_pct=0.78,
    break_even_threshold=0.34, net_profit_potential=0.44, direction="LONG")
buf = io.StringIO()
with redirect_stdout(buf):
    scanner.print_scan_results([sig])
out = buf.getvalue()
check("output marked ADVISORY (not an order)",
      "ADVISORY (not an order):" in out)
check("conviction shown next to advisory", "1m +0.310%" in out and "5m +0.780%" in out)
check("cost math shown next to advisory", "gross 0.780% - break-even 0.340% = net +0.440%" in out)
check("no bare EXECUTE line", "EXECUTE:" not in out)

print()
print("ALL PASS" if not failures else f"FAILURES: {failures}")
sys.exit(1 if failures else 0)
