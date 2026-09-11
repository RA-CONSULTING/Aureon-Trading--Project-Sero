"""
WorldSense — live world-awareness aggregator for the Queen voice.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The Queen already has access to many live world-awareness sources in
the repo, but they were scattered and only the cosmic one (Dr Auris
Throne) was reaching the voice layer. This module is the coalescing
layer: a single ``snapshot()`` call pulls a compact ``WorldState``
across every source, caches the result for a short TTL so the
per-message cost stays low, and renders a prompt-ready text block.

Sources wired:

  * ``DrAurisThrone``              — cosmic advisory + Kp + Schumann + Λ(t) (10 s cycle)
  * ``SchumannResonanceBridge``    — live 7.83 Hz fundamental + earth_blessing (local
                                     station state first, then derived; 5 min cache)
  * ``EarthResonanceEngine``       — trading-gate status + PHI multiplier
  * ``SpaceWeatherBridge``         — NOAA Kp / solar wind / Bz / flares (5 min cache)
  * ``GlobalFinancialFeed``        — fear/greed + VIX + DXY + market regime (60 s cache)
  * ``news_signal``                — RSS-based news sentiment + geo risk (10 min refresh)
  * ``news_geo_digest``            — cross-agent contract file
                                     (``aureon/data_feeds/state/news_geo_digest.json``);
                                     fail-closed with reason ``digest_not_yet_present``
                                     until the world-digest agent's producer lands

All pullers run concurrently in daemon threads: no single slow source
can starve the others the way the old sequential loop let the Schumann
bridge eat the whole budget. Every source is wrapped in try/except — a
missing or dead source leaves its slice of the state empty instead of
crashing the voice path. A per-snapshot total budget (default 8 s,
override ``AUREON_WORLD_SENSE_BUDGET_S``) caps total wait time even if
a source stalls; stalled sources are recorded as
``<name>:budget_exhausted``.

Usage::

    ws = get_world_sense()
    state = ws.snapshot()
    print(state.render_for_prompt())
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aureon.queen.world_sense")


# ─────────────────────────────────────────────────────────────────────────────
# Data type
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class WorldState:
    """Snapshot of the Queen's external awareness at a single moment."""

    # ── Temporal ───────────────────────────────────────────────
    now_iso: str = ""
    weekday: str = ""
    hour_local: int = 0
    market_hours_open: Optional[bool] = None

    # ── Cosmic ─────────────────────────────────────────────────
    kp_index: Optional[float] = None
    solar_wind_kms: Optional[float] = None
    bz_component_nt: Optional[float] = None
    cosmic_advisory: str = ""
    cosmic_score: Optional[float] = None
    schumann_hz: Optional[float] = None
    schumann_coherence: Optional[float] = None
    earth_blessing: Optional[float] = None
    earth_gate_open: Optional[bool] = None

    # ── Market ─────────────────────────────────────────────────
    fear_greed: Optional[int] = None
    fear_greed_label: str = ""
    market_regime: str = ""
    risk_on_off: str = ""
    vix: Optional[float] = None
    dxy: Optional[float] = None
    btc_dominance: Optional[float] = None

    # ── News ───────────────────────────────────────────────────
    geo_risk: Optional[float] = None
    news_risk_level: str = ""
    dominant_themes: List[str] = field(default_factory=list)

    # ── News geo digest (cross-agent contract) ─────────────────
    news_geo_risk: Optional[float] = None
    news_geo_level: str = ""
    news_geo_themes: List[str] = field(default_factory=list)
    news_geo_headline: str = ""

    # ── Bookkeeping ────────────────────────────────────────────
    sources_ok: List[str] = field(default_factory=list)
    sources_failed: List[str] = field(default_factory=list)
    resolve_ms: float = 0.0
    captured_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def has_any(self) -> bool:
        return bool(self.sources_ok)

    def render_for_prompt(self, max_chars: int = 420) -> str:
        """
        Compact multi-line block the LLM can consume as "the world
        right now". Each line is one axis. Empty / unknown values are
        skipped so we never inject stale placeholders.
        """
        lines: List[str] = ["The world right now:"]

        # Time + market hours
        time_bits: List[str] = []
        if self.now_iso:
            time_bits.append(self.now_iso[:16].replace("T", " "))
        if self.weekday:
            time_bits.append(self.weekday)
        if self.market_hours_open is not None:
            time_bits.append("markets open" if self.market_hours_open else "markets closed")
        if time_bits:
            lines.append("  • time: " + ", ".join(time_bits))

        # Cosmic
        cosmic_bits: List[str] = []
        if self.cosmic_advisory:
            cosmic_bits.append(f"advisory={self.cosmic_advisory}")
        if self.kp_index is not None:
            cosmic_bits.append(f"Kp={self.kp_index:.1f}")
        if self.schumann_hz is not None:
            cosmic_bits.append(f"Schumann={self.schumann_hz:.2f}Hz")
        if self.earth_blessing is not None:
            cosmic_bits.append(f"earth_blessing={self.earth_blessing:.2f}")
        if self.earth_gate_open is not None:
            cosmic_bits.append("gate=open" if self.earth_gate_open else "gate=closed")
        if cosmic_bits:
            lines.append("  • cosmic: " + ", ".join(cosmic_bits))

        # Market
        market_bits: List[str] = []
        if self.fear_greed is not None:
            lbl = f"({self.fear_greed_label})" if self.fear_greed_label else ""
            market_bits.append(f"fear_greed={self.fear_greed}{lbl}")
        if self.market_regime:
            market_bits.append(f"regime={self.market_regime}")
        if self.vix is not None:
            market_bits.append(f"VIX={self.vix:.1f}")
        if self.dxy is not None:
            market_bits.append(f"DXY={self.dxy:.1f}")
        if self.btc_dominance is not None:
            market_bits.append(f"BTC.D={self.btc_dominance:.1f}%")
        if market_bits:
            lines.append("  • markets: " + ", ".join(market_bits))

        # News
        news_bits: List[str] = []
        if self.geo_risk is not None:
            news_bits.append(f"geo_risk={self.geo_risk:.2f}")
        if self.news_risk_level:
            news_bits.append(self.news_risk_level)
        if self.dominant_themes:
            news_bits.append("themes: " + ", ".join(self.dominant_themes[:3]))
        if news_bits:
            lines.append("  • news: " + ", ".join(news_bits))

        # News geo digest contract file (another agent produces it)
        news_geo_bits: List[str] = []
        if self.news_geo_risk is not None:
            news_geo_bits.append(f"risk={self.news_geo_risk:.2f}")
        if self.news_geo_level:
            news_geo_bits.append(self.news_geo_level)
        if self.news_geo_themes:
            news_geo_bits.append("themes: " + ", ".join(self.news_geo_themes[:3]))
        if self.news_geo_headline:
            news_geo_bits.append(self.news_geo_headline[:60])
        if news_geo_bits:
            lines.append("  • news_geo: " + ", ".join(news_geo_bits))

        block = "\n".join(lines)
        if len(block) > max_chars:
            block = block[: max_chars - 3].rstrip() + "..."
        return block


# ─────────────────────────────────────────────────────────────────────────────
# WorldSense
# ─────────────────────────────────────────────────────────────────────────────


class WorldSense:
    """
    Coalescing aggregator over the live world-awareness sources.

    Thread-safe, TTL-cached. Callers should use ``get_world_sense()`` to
    get the process-wide singleton and call ``snapshot()`` every time
    they need a fresh read.
    """

    # Maximum age of the cross-agent news geo digest file (seconds).
    _NEWS_GEO_DIGEST_MAX_AGE_S: float = float(
        os.environ.get("AUREON_NEWS_GEO_DIGEST_MAX_AGE_S", "1800")
    )

    def __init__(
        self,
        *,
        cache_ttl_s: float = 20.0,
        total_budget_s: Optional[float] = None,
        sources: Optional[Dict[str, Any]] = None,
    ):
        self.cache_ttl_s = float(cache_ttl_s)
        self.total_budget_s = float(
            total_budget_s
            if total_budget_s is not None
            else os.environ.get("AUREON_WORLD_SENSE_BUDGET_S", "8.0")
        )
        self._cached: Optional[WorldState] = None
        self._cached_at: float = 0.0
        self._lock = threading.RLock()
        # ``sources`` lets tests inject fakes without monkey-patching.
        # Keys map to callables that return a dict with the fields
        # this aggregator cares about. Real sources are wired lazily.
        self._sources = sources or {}

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    def snapshot(self) -> WorldState:
        now = time.time()
        with self._lock:
            if (
                self._cached is not None
                and (now - self._cached_at) < self.cache_ttl_s
            ):
                return self._cached

        t0 = time.time()
        state = WorldState(captured_at=now)
        self._populate_temporal(state)

        # Run every puller in its own daemon thread so a single slow
        # source (historically the Schumann bridge) cannot starve the
        # others. Each thread writes into a private scratch state; we
        # merge in the order below, giving Dr Auris priority over the
        # direct space-weather bridge for overlapping fields.
        pullers = [
            ("dr_auris", self._pull_dr_auris),
            ("schumann", self._pull_schumann),
            ("earth_gate", self._pull_earth_gate),
            ("space_weather", self._pull_space_weather),
            ("financial", self._pull_financial),
            ("news", self._pull_news),
            ("news_geo_digest", self._pull_news_geo_digest),
        ]

        scratch: Dict[str, Any] = {}
        scratch_lock = threading.Lock()

        def _run_puller(name: str, fn: Any) -> None:
            local = WorldState()
            try:
                fn(local)
            except SourceSkipped as exc:
                with scratch_lock:
                    scratch[name] = ("skipped", str(exc) or "skipped")
                return
            except Exception as exc:
                logger.debug("world_sense: %s pull failed: %s", name, exc)
                with scratch_lock:
                    scratch[name] = ("failed", "")
                return
            with scratch_lock:
                scratch[name] = ("ok", local)

        threads = []
        for name, fn in pullers:
            th = threading.Thread(
                target=_run_puller,
                args=(name, fn),
                daemon=True,
                name=f"world_sense_{name}",
            )
            th.start()
            threads.append((name, th))

        deadline = t0 + self.total_budget_s
        for _name, th in threads:
            remaining = deadline - time.time()
            th.join(timeout=max(0.0, remaining))

        for name, _th in threads:
            outcome = scratch.get(name)
            if outcome is None:
                # Thread never finished in the allotted budget.
                state.sources_failed.append(f"{name}:budget_exhausted")
            elif outcome[0] == "ok":
                _merge_state(state, outcome[1])
                state.sources_ok.append(name)
            elif outcome[0] == "skipped":
                state.sources_failed.append(f"{name}:{outcome[1]}")
            else:
                state.sources_failed.append(name)

        state.resolve_ms = (time.time() - t0) * 1000.0
        with self._lock:
            self._cached = state
            self._cached_at = now
        return state

    def invalidate(self) -> None:
        with self._lock:
            self._cached = None
            self._cached_at = 0.0

    # ─────────────────────────────────────────────────────────────────
    # Per-source pullers (each is tiny and wrapped in try/except above)
    # ─────────────────────────────────────────────────────────────────

    def _populate_temporal(self, state: WorldState) -> None:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        state.now_iso = now_utc.isoformat(timespec="seconds")
        state.weekday = now_utc.strftime("%A")
        state.hour_local = int(now_utc.hour)
        # Rough NYSE core hours check (13:30-20:00 UTC Mon-Fri) —
        # accurate enough for "is wall street awake right now".
        if 0 <= now_utc.weekday() <= 4:
            minutes = now_utc.hour * 60 + now_utc.minute
            state.market_hours_open = (13 * 60 + 30) <= minutes <= (20 * 60)
        else:
            state.market_hours_open = False

    def _pull_dr_auris(self, state: WorldState) -> None:
        src = self._sources.get("dr_auris")
        if src is None:
            try:
                from aureon.intelligence.dr_auris_throne import get_dr_auris_throne
                src = lambda: get_dr_auris_throne().get_state()
            except Exception:
                return
        data = src()
        if data is None:
            return
        for field_name, dst in (
            ("advisory", "cosmic_advisory"),
            ("cosmic_score", "cosmic_score"),
            ("kp_index", "kp_index"),
            ("solar_wind_speed", "solar_wind_kms"),
            ("bz_component", "bz_component_nt"),
        ):
            val = _get_attr_or_key(data, field_name)
            if val is not None:
                setattr(state, dst, val)

    def _pull_schumann(self, state: WorldState) -> None:
        src = self._sources.get("schumann")
        if src is None:
            try:
                from aureon.harmonic.aureon_schumann_resonance_bridge import (
                    SchumannResonanceBridge,
                )
                bridge = SchumannResonanceBridge()
                src = lambda: bridge.get_live_data()
            except Exception:
                return
        data = src()
        if data is None:
            return
        fund = _get_attr_or_key(data, "fundamental_hz")
        if fund is not None and state.schumann_hz is None:
            state.schumann_hz = float(fund)
        coh = _get_attr_or_key(data, "coherence")
        if coh is not None and state.schumann_coherence is None:
            state.schumann_coherence = float(coh)
        blessing = _get_attr_or_key(data, "earth_blessing")
        if blessing is not None and state.earth_blessing is None:
            state.earth_blessing = float(blessing)

    def _pull_earth_gate(self, state: WorldState) -> None:
        src = self._sources.get("earth_gate")
        if src is None:
            try:
                from aureon.harmonic.earth_resonance_engine import get_earth_engine
                engine = get_earth_engine()
                src = lambda: engine.get_trading_gate_status()
            except Exception:
                return
        data = src()
        if data is None:
            return
        # get_trading_gate_status returns either (bool, reason) or a dict
        if isinstance(data, tuple) and len(data) >= 1:
            state.earth_gate_open = bool(data[0])
        elif isinstance(data, dict):
            gate = data.get("gate_open")
            if gate is not None:
                state.earth_gate_open = bool(gate)

    def _pull_space_weather(self, state: WorldState) -> None:
        src = self._sources.get("space_weather")
        if src is None:
            try:
                from aureon.data_feeds.aureon_space_weather_bridge import (
                    SpaceWeatherBridge,
                )
                bridge = SpaceWeatherBridge()
                src = lambda: bridge.get_live_data()
            except Exception:
                return
        data = src()
        if data is None:
            return
        # Prefer Dr Auris values when already set, but fill gaps from
        # the direct bridge.
        for field_name, dst in (
            ("kp_index", "kp_index"),
            ("solar_wind_speed", "solar_wind_kms"),
            ("bz_component", "bz_component_nt"),
        ):
            val = _get_attr_or_key(data, field_name)
            if val is not None and getattr(state, dst) is None:
                setattr(state, dst, float(val))

    def _pull_financial(self, state: WorldState) -> None:
        src = self._sources.get("financial")
        if src is None:
            try:
                from aureon.data_feeds.global_financial_feed import GlobalFinancialFeed
                feed = GlobalFinancialFeed()
                src = lambda: feed.get_snapshot()
            except Exception:
                return
        data = src()
        if data is None:
            return
        for field_name, dst, cast in (
            ("crypto_fear_greed", "fear_greed", int),
            ("crypto_fg_classification", "fear_greed_label", str),
            ("market_regime", "market_regime", str),
            ("risk_on_off", "risk_on_off", str),
            ("vix", "vix", float),
            ("dxy", "dxy", float),
            ("btc_dominance", "btc_dominance", float),
        ):
            val = _get_attr_or_key(data, field_name)
            if val is None:
                continue
            try:
                setattr(state, dst, cast(val))
            except Exception:
                pass

    def _pull_news(self, state: WorldState) -> None:
        src = self._sources.get("news")
        if src is None:
            try:
                from aureon.data_feeds.news_signal import get_news_signal

                src = get_news_signal
            except Exception:
                return
        data = src()
        if data is None:
            return
        geo = _get_attr_or_key(data, "geo_risk")
        if geo is not None:
            try:
                state.geo_risk = float(geo)
            except Exception:
                pass
        lvl = _get_attr_or_key(data, "risk_level")
        if lvl:
            state.news_risk_level = str(lvl)
        themes = _get_attr_or_key(data, "themes")
        if isinstance(themes, (list, tuple)):
            state.dominant_themes = [str(t) for t in themes[:5]]

    def _pull_news_geo_digest(self, state: WorldState) -> None:
        """
        Consume the world-digest agent's contract file. If the file does
        not exist yet the producer is still building it; fail-closed with
        reason ``digest_not_yet_present`` and do not fabricate values.
        """
        src = self._sources.get("news_geo_digest")
        data: Any = None
        if src is not None:
            data = src()
        else:
            path = os.environ.get("AUREON_NEWS_GEO_DIGEST_PATH")
            if not path:
                here = os.path.dirname(os.path.abspath(__file__))
                path = os.path.abspath(
                    os.path.join(here, "..", "data_feeds", "state", "news_geo_digest.json")
                )
            else:
                path = os.path.abspath(path)

            if not os.path.exists(path):
                raise SourceSkipped("digest_not_yet_present")

            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                raise SourceSkipped("digest_unreadable")

            if not isinstance(data, dict):
                raise SourceSkipped("digest_unreadable")

            ts = (
                _get_attr_or_key(data, "timestamp")
                or _get_attr_or_key(data, "captured_at")
                or _get_attr_or_key(data, "generated_at")
                or _get_attr_or_key(data, "updated_at")
                or _get_attr_or_key(data, "ts")
            )
            if ts:
                try:
                    ts_str = str(ts)
                    normalized = (
                        ts_str[:-1] + "+00:00" if ts_str.endswith("Z") else ts_str
                    )
                    age = time.time() - datetime.datetime.fromisoformat(normalized).timestamp()
                    if age > self._NEWS_GEO_DIGEST_MAX_AGE_S:
                        raise SourceSkipped("digest_stale")
                except SourceSkipped:
                    raise
                except Exception:
                    # Unparseable timestamp: fail-closed would be too harsh for a
                    # brand-new contract file, so we accept it but do not invent an age.
                    pass

        if data is None:
            return

        risk = _get_attr_or_key(data, "geo_risk") or _get_attr_or_key(data, "risk")
        if risk is not None:
            try:
                state.news_geo_risk = float(risk)
            except Exception:
                pass
        lvl = _get_attr_or_key(data, "risk_level") or _get_attr_or_key(data, "level")
        if lvl:
            state.news_geo_level = str(lvl)
        themes = _get_attr_or_key(data, "themes") or _get_attr_or_key(data, "dominant_themes")
        if isinstance(themes, (list, tuple)):
            state.news_geo_themes = [str(t) for t in themes[:5]]
        headline = _get_attr_or_key(data, "headline") or _get_attr_or_key(data, "summary")

        # If the producer has not yet written the canonical fields, we can
        # still surface a short, honest headline from the funding-energy
        # slice that the file already carries. This uses real contract data,
        # never fabricating a risk score.
        if not headline:
            funding = _get_attr_or_key(data, "funding_energy") or {}
            flows = _get_attr_or_key(funding, "notable_flows") or []
            if isinstance(flows, (list, tuple)) and flows:
                bits = []
                for flow in flows[:2]:
                    if not isinstance(flow, dict):
                        continue
                    name = flow.get("name") or flow.get("protocol") or "?"
                    change = flow.get("change_1d_pct")
                    if change is None:
                        change = flow.get("change_pct")
                    sign = "+" if change is not None and change >= 0 else ""
                    bits.append(
                        f"{name} {sign}{change:.2f}%" if change is not None else str(name)
                    )
                if bits:
                    headline = "DeFi flows: " + ", ".join(bits)

        if headline:
            state.news_geo_headline = str(headline)[:120]

        # If the file is present but carries nothing we can interpret, say so
        # honestly rather than pretending the source contributed data.
        if (
            state.news_geo_risk is None
            and not state.news_geo_level
            and not state.news_geo_themes
            and not state.news_geo_headline
        ):
            raise SourceSkipped("digest_no_recognized_fields")


class SourceSkipped(Exception):
    """A puller intentionally produced nothing; the reason surfaces in the report."""


def _merge_state(dst: WorldState, src: WorldState) -> None:
    """Merge a per-puller scratch state into the main state, respecting priority."""
    for field_info in fields(src):
        name = field_info.name
        if name in ("sources_ok", "sources_failed", "resolve_ms", "captured_at"):
            continue
        current = getattr(dst, name)
        if current not in (None, "", []):
            continue
        value = getattr(src, name)
        if value in (None, "", []):
            continue
        setattr(dst, name, value)


def _get_attr_or_key(obj: Any, name: str) -> Any:
    """Works on both dataclasses and dict-like snapshots."""
    if obj is None:
        return None
    try:
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────


_singleton: Optional[WorldSense] = None
_singleton_lock = threading.Lock()


def get_world_sense() -> WorldSense:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = WorldSense()
        return _singleton


def reset_world_sense() -> None:
    global _singleton
    with _singleton_lock:
        _singleton = None


__all__ = [
    "WorldState",
    "WorldSense",
    "get_world_sense",
    "reset_world_sense",
]
