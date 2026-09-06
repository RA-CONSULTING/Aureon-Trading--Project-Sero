#!/usr/bin/env python3
"""
🌍⚡ SMOKE TEST: Unified Trading System ⚡🌍
Validates all major components in dry run mode.
"""
from aureon_baton_link import link_system as _baton_link; _baton_link(__name__)
from aureon_unified_ecosystem import AureonKrakenEcosystem

def main():
    eco = AureonKrakenEcosystem(initial_balance=200.0, dry_run=True)
    print('\n🌍⚡ SMOKE TEST: Unified Trading System ⚡🌍\n')
    eco.refresh_tickers()
    opps = eco.find_opportunities()
    print(f'\n📊 Top Opportunities:')
    print('─'*80)
    print(f'  SYMBOL       │ SCORE │ COH  │ FREQ │ PROB │ CONF │ ACTION')
    print('─'*80)
    for opp in opps[:8]:
        print(f'  {opp["symbol"]:12s} │ {opp["score"]:5d} │ {opp["coherence"]:.2f} │ {opp.get("hnc_frequency",256):5.0f} │ {opp.get("probability",0.5):.0%} │ {opp.get("prob_confidence",0.0):.0%} │ {opp.get("prob_action","HOLD")[:10]:10s}')
    print('─'*80)
    print('\n✅ Smoke test complete!')

if __name__ == "__main__":
    main()
