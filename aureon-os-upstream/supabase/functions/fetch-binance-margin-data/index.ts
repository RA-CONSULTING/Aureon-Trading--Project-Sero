import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { symbol = 'BTC' } = await req.json();
    
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Get Binance credentials
    const { data: credentials } = await supabase
      .from('profiles')
      .select('binance_api_key, binance_api_secret')
      .single();

    const BINANCE_API = 'https://api.binance.com';
    const timestamp = Date.now();

    // Fetch multiple margin metrics in parallel
    const [
      crossMarginData,
      isolatedMarginData,
      marginRatioData,
      interestData,
      forceLiquidationData
    ] = await Promise.all([
      // Cross Margin Account Details
      fetch(`${BINANCE_API}/sapi/v1/margin/account?timestamp=${timestamp}`)
        .then(r => r.json())
        .catch(() => null),
      
      // Isolated Margin Account Info for symbol
      fetch(`${BINANCE_API}/sapi/v1/margin/isolated/account?symbols=${symbol}USDT&timestamp=${timestamp}`)
        .then(r => r.json())
        .catch(() => null),
      
      // Cross Margin Collateral Ratio
      fetch(`${BINANCE_API}/sapi/v1/margin/crossMarginCollateralRatio`)
        .then(r => r.json())
        .catch(() => []),
      
      // Current Margin Interest Rate
      fetch(`${BINANCE_API}/sapi/v1/margin/interestRateHistory?asset=${symbol}&timestamp=${timestamp}`)
        .then(r => r.json())
        .catch(() => []),
      
      // Force Liquidation Records (last 24h)
      fetch(`${BINANCE_API}/sapi/v1/margin/forceLiquidationRec?timestamp=${timestamp}`)
        .then(r => r.json())
        .catch(() => { return { rows: [] }; })
    ]);

    // Calculate margin sentiment metrics
    const marginSentiment = {
      crossMargin: {
        marginLevel: crossMarginData?.marginLevel || 0,
        totalAssetOfBtc: crossMarginData?.totalAssetOfBtc || 0,
        totalLiabilityOfBtc: crossMarginData?.totalLiabilityOfBtc || 0,
        totalNetAssetOfBtc: crossMarginData?.totalNetAssetOfBtc || 0,
        riskLevel: calculateRiskLevel(crossMarginData?.marginLevel || 0),
      },
      isolatedMargin: isolatedMarginData?.assets?.[0] || null,
      collateralRatio: marginRatioData,
      interestRate: interestData[0] || null,
      recentLiquidations: {
        count: forceLiquidationData?.rows?.length || 0,
        totalVolume: forceLiquidationData?.rows?.reduce((sum: number, liq: any) => 
          sum + parseFloat(liq.price) * parseFloat(liq.origQty), 0) || 0,
        avgPrice: forceLiquidationData?.rows?.length > 0
          ? forceLiquidationData.rows.reduce((sum: number, liq: any) => 
              sum + parseFloat(liq.price), 0) / forceLiquidationData.rows.length
          : 0,
      },
      sentiment: {
        leverageRisk: calculateLeverageRisk(crossMarginData?.marginLevel || 999),
        liquidationPressure: calculateLiquidationPressure(forceLiquidationData?.rows || []),
        borrowingCost: parseFloat(interestData[0]?.dailyInterestRate || '0'),
        marketHealth: calculateMarketHealth(
          crossMarginData?.marginLevel || 999,
          forceLiquidationData?.rows?.length || 0
        ),
      }
    };

    console.log('[fetch-binance-margin-data] Fetched margin data:', {
      symbol,
      marginLevel: marginSentiment.crossMargin.marginLevel,
      liquidations: marginSentiment.recentLiquidations.count,
      sentiment: marginSentiment.sentiment.marketHealth
    });

    return new Response(
      JSON.stringify(marginSentiment),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('[fetch-binance-margin-data] Error:', errorMessage);
    return new Response(
      JSON.stringify({ error: errorMessage }),
      { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );
  }
});

function calculateRiskLevel(marginLevel: number): string {
  if (marginLevel > 3) return 'SAFE';
  if (marginLevel > 2) return 'MODERATE';
  if (marginLevel > 1.5) return 'WARNING';
  return 'DANGER';
}

function calculateLeverageRisk(marginLevel: number): number {
  // Lower margin level = higher leverage risk
  // Returns 0-1 where 1 is maximum risk
  if (marginLevel > 10) return 0;
  if (marginLevel > 5) return 0.2;
  if (marginLevel > 3) return 0.4;
  if (marginLevel > 2) return 0.6;
  if (marginLevel > 1.5) return 0.8;
  return 1.0;
}

function calculateLiquidationPressure(liquidations: any[]): number {
  // More liquidations = more pressure
  // Returns 0-1 where 1 is maximum pressure
  const count = liquidations.length;
  if (count === 0) return 0;
  if (count < 5) return 0.2;
  if (count < 10) return 0.4;
  if (count < 20) return 0.6;
  if (count < 50) return 0.8;
  return 1.0;
}

function calculateMarketHealth(marginLevel: number, liquidationCount: number): number {
  // Combines margin level and liquidations into health score
  // Returns 0-1 where 1 is healthiest
  const marginScore = Math.min(marginLevel / 5, 1); // Normalize to 0-1
  const liquidationScore = 1 - Math.min(liquidationCount / 50, 1); // Inverse, fewer is better
  
  return (marginScore * 0.6 + liquidationScore * 0.4); // Weight margin more
}