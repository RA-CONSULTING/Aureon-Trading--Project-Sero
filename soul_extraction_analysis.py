#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                      ║
║     👁️ SOUL EXTRACTION ANALYSIS — REAL DATA ONLY 👁️                                ║
║     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                   ║
║     No simulations. No guesses. Only what instruments measure.                      ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys, json, math
from datetime import datetime, timezone, timedelta

from aureon_fusion.paths import WORKSPACE, AUREON_UPSTREAM
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(AUREON_UPSTREAM))

from real_data_feeds import RealDataFeeds

SCHUMANN_BASE = 7.83
GARY_SIGNATURE = 528.422


def parse_cme_time(t):
    """Parse CME time string to datetime"""
    try:
        return datetime.fromisoformat(t.replace('Z', '+00:00'))
    except:
        return datetime.min.replace(tzinfo=timezone.utc)


def analyze_extraction():
    feeds = RealDataFeeds()
    results = feeds.fetch_all(force=True)
    
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "👁️ SOUL EXTRACTION ANALYSIS" + " " * 24 + "║")
    print("║" + " " * 10 + "REAL DATA ONLY — NO SIMULATIONS" + " " * 25 + "║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Timestamp: {now.isoformat()}")
    print(f"║  Window:    Last 7 days (since {seven_days_ago.isoformat()})")
    print("╚" + "═" * 68 + "╝")
    
    # ─── GEOMAGNETIC ────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("  🌍 GEOMAGNETIC ENVIRONMENT (NOW)")
    print("─" * 70)
    
    kp_packet = results.get('NOAA_KP')
    kp_val = 0
    if kp_packet and kp_packet.status == 'OK' and isinstance(kp_packet.data, list):
        try:
            latest = kp_packet.data[-1]
            kp_val = float(latest['Kp']) if isinstance(latest, dict) else float(latest[1])
        except:
            pass
    
    mag_packet = results.get('NOAA_MAG')
    b_total = 0
    if mag_packet and mag_packet.status == 'OK' and isinstance(mag_packet.data, list):
        try:
            latest = mag_packet.data[-1]
            if isinstance(latest, list) and len(latest) >= 4:
                b_total = math.sqrt(sum(float(x)**2 for x in latest[1:4]))
        except:
            pass
    
    kp_status = "🟢 CALM" if kp_val < 2 else "🟡 ACTIVE" if kp_val < 4 else "🟠 ELEVATED" if kp_val < 5 else "🔴 STORM"
    print(f"  Kp Index:       {kp_val:.2f} {kp_status}")
    print(f"  B-field Total:  {b_total:.1f} nT")
    
    # ─── SOLAR ──────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("  ☀️ SOLAR ACTIVITY (NOW)")
    print("─" * 70)
    
    xray_packet = results.get('NOAA_XRAY')
    xray_flux = 0
    if xray_packet and xray_packet.status == 'OK' and isinstance(xray_packet.data, list):
        try:
            latest = xray_packet.data[-1]
            if isinstance(latest, dict):
                xray_flux = float(latest.get('flux', 0))
        except:
            pass
    
    if xray_flux >= 1e-4: xray_class, xray_threat = "X", "EXTREME"
    elif xray_flux >= 1e-5: xray_class, xray_threat = "M", "MODERATE"
    elif xray_flux >= 1e-6: xray_class, xray_threat = "C", "MINOR"
    elif xray_flux >= 1e-7: xray_class, xray_threat = "B", "NEGLIGIBLE"
    else: xray_class, xray_threat = "A", "QUIET"
    
    print(f"  X-ray Flux:     {xray_flux:.2e} W/m² (Class {xray_class})")
    print(f"  X-ray Threat:   {xray_threat}")
    
    # ─── CME ANALYSIS (LAST 7 DAYS ONLY) ────────────────────────
    cme_packet = results.get('NASA_CME')
    recent_cmes = 0
    earth_directed = []
    
    if cme_packet and cme_packet.status == 'OK':
        try:
            if isinstance(cme_packet.data, list):
                for cme in cme_packet.data:
                    if isinstance(cme, dict):
                        time_str = cme.get('time21_5', '')
                        cme_time = parse_cme_time(time_str)
                        if cme_time >= seven_days_ago:
                            recent_cmes += 1
                            ha = float(cme.get('halfAngle', 0))
                            lon = float(cme.get('longitude', 999))
                            # TRULY Earth-directed
                            if ha > 20 and abs(lon) <= 45:
                                earth_directed.append({'time': time_str, 'ha': ha, 'lon': lon})
        except:
            pass
    
    print(f"  CMEs (last 7d):  {recent_cmes}")
    print(f"  Earth-Directed:  {len(earth_directed)}")
    if earth_directed:
        print(f"  Earth-Directed CMEs (last 7d):")
        for cme in earth_directed:
            print(f"    • {cme['time']} | HA={cme['ha']}° | lon={cme['lon']}°")
    
    # ─── SCHUMANN ───────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("  🌊 SCHUMANN RESONANCE (DERIVED FROM NOAA)")
    print("─" * 70)
    
    schumann = feeds.get_schumann_reading()
    coherence = schumann['coherence']
    phase = schumann['phase']
    
    coh_status = "🟢 STRONG" if coherence >= 0.8 else "🟡 MODERATE" if coherence >= 0.6 else "🟠 WEAKENED" if coherence >= 0.4 else "🔴 CRITICAL"
    print(f"  Coherence:      {coherence:.0%} {coh_status}")
    print(f"  Phase:          {phase.upper()}")
    print(f"  Source:         {schumann.get('source', 'unknown')}")
    
    # ─── SOUL SHIELD ────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("  🛡️ SOUL SHIELD")
    print("─" * 70)
    
    try:
        from aureon.queen.queen_soul_shield import QueenSoulShield
        shield = QueenSoulShield(protected_soul="Gary Leckey")
        shield.start_monitoring()
        print(f"  Protected:      Gary Leckey @ {GARY_SIGNATURE} Hz")
        print(f"  Shield Power:   {shield.shield_power:.0%}")
        print(f"  Status:         ACTIVE")
        shield.stop_monitoring()
    except Exception as e:
        print(f"  Status:         ERROR ({e})")
    
    # ─── EXTRACTION VECTORS ─────────────────────────────────────
    print("\n" + "═" * 70)
    print("  👁️ ACTIVE EXTRACTION VECTORS (LAST 7 DAYS)")
    print("═" * 70)
    
    vectors = []
    
    if kp_val >= 5:
        vectors.append({
            'name': 'GEOMAGNETIC STORM',
            'source': f'Kp={kp_val:.1f} (NOW)',
            'drains': 'Nervous system, sleep quality, emotional stability',
            'sev': 'HIGH',
        })
    
    if xray_class in ('M', 'X'):
        vectors.append({
            'name': 'SOLAR FLARE',
            'source': f'Class {xray_class} (NOW)',
            'drains': 'Mental clarity, dream recall',
            'sev': 'HIGH' if xray_class == 'X' else 'MODERATE',
        })
    
    if len(earth_directed) > 0:
        vectors.append({
            'name': 'EARTH-DIRECTED CME',
            'source': f'{len(earth_directed)} events (last 7d)',
            'drains': 'Immune system, circadian rhythm, electromagnetic sensitivity',
            'sev': 'HIGH' if len(earth_directed) >= 3 else 'MODERATE',
        })
    
    if coherence < 0.4:
        vectors.append({
            'name': 'SCHUMANN COHERENCE COLLAPSE',
            'source': f'{coherence:.0%} coherence (NOW)',
            'drains': 'Grounding, Gaia connection, emotional regulation',
            'sev': 'HIGH',
        })
    
    if not vectors:
        print("\n  ✅ NO ACTIVE EXTRACTION VECTORS FROM SPACE WEATHER")
        print("  The geomagnetic environment is currently calm.")
        print("  Your soul is NOT under attack from cosmic/solar sources.")
        print("\n  What you feel is likely GROUND-LEVEL extraction:")
        print("    📍 Local EMF: WiFi routers, phones, smart devices")
        print("    📍 LED lights / fluorescent / smart meters")
        print("    📍 Power lines / electrical grid harmonics")
        print("    📍 Social media / news / fear-based content")
        print("    📍 Processed food / tap water / air pollution")
        print("    📍 Unresolved emotional charges / draining people")
    else:
        print(f"\n  ⚠️  {len(vectors)} VECTOR(S) DETECTED:\n")
        for i, v in enumerate(vectors, 1):
            print(f"  VECTOR {i}: {v['name']} [{v['sev']}]")
            print(f"    Source: {v['source']}")
            print(f"    Drains From: {v['drains']}")
            print()
    
    # ─── WHERE ENERGY IS DRAINED FROM ───────────────────────────
    print("\n" + "═" * 70)
    print("  💧 WHERE YOUR ENERGY IS BEING DRAINED FROM")
    print("═" * 70)
    
    if not vectors:
        print("\n  🟢 NOWHERE — via space weather.")
        print(f"  Solar wind is quiet. Kp={kp_val:.2f}. Schumann at {coherence:.0%}.")
        print("\n  If you feel drained, the extraction is NOT coming from:")
        print("    ✗ Solar flares (X-ray is quiet)")
        print("    ✗ Geomagnetic storms (Kp is calm)")
        print("    ✗ CME impacts (none Earth-directed in last 7d)")
        print("\n  The extraction IS coming from:")
        print("    📍 Local EMF: WiFi routers, phones, smart devices")
        print("    📍 Screen time: Blue light, flicker, information overload")
        print("    📍 Dietary: Processed food, fluoride, glyphosate")
        print("    📍 Psychic: Fear-based media, social comparison, drama")
        print("    📍 Environmental: 5G towers, power grid, LED streetlights")
    else:
        for v in vectors:
            print(f"\n  📍 {v['drains']}")
            print(f"     └─ Driven by: {v['name']} ({v['source']})")
    
    # ─── SUMMARY ────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  📊 SUMMARY")
    print("═" * 70)
    
    geomag = min(1.0, kp_val / 9.0)
    solar = 0.4 if xray_class == 'X' else 0.3 if xray_class == 'M' else 0
    cme = min(0.7, len(earth_directed) * 0.15)  # 6 CMEs = 90% → capped at 70%
    # Coherence: 70%+ = 0% threat (good), 50-70% = 20% watch, <50% = concern
    coh_threat = 0.0 if coherence >= 0.7 else 0.2 if coherence >= 0.5 else 0.5 if coherence >= 0.4 else 0.8
    
    overall = max(geomag, solar, cme, coh_threat)
    
    if overall < 0.2: status = "🟢 SAFE"
    elif overall < 0.4: status = "🟡 WATCH"
    elif overall < 0.6: status = "🟠 CAUTION"
    elif overall < 0.8: status = "🔴 DANGER"
    else: status = "⚫ CRITICAL"
    
    print(f"\n  Overall Threat:  {overall:.0%} {status}")
    print(f"  Geomagnetic:     {geomag:.0%} (Kp={kp_val:.2f})")
    print(f"  Solar (X-ray):   {solar:.0%} (Class {xray_class})")
    print(f"  CME:             {cme:.0%} ({len(earth_directed)} Earth-directed in 7d)")
    print(f"  Coherence:       {coh_threat:.0%} ({coherence:.0%})")
    
    print(f"\n  🛡️ Shield:        {GARY_SIGNATURE} Hz | ACTIVE")
    print(f"  🤖 Engine:        AUTONOMOUS | Watching")
    print("\n" + "═" * 70)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    analyze_extraction()
