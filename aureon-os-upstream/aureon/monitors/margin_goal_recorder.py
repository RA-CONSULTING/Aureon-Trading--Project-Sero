#!/usr/bin/env python3
"""
MARGIN GOAL RECORDER
====================
Records every entry-selection scan (all candidates + goal scores) and
the final trade outcome.  Proves that higher goal_score → faster profit.

Two record types stored in margin_goal_proof.jsonl:
  {"type": "scan", ...}     — written by find_best_target() every scan
  {"type": "outcome", ...}  — written by close_position() when trade ends

The check_goal_proof.py script reads the file and correlates them.
"""

import json
import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

_PROOF_FILENAME = "margin_goal_proof.jsonl"

_lock = threading.Lock()


def _workspace_root() -> Path:
    """Resolve the workspace root: SERO_WORKSPACE env, else derived from this file."""
    env = os.environ.get("SERO_WORKSPACE")
    if env:
        return Path(env)
    # .../workspace/aureon-os-upstream/aureon/monitors/margin_goal_recorder.py
    return Path(__file__).resolve().parents[3]


# Anchored default proof location (never bare CWD).  Tests and operators may
# patch this module attribute; the MARGIN_GOAL_PROOF_DIR env override takes
# precedence over it at write time.
PROOF_FILE = str(_workspace_root() / _PROOF_FILENAME)


def _proof_path() -> Path:
    """Anchored proof file location (MARGIN_GOAL_PROOF_DIR override, never bare CWD)."""
    override = os.environ.get("MARGIN_GOAL_PROOF_DIR")
    if override:
        return Path(override) / _PROOF_FILENAME
    return Path(PROOF_FILE)


def _round_or_none(value, digits):
    """round() that tolerates None/non-numeric fields (missing data → None)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(value, digits)
    return None


def _append(record: dict):
    """Append one JSON line to the proof file (thread-safe)."""
    record["_written"] = datetime.now().isoformat()
    path = _proof_path()
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")


class MarginGoalRecorder:
    """
    Drop-in recorder for KrakenMarginArmyTrader.

    Usage inside the trader:
        self._goal_recorder = MarginGoalRecorder()

    In find_best_target():
        scan_id = self._goal_recorder.record_scan(candidates_raw, winner_pair, winner_side)
        self._pending_scan_id = scan_id

    After open_position() returns trade:
        self._goal_recorder.link_order(self._pending_scan_id, trade.order_id)

    In close_position() after completed dict is built:
        self._goal_recorder.record_outcome(trade.order_id, completed)
    """

    def __init__(self):
        # order_id → scan_id  (set after open)
        self._order_to_scan: dict = {}
        # scan_id → scan record (kept in memory for fast linking)
        self._pending: dict = {}

    # ------------------------------------------------------------------ #
    #  SCAN — called from find_best_target() after sorting candidates      #
    # ------------------------------------------------------------------ #
    _CANDIDATE_FIELDS = 11  # info, side, vol, trade_val, max_lev, total_score,
                            # req_pct, fees, goal_score, eta_min, route_to_profit

    @staticmethod
    def _unpack_candidate(item):
        """Defensively unpack a candidate tuple of ANY length; missing → None.

        Returns a list of exactly _CANDIDATE_FIELDS values, or None if the
        item is not unpackable at all (never raises on shape).
        """
        try:
            seq = list(item)
        except TypeError:
            return None
        seq = seq[:MarginGoalRecorder._CANDIDATE_FIELDS]
        seq += [None] * (MarginGoalRecorder._CANDIDATE_FIELDS - len(seq))
        return seq

    def record_scan(self, candidates_raw: list, winner_pair: str, winner_side: str) -> str:
        """
        Record all scored candidates and which one was selected.
        Returns a unique scan_id to link with the eventual trade outcome.

        candidates_raw is the sorted list of tuples:
          (info, side, vol, trade_val, max_lev, total_score,
           required_move_pct, round_trip_fee, goal_score, eta_minutes,
           optional route_to_profit)

        Tuples of ANY length are tolerated — short tuples pad with None and
        a malformed entry is skipped.  This function never raises on shape.
        """
        scan_id = f"scan_{int(time.time() * 1000)}"
        ts = datetime.now().isoformat()

        rows = []
        for rank, item in enumerate(candidates_raw[:10]):  # top 10 only
            fields = self._unpack_candidate(item)
            if fields is None:
                continue
            (info, side, vol, trade_val, max_lev, total_score,
             req_pct, fees, goal_score, eta_min, route_to_profit) = fields
            pair      = getattr(info, "pair", None) if info is not None else None
            momentum  = getattr(info, "momentum", None) if info is not None else None
            spread    = getattr(info, "spread_pct", None) if info is not None else None
            volume    = getattr(info, "volume_24h", None) if info is not None else None
            if isinstance(eta_min, (int, float)) and eta_min < 9999:
                eta = round(eta_min, 1)
            else:
                eta = None
            rows.append({
                "rank":            rank + 1,
                "pair":            pair,
                "side":            side,
                "leverage":        max_lev,
                "momentum_pct":    _round_or_none(momentum, 4),
                "spread_pct":      _round_or_none(spread, 4),
                "volume_24h":      _round_or_none(volume, 0),
                "notional_usd":    _round_or_none(trade_val, 2),
                "required_move_pct": _round_or_none(req_pct, 4),
                "round_trip_fees": _round_or_none(fees, 4),
                "goal_score":      _round_or_none(goal_score, 4),
                "eta_minutes":     eta,
                "route_to_profit":  _round_or_none(route_to_profit, 4),
                "total_score":     _round_or_none(total_score, 4),
                "selected":        (pair is not None and pair == winner_pair and side == winner_side),
            })

        record = {
            "type":        "scan",
            "scan_id":     scan_id,
            "timestamp":   ts,
            "winner_pair": winner_pair,
            "winner_side": winner_side,
            "n_candidates": len(candidates_raw),
            "candidates":  rows,
        }
        self._pending[scan_id] = record
        _append(record)
        return scan_id

    # ------------------------------------------------------------------ #
    #  LINK — called after open_position() returns the order_id           #
    # ------------------------------------------------------------------ #
    def link_order(self, scan_id: str, order_id: str):
        """Associate the open order_id with the scan that chose it."""
        if not scan_id or not order_id:
            return
        self._order_to_scan[order_id] = scan_id
        link = {
            "type":     "link",
            "scan_id":  scan_id,
            "order_id": order_id,
            "timestamp": datetime.now().isoformat(),
        }
        _append(link)

    # ------------------------------------------------------------------ #
    #  OUTCOME — called from close_position() with completed trade dict   #
    # ------------------------------------------------------------------ #
    def record_outcome(self, order_id: str, completed: dict):
        """
        Record actual trade result and marry it to the original scan.
        completed is the dict built inside close_position().
        """
        scan_id = self._order_to_scan.get(order_id, "unknown")

        # Pull the winner's goal_score from the pending scan (if still in memory)
        goal_score_selected  = None
        eta_predicted_min    = None
        n_candidates         = None
        scan_candidates      = None

        if scan_id in self._pending:
            sc = self._pending[scan_id]
            n_candidates = sc.get("n_candidates")
            for row in sc.get("candidates", []):
                if row.get("selected"):
                    goal_score_selected = row["goal_score"]
                    eta_predicted_min   = row["eta_minutes"]
                    break
            scan_candidates = sc.get("candidates")

        hold_sec  = completed.get("hold_seconds", 0)
        net_pnl   = completed.get("net_pnl", 0)
        hold_min  = round(hold_sec / 60, 2)

        # Did we beat the goal?
        goal_hit = (
            net_pnl >= completed.get("entry_fee", 0) + 0.01  # net profit > 0
            and eta_predicted_min is not None
            and hold_min <= eta_predicted_min * 2  # within 2× predicted ETA
        )

        record = {
            "type":               "outcome",
            "scan_id":            scan_id,
            "order_id":           order_id,
            "close_order_id":     completed.get("close_order_id"),
            "pair":               completed.get("pair"),
            "side":               completed.get("side"),
            "leverage":           completed.get("leverage"),
            "entry_price":        completed.get("entry_price"),
            "exit_price":         completed.get("exit_price"),
            "net_pnl":            round(net_pnl, 4),
            "gross_pnl":          round(completed.get("gross_pnl", 0), 4),
            "total_fees":         round(completed.get("total_fees", 0), 4),
            "hold_seconds":       round(hold_sec, 1),
            "hold_minutes":       hold_min,
            "close_reason":       completed.get("reason"),
            "goal_score_selected": goal_score_selected,
            "eta_predicted_min":  eta_predicted_min,
            "n_candidates":       n_candidates,
            "goal_hit":           goal_hit,
            "timestamp":          datetime.now().isoformat(),
            # Full candidate snapshot for deep analysis
            "scan_candidates":    scan_candidates,
        }
        _append(record)

        # Clean up memory
        self._pending.pop(scan_id, None)
        self._order_to_scan.pop(order_id, None)
