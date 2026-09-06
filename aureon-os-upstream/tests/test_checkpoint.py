#!/usr/bin/env python3
"""Simple test to verify checkpoint logic."""

from aureon_baton_link import link_system as _baton_link; _baton_link(__name__)
import asyncio
import sys
sys.path.insert(0, '/workspaces/aureon-trading')

async def main():
    print("🔬 Testing Checkpoint Logic...")
    
    from micro_profit_labyrinth import MicroProfitLabyrinth
    
    # Create engine in simulation mode
    engine = MicroProfitLabyrinth(live_mode=False)
    await engine.initialize()
    
    # Debug: Show balances
    print(f"\n📦 Balances: {engine.balances}")
    print(f"💰 Prices (CHZ): ${engine.prices.get('CHZ', 0):.4f}")
    print(f"💰 Prices (TUSD): ${engine.prices.get('TUSD', 0):.4f}")
    
    # Check exchange for CHZ
    chz_exchange = engine._find_asset_exchange('CHZ')
    print(f"\n🔍 CHZ Exchange: {chz_exchange}")
    
    # Check pair lookup
    chz_usd_pair = engine._find_exchange_pair('CHZ', 'USD', chz_exchange or 'kraken')
    print(f"🔍 CHZ/USD Pair: {chz_usd_pair}")
    
    # Show Kraken CHZ pairs
    if engine.kraken_pairs:
        chz_pairs = [p for p in engine.kraken_pairs.keys() if 'CHZ' in p.upper()]
        print(f"\n🐙 Kraken CHZ pairs: {chz_pairs[:10]}")
    
    # Run one scan
    print("\n🔬 Running find_opportunities()...")
    opps = await engine.find_opportunities()
    
    print(f"\n✅ Found {len(opps)} opportunities")
    for opp in opps[:5]:
        print(f"   {opp.from_asset} → {opp.to_asset}: ${opp.expected_pnl_usd:.4f} (checkpoint={opp.is_checkpoint})")

if __name__ == '__main__':
    asyncio.run(main())
