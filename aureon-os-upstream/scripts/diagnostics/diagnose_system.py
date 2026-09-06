#!/usr/bin/env python3
"""
Quick system diagnostic - why isn't trading working?
"""
from aureon_baton_link import link_system as _baton_link; _baton_link(__name__)
import os
import sys

print("=" * 60)
print("🔍 AUREON SYSTEM DIAGNOSTIC")
print("=" * 60)

# 1. Check Python version
print(f"\n1️⃣ Python Version: {sys.version}")

# 2. Check .env exists
env_exists = os.path.exists('.env')
print(f"2️⃣ .env file: {'✅ Found' if env_exists else '❌ Missing'}")

# 3. Check if we can load dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("3️⃣ dotenv: ✅ Loaded")
except ImportError:
    print("3️⃣ dotenv: ❌ NOT INSTALLED - Run: pip install python-dotenv")
    sys.exit(1)

# 4. Check critical environment variables
print("\n4️⃣ Environment Variables:")
critical_vars = [
    'BINANCE_API_KEY', 'BINANCE_SECRET_KEY',
    'KRAKEN_API_KEY', 'KRAKEN_PRIVATE_KEY',
    'LIVE', 'BASE_CURRENCY'
]
for var in critical_vars:
    val = os.getenv(var)
    if val:
        # Mask secrets
        if 'KEY' in var or 'SECRET' in var:
            masked = val[:8] + '...' + val[-4:] if len(val) > 12 else '***'
            print(f"   ✅ {var}: {masked}")
        else:
            print(f"   ✅ {var}: {val}")
    else:
        print(f"   ❌ {var}: NOT SET")

# 5. Check Binance connection
print("\n5️⃣ Binance Connection:")
try:
    from binance_client import BinanceClient
    client = get_binance_client()
    print("   ✅ BinanceClient imported")
    
    # Try to get account info
    try:
        account = client.client.get_account()
        print("   ✅ API connection working")
        
        # Check for liquid funds
        liquid_funds = 0
        for asset in ['USDT', 'USDC', 'BUSD', 'FDUSD']:
            try:
                bal = client.get_balance(asset)
                if bal > 0:
                    print(f"   💰 {asset}: ${bal:.2f}")
                    liquid_funds += bal
            except:
                pass
        
        if liquid_funds == 0:
            print("   ⚠️  NO LIQUID STABLECOINS FOUND")
            # Check for staked
            try:
                ldusdc = client.get_balance('LDUSDC')
                if ldusdc > 0:
                    print(f"   🔒 LDUSDC (STAKED): ${ldusdc:.2f}")
                    print("   ❌ PROBLEM: Your funds are STAKED, not tradable!")
                    print("   📝 ACTION: Go to Binance Earn → Redeem LDUSDC to USDC")
            except:
                pass
        else:
            print(f"   ✅ Total Liquid: ${liquid_funds:.2f}")
            
    except Exception as e:
        print(f"   ❌ API Error: {e}")
        
except Exception as e:
    print(f"   ❌ Import Error: {e}")

# 6. Check if system can import main module
print("\n6️⃣ Main System Import:")
try:
    sys.path.insert(0, '/workspaces/aureon-trading')
    # Don't actually run it, just check if it can be imported
    with open('aureon_unified_ecosystem.py', 'r') as f:
        content = f.read()
        if 'class AureonKrakenEcosystem' in content:
            print("   ✅ aureon_unified_ecosystem.py found")
        else:
            print("   ❌ Main class not found in file")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 7. Check state file
print("\n7️⃣ State File:")
try:
    import json
    with open('aureon_kraken_state.json', 'r') as f:
        state = json.load(f)
        print(f"   Balance: ${state.get('balance', 0):.2f}")
        print(f"   Total Trades: {state.get('total_trades', 0)}")
        print(f"   Iterations: {state.get('iteration', 0)}")
        print(f"   Positions: {len(state.get('positions', {}))}")
except Exception as e:
    print(f"   ⚠️  State file issue: {e}")

print("\n" + "=" * 60)
print("🎯 DIAGNOSIS COMPLETE")
print("=" * 60)
