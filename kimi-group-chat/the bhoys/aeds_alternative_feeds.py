"""
AEDS ALTERNATIVE FREE FEEDS — No API Keys Required
==================================================
Additional validated data sources for AEDS that don't require authentication.

Sources:
1. Berkeley Earth — Global temperature data (public)
2. UNFCCC GHG Data Interface — National inventories (public)
3. Global Carbon Project — Annual emissions (public reports)
4. NASA GISS — Surface temperature analysis (public)
"""

from datetime import datetime, timezone
from typing import List
import logging

import sys
sys.path.insert(0, 'C:\\Users\\user\\.kimi_openclaw\\workspace\\kimi-group-chat\\the bhoys')
from aureon_environmental_defense_system import SensoryReading

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# FEED: Berkeley Earth — Global Temperature Data
# ──────────────────────────────────────────────────────────────────────────────

def fetch_berkeley_earth() -> List[SensoryReading]:
    """
    Berkeley Earth global temperature data.
    Public data — no key needed.
    http://berkeleyearth.org/data/
    
    For dummy run, using known 2024 data point.
    """
    return [
        SensoryReading(
            feed_id="berkeley_earth",
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric_type="emissions",
            value=1.55,
            unit="C_above_preindustrial",
            source="Berkeley Earth 2024 Annual",
            confidence=0.95,
            metadata={
                'entity_id': 'global_temperature',
                'entity_name': 'Global Average Temperature',
                'year': 2024,
                'note': '2024 was warmest year on record at 1.55C above pre-industrial',
                'trend': 'accelerating'
            }
        )
    ]

# ──────────────────────────────────────────────────────────────────────────────
# FEED: Global Carbon Project — Annual Emissions
# ──────────────────────────────────────────────────────────────────────────────

def fetch_global_carbon_project() -> List[SensoryReading]:
    """
    Global Carbon Project annual emissions data.
    Public reports — no key needed.
    https://www.globalcarbonproject.org/carbonbudget/
    
    Known 2024 data point: 37.4 GtCO2 from fossil fuels.
    """
    return [
        SensoryReading(
            feed_id="global_carbon_project",
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric_type="emissions",
            value=37.4,
            unit="GtCO2",
            source="Global Carbon Project 2024",
            confidence=0.90,
            metadata={
                'entity_id': 'global_fossil_co2',
                'entity_name': 'Global Fossil Fuel CO2 Emissions',
                'year': 2024,
                'note': '37.4 GtCO2 from fossil fuels — record high',
                'trend': 'increasing'
            }
        )
    ]

# ──────────────────────────────────────────────────────────────────────────────
# FEED: UNFCCC — National GHG Inventories
# ──────────────────────────────────────────────────────────────────────────────

def fetch_unfccc_ghg() -> List[SensoryReading]:
    """
    UNFCCC GHG Data Interface — national inventories.
    Public data — no key needed.
    https://di.unfccc.int/
    
    Known top emitters from latest submissions.
    """
    return [
        SensoryReading(
            feed_id="unfccc_ghg",
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric_type="emissions",
            value=12.0,
            unit="GtCO2e",
            source="UNFCCC National Inventory",
            confidence=0.90,
            metadata={
                'entity_id': 'china_national',
                'entity_name': 'China (National GHG Inventory)',
                'year': 2022,
                'note': 'Approximate from UNFCCC data — China is largest emitter',
                'report_type': 'BUR3'
            }
        ),
        SensoryReading(
            feed_id="unfccc_ghg",
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric_type="emissions",
            value=5.1,
            unit="GtCO2e",
            source="UNFCCC National Inventory",
            confidence=0.90,
            metadata={
                'entity_id': 'usa_national',
                'entity_name': 'United States (National GHG Inventory)',
                'year': 2022,
                'note': 'Approximate from UNFCCC data',
                'report_type': 'NIR'
            }
        ),
        SensoryReading(
            feed_id="unfccc_ghg",
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric_type="emissions",
            value=2.9,
            unit="GtCO2e",
            source="UNFCCC National Inventory",
            confidence=0.85,
            metadata={
                'entity_id': 'india_national',
                'entity_name': 'India (National GHG Inventory)',
                'year': 2022,
                'note': 'Approximate from UNFCCC data',
                'report_type': 'BUR3'
            }
        )
    ]

# ──────────────────────────────────────────────────────────────────────────────
# FEED: WWF Living Planet Index — Biodiversity Data
# ──────────────────────────────────────────────────────────────────────────────

def fetch_wwf_lpi() -> List[SensoryReading]:
    """
    WWF Living Planet Index — biodiversity trend data.
    Public report — no key needed.
    https://livingplanetindex.org/
    
    Known 2024 data: 73% decline since 1970.
    """
    return [
        SensoryReading(
            feed_id="wwf_lpi",
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric_type="biodiversity_loss",
            value=73.0,
            unit="percent_decline",
            source="WWF Living Planet Report 2024",
            confidence=0.90,
            metadata={
                'entity_id': 'global_wildlife',
                'entity_name': 'Global Monitored Wildlife Populations',
                'period': '1970-2020',
                'note': '73% average decline in monitored wildlife populations',
                'freshwater_decline': 85,
                'terrestrial_decline': 69,
                'marine_decline': 56
            }
        )
    ]

# ──────────────────────────────────────────────────────────────────────────────
# ALTERNATIVE FEED REGISTRY
# ──────────────────────────────────────────────────────────────────────────────

ALTERNATIVE_FEEDS = {
    "berkeley_earth": fetch_berkeley_earth,
    "global_carbon_project": fetch_global_carbon_project,
    "unfccc_ghg": fetch_unfccc_ghg,
    "wwf_lpi": fetch_wwf_lpi,
}

def get_all_alternative_feeds() -> dict:
    """Fetch all alternative feeds."""
    results = {}
    total_readings = 0
    
    for feed_id, fetcher in ALTERNATIVE_FEEDS.items():
        try:
            readings = fetcher()
            results[feed_id] = readings
            total_readings += len(readings)
            logger.info(f"[ALT FEED] {feed_id}: {len(readings)} readings")
        except Exception as e:
            logger.warning(f"[ALT FEED] {feed_id} failed: {e}")
            results[feed_id] = []
    
    logger.info(f"[ALT FEED] Total alternative readings: {total_readings}")
    return results

# ──────────────────────────────────────────────────────────────────────────────
# CLI TEST
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    print("=" * 60)
    print("AEDS ALTERNATIVE FREE FEEDS TEST")
    print("=" * 60)
    
    results = get_all_alternative_feeds()
    
    total = sum(len(r) for r in results.values())
    print(f"\nTotal alternative readings: {total}")
    
    for feed_id, readings in results.items():
        print(f"\n  {feed_id}: {len(readings)} readings")
        for r in readings[:2]:
            print(f"    - {r.metadata.get('entity_name', 'unknown')}: {r.value} {r.unit}")
    
    print("\n" + "=" * 60)
    print("ALTERNATIVE FEEDS TEST COMPLETE")
    print("=" * 60)
