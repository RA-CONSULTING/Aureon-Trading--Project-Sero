/**
 * ═══════════════════════════════════════════════════════════════════════════════
 * 🔍 CHECK ACCOUNT PERMISSIONS - What can we trade?
 * ═══════════════════════════════════════════════════════════════════════════════
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const keysPath = path.join(__dirname, 'binanceKeys.json');
const { keys } = JSON.parse(fs.readFileSync(keysPath, 'utf-8'));

async function checkPermissions() {
  console.log(`\n🔍 CHECKING ACCOUNT PERMISSIONS...\n`);
  
  const BinanceLib = await import('binance-api-node');
  const client = (BinanceLib as any).default({
    apiKey: keys[0].apiKey,
    apiSecret: keys[0].apiSecret,
  });

  // Get account info
  const account = await client.accountInfo();
  
  console.log(`📊 ACCOUNT STATUS:`);
  console.log(`   Can Trade: ${account.canTrade}`);
  console.log(`   Can Withdraw: ${account.canWithdraw}`);
  console.log(`   Can Deposit: ${account.canDeposit}`);
  console.log(`   Account Type: ${account.accountType}`);
  
  // Get balances with value
  console.log(`\n💰 YOUR ASSETS:`);
  const assets = account.balances.filter((b: any) => parseFloat(b.free) > 0 || parseFloat(b.locked) > 0);
  for (const a of assets) {
    console.log(`   ${a.asset}: ${a.free} free, ${a.locked} locked`);
  }

  // Check API key permissions
  console.log(`\n🔑 API KEY PERMISSIONS:`);
  try {
    const apiPerms = await client.apiPermissions();
    console.log(`   IP Restrict: ${apiPerms.ipRestrict}`);
    console.log(`   Enable Spot: ${apiPerms.enableSpotAndMarginTrading}`);
    console.log(`   Enable Withdrawals: ${apiPerms.enableWithdrawals}`);
    console.log(`   Enable Internal Transfer: ${apiPerms.enableInternalTransfer}`);
    console.log(`   Enable Margin: ${apiPerms.enableMargin}`);
    console.log(`   Enable Futures: ${apiPerms.enableFutures}`);
  } catch (e: any) {
    console.log(`   Could not get API permissions: ${e.message}`);
  }

  // Try a test order to see what works
  console.log(`\n🧪 TESTING TRADEABLE PAIRS...`);
  
  const testPairs = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'DOGEUSDT', 'ADAUSDT', 'DOTUSDT', 'XRPUSDT', 'SOLUSDT'];
  
  for (const symbol of testPairs) {
    try {
      // Try to get order book - if this works, we can trade it
      await client.book({ symbol, limit: 1 });
      
      // Check if we have balance
      const base = symbol.replace('USDT', '');
      const bal = assets.find((a: any) => a.asset === base);
      const hasBal = bal && parseFloat(bal.free) > 0;
      
      console.log(`   ✅ ${symbol} - Accessible ${hasBal ? `(Have ${bal.free} ${base})` : '(No balance)'}`);
    } catch (e: any) {
      console.log(`   ❌ ${symbol} - ${e.message.substring(0, 50)}`);
    }
  }

  // Check if it's a sub-account
  console.log(`\n📋 CHECKING ACCOUNT TYPE...`);
  try {
    // This will fail if not a sub-account
    const subAccounts = await client.subAccountList();
    console.log(`   This is a MASTER account with ${subAccounts.subAccounts?.length || 0} sub-accounts`);
  } catch (e: any) {
    if (e.message.includes('not authorized')) {
      console.log(`   This appears to be a SUB-ACCOUNT (or no sub-account access)`);
    } else {
      console.log(`   ${e.message}`);
    }
  }

  console.log(`\n${'═'.repeat(60)}`);
  console.log(`\n💡 RECOMMENDATION:`);
  console.log(`   If trading is blocked, you may need to:`);
  console.log(`   1. Enable Spot Trading in Binance API settings`);
  console.log(`   2. Complete identity verification (KYC)`);
  console.log(`   3. Check if your region has trading restrictions`);
  console.log(`   4. Check if this is a sub-account with limited permissions`);
}

checkPermissions().catch(console.error);
