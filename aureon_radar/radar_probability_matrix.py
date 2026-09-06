"""
🎯 AUREON RADAR — Probability Intelligence Adapter
====================================================
Wires Probability Intelligence Matrix into the Honey Ladder radar.

Every signal gets probability-validated BEFORE spending a demo trade.
Multi-factor analysis: momentum, volatility, proximity, sample quality.

STOPS bad trades before they cost money.
"""
import json
import math
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════
# FACTORS
# ═══════════════════════════════════════════════════════════════

@dataclass
class IntelligenceFactor:
    name: str
    weight: float  # 0-1
    value: float   # 0-1, where 1 is good
    reason: str

    @property
    def contribution(self) -> float:
        return self.weight * self.value


@dataclass
class ProbabilityIntelligence:
    raw_probability: float = 0.0
    adjusted_probability: float = 0.0
    confidence: float = 0.0
    factors: List[IntelligenceFactor] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    action: str = "PROCEED"  # PROCEED (no flags), WATCH, CAUTION, DANGER

    def add_factor(self, name: str, weight: float, value: float, reason: str):
        self.factors.append(IntelligenceFactor(name, weight, value, reason))

    def add_risk(self, flag: str):
        if flag not in self.risk_flags:
            self.risk_flags.append(flag)

    def calculate_adjusted(self):
        if not self.factors:
            self.adjusted_probability = self.raw_probability
            return
        total_weight = sum(f.weight for f in self.factors)
        if total_weight == 0:
            self.adjusted_probability = self.raw_probability
            return
        adjustment = sum((f.weight / total_weight) * f.value for f in self.factors)
        if adjustment >= 0.5:
            boost = (adjustment - 0.5) * 2
            self.adjusted_probability = self.raw_probability + (1 - self.raw_probability) * boost * 0.3
        else:
            penalty = (0.5 - adjustment) * 2
            self.adjusted_probability = self.raw_probability * (1 - penalty * 0.7)
        self.adjusted_probability = max(0, min(1, self.adjusted_probability))
        # Risk flags
        if len(self.risk_flags) >= 3:
            self.action = "DANGER"
        elif len(self.risk_flags) >= 2:
            self.action = "CAUTION"
        elif len(self.risk_flags) >= 1:
            self.action = "WATCH"
        else:
            # "PROCEED", not "HOLD": in trading semantics HOLD means "do not
            # trade" — the old name was an inversion trap for any consumer
            # that gates on the action string.
            self.action = "PROCEED"


# ═══════════════════════════════════════════════════════════════
# PROBABILITY MATRIX
# ═══════════════════════════════════════════════════════════════

class RadarProbabilityMatrix:
    """
    Probability Intelligence Matrix adapted for the Radar's signal pipeline.

    Analyzes each signal before it hits the honey ladder:
    - Signal confidence → raw probability
    - Price momentum → momentum factor
    - Price volatility → volatility factor
    - Shadow hit history → pattern factor
    - Time of day/phase → temporal factor

    Outputs: adjusted probability, risk flags, action recommendation.
    """

    def __init__(self, state_file: Optional[str] = None):
        self.state_file = state_file or Path(__file__).parent / "probability_matrix_state.json"
        self.factor_weights = {
            'signal_confidence': 0.30,
            'momentum': 0.20,
            'volatility': 0.15,
            'shadow_history': 0.15,
            'temporal_phase': 0.10,
            'source_reliability': 0.10,
        }
        self.source_accuracy: Dict[str, Dict] = {}  # source -> {hits, misses, accuracy}
        self._load_state()

    def _journal(self, event: str, detail: str):
        """Append a fail-closed journal line (corrupt-state resets, bad data)."""
        try:
            journal = Path(self.state_file).with_suffix('.journal.jsonl')
            with open(journal, 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'ts': time.time(),
                    'event': event,
                    'detail': detail,
                }) + '\n')
        except Exception:
            pass

    @staticmethod
    def _valid_accuracy_entry(stats: Any) -> bool:
        return (
            isinstance(stats, dict)
            and isinstance(stats.get('hits'), (int, float))
            and isinstance(stats.get('misses'), (int, float))
            and not isinstance(stats.get('hits'), bool)
            and not isinstance(stats.get('misses'), bool)
            and stats['hits'] >= 0 and stats['misses'] >= 0
            and math.isfinite(stats['hits']) and math.isfinite(stats['misses'])
        )

    def _load_state(self):
        """Fail-closed: corrupt or invalid state is RESET to defaults and
        journaled — never silently half-loaded, never fabricated."""
        path = Path(self.state_file)
        if not path.exists():
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.source_accuracy = {}
            self._journal('state_reset_corrupt', f'json load failed: {e}')
            return
        if not isinstance(data, dict):
            self.source_accuracy = {}
            self._journal('state_reset_corrupt', 'top-level is not a dict')
            return

        saved_acc = data.get('source_accuracy', {})
        if isinstance(saved_acc, dict):
            dropped = []
            for source, stats in saved_acc.items():
                if isinstance(source, str) and self._valid_accuracy_entry(stats):
                    self.source_accuracy[source] = {
                        'hits': int(stats['hits']), 'misses': int(stats['misses'])}
                else:
                    dropped.append(str(source))
            if dropped:
                self._journal('state_entry_dropped',
                              f'invalid source_accuracy entries: {dropped}')

        saved_w = data.get('factor_weights', {})
        if isinstance(saved_w, dict):
            bad = []
            for k, v in saved_w.items():
                if k in self.factor_weights:
                    if isinstance(v, (int, float)) and not isinstance(v, bool) \
                            and math.isfinite(v) and 0.0 <= v <= 1.0:
                        self.factor_weights[k] = float(v)
                    else:
                        bad.append(k)
            if bad:
                self._journal('state_entry_dropped',
                              f'invalid factor_weights kept at default: {bad}')

    def _save_state(self):
        """Atomic: write tmp + os.replace so a crash mid-write can never
        leave a truncated state file behind."""
        try:
            data = {
                'source_accuracy': self.source_accuracy,
                'factor_weights': self.factor_weights,
                'last_updated': time.time()
            }
            path = Path(self.state_file)
            tmp = path.with_suffix('.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            self._journal('save_failed', str(e))

    def evaluate_signal(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        source: str,
        price_history: Optional[List[float]] = None,
        sector: str = "commodity",
    ) -> ProbabilityIntelligence:
        """
        Evaluate a trading signal through the probability matrix.

        Returns enriched probability intelligence.
        """
        intel = ProbabilityIntelligence()
        # Sanitize confidence: non-finite or out-of-range input must never
        # reach the factor math (NaN poisons the weighted adjustment below —
        # max/min comparisons don't catch it — and can surface downstream as
        # a bogus approval). Fail-closed: unparseable/NaN → 0.0.
        try:
            conf = float(confidence)
        except (TypeError, ValueError):
            conf = 0.0
        if not math.isfinite(conf):
            conf = 0.0
        intel.raw_probability = max(0.0, min(1.0, conf))

        # ==== 1. SIGNAL CONFIDENCE FACTOR ====
        intel.add_factor(
            name="signal_confidence",
            weight=self.factor_weights['signal_confidence'],
            value=intel.raw_probability,
            reason=f"Signal confidence {intel.raw_probability:.0%}"
        )
        if intel.raw_probability < 0.5:
            intel.add_risk("LOW_CONFIDENCE")

        # ==== 2. MOMENTUM FACTOR ====
        momentum_value = 0.5
        last_price = price_history[-1] if price_history else 0.0
        if price_history and len(price_history) >= 3 and isinstance(last_price, (int, float)) \
                and math.isfinite(last_price) and last_price > 0:
            # Calculate recent momentum
            recent = price_history[-3:]
            deltas = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
            if len(deltas) >= 2:
                avg_delta = sum(deltas) / len(deltas)
                if direction.upper() in ["LONG", "BUY"]:
                    momentum_value = 0.5 + min(0.5, max(-0.5, avg_delta / last_price * 100))
                else:
                    momentum_value = 0.5 + min(0.5, max(-0.5, -avg_delta / last_price * 100))

        intel.add_factor(
            name="momentum",
            weight=self.factor_weights['momentum'],
            value=momentum_value,
            reason=f"Momentum score {momentum_value:.2f}"
        )
        if momentum_value < 0.3:
            intel.add_risk("NEGATIVE_MOMENTUM")

        # ==== 3. VOLATILITY FACTOR ====
        vol_value = 0.5
        cv: Optional[float] = None  # None = not enough samples (never raises)
        if price_history and len(price_history) >= 5:
            mean = sum(price_history) / len(price_history)
            variance = sum((p - mean) ** 2 for p in price_history) / len(price_history)
            std = variance ** 0.5
            cv = std / mean if mean > 0 else 0.0
            # Low CV = good (stable), High CV = bad (volatile)
            if cv > 0.05:
                vol_value = 0.2
                intel.add_risk("HIGH_VOLATILITY")
            elif cv > 0.03:
                vol_value = 0.4
            elif cv > 0.01:
                vol_value = 0.6
            else:
                vol_value = 0.8

        intel.add_factor(
            name="volatility",
            weight=self.factor_weights['volatility'],
            value=vol_value,
            reason=f"Volatility CV={cv:.4f}" if cv is not None else "Unknown volatility (few samples)"
        )

        # ==== 4. SHADOW HISTORY FACTOR ====
        source_acc = self._get_source_accuracy(source)
        intel.add_factor(
            name="shadow_history",
            weight=self.factor_weights['shadow_history'],
            value=source_acc,
            reason=f"Source '{source}' accuracy {source_acc:.0%}"
        )
        if source_acc < 0.3:
            intel.add_risk("UNRELIABLE_SOURCE")

        # ==== 5. TEMPORAL PHASE FACTOR ====
        temporal_value = self._evaluate_temporal_phase()
        intel.add_factor(
            name="temporal_phase",
            weight=self.factor_weights['temporal_phase'],
            value=temporal_value,
            reason=f"Temporal phase score {temporal_value:.2f}"
        )

        # ==== 6. SOURCE RELIABILITY FACTOR ====
        source_reliability = self._get_source_reliability(source)
        intel.add_factor(
            name="source_reliability",
            weight=self.factor_weights['source_reliability'],
            value=source_reliability,
            reason=f"Source reliability {source_reliability:.0%}"
        )

        # ==== CALCULATE ====
        intel.calculate_adjusted()
        # Apply risk penalties
        risk_penalty = len(intel.risk_flags) * 0.1
        intel.adjusted_probability *= (1 - risk_penalty)
        intel.adjusted_probability = max(0, min(1, intel.adjusted_probability))
        intel.confidence = intel.adjusted_probability

        return intel

    def _get_source_accuracy(self, source: str) -> float:
        """Smoothed source accuracy in (0, 1) — Laplace (hits+1)/(total+2).

        Smoothing keeps a single early hit from reading as a calibrated 100%
        and a single early miss from reading as 0%; the prior centre is the
        same 0.5 the unsmoothed path used for unknown sources.
        """
        stats = self.source_accuracy.get(source)
        if self._valid_accuracy_entry(stats):
            hits = stats['hits']
            total = hits + stats['misses']
            if total > 0:
                return (hits + 1.0) / (total + 2.0)
        return 0.5  # Unknown source

    def _get_source_reliability(self, source: str) -> float:
        """Hardcoded reliability tiers based on observed performance."""
        tiers = {
            'aureon_os_bridge': 0.85,
            'aureon_wolf': 0.75,
            'aureon_lion': 0.75,
            'scanner': 0.60,
            'crypto_correlation': 0.55,
            'stock_momentum': 0.55,
            'planetary': 0.50,
            'ollama': 0.45,
        }
        return tiers.get(source, 0.50)

    def _evaluate_temporal_phase(self) -> float:
        """Evaluate current temporal phase for trading quality.

        UTC throughout — the windows below are documented in UTC (London
        8-11, NY 13-16); using local server time shifts every window by the
        host's UTC offset.
        """
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        hour = now.hour
        weekday = now.weekday()

        # Avoid weekends for most instruments
        if weekday >= 5:
            return 0.3

        # Best trading hours: London open (8-11 UTC), NY open (13-16 UTC)
        if 8 <= hour <= 11 or 13 <= hour <= 16:
            return 0.9
        elif 6 <= hour <= 18:
            return 0.7
        elif 19 <= hour <= 22:
            return 0.5
        else:
            return 0.3  # Night/low liquidity

    def record_outcome(self, source: str, success: bool):
        """Record shadow/demo outcome to learn source accuracy.

        Only real outcomes belong here (caller verifies the terminal state);
        the bool coercion merely guards the counter arithmetic.
        """
        if not isinstance(source, str) or not source:
            return
        if source not in self.source_accuracy or \
                not self._valid_accuracy_entry(self.source_accuracy[source]):
            self.source_accuracy[source] = {'hits': 0, 'misses': 0}
        if bool(success):
            self.source_accuracy[source]['hits'] += 1
        else:
            self.source_accuracy[source]['misses'] += 1
        self._save_state()

    def should_trade(self, intel: ProbabilityIntelligence, min_threshold: float = 0.55) -> bool:
        """Gate: should this signal proceed to demo/live execution?"""
        if intel.action == "DANGER":
            return False
        if intel.action == "CAUTION" and intel.adjusted_probability < 0.65:
            return False
        return intel.adjusted_probability >= min_threshold

    def explain(self, intel: ProbabilityIntelligence, symbol: str = "") -> str:
        lines = [
            f"╔══════════════════════════════════════════════════════════════╗",
            f"║  🧠 PROBABILITY MATRIX — {symbol:12s}                 ║",
            f"╠══════════════════════════════════════════════════════════════╣",
            f"║  Raw:      {intel.raw_probability:.1%}",
            f"║  Adjusted: {intel.adjusted_probability:.1%}  {'✅ PASS' if intel.adjusted_probability >= 0.55 else '❌ BLOCK'}",
            f"║  Action:   {intel.action}",
            f"║  ────────────────────────────────────────────────────────",
        ]
        for f in intel.factors:
            bar = "█" * int(f.value * 10) + "░" * (10 - int(f.value * 10))
            lines.append(f"║  {f.name:18s} [{bar}] {f.value:.0%}")
        if intel.risk_flags:
            lines.append(f"║  ⚠️  RISK: {', '.join(intel.risk_flags)}")
        lines.append(f"╚══════════════════════════════════════════════════════════════╝")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════

_MATRIX: Optional[RadarProbabilityMatrix] = None

def get_matrix() -> RadarProbabilityMatrix:
    global _MATRIX
    if _MATRIX is None:
        _MATRIX = RadarProbabilityMatrix()
    return _MATRIX


def evaluate_signal(symbol, direction, confidence, source, price_history=None, sector="commodity"):
    return get_matrix().evaluate_signal(symbol, direction, confidence, source, price_history, sector)


def should_trade(intel, min_threshold=0.55):
    return get_matrix().should_trade(intel, min_threshold)


if __name__ == "__main__":
    # SELF-TEST — synthetic fixtures, clearly labeled; no live data touched.
    # Verifies: short-history volatility path (regression: NameError on cv),
    # NaN confidence fail-closed, outcome learning + smoothing, state
    # round-trip through a temp file, action ladder naming.
    import tempfile

    failures = []

    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}  {name}")
        if not cond:
            failures.append(name)

    tmp = Path(tempfile.mkdtemp()) / "pm_state.json"
    m = RadarProbabilityMatrix(state_file=str(tmp))

    # 1. Volatility reason with 1-4 price samples must not raise (cv fix)
    intel = m.evaluate_signal("X", "LONG", 0.7, "scanner", price_history=[100.0])
    check("short history: no NameError, vol reason set",
          any(f.name == "volatility" and "CV" not in f.reason for f in intel.factors))

    # 2. NaN confidence → fail-closed 0.0, LOW_CONFIDENCE risk, blocked
    nan_intel = m.evaluate_signal("X", "LONG", float("nan"), "scanner",
                                  price_history=[100.0, 100.1, 100.2, 100.3, 100.4])
    check("NaN confidence sanitized to 0.0", nan_intel.raw_probability == 0.0)
    check("NaN confidence flagged + blocked",
          "LOW_CONFIDENCE" in nan_intel.risk_flags and not m.should_trade(nan_intel))

    # 3. Outcome learning: 3 hits, 1 miss → smoothed 4/6 = 0.667 (not 1.0)
    for _ in range(3):
        m.record_outcome("src_a", True)
    m.record_outcome("src_a", False)
    acc = m._get_source_accuracy("src_a")
    check("smoothed accuracy 3h1m ≈ 0.667", abs(acc - 4.0 / 6.0) < 1e-9)
    check("unknown source = 0.5 prior", m._get_source_accuracy("nope") == 0.5)

    # 4. State round-trip: reload from disk preserves learned counts
    m2 = RadarProbabilityMatrix(state_file=str(tmp))
    check("state reload preserves counts",
          m2.source_accuracy.get("src_a", {}).get("hits") == 3
          and m2.source_accuracy.get("src_a", {}).get("misses") == 1)

    # 5. Corrupt state: reset to empty, journaled (never fabricated)
    tmp.write_text("{not json", encoding="utf-8")
    m3 = RadarProbabilityMatrix(state_file=str(tmp))
    check("corrupt state reset to empty", m3.source_accuracy == {})
    check("corruption journaled", tmp.with_suffix(".journal.jsonl").exists())

    # 6. Action ladder naming: no flags → PROCEED, never "HOLD"
    good = m.evaluate_signal("X", "LONG", 0.9, "src_a",
                             price_history=[100, 100.05, 100.10, 100.15, 100.20])
    check("clean signal → PROCEED", good.action == "PROCEED")

    # 7. Adjusted probability stays a calibrated 0..1 quantity
    check("adjusted in [0,1]",
          all(0.0 <= i.adjusted_probability <= 1.0
              for i in (intel, nan_intel, good)))

    print(f"\n{'ALL PASS' if not failures else f'{len(failures)} FAILURES: {failures}'}")
    raise SystemExit(1 if failures else 0)
