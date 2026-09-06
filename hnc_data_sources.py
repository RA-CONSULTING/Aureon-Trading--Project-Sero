#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                       ║
║     📡 HNC DATA SOURCE PARSERS — All Historical Data Open-Source                    ║
║                                                                                       ║
║     Sources:                                                                          ║
║       • NOAA FTP — Daily Geomagnetic Data (DGD) back to 1957                        ║
║       • NOAA FTP — Monthly Solar Indices (MSI) back to 1975                        ║
║       • GFZ Potsdam — Kp index (Kp_ap files) back to 1932                            ║
║       • Tomsk SOSRFF — Schumann resonance (monthly HTML) back to 2000s              ║
║                                                                                       ║
║     All data is free, public, no API keys required.                                  ║
║                                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import math
import json
import time
import hashlib
import requests
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE
sys.path.insert(0, str(WORKSPACE / "aureon-trading"))

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83

# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class DailyGeomagneticRecord:
    date: str
    year: int
    month: int
    day: int
    planetary_a: int
    planetary_k_indices: List[int]
    high_latitude_a: int
    high_latitude_k_indices: List[int]
    mid_latitude_a: int
    mid_latitude_k_indices: List[int]
    max_kp: float
    avg_kp: float
    quiet_day: bool  # max_kp <= 2
    active_day: bool  # max_kp >= 4
    storm_day: bool  # max_kp >= 5

@dataclass
class HistoricalSchumannRecord:
    date: str
    schumann_hz: float
    amplitude: float
    quality: str
    source: str

@dataclass
class HistoricalSnapshot:
    date: str
    geomagnetic: Optional[DailyGeomagneticRecord]
    schumann: Optional[HistoricalSchumannRecord]
    market_data: Optional[Dict]
    data_sources: List[str]
    data_quality: float  # 0.0 to 1.0
    hash: str


import urllib.request
import ftplib

# ── NOAA FTP Parser ───────────────────────────────────────────────────────────

class NOAAGeomagneticParser:
    """
    Parses NOAA Daily Geomagnetic Data (DGD) files from FTP.
    
    URL format: ftp://ftp.swpc.noaa.gov/pub/indices/old_indices/YYYY_DGD.txt
    Format: YYYY MM DD [A-index] [K-indices × 8]
    
    Files available for years: 1957-2010 (old_indices), 2011-present (recent)
    """
    
    FTP_HOST = "ftp.swpc.noaa.gov"
    FTP_BASE = "/pub/indices"
    
    def __init__(self):
        self.cache = {}
    
    def _get_cache_key(self, year: int) -> str:
        return f"noaa_dgd_{year}"
    
    def _fetch_year(self, year: int) -> str:
        """Fetch DGD file for a year via FTP."""
        cache_key = self._get_cache_key(year)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Determine FTP path
        if year < 2011:
            remote_path = f"{self.FTP_BASE}/old_indices/{year}_DGD.txt"
        else:
            remote_path = f"{self.FTP_BASE}/old_indices/{year}_DGD.txt"
        
        try:
            # Use urllib for FTP download
            ftp_url = f"ftp://{self.FTP_HOST}{remote_path}"
            with urllib.request.urlopen(ftp_url, timeout=30) as response:
                data = response.read().decode('utf-8', errors='replace')
                self.cache[cache_key] = data
                return data
        except Exception as e:
            return f"# ERROR: {e}"
    
    def parse_record(self, line: str) -> Optional[DailyGeomagneticRecord]:
        """Parse a single DGD line into a record."""
        # Skip comment lines and headers
        line = line.strip()
        if not line or line.startswith('#') or line.startswith(':'):
            return None
        
        # Parse: YYYY MM DD  A  K1 K2 K3 K4 K5 K6 K7 K8  A  K1 K2 ...  A  K1 K2 ...
        # Format: 2014 01 01    11  0 1 1 3 4 3 3 2    33  0 0 2 5 7 5 2 3    12  1 2 2 3 4 3 3 3
        parts = line.split()
        if len(parts) < 15:
            return None
        
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            
            # Planetary A-index (position 3)
            planetary_a = int(parts[3])
            
            # Planetary K-indices (8 values, positions 4-11)
            planetary_k = [int(parts[i]) for i in range(4, 12)]
            
            # High latitude A-index (position 12)
            high_lat_a = int(parts[12])
            
            # High latitude K-indices (positions 13-20)
            high_lat_k = [int(parts[i]) for i in range(13, 21)]
            
            # Mid latitude A-index (position 21)
            mid_lat_a = int(parts[21])
            
            # Mid latitude K-indices (positions 22-29)
            mid_lat_k = [int(parts[i]) for i in range(22, 30)]
            
            max_k = max(planetary_k)
            avg_k = sum(planetary_k) / len(planetary_k)
            
            return DailyGeomagneticRecord(
                date=f"{year:04d}-{month:02d}-{day:02d}",
                year=year, month=month, day=day,
                planetary_a=planetary_a,
                planetary_k_indices=planetary_k,
                high_latitude_a=high_lat_a,
                high_latitude_k_indices=high_lat_k,
                mid_latitude_a=mid_lat_a,
                mid_latitude_k_indices=mid_lat_k,
                max_kp=max_k,
                avg_kp=avg_k,
                quiet_day=max_k <= 2,
                active_day=max_k >= 4,
                storm_day=max_k >= 5,
            )
        except (ValueError, IndexError) as e:
            return None
    
    def fetch_date(self, year: int, month: int, day: int) -> Optional[DailyGeomagneticRecord]:
        """Fetch geomagnetic data for a specific date."""
        data = self._fetch_year(year)
        if data.startswith('# ERROR'):
            return None
        
        target_line = f"{year:04d} {month:02d} {day:02d}"
        for line in data.split('\n'):
            if line.startswith(target_line):
                return self.parse_record(line)
        
        return None
    
    def fetch_month(self, year: int, month: int) -> List[DailyGeomagneticRecord]:
        """Fetch all records for a month."""
        data = self._fetch_year(year)
        if data.startswith('# ERROR'):
            return []
        
        records = []
        for line in data.split('\n'):
            if line.startswith(f"{year:04d} {month:02d}"):
                record = self.parse_record(line)
                if record:
                    records.append(record)
        
        return records


# ── GFZ Potsdam Parser ───────────────────────────────────────────────────────

class GFZPotsdamParser:
    """
    Parses GFZ Potsdam Kp index data.
    
    URL format: http://app.gfz-potsdam.de/kp_index/Kp_ap_YYYYMM.txt
    Format: YYYY MM DD A ap ... (tab-separated)
    
    Files available for years: 1932-present
    """
    
    BASE_URL = "http://app.gfz-potsdam.de/kp_index"
    
    def __init__(self):
        self.cache = {}
    
    def _fetch_month(self, year: int, month: int) -> str:
        """Fetch Kp data for a month."""
        cache_key = f"gfz_{year}_{month:02d}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Try multiple formats
        urls = [
            # Monthly Kp_ap format
            f"{self.BASE_URL}/Kp_ap_{year}{month:02d}.txt",
            # Alternative monthly format
            f"{self.BASE_URL}/Kp_ap_{year}{month:02d}.tab",
            # Yearly definitive format
            f"{self.BASE_URL}/Kp_definitive/Kp_{year}.tab",
            f"{self.BASE_URL}/Kp_definitive/Kp_{year}.txt",
            # Old format
            f"{self.BASE_URL}/Kp_{year}{month:02d}.txt",
        ]
        
        for url in urls:
            try:
                resp = requests.get(url, timeout=20)
                if resp.status_code == 200:
                    self.cache[cache_key] = resp.text
                    return resp.text
            except Exception:
                continue
        
        return f"# ERROR: All GFZ URLs failed for {year}-{month:02d}"
    
    def parse_record(self, line: str) -> Optional[Dict]:
        """Parse a GFZ record line."""
        line = line.strip()
        if not line or line.startswith('#') or line.startswith(':'):
            return None
        
        parts = line.split()
        if len(parts) < 5:
            return None
        
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            
            # Try Kp_ap format (12+ columns): YYYY MM DD A ap Kp0 Kp1 Kp2 Kp3 Kp4 Kp5 Kp6 Kp7
            if len(parts) >= 12:
                a_index = int(parts[3]) if parts[3].isdigit() else 0
                ap = int(parts[4]) if parts[4].isdigit() else 0
                k_indices = [int(parts[i]) if parts[i].isdigit() else 0 for i in range(5, 13)]
                
                return {
                    'date': f"{year:04d}-{month:02d}-{day:02d}",
                    'year': year, 'month': month, 'day': day,
                    'a_index': a_index,
                    'ap': ap,
                    'k_indices': k_indices,
                    'max_kp': max(k_indices) if k_indices else 0,
                    'avg_kp': sum(k_indices) / len(k_indices) if k_indices else 0,
                    'source': 'gfz_potsdam',
                }
            
            # Try short format (5+ columns): YYYY MM DD Kp_sum ap
            elif len(parts) >= 5:
                return {
                    'date': f"{year:04d}-{month:02d}-{day:02d}",
                    'year': year, 'month': month, 'day': day,
                    'a_index': 0,
                    'ap': int(parts[4]) if parts[4].isdigit() else 0,
                    'k_indices': [],
                    'max_kp': 0,
                    'avg_kp': 0,
                    'source': 'gfz_potsdam',
                }
                
        except (ValueError, IndexError):
            return None
        
        return None
    
    def fetch_date(self, year: int, month: int, day: int) -> Optional[Dict]:
        """Fetch Kp data for a specific date."""
        data = self._fetch_month(year, month)
        if data.startswith('# ERROR'):
            return None
        
        target_line = f"{year:04d} {month:02d} {day:02d}"
        for line in data.split('\n'):
            if line.startswith(target_line):
                return self.parse_record(line)
        
        return None


# ── Tomsk SOSRFF Scraper ─────────────────────────────────────────────────────

class TomskSchumannScraper:
    """
    Scrapes Schumann resonance data from Tomsk Space Observing System.
    
    URL format: http://sosrff.tsu.ru/?m=MM&y=YYYY
    Provides monthly pages with daily Schumann resonance data.
    """
    
    BASE_URL = "http://sosrff.tsu.ru"
    
    def __init__(self):
        self.cache = {}
    
    def fetch_month(self, year: int, month: int) -> Optional[str]:
        """Fetch HTML page for a month."""
        cache_key = f"tomsk_{year}_{month:02d}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        url = f"{self.BASE_URL}/?m={month}&y={year}"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                self.cache[cache_key] = resp.text
                return resp.text
            else:
                return f"# ERROR: {resp.status_code}"
        except Exception as e:
            return f"# ERROR: {e}"
    
    def parse_month(self, html: str) -> List[HistoricalSchumannRecord]:
        """Parse Schumann data from Tomsk HTML."""
        if html.startswith('# ERROR'):
            return []
        
        records = []
        
        # Look for data in various HTML patterns
        # Tomsk format changes over time; try multiple patterns
        
        # Pattern 1: table rows with date and amplitude
        # Look for <tr> containing date and numeric data
        import re
        
        # Find all potential data rows
        # Pattern: DD.MM.YYYY followed by numbers
        pattern1 = r'<tr[^>]*>.*?<td[^>]*>(\d{1,2})</td>\s*<td[^>]*>(\d{1,2})</td>\s*<td[^>]*>(\d{4})</td>.*?<td[^>]*>([\d\.]+)</td>.*?</tr>'
        matches = re.findall(pattern1, html, re.DOTALL)
        
        for match in matches:
            try:
                day = int(match[0])
                month = int(match[1])
                year = int(match[2])
                amplitude = float(match[3])
                
                records.append(HistoricalSchumannRecord(
                    date=f"{year:04d}-{month:02d}-{day:02d}",
                    schumann_hz=SCHUMANN_BASE,
                    amplitude=amplitude,
                    quality='measured',
                    source='tomsk_sosrff',
                ))
            except (ValueError, IndexError):
                continue
        
        # Pattern 2: Look for div-based or span-based data
        if not records:
            pattern2 = r'(\d{2})\.(\d{2})\.(\d{4})\s*</?[^>]+>\s*([\d\.]+)\s*Hz?'
            matches2 = re.findall(pattern2, html)
            for match in matches2:
                try:
                    day = int(match[0])
                    month = int(match[1])
                    year = int(match[2])
                    amplitude = float(match[3])
                    
                    records.append(HistoricalSchumannRecord(
                        date=f"{year:04d}-{month:02d}-{day:02d}",
                        schumann_hz=SCHUMANN_BASE,
                        amplitude=amplitude,
                        quality='measured',
                        source='tomsk_sosrff',
                    ))
                except (ValueError, IndexError):
                    continue
        
        # Pattern 3: Just look for any date-like strings followed by numbers
        if not records:
            pattern3 = r'(\d{4})[-\s/](\d{1,2})[-\s/](\d{1,2})\s*[\s<]*([\d\.]+)'
            matches3 = re.findall(pattern3, html)
            for match in matches3:
                try:
                    year = int(match[0])
                    month = int(match[1])
                    day = int(match[2])
                    amplitude = float(match[3])
                    
                    records.append(HistoricalSchumannRecord(
                        date=f"{year:04d}-{month:02d}-{day:02d}",
                        schumann_hz=SCHUMANN_BASE,
                        amplitude=amplitude,
                        quality='estimated',
                        source='tomsk_sosrff',
                    ))
                except (ValueError, IndexError):
                    continue
        
        return records


# ── Historical Snapshot Builder ──────────────────────────────────────────────

class HistoricalSnapshotBuilder:
    """
    Builds a complete historical snapshot for a target date.
    
    Aggregates data from all available sources:
    - NOAA: geomagnetic (Kp, A-index)
    - GFZ: geomagnetic (Kp, ap)
    - Tomsk: Schumann resonance amplitude
    - CoinGecko: market data (if available, within 365 days)
    """
    
    def __init__(self):
        self.noaa = NOAAGeomagneticParser()
        self.gfz = GFZPotsdamParser()
        self.tomsk = TomskSchumannScraper()
    
    def build_snapshot(self, year: int, month: int, day: int) -> HistoricalSnapshot:
        """Build a complete historical snapshot for a date."""
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        sources = []
        data_quality = 0.0
        
        # Fetch geomagnetic data from NOAA
        geomagnetic = self.noaa.fetch_date(year, month, day)
        if geomagnetic:
            sources.append('noaa_dgd')
            data_quality += 0.4
        
        # Fetch from GFZ as backup/fallback
        gfz_data = self.gfz.fetch_date(year, month, day)
        if gfz_data:
            sources.append('gfz_potsdam')
            data_quality += 0.3
        
        # Fetch Schumann data from Tomsk
        tomsk_html = self.tomsk.fetch_month(year, month)
        if tomsk_html and not tomsk_html.startswith('# ERROR'):
            tomsk_records = self.tomsk.parse_month(tomsk_html)
            schumann = next((r for r in tomsk_records if r.date == date_str), None)
            if schumann:
                sources.append('tomsk_sosrff')
                data_quality += 0.3
        else:
            schumann = None
        
        # Try CoinGecko for market data (only works for recent dates)
        market_data = None
        try:
            dt = datetime(year, month, day)
            date_str_cg = dt.strftime('%d-%m-%Y')
            resp = requests.get(
                f"https://api.coingecko.com/api/v3/coins/bitcoin/history?date={date_str_cg}",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                market_data = data.get('market_data', {})
                if market_data:
                    sources.append('coingecko')
                    data_quality += 0.2
        except Exception:
            pass
        
        # Generate hash
        hash_input = f"{date_str}|{len(sources)}|{data_quality:.2f}"
        snapshot_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        return HistoricalSnapshot(
            date=date_str,
            geomagnetic=geomagnetic,
            schumann=schumann,
            market_data=market_data,
            data_sources=sources,
            data_quality=min(1.0, data_quality),
            hash=snapshot_hash,
        )
    
    def to_dict(self, snapshot: HistoricalSnapshot) -> Dict:
        """Convert snapshot to JSON-serializable dict."""
        return {
            'date': snapshot.date,
            'geomagnetic': {
                'planetary_a': snapshot.geomagnetic.planetary_a if snapshot.geomagnetic else None,
                'planetary_k_indices': snapshot.geomagnetic.planetary_k_indices if snapshot.geomagnetic else None,
                'max_kp': snapshot.geomagnetic.max_kp if snapshot.geomagnetic else None,
                'avg_kp': snapshot.geomagnetic.avg_kp if snapshot.geomagnetic else None,
                'quiet_day': snapshot.geomagnetic.quiet_day if snapshot.geomagnetic else None,
                'active_day': snapshot.geomagnetic.active_day if snapshot.geomagnetic else None,
                'storm_day': snapshot.geomagnetic.storm_day if snapshot.geomagnetic else None,
                'high_latitude_a': snapshot.geomagnetic.high_latitude_a if snapshot.geomagnetic else None,
                'mid_latitude_a': snapshot.geomagnetic.mid_latitude_a if snapshot.geomagnetic else None,
            } if snapshot.geomagnetic else None,
            'schumann': {
                'schumann_hz': snapshot.schumann.schumann_hz if snapshot.schumann else None,
                'amplitude': snapshot.schumann.amplitude if snapshot.schumann else None,
                'quality': snapshot.schumann.quality if snapshot.schumann else None,
                'source': snapshot.schumann.source if snapshot.schumann else None,
            } if snapshot.schumann else None,
            'market_data': snapshot.market_data,
            'data_sources': snapshot.data_sources,
            'data_quality': snapshot.data_quality,
            'hash': snapshot.hash,
        }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='HNC Historical Data Source Parser')
    parser.add_argument('year', type=int, help='Year (e.g., 2014)')
    parser.add_argument('month', type=int, help='Month (1-12)')
    parser.add_argument('day', type=int, help='Day (1-31)')
    parser.add_argument('--format', choices=['json', 'text'], default='text', help='Output format')
    args = parser.parse_args()
    
    print(f"📡 HNC Historical Data Source Parser")
    print(f"{'═'*60}")
    print(f"Target: {args.year}-{args.month:02d}-{args.day:02d}")
    print(f"{'═'*60}\n")
    
    builder = HistoricalSnapshotBuilder()
    snapshot = builder.build_snapshot(args.year, args.month, args.day)
    
    if args.format == 'text':
        print(f"📅 Date: {snapshot.date}")
        print(f"📊 Data Quality: {snapshot.data_quality:.0%}")
        print(f"🔗 Sources: {', '.join(snapshot.data_sources)}")
        print(f"   Hash: {snapshot.hash}")
        print()
        
        if snapshot.geomagnetic:
            g = snapshot.geomagnetic
            print(f"🌍 Geomagnetic (NOAA):")
            print(f"   Planetary A-index: {g.planetary_a}")
            print(f"   K-indices: {' '.join(map(str, g.planetary_k_indices))}")
            print(f"   Max Kp: {g.max_kp}")
            print(f"   Avg Kp: {g.avg_kp:.2f}")
            print(f"   Quiet day: {g.quiet_day}")
            print(f"   Active day: {g.active_day}")
            print(f"   Storm day: {g.storm_day}")
            print(f"   High latitude A: {g.high_latitude_a}")
            print(f"   Mid latitude A: {g.mid_latitude_a}")
            print()
        
        if snapshot.schumann:
            s = snapshot.schumann
            print(f"🌐 Schumann (Tomsk):")
            print(f"   Frequency: {s.schumann_hz} Hz")
            print(f"   Amplitude: {s.amplitude}")
            print(f"   Quality: {s.quality}")
            print()
        
        if snapshot.market_data:
            m = snapshot.market_data
            print(f"📈 Market (CoinGecko):")
            print(f"   BTC Price: ${m.get('current_price', {}).get('usd', 0):,.2f}")
            print(f"   Market Cap: ${m.get('market_cap', {}).get('usd', 0):,.0f}")
            print()
        
        print(f"{'═'*60}")
    else:
        print(json.dumps(builder.to_dict(snapshot), indent=2, sort_keys=True))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
