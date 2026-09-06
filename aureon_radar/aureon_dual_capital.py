"""
Aureon Dual Capital Connector

Manages BOTH demo and live Capital.com sessions simultaneously.

Architecture:
  - SHADOWS: Trades on DEMO account (risk-free validation)
  - HONEY POT: Trades on LIVE account (real money, proven shadows only)

A shadow must hit its profit target in DEMO before graduating to LIVE.

Gary Leckey | 2026 | Validate in demo, earn in live
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

# Import the CapitalClient
from capital_client import CapitalClient

logger = logging.getLogger(__name__)


class DualCapitalConnector:
    """
    Dual-mode Capital.com connector.
    
    Demo session: For shadow trades (validation)
    Live session: For honey pot trades (real money)
    """
    
    def __init__(self):
        # Demo connector
        os.environ['CAPITAL_DEMO'] = '1'
        self.demo = CapitalClient()
        
        # Live connector  
        os.environ['CAPITAL_DEMO'] = '0'
        self.live = CapitalClient()
        
        # Expose authenticated property for backward compat
        self.authenticated = False
        
        logger.info("[DUAL CAPITAL] Demo + Live connectors initialized")
    
    def authenticate(self) -> bool:
        """Authenticate both demo and live sessions."""
        demo_ok = self.demo.authenticate() if hasattr(self.demo, 'authenticate') else False
        live_ok = self.live.authenticate() if hasattr(self.live, 'authenticate') else False
        self.authenticated = live_ok
        return live_ok
    
    def is_demo_ready(self) -> bool:
        return self.demo.enabled and self.demo.x_security_token is not None
    
    def is_live_ready(self) -> bool:
        return self.live.enabled and self.live.x_security_token is not None
    
    def get_demo_balance(self) -> float:
        try:
            accounts = self.demo.get_accounts()
            if accounts:
                acc = accounts[0]
                return float(acc.get('available', acc.get('balance', 0)))
        except Exception:
            pass
        return 0.0

    def get_live_balance(self) -> float:
        try:
            accounts = self.live.get_accounts()
            if accounts:
                acc = accounts[0]
                return float(acc.get('available', acc.get('balance', 0)))
        except Exception:
            pass
        return 0.0
    
    def place_demo_order(self, symbol: str, direction: str, size: float,
                         stop_level=None, profit_level=None) -> dict:
        """Place a shadow trade on DEMO account."""
        return self._place_order(self.demo, symbol, direction, size, stop_level, profit_level)
    
    def place_live_order(self, symbol: str, direction: str, size: float,
                         stop_level=None, profit_level=None) -> dict:
        """Place a honey pot trade on LIVE account.

        FAIL-CLOSED hardening (owner decree 2026-09-04):
          1. Capability gate `trading_execution:execute_live_trades` must
             ALLOW — checked BEFORE any network call. Gate module error,
             missing gate, or HOLD verdict → order refused.
          2. A broker-side stop level is MANDATORY — None → refused.
        """
        if not self._live_trade_gate_allowed(f"{symbol} {direction} size={size}"):
            return {"error": "refused_by_capability_gate"}

        if stop_level is None:
            logger.error(
                "[GATE] REFUSED live order (%s %s size=%s): mandatory broker-side "
                "stop loss missing [fail-closed]", symbol, direction, size)
            self._emit_gate_refused({
                "gate": "trading_execution:execute_live_trades",
                "verdict": "REFUSED",
                "allowed": False,
                "reason": "mandatory stop loss missing (stop_level=None)",
                "context": f"{symbol} {direction} size={size}",
            })
            return {"error": "refused_missing_stop_loss"}

        return self._place_order(self.live, symbol, direction, size, stop_level, profit_level)

    @staticmethod
    def _workspace_root() -> Path:
        return Path(__file__).resolve().parent.parent

    def _emit_gate_refused(self, payload: dict):
        """Best-effort trading.gate_refused event — never raises."""
        try:
            root = str(self._workspace_root())
            if root not in sys.path:
                sys.path.insert(0, root)
            from aureon_fusion import events
            events.publish_event("trading", "trading.gate_refused", payload, priority=7)
        except Exception:
            pass  # event spine unavailable — refusal already logged

    def _live_trade_gate_allowed(self, context: str) -> bool:
        """Fail-closed capability gate check for LIVE order placement.

        Returns True only if aureon_fusion.capability_gate.check() says
        allowed=True. ANY error (module missing, import failure, exception)
        → refuse. Runs BEFORE any broker network activity.
        """
        gate_key = "trading_execution:execute_live_trades"
        try:
            root = str(self._workspace_root())
            if root not in sys.path:
                sys.path.insert(0, root)
            from aureon_fusion import capability_gate
            verdict = capability_gate.check(gate_key)
        except Exception as e:
            logger.error(
                "[GATE] capability_gate unavailable/error (%s) — REFUSING live "
                "order (%s) [fail-closed]", e, context)
            self._emit_gate_refused({
                "gate": gate_key,
                "verdict": "ERROR",
                "allowed": False,
                "reason": f"capability_gate check raised: {e}",
                "context": context,
            })
            return False

        if not verdict.get("allowed"):
            logger.warning(
                "[GATE] REFUSED live order (%s): verdict=%s level=%s reason=%s",
                context, verdict.get("verdict"), verdict.get("level"),
                verdict.get("reason"))
            self._emit_gate_refused({
                "gate": gate_key,
                "verdict": verdict.get("verdict"),
                "allowed": False,
                "level": verdict.get("level"),
                "reason": verdict.get("reason"),
                "context": context,
            })
            return False

        return True
    
    def _place_order(self, client: CapitalClient, symbol: str, direction: str, 
                     size: float, stop_level=None, profit_level=None) -> dict:
        """Internal order placement with retry logic.
        
        Capital.com CFD sizing:
        - Forex: min size 1.0
        - Stocks: min size 1.0  
        - Commodities: min size 1.0
        - Indices: min size 1.0
        """
        try:
            # Get epic from symbol
            epic = self._symbol_to_epic(client, symbol)
            if not epic:
                return {"error": f"No epic for {symbol}"}
            
            # Determine category for sizing
            category = self._get_symbol_category(symbol)
            
            # Minimum sizes for Capital.com CFDs
            # Forex: 1000 (1K units = 0.01 lot)
            # Stocks: 1 share
            # Commodities: 1 unit
            # Indices: 1 unit
            min_sizes = {
                "forex": 1000.0,
                "stock": 1.0,
                "commodity": 1.0,
                "index": 1.0,
                "crypto": 0.1,
            }
            min_size = min_sizes.get(category, 1.0)
            
            # Ensure size meets minimum
            actual_size = max(float(size), min_size)
            
            # Build order payload
            payload = {
                "epic": epic,
                "direction": direction.upper(),  # BUY or SELL
                "size": actual_size,
                "orderType": "MARKET",
            }
            
            # Capital.com requires minimum distance for TP/SL
            # For most CFDs this is ~0.5% or a few pips
            if stop_level:
                payload["stopLevel"] = float(stop_level)
            if profit_level:
                payload["profitLevel"] = float(profit_level)
            
            # Place order — routed through the hardened request layer
            # (automatic re-auth on 401/session expiry; bug-hunt MEDIUM)
            resp = client._request('POST', '/positions', json_body=payload)
            
            if resp.status_code == 200:
                data = resp.json()
                deal_id = data.get('dealReference', data.get('dealId', 'unknown'))
                return {
                    "dealId": deal_id,
                    "epic": epic,
                    "direction": direction,
                    "size": actual_size,
                    "account": "demo" if client.demo_mode else "live"
                }
            else:
                return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def _get_symbol_category(self, symbol: str) -> str:
        """Determine symbol category for sizing."""
        forex = ["USDJPY", "EURUSD", "GBPUSD"]
        stocks = ["AAPL", "TSLA", "NVDA"]
        commodities = ["GOLD", "SILVER", "OIL_CRUDE", "NATURALGAS"]
        indices = ["US100"]
        crypto = ["BTCUSD", "ETHUSD"]
        
        if symbol in forex:
            return "forex"
        elif symbol in stocks:
            return "stock"
        elif symbol in commodities:
            return "commodity"
        elif symbol in indices:
            return "index"
        elif symbol in crypto:
            return "crypto"
        return "forex"
    
    def _symbol_to_epic(self, client: CapitalClient, symbol: str) -> Optional[str]:
        """Convert symbol to Capital.com epic using client's market search."""
        # Try the client's built-in market search API
        try:
            resp = client._request('GET', '/markets', params={'searchTerm': symbol, 'pageSize': 10})
            if resp.status_code == 200:
                data = resp.json()
                markets = data.get('markets', [])
                for m in markets:
                    epic = m.get('epic', '')
                    name = m.get('instrumentName', '')
                    # Match exact symbol name first
                    if symbol.upper() == epic.upper() or symbol.upper() in name.upper().split():
                        return epic
        except:
            pass
        
        # Fallback: simple epic (Capital.com uses same as symbol name)
        return symbol
    
    def get_demo_positions(self) -> list:
        """Get positions from DEMO account."""
        return self._get_positions(self.demo)
    
    def get_live_positions(self) -> list:
        """Get positions from LIVE account."""
        return self._get_positions(self.live)
    
    def _get_positions(self, client: CapitalClient) -> list:
        """Internal position fetch (hardened request layer: re-auth on 401)."""
        try:
            resp = client._request('GET', '/positions')
            if resp.status_code == 200:
                return resp.json().get('positions', [])
        except Exception as e:
            logger.debug(f"Position fetch error: {e}")
        return []
    
    def close_demo_position(self, deal_id: str) -> dict:
        return self._close_position(self.demo, deal_id)
    
    def close_live_position(self, deal_id: str) -> dict:
        return self._close_position(self.live, deal_id)
    
    def _close_position(self, client: CapitalClient, deal_id: str) -> dict:
        """Close a position by dealId (hardened request layer: re-auth on 401)."""
        try:
            resp = client._request('DELETE', f'/positions/{deal_id}')
            if resp.status_code == 200:
                return {"success": True}
            else:
                return {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def validate_demo_shadow(self, symbol: str) -> bool:
        """Check if a shadow position exists and is profitable in DEMO."""
        positions = self.get_demo_positions()
        for pos in positions:
            market = pos.get('market', {})
            epic = market.get('epic', '')
            if symbol.upper() in epic.upper():
                position = pos.get('position', {})
                upl = position.get('upl', 0)
                if upl > 0:
                    return True
        return False
    
    def get_minimum_tp_distance(self, symbol: str, entry_price: float) -> float:
        """Calculate minimum take-profit distance for Capital.com.

        Capital.com enforces percentage-based minimum distances per instrument.
        Derived from actual API rejection data (2026-09-04):
          NVDA $228.45 → min $2.06  (0.9%)
          US100 29482  → min 118    (0.4%)
          GOLD $4525   → min $50    (1.1%)
        """
        # Minimum distance as percentage of entry price
        min_pct = {
            "USDJPY": 0.001,    # 0.1%
            "EURUSD": 0.0003,   # 0.03%
            "GBPUSD": 0.0003,   # 0.03%
            "AAPL": 0.006,      # 0.6%
            "TSLA": 0.006,      # 0.6%
            "NVDA": 0.009,      # 0.9%
            "US100": 0.004,     # 0.4%
            "GOLD": 0.012,      # 1.2% (was 1.1% — still hitting limit)
            "SILVER": 0.012,    # 1.2% (was 0.6% — hitting limit at 67.435)
            "OIL_CRUDE": 0.005, # 0.5%
            "NATURALGAS": 0.010,# 1.0%
            "BTCUSD": 0.005,    # 0.5%
            "ETHUSD": 0.005,    # 0.5%
        }
        pct = min_pct.get(symbol, 0.005)  # default 0.5%
        distance = entry_price * pct

        # Absolute minimum floor (never go below this)
        # Increased 2026-09-04 with 5% safety margin over observed API limits
        abs_floor = {
            "USDJPY": 0.03,
            "EURUSD": 0.0003,
            "GBPUSD": 0.0003,
            "AAPL": 1.50,
            "TSLA": 2.00,
            "NVDA": 4.00,       # $4.00 min (was $2.50, API needs ~$3.65)
            "US100": 125.0,     # was 120 — 5% margin over observed 118.28
            "GOLD": 52.0,       # was 50 — margin over observed 50.07
            "SILVER": 0.50,
            "OIL_CRUDE": 0.50,
            "NATURALGAS": 0.05,
        }
        return max(distance, abs_floor.get(symbol, 1.0))

    def get_minimum_tick(self, symbol: str) -> float:
        """DEPRECATED — use get_minimum_tp_distance instead.
        Kept for backward compatibility.
        """
        return self.get_minimum_tp_distance(symbol, 100.0)  # fallback at $100 reference

    def calculate_micro_tp(self, symbol: str, direction: str, entry_price: float) -> float:
        """Calculate take-profit at Capital.com's minimum allowed distance.

        Uses percentage-based distance scaled to entry price.
        Ensures orders pass Capital.com validation.
        """
        distance = self.get_minimum_tp_distance(symbol, entry_price)

        if direction.upper() in ["LONG", "BUY"]:
            tp = entry_price + distance
        else:
            tp = entry_price - distance

        # Round to appropriate precision
        if distance >= 100:
            return round(tp, 0)
        elif distance >= 1:
            return round(tp, 1)
        elif distance >= 0.01:
            return round(tp, 2)
        else:
            return round(tp, 4)
    
    def get_status(self) -> dict:
        """Get full status of both accounts."""
        return {
            "demo": {
                "ready": self.is_demo_ready(),
                "balance": self.get_demo_balance(),
                "positions": len(self.get_demo_positions())
            },
            "live": {
                "ready": self.is_live_ready(),
                "balance": self.get_live_balance(),
                "positions": len(self.get_live_positions())
            }
        }
