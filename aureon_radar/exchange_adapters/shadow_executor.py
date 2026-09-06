"""Shadow execution engine — Aureon radar (organism-controlled).

BINDING SCHEMA (decided here; venue agents and the hub must conform):

- A "shadow order" is a labeled simulation of intent filled against a REAL,
  FRESH public quote. It never leaves the machine and never touches keys.
- Data-freshness doctrine is ABSOLUTE. If the injected quote function is
  unreachable, returns no usable price, or returns a quote older than
  STALE_AFTER_SEC (30 s), the order is REFUSED with event="refused" and a
  `reason` of:
      refused_feed_unavailable  — quote function raised / returned nothing
      refused_feed_stale        — quote timestamp older than 30 s, or its
                                  timestamp is missing/unparseable (cannot
                                  prove freshness => not fresh)
      refused_invalid_order     — bad side/qty/symbol
  A refused order is journaled and NEVER filled. No price is ever fabricated.

- QUOTE CONTRACT (venue quote functions must return a mapping with):
      bid, ask, last   : floats (any may be absent, not all)
      source           : str provenance label (e.g. "kraken_public_ticker_live")
      fetched_at       : epoch seconds (float/int) OR ISO-8601 str
      ts_utc           : ISO-8601 str (alternative to fetched_at)
  The venue wrappers in shadow_{kraken,alpaca,binance}.py adapt the native
  adapter payloads to this contract. `provenance` in the journal is
  "<source>@<ISO-8601 of the quote's own timestamp>". A quote function that
  fails must return None or raise — the engine converts that into
  refused_feed_unavailable.

- FILL MODEL: reference = ask for BUY, bid for SELL (taker realism);
  fallbacks: last, then mid=(bid+ask)/2. Adverse slippage SLIPPAGE (0.05 %)
  is applied against the direction: buy_fill = ref*(1+SLIPPAGE),
  sell_fill = ref*(1-SLIPPAGE). Taker fee is charged on fill notional:
  kraken 0.26 %, binance 0.10 %, alpaca 0.0 % (VENUE_FEES below).

- POSITIONS: one open position per (venue, symbol). An opposite-side propose
  on an open position closes it first (reason="reversal"), then opens the new
  one. Same-side propose on an open position adds to it at a volume-weighted
  average entry and journals event="filled". Protective levels from entry:
  stop-loss -2 %, take-profit +3 % (STOP_PCT / TAKE_PROFIT_PCT).

- JOURNAL: aureon_radar/state/shadow_trades.jsonl — one JSON line per event:
  event in {"opened","filled","closed","refused","mark"} with fields
  ts_utc, event, venue, symbol, side, qty, price, fee, signal_source,
  signal_confidence, provenance (omitted when unavailable); closes add
  entry_price, exit_reason, gross_pnl, fees, net_pnl, pnl_pct, hold_seconds.
  `mark` events (MTM heartbeat) are throttled to one per position per
  MARK_JOURNAL_THROTTLE_SEC (default 300 s) to keep the journal honest but
  bounded; MTM itself updates in memory every call.

- LEDGER: aureon_radar/state/shadow_ledger_summary.json — rewritten after
  every close, keyed "<venue>:<symbol>", with closed_trades, wins, losses,
  win_rate, total gross/net pnl, total fees, plus a "totals" block.

- LIVE GATE: live_place() in the venue wrappers is FAIL-CLOSED. It re-reads
  aureon_radar/.env AND os.environ at CALL TIME (values are never logged,
  returned, or journaled — key NAMES only) and returns
  {"status": "refused_not_authorized", ...} unless both required key
  variables are non-empty. When keys are present it delegates to the venue
  adapter's existing order path.

Import has no side effects. Network happens only inside venue quote functions.
"""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

RADAR_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOURNAL_PATH = RADAR_ROOT / "state" / "shadow_trades.jsonl"
DEFAULT_LEDGER_PATH = RADAR_ROOT / "state" / "shadow_ledger_summary.json"
ENV_PATH = RADAR_ROOT / ".env"

# ── binding constants (see module docstring) ─────────────────────────────
STALE_AFTER_SEC = 30.0
SLIPPAGE = 0.0005          # 0.05 % adverse, applied to fill price
MARK_JOURNAL_THROTTLE_SEC = 300.0
STOP_PCT = -0.02           # -2 % from entry fill
TAKE_PROFIT_PCT = 0.03     # +3 % from entry fill
VENUE_FEES: Dict[str, float] = {
    # Taker fees (all organism orders are market orders = takers).
    # Kraken tier 0 (<$10k 30d volume): 0.40% taker / 0.25% maker — corrected
    # 2026-09-06 from 0.26% (bug-hunt: fee math understated real cost).
    "kraken": 0.0040,
    "binance": 0.0010,   # VIP0 spot taker
    "alpaca": 0.0,       # crypto: commission-free, cost lives in spread
    # Capital.com CFD: no flat taker fee — the round-trip cost IS the spread,
    # and the spread is already embedded in the quoted/fill price, so adding
    # a fee here would double-count. Round-trip cost for the expectancy gate
    # is therefore slippage-only (2 * 0.05% via round_trip_cost()).
    "capital": 0.0,
}
DEFAULT_FEE = 0.0

QuoteFn = Callable[[str], Optional[Dict[str, Any]]]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_from_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _parse_ts_epoch(value: Any) -> Optional[float]:
    """Epoch seconds from an epoch number or an ISO-8601 string; None if bad."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(float(value)) else None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


@dataclass
class ShadowOrder:
    venue: str
    symbol: str
    side: str            # "buy" | "sell"
    qty: float
    signal_source: str
    signal_confidence: float
    ts_utc: str = field(default_factory=utc_now_iso)


@dataclass
class ShadowPosition:
    venue: str
    symbol: str
    side: str
    qty: float
    entry_price: float
    entry_fee: float
    entry_ts_utc: str
    signal_source: str
    signal_confidence: float
    fees_paid: float = 0.0
    last_mark: float = 0.0
    last_mark_ts_utc: str = ""
    last_mark_journal_ts: float = 0.0

    @property
    def direction_sign(self) -> int:
        return 1 if self.side == "buy" else -1

    def unrealized(self, mark_price: float) -> float:
        return (mark_price - self.entry_price) * self.qty * self.direction_sign


def normalize_quote(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate a venue quote payload against the contract. Raises ValueError.

    Returns {bid, ask, last, mid, ref candidates..., ts_epoch, provenance}.
    """
    if not isinstance(raw, dict):
        raise ValueError("quote function returned no payload")
    bid = _finite(raw.get("bid"))
    ask = _finite(raw.get("ask"))
    last = _finite(raw.get("last"))
    price = _finite(raw.get("price"))          # binance-style {price: ...}
    if last is None:
        last = price
    if bid is None and ask is None and last is None:
        raise ValueError(f"quote has no usable price fields: {sorted(raw.keys())}")
    mid = (bid + ask) / 2.0 if (bid is not None and ask is not None) else None
    ts_epoch = _parse_ts_epoch(raw.get("fetched_at"))
    if ts_epoch is None:
        ts_epoch = _parse_ts_epoch(raw.get("ts_utc"))
    if ts_epoch is None:
        raise ValueError("quote has no parseable timestamp — freshness unprovable")
    source = str(raw.get("source") or raw.get("provenance") or "unknown_feed")
    return {
        "bid": bid, "ask": ask, "last": last, "mid": mid,
        "ts_epoch": ts_epoch, "source": source,
        "provenance": f"{source}@{_iso_from_epoch(ts_epoch)}",
    }


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def check_quote_fresh(quote: Dict[str, Any], now: Optional[float] = None) -> Tuple[bool, str]:
    """(is_fresh, refusal_reason_if_not). Age > STALE_AFTER_SEC => stale."""
    now = time.time() if now is None else now
    age = now - quote["ts_epoch"]
    if age > STALE_AFTER_SEC:
        return False, "refused_feed_stale"
    return True, ""


def reference_price(quote: Dict[str, Any], side: str) -> float:
    """Taker reference: ask for buy, bid for sell; fallback last, then mid."""
    primary = quote["ask"] if side == "buy" else quote["bid"]
    for candidate in (primary, quote["last"], quote["mid"]):
        if candidate is not None and candidate > 0:
            return candidate
    raise ValueError("no positive reference price in quote")


def apply_fill(price: float, side: str, fee_rate: float, qty: float) -> Dict[str, float]:
    """Adverse slippage on price + taker fee on notional. Never fabricates."""
    slipped = price * (1 + SLIPPAGE) if side == "buy" else price * (1 - SLIPPAGE)
    notional = slipped * qty
    fee = notional * fee_rate
    return {"fill_price": slipped, "notional": notional, "fee": fee}


def env_has_keys(key_names: Tuple[str, ...], env_path: Path = ENV_PATH) -> Tuple[bool, Dict[str, bool]]:
    """CALL-TIME, fail-closed key presence check. Never reads values into
    logs: returns (all_present, {name: present_bool}) only."""
    present: Dict[str, bool] = {}
    file_vals: Dict[str, str] = {}
    try:
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            file_vals[name.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    for name in key_names:
        from_env = bool((os.environ.get(name) or "").strip())
        from_file = bool(file_vals.get(name, ""))
        present[name] = from_env or from_file
    return all(present.values()), present


def _atomic_write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class ShadowLedger:
    """Per (venue:symbol) closed-trade stats, exported after every close."""

    def __init__(self, path: Path = DEFAULT_LEDGER_PATH):
        self.path = Path(path)
        self._lock = threading.Lock()

    def record_close(self, close: Dict[str, Any]) -> Dict[str, Any]:
        key = f"{close['venue']}:{close['symbol']}"
        with self._lock:
            try:
                summary = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                summary = {"by_pair": {}, "totals": {}}
            by_pair = summary.setdefault("by_pair", {})
            entry = by_pair.setdefault(key, {
                "venue": close["venue"], "symbol": close["symbol"],
                "closed_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
                "total_gross_pnl": 0.0, "total_net_pnl": 0.0, "total_fees": 0.0,
                "last_close_ts_utc": "", "updated_ts_utc": "",
            })
            net = float(close.get("net_pnl", 0.0))
            gross = float(close.get("gross_pnl", 0.0))
            fees = float(close.get("fees", 0.0))
            entry["closed_trades"] += 1
            if net > 0:
                entry["wins"] += 1
            elif net < 0:
                entry["losses"] += 1
            entry["total_gross_pnl"] += gross
            entry["total_net_pnl"] += net
            entry["total_fees"] += fees
            decided = entry["wins"] + entry["losses"]
            entry["win_rate"] = round(entry["wins"] / decided, 4) if decided else 0.0
            entry["last_close_ts_utc"] = close.get("ts_utc", "")
            entry["updated_ts_utc"] = utc_now_iso()
            totals = summary.setdefault("totals", {})
            for k, v in (("closed_trades", 0), ("wins", 0), ("losses", 0),
                         ("win_rate", 0.0), ("total_gross_pnl", 0.0),
                         ("total_net_pnl", 0.0), ("total_fees", 0.0)):
                totals.setdefault(k, v)
            totals["closed_trades"] += 1
            if net > 0:
                totals["wins"] += 1
            elif net < 0:
                totals["losses"] += 1
            totals["total_gross_pnl"] += gross
            totals["total_net_pnl"] += net
            totals["total_fees"] += fees
            t_decided = totals["wins"] + totals["losses"]
            totals["win_rate"] = round(totals["wins"] / t_decided, 4) if t_decided else 0.0
            summary["ts_utc"] = utc_now_iso()
            _atomic_write_json(self.path, summary)
            return summary


class ShadowEngine:
    """Venue-scoped shadow book: proposals -> fills -> positions -> closes.

    quote_fn(symbol) -> quote-contract mapping, or None/raise on failure.
    """

    def __init__(self, venue: str,
                 journal_path: Path = DEFAULT_JOURNAL_PATH,
                 ledger_path: Path = DEFAULT_LEDGER_PATH):
        self.venue = venue.lower().strip()
        self.journal_path = Path(journal_path)
        self.ledger = ShadowLedger(ledger_path)
        self.fee_rate = VENUE_FEES.get(self.venue, DEFAULT_FEE)
        self.positions: Dict[str, ShadowPosition] = {}
        self._lock = threading.Lock()

    # ── journal ──────────────────────────────────────────────────────────
    def _journal(self, entry: Dict[str, Any]) -> None:
        entry.setdefault("ts_utc", utc_now_iso())
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True, default=str) + "\n")
        logger.debug("shadow journal: %s", {k: entry.get(k) for k in
                                            ("event", "venue", "symbol", "reason")})

    def _refuse(self, order: ShadowOrder, reason: str, detail: str = "") -> Dict[str, Any]:
        entry = {
            "event": "refused", "venue": self.venue, "symbol": order.symbol,
            "side": order.side, "qty": order.qty, "price": None, "fee": None,
            "signal_source": order.signal_source,
            "signal_confidence": order.signal_confidence,
            "reason": reason,
        }
        if detail:
            entry["detail"] = detail[:300]
        self._journal(entry)
        return {"status": "refused", "reason": reason, "detail": detail,
                "journal": str(self.journal_path)}

    # ── quote acquisition (absolute freshness doctrine) ──────────────────
    def _fresh_quote(self, symbol: str, quote_fn: QuoteFn) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Returns (quote, refusal_reason). quote is None on any failure."""
        try:
            raw = quote_fn(symbol)
            quote = normalize_quote(raw)
        except Exception as exc:
            return None, "refused_feed_unavailable",  # type: ignore[return-value]
        fresh, reason = check_quote_fresh(quote)
        if not fresh:
            return None, reason
        return quote, None

    # ── order path ───────────────────────────────────────────────────────
    def propose(self, order: ShadowOrder, quote_fn: QuoteFn) -> Dict[str, Any]:
        order.venue = self.venue
        order.side = str(order.side).strip().lower()
        if order.side not in {"buy", "sell"}:
            return self._refuse(order, "refused_invalid_order", f"side={order.side!r}")
        qty = _finite(order.qty)
        if qty is None or qty <= 0:
            return self._refuse(order, "refused_invalid_order", f"qty={order.qty!r}")
        order.qty = qty
        if not str(order.symbol).strip():
            return self._refuse(order, "refused_invalid_order", "empty symbol")

        quote, refusal = self._fresh_quote(order.symbol, quote_fn)
        if quote is None:
            return self._refuse(order, refusal or "refused_feed_unavailable")

        with self._lock:
            open_pos = self.positions.get(order.symbol)
            if open_pos and open_pos.side != order.side:
                close = self._close_locked(open_pos, quote, reason="reversal")
                if close.get("status") != "closed":
                    return close
            return self._fill_locked(order, quote)

    def _fill_locked(self, order: ShadowOrder, quote: Dict[str, Any]) -> Dict[str, Any]:
        ref = reference_price(quote, order.side)
        fill = apply_fill(ref, order.side, self.fee_rate, order.qty)
        existing = self.positions.get(order.symbol)
        if existing and existing.side == order.side:
            total_qty = existing.qty + order.qty
            existing.entry_price = (
                existing.entry_price * existing.qty + fill["fill_price"] * order.qty
            ) / total_qty
            existing.qty = total_qty
            existing.fees_paid += fill["fee"]
            existing.signal_source = order.signal_source
            existing.signal_confidence = order.signal_confidence
            event = "filled"
            position = existing
        else:
            position = ShadowPosition(
                venue=self.venue, symbol=order.symbol, side=order.side,
                qty=order.qty, entry_price=fill["fill_price"], entry_fee=fill["fee"],
                entry_ts_utc=order.ts_utc,
                signal_source=order.signal_source,
                signal_confidence=order.signal_confidence,
                fees_paid=fill["fee"],
            )
            self.positions[order.symbol] = position
            event = "opened"
        position.last_mark = fill["fill_price"]
        position.last_mark_ts_utc = utc_now_iso()
        entry = {
            "event": event, "venue": self.venue, "symbol": order.symbol,
            "side": order.side, "qty": order.qty, "price": fill["fill_price"],
            "fee": round(fill["fee"], 10), "signal_source": order.signal_source,
            "signal_confidence": order.signal_confidence,
            "provenance": quote["provenance"],
            "position_qty": position.qty,
            "position_entry_price": position.entry_price,
        }
        self._journal(entry)
        return {"status": event, "fill_price": fill["fill_price"],
                "fee": fill["fee"], "position": position,
                "provenance": quote["provenance"], "journal": str(self.journal_path)}

    # ── close path ───────────────────────────────────────────────────────
    def _close_locked(self, pos: ShadowPosition, quote: Dict[str, Any],
                      reason: str) -> Dict[str, Any]:
        exit_side = "sell" if pos.side == "buy" else "buy"
        ref = reference_price(quote, exit_side)
        fill = apply_fill(ref, exit_side, self.fee_rate, pos.qty)
        gross = (fill["fill_price"] - pos.entry_price) * pos.qty * pos.direction_sign
        fees = pos.fees_paid + fill["fee"]
        net = gross - fees                  # gross minus entry+exit taker fees
        entry_epoch = _parse_ts_epoch(pos.entry_ts_utc) or time.time()
        hold = max(0.0, time.time() - entry_epoch)
        pnl_pct = (net / (pos.entry_price * pos.qty)) if pos.entry_price * pos.qty else 0.0
        entry = {
            "event": "closed", "venue": self.venue, "symbol": pos.symbol,
            "side": exit_side, "qty": pos.qty, "price": fill["fill_price"],
            "fee": round(fill["fee"], 10),
            "signal_source": pos.signal_source,
            "signal_confidence": pos.signal_confidence,
            "provenance": quote["provenance"],
            "entry_price": pos.entry_price, "exit_reason": reason,
            "gross_pnl": round(gross, 10), "fees": round(fees, 10),
            "net_pnl": round(net, 10), "pnl_pct": round(pnl_pct, 8),
            "hold_seconds": round(hold, 3),
        }
        self._journal(entry)
        self.ledger.record_close(entry)
        del self.positions[pos.symbol]
        result = dict(entry)
        result.update({"status": "closed", "journal": str(self.journal_path)})
        return result

    def close_position(self, symbol: str, reason: str, quote_fn: QuoteFn) -> Dict[str, Any]:
        symbol = str(symbol).strip()
        with self._lock:
            pos = self.positions.get(symbol)
            if pos is None:
                return {"status": "no_position", "venue": self.venue, "symbol": symbol}
            quote, refusal = self._fresh_quote(symbol, quote_fn)
            if quote is None:
                order = ShadowOrder(self.venue, symbol, "sell", pos.qty,
                                    pos.signal_source, pos.signal_confidence)
                return self._refuse(order, refusal or "refused_feed_unavailable")
            return self._close_locked(pos, quote, reason)

    # ── mark-to-market + protective levels ───────────────────────────────
    def _check_protective(self, pos: ShadowPosition, mark_price: float) -> Optional[str]:
        if pos.side == "buy":
            if mark_price <= pos.entry_price * (1 + STOP_PCT):
                return "stop_loss"
            if mark_price >= pos.entry_price * (1 + TAKE_PROFIT_PCT):
                return "take_profit"
        else:
            if mark_price >= pos.entry_price * (1 - STOP_PCT):
                return "stop_loss"
            if mark_price <= pos.entry_price * (1 - TAKE_PROFIT_PCT):
                return "take_profit"
        return None

    def mark_all(self, quote_fn: QuoteFn, journal_marks: bool = True,
                 throttle_sec: float = MARK_JOURNAL_THROTTLE_SEC) -> Dict[str, Any]:
        """MTM every open position; close any that hit stop (-2%) or TP (+3%)."""
        results = {"marked": [], "closed": [], "refused": []}
        with self._lock:
            symbols = list(self.positions.keys())
        for symbol in symbols:
            with self._lock:
                pos = self.positions.get(symbol)
            if pos is None:
                continue
            quote, refusal = self._fresh_quote(symbol, quote_fn)
            if quote is None:
                results["refused"].append({"symbol": symbol, "reason": refusal})
                continue
            mark = quote["last"] or quote["mid"] or reference_price(quote, pos.side)
            with self._lock:
                pos = self.positions.get(symbol)
                if pos is None:
                    continue
                pos.last_mark = mark
                pos.last_mark_ts_utc = utc_now_iso()
                hit = self._check_protective(pos, mark)
                if hit:
                    results["closed"].append(self._close_locked(pos, quote, hit))
                    continue
            unreal = pos.unrealized(mark)
            results["marked"].append({
                "venue": self.venue, "symbol": symbol, "mark": mark,
                "unrealized_pnl": round(unreal, 10),
                "provenance": quote["provenance"],
            })
            now = time.time()
            if journal_marks and (now - pos.last_mark_journal_ts) >= throttle_sec:
                pos.last_mark_journal_ts = now
                self._journal({
                    "event": "mark", "venue": self.venue, "symbol": symbol,
                    "side": pos.side, "qty": pos.qty, "price": mark,
                    "fee": None, "signal_source": pos.signal_source,
                    "signal_confidence": pos.signal_confidence,
                    "provenance": quote["provenance"],
                    "unrealized_pnl": round(unreal, 10),
                    "entry_price": pos.entry_price,
                })
        return results

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "venue": self.venue,
                "open_positions": {
                    sym: {
                        "side": p.side, "qty": p.qty, "entry_price": p.entry_price,
                        "last_mark": p.last_mark,
                        "unrealized_pnl": round(p.unrealized(p.last_mark), 10)
                        if p.last_mark else None,
                        "signal_source": p.signal_source,
                    } for sym, p in self.positions.items()
                },
            }


# ═══════════════════════════════════════════════════════════════════════════
# SELF-TEST — stub quote function only; no network, real files untouched.
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    tmpdir = Path(tempfile.mkdtemp(prefix="shadow_selftest_"))
    journal = tmpdir / "shadow_trades.jsonl"
    ledger_path = tmpdir / "shadow_ledger_summary.json"

    _price = 100.0

    def stub_quote(symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol, "bid": _price - 0.1, "ask": _price + 0.1,
            "last": _price, "source": "stub_feed",
            "fetched_at": time.time(),
        }

    engine = ShadowEngine("kraken", journal_path=journal, ledger_path=ledger_path)

    order = ShadowOrder("kraken", "TESTUSD", "buy", 2.0, "selftest", 0.9)
    res = engine.propose(order, stub_quote)
    assert res["status"] == "opened", res
    fill = res["fill_price"]
    assert abs(fill - 100.1 * 1.0005) < 1e-9, fill          # ask + slippage
    assert abs(res["fee"] - fill * 2.0 * 0.0026) < 1e-9, res["fee"]
    print(f"OK opened: fill={fill} fee={res['fee']:.6f} provenance={res['provenance']}")

    # stale feed must refuse
    def stale_quote(symbol: str) -> Dict[str, Any]:
        q = stub_quote(symbol)
        q["fetched_at"] = time.time() - 60
        return q

    res2 = engine.propose(ShadowOrder("kraken", "TESTUSD", "buy", 1.0, "selftest", 0.9), stale_quote)
    assert res2["status"] == "refused" and res2["reason"] == "refused_feed_stale", res2
    print("OK stale quote refused:", res2["reason"])

    def dead_quote(symbol: str) -> None:
        return None

    res3 = engine.propose(ShadowOrder("kraken", "TESTUSD", "buy", 1.0, "selftest", 0.9), dead_quote)
    assert res3["reason"] == "refused_feed_unavailable", res3
    print("OK dead feed refused:", res3["reason"])

    # move price +3.1% -> mark should trigger take_profit on mark_all
    _price = 103.2
    marks = engine.mark_all(stub_quote, journal_marks=True, throttle_sec=0)
    assert marks["closed"] and marks["closed"][0]["exit_reason"] == "take_profit", marks
    closed = marks["closed"][0]
    print(f"OK TP close: exit={closed['price']} gross={closed['gross_pnl']:.4f} "
          f"net={closed['net_pnl']:.4f} pnl_pct={closed['pnl_pct']:.5f}")

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    pair = ledger["by_pair"]["kraken:TESTUSD"]
    assert pair["closed_trades"] == 1 and pair["wins"] == 1 and pair["win_rate"] == 1.0, pair
    print("OK ledger:", json.dumps(pair, sort_keys=True))

    lines = [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines()]
    events = [l["event"] for l in lines]
    print("OK journal events:", events)
    assert events == ["opened", "refused", "refused", "closed", "mark"] or \
           events == ["opened", "refused", "refused", "closed"], events
    print(f"SELF-TEST PASSED — journal at {journal}")
