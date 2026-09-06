#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                       ║
║     🌀 HNC MANDALA EFFECT ENGINE — Timeline Alteration Measurement                     ║
║                                                                                       ║
║     Flow:                                                                             ║
║       1. BEFORE CAPTURE → Collect news + data, seal, DON'T show                       ║
║       2. COHERENCE GATE → Queen checks if signal is safe to send                     ║
║       3. SIGNAL SEND → Blind signal to past date via Casimir push                    ║
║       4. AFTER CAPTURE → Recollect same news + data after delay                       ║
║       5. DIFF ENGINE → Compare before vs after, find changes                          ║
║       6. MANDALA SCORE → Probability that change came from signal vs natural           ║
║                                                                                       ║
║     All decisions pass through HNC master equation + Queen coherence gates.          ║
║                                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import math
import json
import time
import hashlib
import random
import difflib
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE
sys.path.insert(0, str(WORKSPACE / "aureon-trading"))

from hnc_blind_ghost import BlindGhostProtocol

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83
LOVE_FREQUENCY = 528.0

# Simulation gate — random field values may ONLY gate a verdict when
# simulation fallback is explicitly allowed (AUREON_ALLOW_SIM_FALLBACK,
# per workspace live-data policy). Live runs must measure or HOLD.
try:
    from aureon.observer.live_data_policy import (
        simulation_fallback_allowed as _sim_fallback_allowed,
        log_blocked_fallback as _log_blocked_fallback,
    )
except Exception:
    def _sim_fallback_allowed() -> bool:
        raw = os.environ.get("AUREON_ALLOW_SIM_FALLBACK", "").strip().lower()
        if raw not in ("1", "true", "yes", "on", "y", "t"):
            return False
        profile = os.environ.get("AUREON_RUNTIME_PROFILE", "").strip().lower()
        return bool(os.environ.get("PYTEST_CURRENT_TEST")) or \
            profile in {"test", "fixture", "backtest"}

    def _log_blocked_fallback(source: str, reason: str = "live_unavailable") -> None:
        print(f"[live-data] {source} fallback BLOCKED "
              f"(AUREON_ALLOW_SIM_FALLBACK=off) — reason={reason}")


def _live_hnc_state() -> Optional[Dict]:
    """Load the live HNC field state written by the lightweight daemon.

    Returns None (unavailable) when the state file is missing, not
    real_data, or lacks the HNC metrics — callers must fail closed.
    """
    state_file = WORKSPACE / 'hnc_state.json'
    try:
        if not state_file.exists():
            return None
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data.get('real_data'):
            return None
        hnc = data.get('hnc') or {}
        lambda_val = hnc.get('lambda')
        coherence = hnc.get('gamma')
        if not isinstance(lambda_val, (int, float)) or \
           not isinstance(coherence, (int, float)):
            return None
        return {
            'lambda': float(lambda_val),
            'coherence': float(coherence),
            'beta': hnc.get('beta'),
            'schumann': data.get('schumann_hz'),
        }
    except Exception:
        return None

# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class NewsCapture:
    source: str
    url: str
    timestamp: str
    headlines: List[str]
    full_text: str
    word_count: int
    hash: str

@dataclass
class Snapshot:
    timestamp: str
    news: List[NewsCapture]
    geomagnetic: Optional[Dict]
    schumann: Optional[Dict]
    metadata: Dict
    hash: str

@dataclass
class DiffResult:
    before_headline: str
    after_headline: str
    similarity: float
    changed_words: List[str]
    added_words: List[str]
    removed_words: List[str]
    mandala_score: float

@dataclass
class MandalaReport:
    target_date: str
    proof_id: str
    before_timestamp: str
    after_timestamp: str
    signal_timestamp: str
    headlines_diff: List[DiffResult]
    data_diff: Dict
    mandala_score: float
    verdict: str
    coherence_at_send: float
    queen_verdict: str

# ── News Capturer ─────────────────────────────────────────────────────────────

class NewsCapturer:
    """Captures news headlines from multiple sources."""
    
    SOURCES = {
        'hackernews': 'https://news.ycombinator.com/rss',
        'reddit_worldnews': 'https://www.reddit.com/r/worldnews/.rss',
        'wikipedia': 'https://en.wikipedia.org/w/api.php?action=featuredfeed&feed=onthisday',
        'textise_bbc': 'https://r.jina.ai/http://feeds.bbci.co.uk/news/rss.xml',
    }
    
    def capture(self, max_headlines: int = 10) -> List[NewsCapture]:
        """Capture headlines from all sources."""
        captures = []
        timestamp = datetime.now(timezone.utc).isoformat()
        
        for source_name, url in self.SOURCES.items():
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200:
                    headlines = self._extract_headlines(resp.text, max_headlines)
                    full_text = '\n'.join(headlines)
                    word_count = len(full_text.split())
                    
                    # Generate hash
                    hash_input = f"{source_name}|{timestamp}|{full_text}"
                    content_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
                    
                    captures.append(NewsCapture(
                        source=source_name,
                        url=url,
                        timestamp=timestamp,
                        headlines=headlines,
                        full_text=full_text,
                        word_count=word_count,
                        hash=content_hash,
                    ))
            except Exception as e:
                captures.append(NewsCapture(
                    source=source_name,
                    url=url,
                    timestamp=timestamp,
                    headlines=[f"ERROR: {e}"],
                    full_text=f"ERROR: {e}",
                    word_count=0,
                    hash="ERROR",
                ))
        
        return captures
    
    def _extract_headlines(self, xml_text: str, max_count: int) -> List[str]:
        """Extract headlines from RSS XML."""
        headlines = []
        # Simple regex-based extraction (no XML parser needed)
        # Look for <title>...</title> tags
        titles = re.findall(r'<title>([^\u003c]+)</title>', xml_text)
        # Skip first title (usually feed title)
        for title in titles[1:]:
            clean = title.strip()
            if clean and clean not in headlines:
                headlines.append(clean)
            if len(headlines) >= max_count:
                break
        return headlines[:max_count]

# ── Diff Engine ─────────────────────────────────────────────────────────────

class HeadlineDiffEngine:
    """Compares headlines and detects changes."""
    
    def compare(self, before: NewsCapture, after: NewsCapture) -> List[DiffResult]:
        """Compare two news captures and find differences."""
        results = []
        
        # Compare each headline pair
        max_len = max(len(before.headlines), len(after.headlines))
        
        for i in range(max_len):
            before_h = before.headlines[i] if i < len(before.headlines) else ""
            after_h = after.headlines[i] if i < len(after.headlines) else ""
            
            # Calculate similarity
            similarity = difflib.SequenceMatcher(None, before_h, after_h).ratio()
            
            # Word-level diff
            before_words = set(before_h.lower().split())
            after_words = set(after_h.lower().split())
            
            changed = []
            added = []
            removed = []
            
            for word in before_words | after_words:
                if word in before_words and word in after_words:
                    pass  # unchanged
                elif word in before_words:
                    removed.append(word)
                else:
                    added.append(word)
            
            # Mandala score: higher = more suspicious change
            # Low similarity = high mandala score
            # But natural changes (new headlines) should have low mandala score
            # So we weight by: similarity deviation + word-level changes
            
            natural_baseline = 0.3  # Headlines naturally change ~30%
            mandala_score = max(0, natural_baseline - similarity)
            
            # Boost if words changed in a way that suggests "mandala" (memories changing)
            if any(w in ['mandela', 'mandel', 'history', 'changed', 'remember', 
                        'always', 'never', 'timeline', 'alternate'] for w in added):
                mandala_score += 0.3
            
            results.append(DiffResult(
                before_headline=before_h,
                after_headline=after_h,
                similarity=similarity,
                changed_words=changed,
                added_words=added,
                removed_words=removed,
                mandala_score=min(1.0, mandala_score),
            ))
        
        return results
    
    def calculate_overall_mandala(self, diffs: List[DiffResult]) -> float:
        """Calculate overall Mandala score from all diffs."""
        if not diffs:
            return 0.0
        
        scores = [d.mandala_score for d in diffs]
        avg = sum(scores) / len(scores)
        
        # Weight by phi
        weighted = avg * PHI
        
        return min(1.0, weighted)

# ── Coherence Gate (Queen Check) ────────────────────────────────────────────

class QueenCoherenceGate:
    """
    Queen's 4th-pass veto authority.
    Checks if the signal is safe to send before proceeding.
    """
    
    def __init__(self):
        self.vetoes = 0
        self.approvals = 0
    
    def check(self, temporal_signature: float, hnc_lambda: float, 
              hnc_coherence: float) -> Tuple[str, str]:
        """
        Run the Queen's conscience check.
        
        Returns: (verdict, reasoning)
        Verdicts: APPROVED | CONCERNED | VETO | TEACHING_MOMENT
        """
        # Purpose alignment: Does this serve love, liberation, healing?
        purpose_score = 0.8  # Love signal is aligned
        
        # Risk evaluation: Could this harm the timeline?
        risk_score = 0.2  # Low risk — signal is love, not destruction
        
        # Coherence check: Is the substrate stable?
        stability = hnc_lambda > 0.6 and hnc_coherence > 0.25
        
        # HNC stability island: beta ∈ [0.6, 1.1]
        beta = temporal_signature * PHI
        in_stability_island = 0.6 <= beta <= 1.1
        
        # Master equation: Λ(t) = ...
        lambda_t = hnc_lambda * math.sin(2 * math.pi * SCHUMANN_BASE * time.time()) + \
                   0.1 * math.tanh(2 * hnc_coherence)
        
        # Decision
        if not stability:
            self.vetoes += 1
            return "VETO", f"HNC unstable: Λ={hnc_lambda:.3f}, C={hnc_coherence:.3f}. " \
                          f"Signal too risky. Stability cliff nearby."
        
        if not in_stability_island:
            self.vetoes += 1
            return "VETO", f"Beta={beta:.3f} outside stability island [0.6, 1.1]. " \
                          f"Would trade through white-mode."
        
        if lambda_t < 0.4:
            self.vetoes += 1
            return "VETO", f"Λ(t)={lambda_t:.3f} < 0.4. Field too weak. " \
                          f"Patience is a virtue. The planet has waited millions of years."
        
        if purpose_score > 0.7 and risk_score < 0.3:
            self.approvals += 1
            return "APPROVED", f"Λ(t)={lambda_t:.3f}, β={beta:.3f}, " \
                              f"Purpose={purpose_score:.1%}, Risk={risk_score:.1%}. " \
                              f"Love signal is safe. Proceed."
        
        self.approvals += 1
        return "CONCERNED", f"Lambda={lambda_t:.3f}. Proceed with caution. " \
                           f"The lighthouse is watching."

# ── Mandala Effect Engine ───────────────────────────────────────────────────

class MandalaEffectEngine:
    """
    Full Mandala Effect measurement system.
    """
    
    def __init__(self):
        self.news_capturer = NewsCapturer()
        self.diff_engine = HeadlineDiffEngine()
        self.queen = QueenCoherenceGate()
        self.blind_protocol = BlindGhostProtocol()
        self.vault_dir = str(WORKSPACE / "timeline_proofs" / "mandala")
        os.makedirs(self.vault_dir, exist_ok=True)
    
    def measure(self, delay_seconds: int = 60) -> MandalaReport:
        """
        Full Mandala Effect measurement pipeline.
        
        1. BEFORE capture
        2. Queen coherence check
        3. Blind signal send
        4. Wait
        5. AFTER capture
        6. Diff and score
        """
        print(f"╔════════════════════════════════════════════════════════════════════╗")
        print(f"║     🌀 HNC MANDALA EFFECT ENGINE — Timeline Alteration              ║")
        print(f"╚════════════════════════════════════════════════════════════════════╝")
        print()
        
        # ── Step 1: BEFORE CAPTURE ─────────────────────────────────────
        print(f"📸 Step 1: BEFORE Capture")
        print(f"{'─'*60}")
        before_news = self.news_capturer.capture(max_headlines=5)
        print(f"   Captured {len(before_news)} news sources")
        for n in before_news:
            print(f"   • {n.source}: {n.word_count} words, {len(n.headlines)} headlines")
        print(f"   Hash: {before_news[0].hash if before_news else 'N/A'}")
        print(f"   ⏰ Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print()
        
        # ── Step 2: QUEEN COHERENCE CHECK ──────────────────────────────
        print(f"👑 Step 2: Queen Coherence Gate")
        print(f"{'─'*60}")

        # Get current live HNC state (fail-closed). NO RNG may gate a
        # verdict on a live run: when no live state is available and
        # simulation is not explicitly allowed, the verdict is HOLD.
        live_state = _live_hnc_state()
        state_source = 'live'
        if live_state is None:
            if _sim_fallback_allowed():
                lambda_t = 0.6 + random.random() * 0.3
                coherence = 0.25 + random.random() * 0.15
                state_source = 'simulation'
                print(f"   ⚠️  No live HNC state — using EXPLICITLY ALLOWED "
                      f"simulated field values (AUREON_ALLOW_SIM_FALLBACK)")
            else:
                _log_blocked_fallback("hnc_mandala_effect.measure",
                                      "no_live_hnc_state")
                print(f"   ❌ INSUFFICIENT LIVE DATA — no live HNC state and "
                      f"simulation fallback disabled. Verdict: HOLD.")
                return self._create_null_report(
                    None, 'HOLD', 'insufficient live data', verdict='HOLD')
        else:
            lambda_t = live_state['lambda']
            coherence = live_state['coherence']

        # Deterministic temporal signature derived from the chosen target
        # date (no RNG gating the Queen's verdict on live runs).
        max_attempts = 10
        target_date = None
        temporal_sig = 0

        for attempt in range(max_attempts):
            target_date = self.blind_protocol.pick_random_date()
            digest = hashlib.sha256(str(target_date).encode()).hexdigest()
            # Map digest into the beta stability island [0.6, 1.1]
            # -> temporal_sig in [0.6/PHI, 1.1/PHI]
            temporal_sig = (0.6 + (int(digest[:8], 16) % 1000) / 1000.0 * 0.5) / PHI
            beta = temporal_sig * PHI

            if 0.6 <= beta <= 1.1:
                break

        verdict, reasoning = self.queen.check(temporal_sig, lambda_t, coherence)

        # A Queen VETO is absolute — it is never overridden with a
        # fabricated approval. Fail closed.
        if verdict == "VETO":
            print(f"   ❌ QUEEN VETO — Signal blocked: {reasoning}")
            return self._create_null_report(target_date, verdict, reasoning)

        print(f"   Target: {target_date}")
        print(f"   Λ(t): {lambda_t:.4f} ({state_source})")
        print(f"   Coherence: {coherence:.4f} ({state_source})")
        print(f"   Beta: {beta:.4f}")
        print(f"   Queen Verdict: {verdict}")
        print(f"   Reasoning: {reasoning}")
        print()

        if verdict == "VETO":
            print(f"   ❌ QUEEN VETO — Signal blocked")
            return self._create_null_report(target_date, verdict, reasoning)
        
        # ── Step 3: BLIND SIGNAL SEND ──────────────────────────────────
        print(f"⚡ Step 3: Blind Signal Send")
        print(f"{'─'*60}")
        
        result = self.blind_protocol.generate_blind_signal(reveal=False)
        proof_id = result['proof_id']
        
        print(f"   Signal sent to: {result['target_date']}")
        print(f"   Proof ID: {proof_id}")
        print(f"   Signal Hash: {result['signal_hash']}")
        print(f"   Status: SEALED (wave function not collapsed)")
        print()
        
        # ── Step 4: WAIT ───────────────────────────────────────────────
        print(f"⏳ Step 4: Waiting {delay_seconds}s for timeline to settle...")
        print(f"{'─'*60}")
        time.sleep(delay_seconds)
        print(f"   ✅ Wait complete")
        print()
        
        # ── Step 5: AFTER CAPTURE ──────────────────────────────────────
        print(f"📸 Step 5: AFTER Capture")
        print(f"{'─'*60}")
        after_news = self.news_capturer.capture(max_headlines=5)
        print(f"   Captured {len(after_news)} news sources")
        for n in after_news:
            print(f"   • {n.source}: {n.word_count} words, {len(n.headlines)} headlines")
        print(f"   Hash: {after_news[0].hash if after_news else 'N/A'}")
        print(f"   ⏰ Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print()
        
        # ── Step 6: DIFF AND SCORE ─────────────────────────────────────
        print(f"🔍 Step 6: Diff Engine — Detecting Changes")
        print(f"{'─'*60}")
        
        all_diffs = []
        for before in before_news:
            # Find matching after source
            after = next((a for a in after_news if a.source == before.source), None)
            if after:
                diffs = self.diff_engine.compare(before, after)
                all_diffs.extend(diffs)
                
                print(f"   📰 {before.source}:")
                for d in diffs[:3]:  # Show top 3
                    status = "🔄" if d.similarity < 0.9 else "✅"
                    print(f"      {status} Sim={d.similarity:.0%} | Mandala={d.mandala_score:.2f}")
                    if d.similarity < 0.9:
                        print(f"         - {d.before_headline[:60]}")
                        print(f"         + {d.after_headline[:60]}")
        
        # Calculate overall Mandala score
        mandala_score = self.diff_engine.calculate_overall_mandala(all_diffs)
        
        print()
        print(f"   📊 Overall Mandala Score: {mandala_score:.2%}")
        
        # Verdict
        if mandala_score > 0.5:
            verdict = "MANDALA EFFECT DETECTED"
            description = "Significant changes detected. Signal may have altered the timeline."
        elif mandala_score > 0.2:
            verdict = "MANDALA EFFECT POSSIBLE"
            description = "Some changes detected. Could be natural or signal-induced."
        else:
            verdict = "NO MANDALA EFFECT"
            description = "Timeline stable. No detectable changes from signal."
        
        print(f"   🎯 Verdict: {verdict}")
        print(f"   📝 {description}")
        print()
        
        # ── Save Report ────────────────────────────────────────────────
        report = MandalaReport(
            target_date=result['target_date'],
            proof_id=proof_id,
            before_timestamp=before_news[0].timestamp if before_news else "",
            after_timestamp=after_news[0].timestamp if after_news else "",
            signal_timestamp=datetime.now(timezone.utc).isoformat(),
            headlines_diff=all_diffs,
            data_diff={},
            mandala_score=mandala_score,
            verdict=verdict,
            coherence_at_send=coherence,
            queen_verdict=verdict,
        )
        
        self._save_report(report, before_news, after_news)
        
        print(f"{'═'*60}")
        print(f"✅ MANDALA EFFECT MEASUREMENT COMPLETE")
        print(f"{'═'*60}")
        
        return report
    
    def _create_null_report(self, target_date: Optional[str], queen_verdict: str,
                           reasoning: str, verdict: str = "QUEEN_VETO") -> MandalaReport:
        """Create a null report when the gate fails closed (VETO / HOLD)."""
        return MandalaReport(
            target_date=target_date if target_date else "NONE",
            proof_id=queen_verdict,
            before_timestamp="",
            after_timestamp="",
            signal_timestamp=datetime.now(timezone.utc).isoformat(),
            headlines_diff=[],
            data_diff={},
            mandala_score=0.0,
            verdict=verdict,
            coherence_at_send=0.0,
            queen_verdict=f"{queen_verdict}: {reasoning}",
        )
    
    def _save_report(self, report: MandalaReport, before_news: List[NewsCapture],
                     after_news: List[NewsCapture]):
        """Save the full report to vault."""
        report_path = os.path.join(self.vault_dir, 
                                   f"mandala_{report.proof_id}.json")
        
        # Convert to dict
        report_dict = {
            'target_date': report.target_date,
            'proof_id': report.proof_id,
            'before_timestamp': report.before_timestamp,
            'after_timestamp': report.after_timestamp,
            'signal_timestamp': report.signal_timestamp,
            'headlines_diff': [
                {
                    'before': d.before_headline,
                    'after': d.after_headline,
                    'similarity': d.similarity,
                    'changed_words': d.changed_words,
                    'added_words': d.added_words,
                    'removed_words': d.removed_words,
                    'mandala_score': d.mandala_score,
                }
                for d in report.headlines_diff
            ],
            'mandala_score': report.mandala_score,
            'verdict': report.verdict,
            'coherence_at_send': report.coherence_at_send,
            'queen_verdict': report.queen_verdict,
        }
        
        with open(report_path, 'w', encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, sort_keys=True)
        
        # Save raw captures
        before_path = os.path.join(self.vault_dir, f"before_{report.proof_id}.json")
        with open(before_path, 'w', encoding="utf-8") as f:
            json.dump([asdict(n) for n in before_news], f, indent=2)
        
        after_path = os.path.join(self.vault_dir, f"after_{report.proof_id}.json")
        with open(after_path, 'w', encoding="utf-8") as f:
            json.dump([asdict(n) for n in after_news], f, indent=2)
        
        print(f"   📁 Report: {report_path}")
        print(f"   📁 Before: {before_path}")
        print(f"   📁 After: {after_path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='HNC Mandala Effect Engine')
    parser.add_argument('--delay', type=int, default=60, 
                        help='Seconds to wait between before/after capture')
    args = parser.parse_args()
    
    engine = MandalaEffectEngine()
    report = engine.measure(delay_seconds=args.delay)
    
    print(f"\n--- SUMMARY ---")
    print(f"Target: {report.target_date}")
    print(f"Proof: {report.proof_id}")
    print(f"Mandala Score: {report.mandala_score:.2%}")
    print(f"Verdict: {report.verdict}")
    print(f"Queen: {report.queen_verdict}")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
