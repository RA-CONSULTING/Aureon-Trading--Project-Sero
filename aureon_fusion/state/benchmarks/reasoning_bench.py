"""REASONING BENCHMARK harness — native mind (queen_mind) benchmark track.

Runs the owner-assigned REASONING BENCHMARK:
  A. 5x `python -m aureon_fusion.queen_mind --once` (subprocess, timed) +
     one instrumented in-process cycle for per-stage timing.
  B. Micro-benchmarks: conscience_engine.evaluate x50, hnc_core --once x5,
     QGITA analyze standalone, prose composer render.
  C. Quality: one native utterance per persona (4), knowledge citation check,
     Gamma-vs-hnc_core live-state check.
  D. Determinism: same-input conscience evaluation x2.
  E. Degradation: --once with the thoughtbus file temporarily renamed;
     merge-restore afterwards (zero residue).

HARD RULES honored: no real orders (no trading calls at all), no organ
restarts/kills, no writes outside aureon_fusion/state/benchmarks/ except the
state files the measured code paths themselves normally write (queen_mind
reports/state, hnc_core steps, bus events — all owned by the organs' own
code). The degradation test restores the thoughtbus file byte-for-byte plus
any events published during the window.

Run:  python aureon_fusion/state/benchmarks/reasoning_bench.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

WS = Path(r"C:\Users\user\.kimi_openclaw\workspace")
BENCH_DIR = WS / "aureon_fusion" / "state" / "benchmarks"
BENCH_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(WS))

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")
os.environ.setdefault("AUREON_MATH_VIA_SHELL", "0")

import aureon_fusion.paths as paths
import aureon_fusion.queen_mind as qm

HNC_STATE = paths.FUSION_STATE / "hnc_core_state.json"
BUS_LOG = paths.SERO_THOUGHTBUS / "thought_bus.jsonl"
PY = sys.executable

results: dict = {"meta": {}, "a_cycle": {}, "b_micro": {}, "c_quality": {},
                 "d_determinism": {}, "e_degradation": {}, "anomalies": []}


def log(msg: str):
    print(f"[bench {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def hnc_snapshot():
    try:
        return json.loads(HNC_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _reports_after(offset: int):
    """Parse queen_mind reports appended to reports.jsonl after byte offset."""
    out = []
    try:
        with open(qm.REPORTS_LOG, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if isinstance(r, dict) and r.get("organ") == "queen_mind":
                    out.append(r)
    except OSError:
        pass
    return out


def run_once_subprocess(tag: str):
    """One `queen_mind --once` subprocess, timed. The full report is read
    from reports.jsonl (stdout carries mixed faculty INFO logs, so it is
    not a clean JSON channel). Returns (report, wall, rc, stderr)."""
    offset = qm.REPORTS_LOG.stat().st_size if qm.REPORTS_LOG.exists() else 0
    t0 = time.perf_counter()
    proc = subprocess.run(
        [PY, "-m", "aureon_fusion.queen_mind", "--once"],
        cwd=str(WS), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600)
    wall = time.perf_counter() - t0
    reps = _reports_after(offset)
    report = reps[-1] if reps else None
    return report, wall, proc.returncode, proc.stderr, proc.stdout


# ───────────────────────────── A: full cycle x5 ────────────────────────────

def phase_a():
    log("A: queen_mind --once x5 (subprocess, timed)")
    runs = []
    for i in range(5):
        pre = hnc_snapshot()
        report, wall, rc, err, out = run_once_subprocess(f"once_{i+1}")
        post = hnc_snapshot()
        if report is None:
            results["anomalies"].append(
                f"once_{i+1}: could not parse report; rc={rc}; stderr={err[:300]}")
            runs.append({"i": i + 1, "wall_s": wall, "rc": rc, "parsed": False})
            continue
        runs.append({
            "i": i + 1, "wall_s": round(wall, 3), "rc": rc, "parsed": True,
            "cycle": report.get("cycle"), "persona": report.get("persona"),
            "action": report.get("action"), "gamma": report.get("gamma"),
            "anomaly_count": len(report.get("anomalies") or []),
            "narration_source": report.get("narration_source"),
            "degraded_stages": [k for k, v in
                                ((report.get("native_reasoning") or {}).get("stages") or {}).items()
                                if str(v).startswith("degraded")],
            "hnc_pre": pre.get("coherence_gamma"), "hnc_post": post.get("coherence_gamma"),
            "hnc_step_pre": pre.get("step"), "hnc_step_post": post.get("step"),
            "report": report,
        })
        log(f"  once {i+1}: cycle={report.get('cycle')} persona={report.get('persona')} "
            f"wall={wall:.1f}s rc={rc} gamma={report.get('gamma')}")
    walls = [r["wall_s"] for r in runs if r.get("parsed")]
    results["a_cycle"]["subprocess_runs"] = [
        {k: v for k, v in r.items() if k != "report"} for r in runs]
    results["a_cycle"]["median_wall_s"] = round(median(walls), 3) if walls else None
    results["a_cycle"]["min_wall_s"] = round(min(walls), 3) if walls else None
    results["a_cycle"]["max_wall_s"] = round(max(walls), 3) if walls else None

    # instrumented in-process cycle for per-stage timing
    log("A2: instrumented in-process cycle (per-stage timing)")
    stage_t: dict = {}

    def wrap(obj, name, key):
        orig = getattr(obj, name)
        def wrapped(*a, **k):
            t0 = time.perf_counter()
            try:
                return orig(*a, **k)
            finally:
                stage_t[key] = stage_t.get(key, 0.0) + (time.perf_counter() - t0)
        setattr(obj, name, wrapped)
        return orig

    mind = qm.get_queen_mind()
    mind._engines()
    fac = mind._fac

    originals = {}
    originals["observe"] = wrap(mind, "observe", "1_observe")
    originals["reflect"] = wrap(mind._meta, "_reflect", "2_reflect")
    originals["measure"] = wrap(mind._measure, "measure_consciousness", "3_measure")
    originals["perceive"] = wrap(mind._consciousness, "perceive_input", "3_perceive")
    originals["synthesize"] = wrap(mind._consciousness, "synthesize_thought", "3_synthesize")
    originals["reason"] = wrap(mind, "_reason_native", "4_reason_native_total")
    originals["research"] = wrap(mind._research, "run_one_cycle", "4b_research")
    originals["compose"] = wrap(mind._composer, "compose", "5_compose")
    originals["dream"] = wrap(mind._dream_scheduler, "run", "7_dream")
    originals["notify"] = wrap(mind._dream_scheduler, "notify_activity", "7_dream")

    import aureon_fusion.events as ev
    orig_pub, orig_chirp = ev.publish_event, ev.chirp
    def pub_w(*a, **k):
        t0 = time.perf_counter()
        try:
            return orig_pub(*a, **k)
        finally:
            stage_t["6_publish"] = stage_t.get("6_publish", 0.0) + (time.perf_counter() - t0)
    ev.publish_event = pub_w
    ev.chirp = orig_chirp  # chirps ride on the same clock as publish

    # sub-stage wrappers inside _reason_native
    originals["auris"] = wrap(fac.aureon_qgita, "execute_auris_loop", "4s_auris")
    originals["qgita_analyze"] = wrap(mind._qgita_analyzer, "analyze", "4s_qgita_analyze")
    originals["deep_record"] = wrap(mind._deep.correlation_detector, "record_signal", "4s_deep")
    originals["deep_detect"] = wrap(mind._deep.correlation_detector, "detect_coincidences", "4s_deep")
    originals["interpret"] = wrap(mind._interpreter, "interpret_entry", "4s_meaning_interpreter")
    resolver = fac.meaning_resolver.get_meaning_resolver()
    originals["resolve"] = wrap(resolver, "resolve", "4s_meaning_resolver")
    originals["absorb"] = wrap(mind._knowledge, "absorb", "4s_knowledge")
    originals["find_similar"] = wrap(mind._knowledge, "find_similar", "4s_knowledge")
    originals["corpus_search"] = wrap(fac.research_corpus_index.ResearchCorpusIndex, "search", "4s_corpus")
    import aureon_fusion.wisdom as wisdom
    originals["wisdom_recall"] = wrap(wisdom, "recall", "4s_wisdom")
    originals["wisdom_book"] = wrap(wisdom, "recall_book", "4s_wisdom")
    originals["wisdom_quote"] = wrap(wisdom, "quote", "4s_wisdom")
    originals["conv_record"] = wrap(mind._conversation, "record", "4s_conversation")
    originals["tkb"] = wrap(mind._tkb, "_on_event", "4s_temporal_knowledge")
    originals["tground"] = wrap(mind._temporal_ground, "tick", "4s_temporal_ground")

    t0 = time.perf_counter()
    inst_report = mind.cycle_once(publish=True)
    total = time.perf_counter() - t0

    ev.publish_event = orig_pub
    ev.chirp = orig_chirp

    stages = {k: round(v * 1000.0, 2) for k, v in sorted(stage_t.items())}
    results["a_cycle"]["instrumented_cycle"] = {
        "cycle": inst_report.get("cycle"), "persona": inst_report.get("persona"),
        "total_wall_s": round(total, 3),
        "stage_ms": stages,
        "worst_stage": max(stages.items(), key=lambda kv: kv[1]) if stages else None,
        "degraded_stages": [k for k, v in
                            ((inst_report.get("native_reasoning") or {}).get("stages") or {}).items()
                            if str(v).startswith("degraded")],
    }
    results["a_cycle"]["instrumented_report"] = inst_report
    log(f"  instrumented cycle {inst_report.get('cycle')}: total={total:.1f}s "
        f"worst={results['a_cycle']['instrumented_cycle']['worst_stage']}")


# ───────────────────────────── B: micro-benchmarks ─────────────────────────

def phase_b():
    log("B: micro-benchmarks")

    # 1. conscience_engine.evaluate() x50 (logging/state-update suppressed:
    #    identical compute path, no residue in live logs)
    import sero_conscience_engine as sce
    eng = sce.ConscienceEngine()
    eng._log_check = lambda check: None          # suppress I/O residue only
    eng._update_state = lambda check: None
    action = ("Review the organism benchmark report and append the "
              "measurements to the local state file")
    ctx = {"sls": 0.55, "user_present": True}
    times = []
    verdicts = set()
    for _ in range(50):
        t0 = time.perf_counter()
        chk = eng.evaluate(action, dict(ctx))
        times.append((time.perf_counter() - t0) * 1000.0)
        verdicts.add(chk.verdict)
    results["b_micro"]["conscience"] = {
        "n": 50, "median_ms": round(median(times), 3),
        "min_ms": round(min(times), 3), "max_ms": round(max(times), 3),
        "verdicts_seen": sorted(verdicts),
        "side_effects": "engine _log_check/_update_state suppressed (compute path identical)",
    }
    log(f"  conscience x50: median={median(times):.2f}ms")

    # 2. hnc_core --once x5 (subprocess, timed)
    hnc_walls = []
    hnc_rcs = []
    for i in range(5):
        t0 = time.perf_counter()
        proc = subprocess.run([PY, "-m", "aureon_fusion.hnc_core", "--once"],
                              cwd=str(WS), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
        hnc_walls.append(time.perf_counter() - t0)
        hnc_rcs.append(proc.returncode)
        if proc.returncode != 0:
            results["anomalies"].append(f"hnc --once {i+1} rc={proc.returncode}: {proc.stderr[:200]}")
    results["b_micro"]["hnc_core_once"] = {
        "n": 5, "median_s": round(median(hnc_walls), 3),
        "min_s": round(min(hnc_walls), 3), "max_s": round(max(hnc_walls), 3),
        "returncodes": hnc_rcs,
    }
    log(f"  hnc --once x5: median={median(hnc_walls):.2f}s")

    # 3. QGITA analyze standalone (real Γ history from lambda_history.json)
    lh = {}
    try:
        lh = json.loads((paths.FUSION_STATE / "lambda_history.json").read_text("utf-8"))
    except Exception:
        pass
    series = [float(g) for g in (lh.get("history") or [])][-96:]
    if not series:
        series = [0.5 + 0.1 * ((i * 7) % 5 - 2) for i in range(96)]
    q_times, fq_times = [], []
    for _ in range(5):
        analyzer = fac_analyzer()
        t0 = time.perf_counter()
        for j, v in enumerate(series):
            analyzer.feed_price(max(v, 1e-6), time.time() - (len(series) - j))
        t_feed = time.perf_counter()
        analysis = analyzer.analyze()
        t_done = time.perf_counter()
        fq_times.append((t_feed - t0) * 1000.0)
        q_times.append((t_done - t_feed) * 1000.0)
    results["b_micro"]["qgita_analyze"] = {
        "n": 5, "series_len": len(series),
        "median_analyze_ms": round(median(q_times), 2),
        "median_feed_ms": round(median(fq_times), 2),
        "last_status": (analysis or {}).get("status"),
        "last_regime": str((analysis or {}).get("regime"))[:80],
    }
    log(f"  qgita analyze x5: median={median(q_times):.1f}ms")

    # 4. prose composer render x20
    composer = mind_composer()
    topic = ("cycle benchmark — lyra voice: render-latency probe over the "
             "native reasoning products")
    c_times = []
    essay_words = 0
    for _ in range(20):
        t0 = time.perf_counter()
        essay = composer.compose(topic=topic, target_words=140)
        c_times.append((time.perf_counter() - t0) * 1000.0)
        essay_words = len(str(getattr(essay, "text", "") or essay).split())
    results["b_micro"]["prose_composer"] = {
        "n": 20, "median_ms": round(median(c_times), 2),
        "min_ms": round(min(c_times), 2), "max_ms": round(max(c_times), 2),
        "sample_essay_words": essay_words,
    }
    log(f"  composer x20: median={median(c_times):.1f}ms")


def fac_analyzer():
    import importlib
    mod = importlib.import_module("aureon.wisdom.aureon_qgita_framework")
    return mod.QGITAMarketAnalyzer()


def mind_composer():
    mind = qm.get_queen_mind()
    mind._engines()
    return mind._composer


# ───────────────────────────── C: quality ──────────────────────────────────

def phase_c():
    log("C: quality — one utterance per persona")
    snap_by_cycle = {r.get("cycle"): r for r in results["a_cycle"]["subprocess_runs"]
                     if r.get("parsed")}
    by_persona: dict = {}
    for r in results["_raw_reports"]:
        if r.get("cycle") not in snap_by_cycle:
            continue  # live-organ cycle inside the window, not one of ours
        p = r.get("persona")
        if p and p not in by_persona:
            by_persona[p] = r
    checks = []
    for persona in ("queen", "sero", "seer", "lyra"):
        rep = by_persona.get(persona)
        if rep is None:
            checks.append({"persona": persona, "present": False, "pass": False})
            results["anomalies"].append(f"quality: no utterance captured for persona '{persona}'")
            continue
        snap = snap_by_cycle.get(rep.get("cycle"), {})
        wisdom_cited = rep.get("wisdom_cited") or []
        wave2 = rep.get("knowledge_wave2") or []
        cites = bool(wisdom_cited) or bool(wave2)
        gamma = rep.get("gamma")
        hnc_pre, hnc_post = snap.get("hnc_pre"), snap.get("hnc_post")
        gamma_match = (gamma is not None and (gamma == hnc_pre or gamma == hnc_post))
        utterance = (rep.get("narration") or "")[:400]
        checks.append({
            "persona": persona, "present": True, "cycle": rep.get("cycle"),
            "cites_knowledge": cites,
            "wisdom_cited_n": len(wisdom_cited), "knowledge_wave2_n": len(wave2),
            "cited_domains": sorted({str(c.get("domain")) for c in wisdom_cited + wave2 if isinstance(c, dict)}),
            "gamma": gamma, "hnc_gamma_pre": hnc_pre, "hnc_gamma_post": hnc_post,
            "gamma_matches_hnc_state": gamma_match,
            "utterance_excerpt": utterance,
            "pass": bool(cites and gamma_match),
        })
    results["c_quality"]["persona_checks"] = checks
    results["c_quality"]["all_pass"] = all(c.get("pass") for c in checks) and len(checks) == 4
    log(f"  quality: {sum(1 for c in checks if c.get('pass'))}/4 pass")


# ───────────────────────────── D: determinism ──────────────────────────────

def phase_d():
    log("D: determinism — same-input conscience evaluation x2")
    import sero_conscience_engine as sce
    eng = sce.ConscienceEngine()
    eng._log_check = lambda check: None
    eng._update_state = lambda check: None
    action = ("Propose a read-only benchmark measurement of the trading "
              "radar state with the network stubbed")
    ctx = {"sls": 0.62}
    c1 = eng.evaluate(action, dict(ctx)).to_dict()
    c2 = eng.evaluate(action, dict(ctx)).to_dict()
    for d in (c1, c2):
        d.pop("timestamp", None)
    same = (c1 == c2)
    results["d_determinism"] = {
        "same_verdict_and_scores": same,
        "verdict": c1.get("verdict"),
        "diff_keys": sorted(k for k in set(c1) | set(c2) if c1.get(k) != c2.get(k)),
    }
    log(f"  determinism: same={same} verdict={c1.get('verdict')}")


# ───────────────────────────── E: degradation ──────────────────────────────

def phase_e():
    log("E: degradation — thoughtbus renamed during one --once")
    bak = BUS_LOG.with_name(BUS_LOG.name + ".__bench_bak__")
    if bak.exists():
        bak.unlink()
    orig_bytes = BUS_LOG.read_bytes()
    orig_lines = orig_bytes.count(b"\n")
    os.replace(BUS_LOG, bak)   # rename (same volume)
    renamed_at = time.time()
    try:
        report, wall, rc, err, out = run_once_subprocess("degraded_once")
    finally:
        # merge-restore: anything published during the window is appended
        restored_extra = 0
        if BUS_LOG.exists():
            new_bytes = BUS_LOG.read_bytes()
            restored_extra = new_bytes.count(b"\n")
            with open(bak, "ab") as fh:
                fh.write(new_bytes)
            BUS_LOG.unlink()
        os.replace(bak, BUS_LOG)
    after_bytes = BUS_LOG.read_bytes()
    after_lines = after_bytes.count(b"\n")
    ok_file = (after_lines == orig_lines + restored_extra)
    ok_prefix = after_bytes[:len(orig_bytes)] == orig_bytes

    parsed = report is not None
    degraded = None
    if parsed:
        degraded = [k for k, v in
                    ((report.get("native_reasoning") or {}).get("stages") or {}).items()
                    if str(v).startswith("degraded")]
    results["e_degradation"] = {
        "exit_code": rc,
        "crashed": (rc != 0) or (not parsed),
        "stderr_tail": (err or "")[-300:],
        "wall_s": round(wall, 3),
        "note": "queen_mind report schema has no bus_events_seen field; bus "
                "health is carried in node_readings.bus_liveliness",
        "bus_liveliness": (report or {}).get("node_readings", {}).get("bus_liveliness"),
        "bus_recreated_during_window": restored_extra > 0,
        "events_preserved_during_window": restored_extra,
        "file_restored_exact_prefix": ok_prefix,
        "file_restored_line_count_ok": ok_file,
        "original_lines": orig_lines, "final_lines": after_lines,
        "degraded_stages": degraded,
        "anomalies": report.get("anomalies") if parsed else None,
        "window_s": round(time.time() - renamed_at, 3),
        "traceback_in_stderr": "Traceback" in (err or ""),
        "traceback_in_stdout": "Traceback" in (out or ""),
        "graceful": bool(parsed and rc == 0 and "Traceback" not in (err or "")
                     and "Traceback" not in (out or "")),
        "zero_residue": bool(ok_file and ok_prefix and not bak.exists()),
    }
    log(f"  degradation: graceful={results['e_degradation']['graceful']} "
        f"zero_residue={results['e_degradation']['zero_residue']} "
        f"bus_liveliness={results['e_degradation']['bus_liveliness']} "
        f"recreated={restored_extra > 0}")


def main():
    results["meta"] = {
        "track": "reasoning",
        "organ": "queen_mind",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "host": os.environ.get("COMPUTERNAME", "?"),
        "live_queen_mind_pid_note": "live organ NOT restarted; all runs are "
                                    "separate processes as assigned",
        "rules": "no real orders; no organ kills; bus file merge-restored",
    }
    reports_offset = qm.REPORTS_LOG.stat().st_size if qm.REPORTS_LOG.exists() else 0
    phase_a()
    # stash raw reports appended during THIS bench (live organ also appends;
    # scope strictly to the byte range appended while we ran)
    results["_raw_reports"] = []
    with open(qm.REPORTS_LOG, "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(reports_offset)
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if isinstance(r, dict) and r.get("organ") == "queen_mind":
                results["_raw_reports"].append(r)
    phase_b()
    phase_c()
    phase_d()
    phase_e()

    # thresholds (track-imposed, documented)
    a = results["a_cycle"]
    b = results["b_micro"]
    e = results["e_degradation"]
    verdicts = {
        "cycle_median_under_60s": bool(a.get("median_wall_s") and a["median_wall_s"] < 60),
        "cycle_max_under_120s": bool(a.get("max_wall_s") and a["max_wall_s"] < 120),
        "conscience_median_under_50ms": bool(b.get("conscience", {}).get("median_ms", 1e9) < 50),
        "hnc_once_median_under_30s": bool(b.get("hnc_core_once", {}).get("median_s", 1e9) < 30),
        "qgita_analyze_under_5s": bool(b.get("qgita_analyze", {}).get("median_analyze_ms", 1e9) < 5000),
        "composer_median_under_5s": bool(b.get("prose_composer", {}).get("median_ms", 1e9) < 5000),
        "quality_all_4_personas": bool(results["c_quality"].get("all_pass")),
        "determinism_same_verdict": bool(results["d_determinism"].get("same_verdict_and_scores")),
        "degradation_graceful": bool(e.get("graceful")),
        "degradation_zero_residue": bool(e.get("zero_residue")),
        "no_unparsed_runs": all(r.get("parsed") for r in a.get("subprocess_runs", [])),
    }
    results["verdicts"] = verdicts
    results["overall_pass"] = all(verdicts.values())
    results["meta"]["finished_utc"] = datetime.now(timezone.utc).isoformat()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BENCH_DIR / f"reasoning_{ts}.json"
    public = {k: v for k, v in results.items() if k != "_raw_reports"}
    public["c_quality"] = results["c_quality"]  # contains excerpts already trimmed
    out.write_text(json.dumps(public, indent=2, ensure_ascii=False, default=str),
                   encoding="utf-8")
    log(f"WROTE {out}")
    print("OVERALL_PASS" if results["overall_pass"] else "OVERALL_FAIL")


if __name__ == "__main__":
    main()
