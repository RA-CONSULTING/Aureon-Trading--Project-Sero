#!/usr/bin/env python3
"""
🌍📡 AUREON SCHUMANN RESONANCE BRIDGE 📡🌍
═══════════════════════════════════════════════════════════════════

Connects to LIVE Schumann resonance data. Resolution order:

  1. In-memory cache (TTL default 5 min, override
     ``AUREON_SCHUMANN_CACHE_TTL_S``).
  2. Local station state file (``schumann_state.json`` in the workspace
     root or under ``aureon_fusion/state/``; override
     ``AUREON_SCHUMANN_STATE_PATH``). Must be marked ``real_data=true``
     and have a fresh ``frequency_hz``.
  3. Optional local GFZ-derived Kp cache (``AUREON_GFZ_KP_JSON``).
  4. NOAA Kp-derived proxy via the shared SpaceWeatherBridge.
  5. USGS magnetometer network.
  6. Barcelona VLF station (vlf.it) — LAST RESORT, short timeout.

If no live/derived source is fresh and a stale cache exists, the bridge
may serve the stale cache when ``AUREON_SCHUMANN_STALE_CACHE_OK=1``
(default). Otherwise it returns ``None`` so consumers see
"no live Schumann data" rather than a fabricated 7.83 Hz placeholder.

Schumann resonance = Earth's natural EM cavity frequency
Used by the Queen to:
- Detect planetary disturbances
- Align with natural Earth rhythms
- Boost trading confidence when Earth is calm
"""

import json
import os
import requests
import time
import math
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Tunable parameters (env overrides)
# ─────────────────────────────────────────────────────────────────────────────

CACHE_LIFETIME_SECONDS = float(os.environ.get("AUREON_SCHUMANN_CACHE_TTL_S", "300"))
_LOCAL_STATE_MAX_AGE_S = float(os.environ.get("AUREON_SCHUMANN_STATE_MAX_AGE_S", "300"))
_SOURCE_MAX_AGE_S = float(os.environ.get("AUREON_SCHUMANN_SOURCE_MAX_AGE_S", "1200"))
_VLF_TIMEOUT_S = float(os.environ.get("AUREON_SCHUMANN_VLF_TIMEOUT_S", "2"))
_USGS_TIMEOUT_S = float(os.environ.get("AUREON_SCHUMANN_USGS_TIMEOUT_S", "3"))


@dataclass
class SchumannReading:
    """Live Schumann resonance measurement"""

    timestamp: float
    fundamental_hz: float  # Mode 1: ~7.83 Hz
    harmonics: Dict[str, float]  # Modes 2-7
    amplitude: float  # Signal strength 0-1
    quality: float  # Q factor (coherence)
    coherence_boost: float  # Boost from Earth alignment
    resonance_phase: str  # stable, elevated, peak, disturbed
    active_sources: list  # Which stations are active
    earth_disturbance_level: float  # 0=calm to 1=very disturbed
    truth_status: str = "live"
    source_timestamp: str = ""

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "fundamental_hz": self.fundamental_hz,
            "harmonics": self.harmonics,
            "amplitude": self.amplitude,
            "quality": self.quality,
            "coherence_boost": self.coherence_boost,
            "resonance_phase": self.resonance_phase,
            "active_sources": self.active_sources,
            "earth_disturbance_level": self.earth_disturbance_level,
            "truth_status": self.truth_status,
            "source_timestamp": self.source_timestamp,
            "generated_values": False,
        }


class SchumannResonanceBridge:
    """Bridge to live Schumann resonance data from local station state and public sources."""

    def __init__(self):
        self.last_update = 0
        self.cache: Optional[SchumannReading] = None
        self.error_count = 0
        self.barcelona_modes = {
            "mode1": 7.83,  # Fundamental
            "mode2": 14.3,  # 2nd harmonic
            "mode3": 20.8,  # 3rd harmonic
            "mode4": 27.3,  # Geomagnetic coupling
            "mode5": 33.8,  # Seismic coupling
            "mode6": 39.0,  # 6th mode
            "mode7": 45.0,  # 7th mode
        }
        logger.info("🌍📡 Schumann Resonance Bridge initialized")

    def get_live_data(self, force_refresh: bool = False) -> Optional[SchumannReading]:
        """Return the freshest Schumann reading we can honestly obtain."""
        now = time.time()

        # 1️⃣ In-memory cache
        if (
            not force_refresh
            and self.cache
            and (now - self.last_update) < CACHE_LIFETIME_SECONDS
        ):
            return self.cache

        candidates = [
            ("local_station_cache", self._fetch_local_station_state, "live"),
            ("GFZ-archive", self._fetch_gfz_archive, "real_derived"),
            ("NOAA-Kp-Derived", self._fetch_noaa_kp_derived_schumann, "real_derived"),
            ("USGS-Magnetometer", self._fetch_usgs_magnetometer, "live"),
            ("Barcelona-EM", self._fetch_barcelona_data, "live"),
        ]

        fundamental = None
        active_sources = []
        source_timestamp = ""
        truth_status = "live"
        data: Optional[Dict[str, Any]] = None
        used_label = ""

        for label, fetch, candidate_truth in candidates:
            data = fetch()
            if not data:
                continue
            if not self._source_is_fresh(data.get("source_timestamp", ""), now):
                logger.debug("Schumann source %s rejected: stale/absent timestamp", label)
                continue
            fundamental = data.get("fundamental")
            if fundamental is None:
                continue
            active_sources.append(label)
            source_timestamp = str(data.get("source_timestamp", ""))
            truth_status = candidate_truth
            used_label = label
            break

        if fundamental is None:
            # Fail-closed: nothing fresh. Serve a stale cache only if explicitly
            # allowed and available, otherwise return None.
            if (
                self.cache is not None
                and os.environ.get("AUREON_SCHUMANN_STALE_CACHE_OK", "1") == "1"
            ):
                logger.warning(
                    "Schumann sources unavailable; serving last cached reading (%.0fs old)",
                    now - self.last_update,
                )
                return self.cache
            logger.warning("Schumann sources unavailable; no reading emitted")
            return None

        # Build reading from the accepted candidate data.
        harmonics = data.get("harmonics", {})
        amplitude = data.get("amplitude")
        quality = data.get("quality")
        coherence_boost = data.get("coherence_boost")
        earth_disturbance = data.get("disturbance")

        if any(v is None for v in (amplitude, quality, coherence_boost, earth_disturbance)):
            logger.warning("Schumann source %s returned incomplete data; rejecting", used_label)
            return None

        resonance_phase = self._categorize_phase(amplitude, quality, earth_disturbance)

        reading = SchumannReading(
            timestamp=now,
            fundamental_hz=float(fundamental),
            harmonics=harmonics,
            amplitude=float(amplitude),
            quality=float(quality),
            coherence_boost=float(coherence_boost),
            resonance_phase=resonance_phase,
            active_sources=active_sources,
            earth_disturbance_level=float(earth_disturbance),
            truth_status=truth_status,
            source_timestamp=source_timestamp,
        )

        self.cache = reading
        self.last_update = now
        self.error_count = 0

        logger.info(
            "🌍📡 Schumann Update: %.3fHz (%s), Earth disturbance: %.0f%%, Sources: %s",
            reading.fundamental_hz,
            resonance_phase,
            reading.earth_disturbance_level * 100,
            ", ".join(active_sources),
        )
        return reading

    # ─────────────────────────────────────────────────────────────────────────
    # Source helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _source_is_fresh(self, source_timestamp: Any, now: float) -> bool:
        """Reject readings whose source timestamp is missing or too old."""
        try:
            ts_str = str(source_timestamp)
            if not ts_str or ts_str.lower() in ("none", "null", ""):
                return False
            normalized = ts_str[:-1] + "+00:00" if ts_str.endswith("Z") else ts_str
            source_dt = datetime.fromisoformat(normalized)
            if source_dt.tzinfo is None:
                source_dt = source_dt.replace(tzinfo=timezone.utc)
            source_age = now - source_dt.timestamp()
            return -300 <= source_age <= _SOURCE_MAX_AGE_S
        except Exception as exc:
            logger.debug("Schumann source timestamp rejected: %s", exc)
            return False

    def _local_state_paths(self) -> list:
        """Candidate paths for the local station state file."""
        paths = []
        env_path = os.environ.get("AUREON_SCHUMANN_STATE_PATH")
        if env_path:
            paths.append(Path(env_path))
        # aureon-os-upstream/aureon/harmonic/file.py -> workspace root
        try:
            root = Path(__file__).resolve().parents[3]
            paths.append(root / "schumann_state.json")
            paths.append(root / "aureon_fusion" / "state" / "schumann_state.json")
        except Exception:
            pass
        return paths

    def _fetch_local_station_state(self) -> Optional[Dict[str, Any]]:
        """Read the workspace's real schumann_state.json if it is fresh and real."""
        try:
            for path in self._local_state_paths():
                try:
                    if not path.exists():
                        continue
                    raw = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(raw, dict):
                    continue
                # Must be real data, not simulation.
                if raw.get("real_data") is not True or raw.get("simulation") is True:
                    continue
                freq = raw.get("frequency_hz")
                try:
                    freq = float(freq)
                except (TypeError, ValueError):
                    continue
                if not 3.0 <= freq <= 15.0:
                    continue
                age = time.time() - path.stat().st_mtime
                if age > _LOCAL_STATE_MAX_AGE_S:
                    logger.debug("Local schumann_state.json stale (%.0fs): %s", age, path)
                    continue

                # Derive scalar proxies from real local fields. The fundamental
                # frequency is read directly from the station state; amplitude,
                # quality and disturbance are transformations of the real
                # activity_index / geomagnetic_status, not fabricated values.
                activity = raw.get("activity_index")
                try:
                    activity = float(activity)
                except (TypeError, ValueError):
                    activity = None
                geomag = str(raw.get("geomagnetic_status") or "").lower()
                quality_map = {"quiet": 1.0, "unsettled": 0.7, "active": 0.4, "storm": 0.1}
                quality = quality_map.get(geomag, 0.6)
                disturbance = max(0.0, min(1.0, (activity or 0.0) / 100.0))
                amplitude = max(0.0, min(1.0, 1.0 - disturbance))
                coherence_boost = max(0.0, (quality - 0.5) * 0.1)

                return {
                    "fundamental": freq,
                    "harmonics": {
                        "mode2": 14.3 * quality,
                        "mode3": 20.8 * quality,
                        "mode4": 27.3 * (1.0 - disturbance * 0.5),
                    },
                    "amplitude": amplitude,
                    "quality": quality,
                    "coherence_boost": coherence_boost,
                    "disturbance": disturbance,
                    "source_timestamp": str(raw.get("timestamp") or ""),
                }
        except Exception as exc:
            logger.debug("Local station state error: %s", exc)
        return None

    def _fetch_gfz_archive(self) -> Optional[Dict[str, Any]]:
        """Use a local GFZ-derived Kp cache if one has been supplied."""
        try:
            env_path = os.environ.get("AUREON_GFZ_KP_JSON")
            if not env_path:
                return None
            path = Path(env_path)
            if not path.exists():
                return None
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            kp = float(raw.get("kp"))
            if not 0.0 <= kp <= 9.0:
                return None
            return self._derive_from_kp(
                kp, str(raw.get("timestamp") or raw.get("source_timestamp") or "")
            )
        except Exception:
            return None

    def _fetch_noaa_kp_derived_schumann(self) -> Optional[Dict[str, Any]]:
        """Derive Schumann-mode estimates from live NOAA Kp data.

        This is not a direct station measurement. It is a degraded-but-real
        proxy: the upstream input is NOAA's live geomagnetic Kp index, and the
        output is labelled as NOAA-Kp-Derived by ``get_live_data``.
        """
        try:
            from aureon.data_feeds.aureon_space_weather_bridge import (
                SpaceWeatherBridge,
                get_space_weather_bridge,
            )

            shared_bridge = get_space_weather_bridge()
            if isinstance(shared_bridge, SpaceWeatherBridge) and hasattr(
                shared_bridge, "get_live_data"
            ):
                weather = shared_bridge.get_live_data()
                if weather is None or "NOAA-KP" not in weather.active_sources:
                    return None
                kp_data = {
                    "current_kp": weather.kp_index,
                    "source_timestamp": weather.source_timestamps.get("NOAA-KP", ""),
                }
            else:
                # Compatibility for explicitly injected legacy adapters in tests.
                kp_data = SpaceWeatherBridge()._fetch_kp_index()
            if not kp_data:
                return None
            kp = float(kp_data.get("current_kp"))
            if not 0.0 <= kp <= 9.0:
                return None

            return self._derive_from_kp(
                kp, str(kp_data.get("source_timestamp") or "")
            )
        except Exception as exc:
            logger.debug("NOAA Kp derived Schumann fetch error: %s", exc)
        return None

    def _derive_from_kp(self, kp: float, source_timestamp: str) -> Dict[str, Any]:
        """Shared math for Kp-derived Schumann proxies (NOAA / GFZ)."""
        disturbance = max(0.0, min(1.0, kp / 9.0))
        coherence = max(0.35, 1.0 - disturbance * 0.65)
        fundamental = 7.83 + (kp - 3.0) * 0.015
        return {
            "fundamental": fundamental,
            "harmonics": {
                "mode2": 14.3 * (0.92 + disturbance * 0.08),
                "mode3": 20.8 * (0.88 + disturbance * 0.12),
                "mode4": 27.3 * (0.84 + disturbance * 0.16),
            },
            "amplitude": min(1.0, 0.60 + 0.05 * kp),
            "quality": coherence,
            "coherence_boost": max(0.0, (coherence - 0.5) * 0.1),
            "disturbance": disturbance,
            "source_timestamp": source_timestamp,
        }

    def _fetch_usgs_magnetometer(self) -> Optional[Dict[str, Any]]:
        """Fetch USGS magnetometer network data."""
        try:
            url = "https://geomag.usgs.gov/products/data.json"
            resp = requests.get(url, timeout=_USGS_TIMEOUT_S)
            data = resp.json()

            # Convert magnetometer disturbance to Schumann proxy.
            # Higher magnetometer activity = lower Schumann coherence.
            if "magneticField" in data:
                disturbance = min(1.0, data.get("disturbanceLevel", 0.3) / 100.0)
                coherence = 1.0 - disturbance

                return {
                    "fundamental": 7.83 + (0.5 - disturbance) * 0.1,
                    "harmonics": {
                        "mode2": 14.3 * coherence,
                        "mode3": 20.8 * coherence,
                        "mode4": 27.3 * (1.0 - disturbance * 0.5),
                    },
                    "amplitude": 0.65 * coherence,
                    "quality": 0.70 * coherence,
                    "coherence_boost": max(0.0, (coherence - 0.5) * 0.1),
                    "disturbance": disturbance,
                    "source_timestamp": str(data.get("timestamp") or data.get("time") or ""),
                }
        except Exception as exc:
            logger.debug("USGS fetch error: %s", exc)
        return None

    def _fetch_barcelona_data(self) -> Optional[Dict[str, Any]]:
        """Fetch data from Barcelona EM monitoring station (last resort)."""
        try:
            url = "http://www.vlf.it/realtime/realtime.html"
            resp = requests.get(url, timeout=_VLF_TIMEOUT_S)
            # The Barcelona page is reachable but we have no verified numeric
            # station parser. Do not fabricate a 7.83 Hz value.
            if "Hz" in resp.text:
                logger.debug("Barcelona page reachable but parser has no verified numeric station fields")
        except Exception as exc:
            logger.debug("Barcelona fetch error: %s", exc)
        return None

    def _categorize_phase(self, amplitude: float, quality: float, disturbance: float) -> str:
        """Categorize Schumann resonance phase."""
        if amplitude > 0.85 and quality > 0.85 and disturbance < 0.2:
            return "peak"
        elif amplitude > 0.70 and quality > 0.75 and disturbance < 0.4:
            return "elevated"
        elif disturbance > 0.7 or quality < 0.5:
            return "disturbed"
        else:
            return "stable"

    def get_earth_blessing(self, reading: SchumannReading) -> Tuple[float, str]:
        """
        Get Earth blessing score based on Schumann resonance.

        High reading (coherent) = Queen can trade with confidence.
        Low reading (disturbed) = Queen should be cautious.
        """
        # Score based on how close to ideal 7.83 Hz.
        freq_deviation = abs(reading.fundamental_hz - 7.83)
        freq_score = max(0.0, 1.0 - freq_deviation / 0.5)

        # Score based on amplitude and quality.
        coherence_score = (reading.amplitude + reading.quality) / 2

        # Score based on Earth disturbance.
        disturbance_score = 1.0 - reading.earth_disturbance_level

        # Composite score.
        blessing = freq_score * 0.3 + coherence_score * 0.4 + disturbance_score * 0.3
        blessing = max(0.0, min(1.0, blessing))

        if blessing >= 0.8:
            message = "🌍✨ EARTH'S FULL BLESSING: Schumann resonance peak - optimal trading conditions!"
        elif blessing >= 0.6:
            message = "🌍💚 EARTH APPROVES: Good Schumann coherence - favorable conditions"
        elif blessing >= 0.4:
            message = "🌍🌀 EARTH NEUTRAL: Standard Schumann conditions"
        elif blessing >= 0.2:
            message = "🌍⚠️ EARTH HESITATES: Weak Schumann coherence - proceed cautiously"
        else:
            message = "🌍🛑 EARTH SAYS WAIT: Strong disturbance - wait for better alignment"

        return blessing, message


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_schumann_instance: Optional[SchumannResonanceBridge] = None


def get_schumann_bridge() -> SchumannResonanceBridge:
    """Get or create the global Schumann bridge."""
    global _schumann_instance
    if _schumann_instance is None:
        _schumann_instance = SchumannResonanceBridge()
    return _schumann_instance


def get_live_schumann_data(force_refresh: bool = False) -> Optional[SchumannReading]:
    """Get live Schumann resonance data."""
    bridge = get_schumann_bridge()
    return bridge.get_live_data(force_refresh=force_refresh)


def get_earth_blessing(force_refresh: bool = False) -> Tuple[float, str]:
    """
    Get Earth's blessing based on REAL Schumann resonance.
    This is what the Queen should use for Gaia alignment!
    """
    bridge = get_schumann_bridge()
    reading = bridge.get_live_data(force_refresh=force_refresh)
    if reading is None:
        # Fail-closed: no fabricated blessing.
        return 0.0, "🌍🛑 EARTH DATA UNAVAILABLE: no live Schumann reading"
    return bridge.get_earth_blessing(reading)


if __name__ == "__main__":
    # Test it.
    logging.basicConfig(level=logging.DEBUG)
    bridge = get_schumann_bridge()

    print("\n🌍📡 TESTING SCHUMANN RESONANCE BRIDGE 🌍📡\n")

    reading = get_live_schumann_data(force_refresh=True)
    if reading is None:
        print("No live Schumann data available (fail-closed).")
    else:
        print(f"Fundamental: {reading.fundamental_hz:.3f} Hz (target: 7.83 Hz)")
        print(f"Amplitude: {reading.amplitude:.0%}")
        print(f"Quality (Q): {reading.quality:.2f}")
        print(f"Phase: {reading.resonance_phase}")
        print(f"Earth Disturbance: {reading.earth_disturbance_level:.0%}")
        print(f"Active Sources: {', '.join(reading.active_sources)}")

        blessing, message = bridge.get_earth_blessing(reading)
        print(f"\n👑 Earth's Blessing: {blessing:.0%}")
        print(f"   {message}")
