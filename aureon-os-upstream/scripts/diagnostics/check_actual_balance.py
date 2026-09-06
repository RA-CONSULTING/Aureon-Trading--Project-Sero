#!/usr/bin/env python3
"""Check actual tradable balance on Binance"""
from aureon_baton_link import link_system as _baton_link; _baton_link(__name__)
from binance_client import BinanceClient
from dotenv import load_dotenv
load_dotenv()

print("=" * 50)
print("BINANCE BALANCE CHECK")
print("=" * 50)

client = BinanceClient(dry_run=False)

# Get all balances
balances = client.get_balance()
print(f"\n📊 All Balances:")
for asset, amount in balances.items():
    if amount > 0:
        print(f"  {asset}: {amount}")

# Check specifically for tradable assets
print(f"\n💰 Tradable Assets (non-staked):")
tradable = ['USDT', 'USDC', 'BUSD', 'GBP', 'EUR', 'BTC', 'ETH']
for asset in tradable:
    bal = client.get_balance(asset)
    if bal > 0:
        print(f"  ✅ {asset}: {bal}")

# Check LDUSDC
ldusdc = client.get_balance('LDUSDC')
print(f"\n🔒 Staked Assets (NOT tradable):")
if ldusdc > 0:
    print(f"  LDUSDC (Lido Staked): {ldusdc}")
    print(f"  ⚠️  This is earning yield but CANNOT be traded directly")
    print(f"  ⚠️  Must redeem to USDC first via Binance Earn")

print("\n" + "=" * 50)
