#!/usr/bin/env python3
"""Test ticker loading"""
from aureon_baton_link import link_system as _baton_link; _baton_link(__name__)
import sys
sys.path.insert(0, '/workspaces/aureon-trading')

print("Testing ticker retrieval...")

try:
    from unified_exchange_client import MultiExchangeClient
    print("✅ Importing MultiExchangeClient...")
    
    client = MultiExchangeClient(dry_run=False)
    print("✅ Created MultiExchangeClient...")
    
    print("\n📊 Fetching tickers...")
    tickers = client.get_24h_tickers()
    print(f"✅ Got {len(tickers)} tickers")
    
    if tickers:
        print(f"\n First 5 tickers:")
        for t in tickers[:5]:
            sym = t.get('symbol', 'N/A')
            price = t.get('lastPrice', 0)
            change = t.get('priceChangePercent', 0)
            print(f"  {sym}: ${price} ({change:+.2f}%)")
    else:
        print("❌ No tickers returned!")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
