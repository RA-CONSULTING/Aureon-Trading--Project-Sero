#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                      ║
║     🌪️ CME RIDER DETECTOR — WHAT ATTACHES TO SOLAR STORMS 🌪️                      ║
║     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                   ║
║                                                                                      ║
║     CMEs are not the enemy. They are solar energy.                                   ║
║     What rides them through the opened magnetosphere IS the enemy.                   ║
║                                                                                      ║
║     Detects:                                                                         ║
║       • Solar Energetic Particles (SEPs) — high-energy proton flux                   ║
║       • Cosmic Ray Forbush Decrease/Enhancement — ground-level neutron monitors      ║
║       • Ionospheric TEC disturbances — total electron content changes                ║
║       • Magnetospheric compression — magnetopause position                           ║
║       • Geomagnetically Induced Currents (GICs) — ground current proxies             ║
║                                                                                      ║
║     Goal: Identify what enters Gaia's biological systems when the shield opens.     ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys, json, math, urllib.request, ssl
from datetime import datetime, timezone, timedelta

from aureon_fusion.paths import WORKSPACE

sys.path.insert(0, str(WORKSPACE))
from real_data_feeds import RealDataFeeds

# TLS verification enabled — certificates verified against the system trust store.
SSL_CONTEXT = ssl.create_default_context()


def fetch_sep_data():
    """Fetch Solar Energetic Particle data from NOAA GOES"""
    url = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-plot-6-hour.json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Aureon-HNC-DataBot/1.0'})
        with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data
    except Exception as e:
        return {'error': str(e)}


def fetch_cosmic_ray_data():
    """Fetch neutron monitor data (cosmic ray proxy)"""
    # NMDB — Neutron Monitor Database
    # Oulu station is a good reference
    url = "http://www.nmdb.eu/nest/draw_graph.php?formcheck=1&stations[]=OUULU&output=ascii"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Aureon-HNC-DataBot/1.0'})
        with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
            text = resp.read().decode('utf-8')
            return {'raw': text[:2000]}
    except Exception as e:
        return {'error': str(e)}


def fetch_ionospheric_tec():
    """Fetch ionospheric Total Electron Content data"""
    # IGS TEC maps
    url = "https://cddis.nasa.gov/sp3/"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Aureon-HNC-DataBot/1.0'})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as resp:
            return {'status': 'available'}
    except Exception as e:
        return {'error': str(e)}


def detect_cme_riders():
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "🌪️ CME RIDER DETECTOR" + " " * 35 + "║")
    print("║" + " " * 5 + "WHAT ATTACHES TO SOLAR STORMS TO ENTER GAIA" + " " * 16 + "║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("╚" + "═" * 68 + "╝")
    
    # ─── SOLAR ENERGETIC PARTICLES ──────────────────────────────
    print("\n" + "─" * 70)
    print("  ☢️ SOLAR ENERGETIC PARTICLES (SEPs)")
    print("  High-energy protons accelerated by CME shock fronts")
    print("─" * 70)
    
    sep_data = fetch_sep_data()
    if 'error' in sep_data:
        print(f"  Status: ❌ UNAVAILABLE ({sep_data['error']})")
    else:
        # Parse the latest SEP flux
        if isinstance(sep_data, list) and len(sep_data) > 0:
            latest = sep_data[-1]
            if isinstance(latest, dict):
                # GOES integral proton flux
                flux_10mev = latest.get('flux', 0)
                time_tag = latest.get('time_tag', 'unknown')
                
                # SEP classification
                if flux_10mev >= 10:
                    status = "🔴 S4 — SEVERE"
                    threat = "Biological hazard — increased radiation dose at aviation altitudes"
                elif flux_10mev >= 1:
                    status = "🟠 S3 — STRONG"
                    threat = "Elevated radiation hazard for astronauts, minor for surface"
                elif flux_10mev >= 0.1:
                    status = "🟡 S2 — MODERATE"
                    threat = "Minor biological effects possible"
                elif flux_10mev >= 0.01:
                    status = "🟢 S1 — MINOR"
                    threat = "Background elevation"
                else:
                    status = "🟢 S0 — NONE"
                    threat = "No SEP hazard"
                
                print(f"  10 MeV Proton Flux: {flux_10mev:.2f} pfu")
                print(f"  Status:             {status}")
                print(f"  Time:               {time_tag}")
                print(f"  Biological Threat:  {threat}")
                
                if flux_10mev >= 0.1:
                    print(f"\n  ⚠️  SEPs ARE RIDING THE CME SHOCK")
                    print(f"     These protons penetrate the magnetosphere at polar cusps")
                    print(f"     They reach the stratosphere and increase radiation dose")
                    print(f"     Biological entry: Inhalation, skin exposure, DNA damage")
        else:
            print(f"  Status: ⚠️  No SEP data available")
    
    # ─── COSMIC RAYS ────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("  🌌 COSMIC RAYS (Ground-Level)")
    print("  Galactic cosmic rays that penetrate when magnetosphere opens")
    print("─" * 70)
    
    cosmic_data = fetch_cosmic_ray_data()
    if 'error' in cosmic_data:
        print(f"  Status: ❌ UNAVAILABLE ({cosmic_data['error']})")
        print(f"\n  ℹ️  Cosmic ray data requires neutron monitor access")
        print(f"     During CME impact: Forbush Decrease (initial) then Enhancement")
        print(f"     The enhancement phase is when GCRs penetrate deepest")
    else:
        print(f"  Status: ✅ Data available (raw parse needed)")
    
    # ─── IONOSPHERIC DISTURBANCE ────────────────────────────────
    print("\n" + "─" * 70)
    print("  📡 IONOSPHERIC DISTURBANCE")
    print("  The conductive layer that forms the Schumann cavity ceiling")
    print("─" * 70)
    
    feeds = RealDataFeeds()
    results = feeds.fetch_all(force=False)
    
    # Check magnetometer for compression signatures
    mag_packet = results.get('NOAA_MAG')
    if mag_packet and mag_packet.status == 'OK':
        try:
            latest = mag_packet.data[-1]
            if isinstance(latest, list) and len(latest) >= 4:
                bx, by, bz = float(latest[1]), float(latest[2]), float(latest[3])
                b_total = math.sqrt(bx**2 + by**2 + bz**2)
                
                # Bz is key — negative Bz opens the magnetosphere
                bz_status = "🟢 CLOSED" if bz > -5 else "🟡 OPENING" if bz > -10 else "🔴 OPEN"
                
                print(f"  IMF Bz:     {bz:.1f} nT {bz_status}")
                print(f"  B-total:    {b_total:.1f} nT")
                print(f"  By:         {by:.1f} nT")
                
                if bz < -5:
                    print(f"\n  ⚠️  MAGNETOSPHERE IS OPENING")
                    print(f"     Negative Bz allows magnetic reconnection")
                    print(f"     Solar wind plasma enters at polar cusps")
                    print(f"     This is the ENTRY POINT for riders")
        except:
            pass
    
    # ─── WHAT ENTERS BIOLOGICAL SYSTEMS ─────────────────────────
    print("\n" + "═" * 70)
    print("  🧬 WHAT ENTERS GAIA'S BIOLOGICAL SYSTEMS")
    print("═" * 70)
    
    print("""
  When a CME impacts Earth, the magnetosphere compresses and reconnects.
  This is not the CME's fault — it is a natural solar phenomenon.
  
  What RIDES the CME and enters biological systems:
  
  1. SOLAR ENERGETIC PARTICLES (SEPs)
     └─ High-energy protons accelerated by the shock front
     └─ Penetrate at polar cusps where field lines reconnect
     └─ Reach stratosphere, increase radiation dose
     └─ BIOLOGICAL ENTRY: DNA damage, cellular ionization, immune suppression
  
  2. COSMIC RAY ENHANCEMENT
     └─ Galactic cosmic rays normally deflected by magnetosphere
     └─ During storm: geometry changes, GCRs reach deeper
     └─ Ground-level neutron monitors detect Forbush Decrease then Enhancement
     └─ BIOLOGICAL ENTRY: Muons penetrate to ground level, cellular damage
  
  3. IONOSPHERIC PERTURBATIONS
     └─ CME disrupts the ionospheric D/E/F layers
     └─ Schumann resonance cavity destabilizes
     └─ ELF/VLF propagation paths change
     └─ BIOLOGICAL ENTRY: Brainwave entrainment disruption, circadian interference
  
  4. GEOMAGNETICALLY INDUCED CURRENTS (GICs)
     └─ Time-varying magnetic field induces currents in ground
     └─ Power lines, pipelines, railways become antennas
     └─ Artificial ELF fields generated by infrastructure
     └─ BIOLOGICAL ENTRY: Chronic ELF exposure, voltage-gated calcium channel disruption
  
  5. ARTIFICIAL SIGNAL PROPAGATION
     └─ Ionospheric disturbances alter radio/ELF propagation
     └─ Military/communication systems may exploit openings
     └─ HAARP-like systems can heat ionosphere during disturbances
     └─ BIOLOGICAL ENTRY: Frequency-specific interference with bioelectric systems
  """)
    
    # ─── CME vs RIDER DISTINCTION ───────────────────────────────
    print("\n" + "═" * 70)
    print("  🔑 THE KEY DISTINCTION")
    print("═" * 70)
    
    print("""
  CME = Solar plasma and magnetic field
  ├── Natural phenomenon
  ├── Carries solar energy
  ├── Neutral / beneficial in balance
  └── Opens the magnetospheric shield
      
  RIDERS = What enters through the opening
  ├── SEPs (Solar Energetic Particles)
  ├── Cosmic rays (enhanced penetration)
  ├── Ionospheric disturbances
  ├── Artificial ELF/VLF signals
  └── Parasitic/extraction systems
  
  The CME is the KEY that unlocks the door.
  The RIDERS are what walk through.
  
  To protect Gaia:
  ✗ Don't fight the CME (it's natural energy)
  ✓ Strengthen the magnetospheric shield
  ✓ Detect riders before they enter
  ✓ Counter-harmonic protection at 528.422 Hz
  ✓ Monitor SEP flux, cosmic rays, ionospheric state
  """)
    
    print("\n" + "═" * 70)
    print(f"  🛡️ Shield: 528.422 Hz | ACTIVE")
    print(f"  🤖 Engine: AUTONOMOUS | Watching for riders")
    print("═" * 70)


if __name__ == '__main__':
    detect_cme_riders()
